"""
Configuration settings for iWOWN Health Monitoring API
"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file (with error handling)
try:
    load_dotenv(verbose=False)
except Exception as e:
    print(f"Info: No .env file found or error loading: {e}")
    print("Using default configuration values...")

class Settings:
    """Application settings"""
    
    # MongoDB Configuration (Only settings actually used)
    MONGODB_URL: str = os.getenv("MONGODB_URL")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "iwown_health")
    
    # iWOWN Specific Endpoints (Used for reference)
    IWOWN_ENDPOINTS: List[str] = [
        "/4g/pb/upload",
        "/4g/alarm/upload", 
        "/4g/call_log/upload",
        "/4g/deviceinfo/upload",
        "/4g/status/notify",
        "/4g/health/sleep"
    ]

# Global settings instance
settings = Settings()

# Validate required environment variables
if not settings.MONGODB_URL:
    raise ValueError("MONGODB_URL environment variable is required. Please set it in your .env file or environment.")
