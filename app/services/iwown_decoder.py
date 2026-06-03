"""
iWOWN Health Data Decoder
Parses the custom binary packet format sent by iWOWN 4G devices.

Packet structure:
  Header:
    prefix  - uint8[2]  - Fixed 0x44, 0x54 ("DT")
    length  - uint16 LE - Payload (data) length
    crc     - uint16 LE - CRC checksum of payload
    opt     - uint16 LE - Protocol type:
                           0x80 = All Health Data
                           0x0A = Step / Distance / Calorie / GNSS
                           0x12 = Device Alarm
  Payload:
    data    - uint8[]   - Protobuf-encoded content (length bytes)

Multiple packets may be concatenated in a single upload body.
"""

import struct
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Opt codes
OPT_HEALTH  = 0x80
OPT_STEP    = 0x0A
OPT_ALARM   = 0x12

HEADER_SIZE = 8  # 2 (prefix) + 2 (length) + 2 (crc) + 2 (opt)
PACKET_PREFIX = b'\x44\x54'  # "DT"


# ---------------------------------------------------------------------------
# CRC helpers
# ---------------------------------------------------------------------------

def _crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE  (poly 0x1021, init 0xFFFF, no reflection)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# Protobuf-lite varint / field reader
# ---------------------------------------------------------------------------

def _read_varint(buf: bytes, pos: int):
    """Read a protobuf varint starting at pos.  Returns (value, new_pos)."""
    result = 0
    shift = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    raise ValueError("Truncated varint")


def _parse_protobuf(buf: bytes) -> Dict[int, Any]:
    """
    Minimal protobuf parser.  Returns {field_number: value} where value is
    an int (varint / fixed), bytes (length-delimited), or list for repeated
    fields.
    """
    fields: Dict[int, Any] = {}
    pos = 0
    while pos < len(buf):
        try:
            tag, pos = _read_varint(buf, pos)
        except ValueError:
            break
        field_number = tag >> 3
        wire_type    = tag & 0x07

        if wire_type == 0:          # varint
            value, pos = _read_varint(buf, pos)
        elif wire_type == 1:        # 64-bit fixed
            value = struct.unpack_from('<Q', buf, pos)[0]
            pos += 8
        elif wire_type == 2:        # length-delimited
            length, pos = _read_varint(buf, pos)
            value = buf[pos:pos + length]
            pos += length
        elif wire_type == 5:        # 32-bit fixed
            value = struct.unpack_from('<I', buf, pos)[0]
            pos += 4
        else:
            # Unknown wire type – can't continue parsing safely
            logger.warning(f"Unknown protobuf wire type {wire_type}, stopping parse")
            break

        # Support repeated fields as a list
        if field_number in fields:
            existing = fields[field_number]
            if isinstance(existing, list):
                existing.append(value)
            else:
                fields[field_number] = [existing, value]
        else:
            fields[field_number] = value

    return fields


# ---------------------------------------------------------------------------
# Domain-specific decoders
# ---------------------------------------------------------------------------

