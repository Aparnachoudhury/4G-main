# Pydantic models for request/response validation
from typing import Optional, Dict, Any
from pydantic import BaseModel

class DeviceInfo(BaseModel):
    deviceid: Optional[str] = None
    battery: Optional[int] = None
    firmware_version: Optional[str] = None
    model: Optional[str] = None

class AlarmData(BaseModel):
    deviceid: Optional[str] = None
    alarm_type: Optional[str] = None
    timestamp: Optional[str] = None
    location: Optional[str] = None

class CallLogData(BaseModel):
    deviceid: Optional[str] = None
    call_type: Optional[str] = None
    timestamp: Optional[str] = None
    duration: Optional[int] = None

class StatusData(BaseModel):
    DeviceId: Optional[str] = None
    Status: Optional[str] = None
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None

class SleepData(BaseModel):
    device_id: Optional[str] = None
    sleep_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    deep_sleep: Optional[int] = None
    light_sleep: Optional[int] = None
    weak_sleep: Optional[int] = None
    eyemove_sleep: Optional[int] = None
    score: Optional[int] = None
    osahs_risk: Optional[int] = None
    spo2_score: Optional[int] = None
    sleep_hr: Optional[int] = None

class HealthResponse(BaseModel):
    ReturnCode: int = 0
    Data: Dict[str, Any] = {}

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: str
