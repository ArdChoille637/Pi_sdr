# satellite_tracker/satellites/definitions.py
#!/usr/bin/env python3
# Satellite definitions and configurations

from pathlib import Path

# Satellite configurations
SATELLITES = {
    "NOAA-15": {
        "freq": 137620000,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,  # Adjust based on your SDR
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-15"),
        "min_elevation": 20  # Minimum elevation for a usable pass
    },
    "NOAA-18": {
        "freq": 137912500,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-18"),
        "min_elevation": 20
    },
    "NOAA-19": {
        "freq": 137100000,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-19"),
        "min_elevation": 20
    },
    "METEOR-M2": {
        "freq": 137100000,  # Hz - sometimes changes to 137.9 MHz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2"),
        "min_elevation": 25  # METEOR needs better signal typically
    },
    "METEOR-M2-2": {
        "freq": 137900000,  # Hz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2-2"),
        "min_elevation": 25
    },
    "METEOR-M2-3": {
        "freq": 137900000,  # Hz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2-3"),
        "min_elevation": 25
    },
    "ISS": {
        "freq": 145800000,  # Hz - FM voice downlink
        "mode": "FM",
        "filter_width": 15000,  # Hz
        "filter_offset": 0,  # Hz
        "squelch": -80,  # dB
        "gain": 40,
        "recording_dir": str(Path.home() / "satellite_data" / "ISS"),
        "min_elevation": 10  # ISS is often receivable at lower elevations
    }
}

def get_satellite_config(name):
    """
    Get configuration for a specific satellite
    
    Args:
        name (str): Satellite name
        
    Returns:
        dict: Satellite configuration, or None if satellite is not defined
    """
    return SATELLITES.get(name)

def get_satellites_list():
    """
    Get list of available satellites
    
    Returns:
        list: Satellite names
    """
    return list(SATELLITES.keys())

def ensure_satellite_directories():
    """Ensure all satellite recording directories exist"""
    for sat_name, config in SATELLITES.items():
        record_dir = Path(config["recording_dir"])
        record_dir.mkdir(parents=True, exist_ok=True)