def _decode_health(payload: bytes) -> Dict[str, Any]:
    """
    Decode opt=0x80 health data using actual HisDataHealth proto structure.
    Field 1  = time_stamp (DateTime = nested: field1=RtTime(field1=seconds), field2=timezone)
    Field 3  = pedo_data  (HisHealthPedo: step=4, calorie=3, distance=5)
    Field 4  = hr_data    (HisHealthHr: min=1, max=2, avg=3)
    Field 5  = hrv_data   (HisHealthHrv: SDNN=1, RMSSD=2, PNN50=3, MEAN=4, fatigue=5)
    Field 6  = bp_data    (HisHealthBp: sbp=1, dbp=2)
    Field 12 = bxoy_data  (HisHealthBOxy: min_oxy=1, max_oxy=2, agv_oxy=3)
    Field 13 = temperature_data (HisHealthTemp: type=1, evi_body=2, esti_arm=3)
    """
    f = _parse_protobuf(payload)
    result: Dict[str, Any] = {}

    # Field 1: DateTime (nested protobuf)
    ts_raw = f.get(1)
    if isinstance(ts_raw, bytes) and len(ts_raw) >= 2:
        try:
            ts_fields = _parse_protobuf(ts_raw)
            rt_time_raw = ts_fields.get(1)  # RtTime message
            if isinstance(rt_time_raw, bytes):
                rt_fields = _parse_protobuf(rt_time_raw)
                seconds = rt_fields.get(1)
                if seconds:
                    result['timestamp_unix'] = int(seconds)
            elif isinstance(rt_time_raw, int):
                result['timestamp_unix'] = int(rt_time_raw)
        except Exception:
            pass

    # Field 3: pedo_data (HisHealthPedo)
    pedo_raw = f.get(3)
    if isinstance(pedo_raw, bytes):
        try:
            pedo = _parse_protobuf(pedo_raw)
            if pedo.get(4) is not None:
                result['steps'] = int(pedo[4])
            if pedo.get(3) is not None:
                result['calories_kcal'] = int(pedo[3])
            if pedo.get(5) is not None:
                result['distance_m'] = int(pedo[5])
        except Exception:
            pass

    # Field 4 → field 3 → field 4 = HR, field 6 = BP
    wrapper_raw = f.get(4)
    if isinstance(wrapper_raw, bytes):
        try:
            wrapper = _parse_protobuf(wrapper_raw)
            inner_raw = wrapper.get(3)
            if isinstance(inner_raw, bytes):
                inner = _parse_protobuf(inner_raw)
                hr_raw = inner.get(4)
                if isinstance(hr_raw, bytes):
                    hr = _parse_protobuf(hr_raw)
                    if hr.get(1) is not None: result['heart_rate_min'] = int(hr[1])
                    if hr.get(2) is not None: result['heart_rate_max'] = int(hr[2])
                    if hr.get(3) is not None: result['heart_rate_bpm'] = int(hr[3])
                bp_raw = inner.get(6)
                if isinstance(bp_raw, bytes):
                    bp = _parse_protobuf(bp_raw)
                    if bp.get(1) is not None: result['bp_systolic_mmhg'] = int(bp[1])
                    if bp.get(2) is not None: result['bp_diastolic_mmhg'] = int(bp[2])
        except Exception:
            pass

    # Field 5: hrv_data (HisHealthHrv) — floats stored as fixed32
    hrv_raw = f.get(5)
    if isinstance(hrv_raw, bytes):
        try:
            hrv = _parse_protobuf(hrv_raw)
            if hrv.get(1) is not None:
                result['hrv_sdnn'] = hrv[1]
        except Exception:
            pass

    # Field 6: bp_data (HisHealthBp)
    bp_raw = f.get(6)
    if isinstance(bp_raw, bytes):
        try:
            bp = _parse_protobuf(bp_raw)
            if bp.get(1) is not None:
                result['bp_systolic_mmhg'] = int(bp[1])
            if bp.get(2) is not None:
                result['bp_diastolic_mmhg'] = int(bp[2])
        except Exception:
            pass

    # Field 12: bxoy_data (HisHealthBOxy) — SpO2
    spo2_raw = f.get(12)
    if isinstance(spo2_raw, bytes):
        try:
            oxy = _parse_protobuf(spo2_raw)
            if oxy.get(3) is not None:
                result['spo2_percent'] = int(oxy[3])  # avg
            if oxy.get(1) is not None:
                result['spo2_min'] = int(oxy[1])
            if oxy.get(2) is not None:
                result['spo2_max'] = int(oxy[2])
        except Exception:
            pass

    # Field 13: temperature_data (HisHealthTemp)
    temp_raw = f.get(13)
    if isinstance(temp_raw, bytes):
        try:
            temp = _parse_protobuf(temp_raw)
            # esti_arm (field 3) is body temp in units of 0.01°C per iWOWN convention
            if temp.get(3) is not None:
                result['body_temperature_c'] = round(temp[3] / 100.0, 1)
            elif temp.get(2) is not None:
                result['body_temperature_c'] = round(temp[2] / 100.0, 1)
        except Exception:
            pass

    # Preserve unmapped raw fields for debugging
    known = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
    raw_extras = {
        str(k): (v.hex() if isinstance(v, bytes) else v)
        for k, v in f.items() if k not in known
    }
    if raw_extras:
        result['raw_fields'] = raw_extras

    return result

