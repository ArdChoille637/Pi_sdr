# satellite_tracker/common/config.py
#!/usr/bin/env python3
# Common configuration management module

import os
import logging
import configparser
from pathlib import Path

logger = logging.getLogger(__name__)

# Default configuration paths
CONFIG_DIR = Path.home() / ".config" / "satellite_tracker"
CONFIG_FILE = CONFIG_DIR / "config.ini"
PASSES_FILE = CONFIG_DIR / "upcoming_passes.json"

def ensure_directories(dirs=None):
    """
    Ensure all necessary directories exist
    
    Args:
        dirs (list): Optional list of additional directories to create
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    if dirs:
        for directory in dirs:
            Path(directory).mkdir(parents=True, exist_ok=True)

def read_config(config_file=None):
    """
    Read configuration from config file
    
    Args:
        config_file (Path): Optional custom config file path
        
    Returns:
        dict: Configuration values
    """
    config_file = config_file or CONFIG_FILE
    config = configparser.ConfigParser()
    
    if not config_file.exists():
        # Create default config
        config['DEFAULT'] = {
            'min_elevation': '20',
            'gpredict_host': 'localhost',
            'gpredict_port': '4532',
            'gqrx_host': 'localhost',
            'gqrx_port': '7356',
            'recording_length': '15',  # minutes
            'check_interval': '5',     # minutes
            'ground_station_lat': '0.0',
            'ground_station_lon': '0.0',
            'ground_station_alt': '0',
            'recording_margin': '1',   # minutes
            'satellites': 'NOAA-15,NOAA-18,NOAA-19,METEOR-M2,METEOR-M2-2,METEOR-M2-3,ISS'
        }
        
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w') as configfile:
            config.write(configfile)
        
        logger.info(f"Created default configuration at {config_file}")
    else:
        config.read(config_file)
    
    return config['DEFAULT']

def update_config(config_data, section='DEFAULT', config_file=None):
    """
    Update configuration file with new settings
    
    Args:
        config_data (dict): Configuration values to update
        section (str): Configuration section to update
        config_file (Path): Optional custom config file path
    """
    config_file = config_file or CONFIG_FILE
    full_config = configparser.ConfigParser()
    
    if config_file.exists():
        full_config.read(config_file)
    
    if section not in full_config:
        full_config[section] = {}
    
    for key, value in config_data.items():
        full_config[section][key] = str(value)
    
    with open(config_file, 'w') as configfile:
        full_config.write(configfile)
    
    logger.info(f"Updated configuration at {config_file}")