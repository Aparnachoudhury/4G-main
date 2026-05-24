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
    Decode opt=0x80 health data protobuf.

    Typical field mapping (derived from iWOWN proto file patterns):
      Field 1  – timestamp (unix seconds, uint32)
      Field 2  – heart_rate (bpm, uint32)
      Field 3  – spo2 (%, uint32)
      Field 4  – hrv_ms (milliseconds, uint32)
      Field 5  – stress_score (0-100, uint32)
      Field 6  – steps (uint32)
      Field 7  – calories (kcal, uint32)
      Field 8  – distance (metres, uint32)
      Field 9  – body_temperature (°C * 10, uint32)  → divide by 10
      Field 10 – systolic_bp (mmHg, uint32)
      Field 11 – diastolic_bp (mmHg, uint32)
      Field 12 – sleep_state (0=awake,1=light,2=deep,3=REM, uint32)
      Field 13 – battery_level (%, uint32)
      Field 14 – signal_strength (dBm-style, int32)

    NOTE: Field numbers may differ between firmware versions.
          Unknown fields are preserved under 'raw_fields'.
    """
    f = _parse_protobuf(payload)

    def _get(field: int, default=None):
        v = f.get(field, default)
        if isinstance(v, list):
            v = v[-1]       # take the last value for scalars
        return v

    result: Dict[str, Any] = {}

    ts = _get(1)
    if ts is not None:
        result['timestamp_unix'] = int(ts)

    hr = _get(2)
    if hr is not None and 30 <= hr <= 250:
        result['heart_rate_bpm'] = int(hr)

    spo2 = _get(3)
    if spo2 is not None and 50 <= spo2 <= 100:
        result['spo2_percent'] = int(spo2)

    hrv = _get(4)
    if hrv is not None:
        result['hrv_ms'] = int(hrv)

    stress = _get(5)
    if stress is not None and 0 <= stress <= 100:
        result['stress_score'] = int(stress)

    steps = _get(6)
    if steps is not None:
        result['steps'] = int(steps)

    cal = _get(7)
    if cal is not None:
        result['calories_kcal'] = int(cal)

    dist = _get(8)
    if dist is not None:
        result['distance_m'] = int(dist)

    temp = _get(9)
    if temp is not None and temp > 0:
        result['body_temperature_c'] = round(temp / 10.0, 1)

    sys_bp = _get(10)
    if sys_bp is not None and sys_bp > 0:
        result['bp_systolic_mmhg'] = int(sys_bp)

    dia_bp = _get(11)
    if dia_bp is not None and dia_bp > 0:
        result['bp_diastolic_mmhg'] = int(dia_bp)

    sleep = _get(12)
    if sleep is not None:
        sleep_map = {0: 'awake', 1: 'light', 2: 'deep', 3: 'rem'}
        result['sleep_state'] = sleep_map.get(int(sleep), f'unknown({sleep})')

    batt = _get(13)
    if batt is not None and 0 <= batt <= 100:
        result['battery_level_pct'] = int(batt)

    # Preserve any fields we didn't explicitly map
    known = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14}
    raw_extras = {str(k): (v.hex() if isinstance(v, bytes) else v)
                  for k, v in f.items() if k not in known}
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
    crc_ok   = (crc_calc == crc_rx)
    if not crc_ok:
        logger.warning(f"CRC mismatch: received 0x{crc_rx:04X}, calculated 0x{crc_calc:04X}")

    opt_names = {OPT_HEALTH: 'health', OPT_STEP: 'step_gnss', OPT_ALARM: 'alarm'}
    opt_name  = opt_names.get(opt, f'unknown_0x{opt:02X}')

    try:
        if opt == OPT_HEALTH:
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