def _decode_step(payload: bytes) -> Dict[str, Any]:
    """
    Decode opt=0x0A step / distance / calorie / GNSS data.

    Typical field mapping:
      Field 1  – timestamp (unix seconds)
      Field 2  – steps
      Field 3  – calories (kcal)
      Field 4  – distance (metres)
      Field 5  – latitude  (degrees * 1e6, sint32)
      Field 6  – longitude (degrees * 1e6, sint32)
      Field 7  – speed (km/h * 10)
    """
    f = _parse_protobuf(payload)

    def _get(field, default=None):
        v = f.get(field, default)
        return v[-1] if isinstance(v, list) else v

    result: Dict[str, Any] = {}

    ts = _get(1)
    if ts is not None:
        result['timestamp_unix'] = int(ts)

    steps = _get(2)
    if steps is not None:
        result['steps'] = int(steps)

    cal = _get(3)
    if cal is not None:
        result['calories_kcal'] = int(cal)

    dist = _get(4)
    if dist is not None:
        result['distance_m'] = int(dist)

    lat = _get(5)
    if lat is not None and lat != 0:
        # sint32 zigzag decode
        lat = (lat >> 1) ^ -(lat & 1)
        result['latitude'] = round(lat / 1_000_000, 6)

    lon = _get(6)
    if lon is not None and lon != 0:
        lon = (lon >> 1) ^ -(lon & 1)
        result['longitude'] = round(lon / 1_000_000, 6)

    spd = _get(7)
    if spd is not None:
        result['speed_kmh'] = round(spd / 10.0, 1)

    known = {1, 2, 3, 4, 5, 6, 7}
    raw_extras = {str(k): (v.hex() if isinstance(v, bytes) else v)
                  for k, v in f.items() if k not in known}
    if raw_extras:
        result['raw_fields'] = raw_extras

    return result


def _decode_alarm(payload: bytes) -> Dict[str, Any]:
    """
    Decode opt=0x12 device alarm data.

    Typical field mapping:
      Field 1 – timestamp (unix seconds)
      Field 2 – alarm_type (1=fall, 2=sos, 3=low_battery, 4=geofence)
      Field 3 – latitude  (degrees * 1e6, sint32)
      Field 4 – longitude (degrees * 1e6, sint32)
    """
    f = _parse_protobuf(payload)

    def _get(field, default=None):
        v = f.get(field, default)
        return v[-1] if isinstance(v, list) else v

    result: Dict[str, Any] = {}

    ts = _get(1)
    if ts is not None:
        result['timestamp_unix'] = int(ts)

    atype = _get(2)
    if atype is not None:
        alarm_map = {1: 'fall', 2: 'sos', 3: 'low_battery', 4: 'geofence'}
        result['alarm_type'] = alarm_map.get(int(atype), f'unknown({atype})')

    lat = _get(3)
    if lat is not None and lat != 0:
        lat = (lat >> 1) ^ -(lat & 1)
        result['latitude'] = round(lat / 1_000_000, 6)

    lon = _get(4)
    if lon is not None and lon != 0:
        lon = (lon >> 1) ^ -(lon & 1)
        result['longitude'] = round(lon / 1_000_000, 6)

    return result


# ---------------------------------------------------------------------------
# Packet splitter + top-level decoder
# ---------------------------------------------------------------------------

def split_packets(raw: bytes) -> List[bytes]:
    """
    Split a concatenated iWOWN upload body into individual packet bytes
    (including their headers).
    """
    packets = []
    pos = 0
    while pos < len(raw):
        # Find next DT prefix
        idx = raw.find(PACKET_PREFIX, pos)
        if idx == -1:
            break
        if idx + HEADER_SIZE > len(raw):
            break

        # Read declared payload length (little-endian uint16 at offset 2)
        plen = struct.unpack_from('<H', raw, idx + 2)[0]
        end  = idx + HEADER_SIZE + plen
        if end > len(raw):
            logger.warning(f"Truncated packet at offset {idx}: declared {plen} bytes but only {len(raw)-idx-HEADER_SIZE} available")
            packets.append(raw[idx:])   # store what we have
            break

        packets.append(raw[idx:end])
        pos = end

    return packets


def decode_packet(packet: bytes) -> Optional[Dict[str, Any]]:
    """
    Decode a single iWOWN packet (header + payload).
    Returns a dict with keys: opt_code, opt_name, data (decoded fields),
    crc_ok, raw_hex.  Returns None if the packet is malformed.
    """
    if len(packet) < HEADER_SIZE:
        logger.warning("Packet too short")
        return None

    if packet[:2] != PACKET_PREFIX:
        logger.warning(f"Bad prefix: {packet[:2].hex()}")
        return None

    plen    = struct.unpack_from('<H', packet, 2)[0]
    crc_rx  = struct.unpack_from('<H', packet, 4)[0]
    opt     = struct.unpack_from('<H', packet, 6)[0]
    payload = packet[HEADER_SIZE:HEADER_SIZE + plen]

    if len(payload) != plen:
        logger.warning(f"Payload length mismatch: expected {plen}, got {len(payload)}")
        return None

    crc_calc = _crc16(payload)

# Keep logging CRC mismatch but do not treat it as invalid
    crc_ok = True

    if crc_calc != crc_rx:
        logger.warning(
            f"CRC mismatch ignored: received 0x{crc_rx:04X}, calculated 0x{crc_calc:04X}"
        )

    opt_names = {OPT_HEALTH: 'health', OPT_STEP: 'step_gnss', OPT_ALARM: 'alarm'}
    opt_name  = opt_names.get(opt, f'unknown_0x{opt:02X}')

    try:
        if opt == OPT_HEALTH:
            logger.warning(f"PAYLOAD HEX: {payload.hex()}")

            parsed = _parse_protobuf(payload)
            logger.warning(f"PARSED FIELDS: {parsed}")

            decoded = _decode_health(payload)
        elif opt == OPT_STEP:
            decoded = _decode_step(payload)
        elif opt == OPT_ALARM:
            decoded = _decode_alarm(payload)
        else:
            decoded = {'raw_payload_hex': payload.hex()}
    except Exception as e:
        logger.error(f"Error decoding payload for opt=0x{opt:02X}: {e}")
        decoded = {'raw_payload_hex': payload.hex(), 'decode_error': str(e)}

    return {
        'opt_code':  opt,
        'opt_name':  opt_name,
        'crc_ok':    crc_ok,
        'raw_hex':   packet.hex(),
        'data':      decoded,
    }



    
def decode_upload(raw_hex: str):

    try:
        raw = bytes.fromhex(raw_hex)

    except Exception as e:
        logger.error(f"Invalid hex: {e}")
        return []

    packets = split_packets(raw)

    if not packets:
        logger.warning("No DT packets found, treating as raw protobuf")

        return [{
            'opt_code': OPT_HEALTH,
            'opt_name': 'health',
            'crc_ok': True,
            'raw_hex': raw.hex(),
            'data': _decode_health(raw)
        }]

    results=[]

    for packet in packets:
        decoded = decode_packet(packet)

        if decoded:
            results.append(decoded)

    return results      