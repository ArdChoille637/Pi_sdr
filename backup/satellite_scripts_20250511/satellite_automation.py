#!/usr/bin/env python3
# satellite_automation.py
# Script to automate satellite reception using GPredict and GQRX

import os
import sys
import time
import socket
import subprocess
import datetime
import configparser
import logging
from pathlib import Path
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(Path.home() / "satellite_automation.log")),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("SatelliteAutomation")

# Configuration
CONFIG_DIR = Path.home() / ".config" / "satellite_automation"
CONFIG_FILE = CONFIG_DIR / "config.ini"
GQRX_CONFIG_DIR = Path.home() / ".config" / "gqrx"

# Satellite configurations
SATELLITE_CONFIGS = {
    "NOAA-15": {
        "freq": 137620000,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,  # Adjust based on your SDR
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-15")
    },
    "NOAA-18": {
        "freq": 137912500,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-18")
    },
    "NOAA-19": {
        "freq": 137100000,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-19")
    },
    "METEOR-M2": {
        "freq": 137100000,  # Hz - sometimes changes to 137.9 MHz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2")
    },
    "METEOR-M2-2": {
        "freq": 137900000,  # Hz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2-2")
    },
    "METEOR-M2-3": {
        "freq": 137900000,  # Hz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2-3")
    },
    "ISS": {
        "freq": 145800000,  # Hz - FM voice downlink
        "mode": "FM",
        "filter_width": 15000,  # Hz
        "filter_offset": 0,  # Hz
        "squelch": -80,  # dB
        "gain": 40,
        "recording_dir": str(Path.home() / "satellite_data" / "ISS")
    }
}

def ensure_directories():
    """Ensure all necessary directories exist"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    for sat_name, config in SATELLITE_CONFIGS.items():
        record_dir = Path(config["recording_dir"])
        record_dir.mkdir(parents=True, exist_ok=True)
        
def read_config():
    """Read configuration from config file"""
    config = configparser.ConfigParser()
    
    if not CONFIG_FILE.exists():
        # Create default config
        config['DEFAULT'] = {
            'min_elevation': '20',
            'gpredict_host': 'localhost',
            'gpredict_port': '4532',
            'gqrx_host': 'localhost',
            'gqrx_port': '7356',
            'recording_length': '15',  # minutes
            'check_interval': '5',      # minutes
            'ground_station_lat': '0.0',
            'ground_station_lon': '0.0',
            'ground_station_alt': '0',
            'satellites': 'NOAA-15,NOAA-18,NOAA-19,METEOR-M2,METEOR-M2-2,METEOR-M2-3,ISS'
        }
        
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        
        logger.info(f"Created default configuration at {CONFIG_FILE}")
    else:
        config.read(CONFIG_FILE)
    
    return config['DEFAULT']

def connect_to_gpredict(host, port):
    """Connect to GPredict's Hamlib interface"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port)))
        return sock
    except Exception as e:
        logger.error(f"Error connecting to GPredict: {e}")
        return None

def connect_to_gqrx(host, port):
    """Connect to GQRX's remote control interface"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port)))
        return sock
    except Exception as e:
        logger.error(f"Error connecting to GQRX: {e}")
        return None

def get_next_pass(gpredict_sock, satellites, min_elevation):
    """Get the next satellite pass from GPredict"""
    min_elevation = float(min_elevation)
    next_pass = None
    next_pass_time = None
    
    for satellite in satellites.split(','):
        try:
            # Request prediction for this satellite
            gpredict_sock.send(f"PREDICT {satellite} 1\n".encode())
            response = gpredict_sock.recv(1024).decode().strip()
            
            # Parse response
            if response.startswith("PREDICT"):
                lines = response.split('\n')
                if len(lines) >= 2:
                    # Extract AOS (Acquisition of Signal) time, LOS (Loss of Signal) time, and max elevation
                    parts = lines[1].split()
                    if len(parts) >= 3:
                        aos_time = datetime.datetime.fromtimestamp(int(parts[0]))
                        los_time = datetime.datetime.fromtimestamp(int(parts[1]))
                        max_elevation = float(parts[2])
                        
                        # Check if pass meets elevation threshold
                        if max_elevation >= min_elevation:
                            # Check if this is the next upcoming pass
                            now = datetime.datetime.now()
                            if aos_time > now and (next_pass_time is None or aos_time < next_pass_time):
                                next_pass = {
                                    'satellite': satellite,
                                    'aos_time': aos_time,
                                    'los_time': los_time,
                                    'duration': (los_time - aos_time).total_seconds() / 60,  # duration in minutes
                                    'max_elevation': max_elevation
                                }
                                next_pass_time = aos_time
        except Exception as e:
            logger.error(f"Error getting prediction for {satellite}: {e}")
    
    return next_pass

def configure_gqrx_for_satellite(gqrx_sock, satellite):
    """Configure GQRX with the appropriate settings for the satellite"""
    if satellite not in SATELLITE_CONFIGS:
        logger.error(f"No configuration available for satellite {satellite}")
        return False
    
    try:
        config = SATELLITE_CONFIGS[satellite]
        
        # Set frequency
        gqrx_sock.send(f"F {config['freq']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set mode
        gqrx_sock.send(f"M {config['mode']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set filter bandwidth
        gqrx_sock.send(f"L {config['filter_width']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set squelch level
        gqrx_sock.send(f"L SQL {config['squelch']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set AGC off (if available in remote API)
        gqrx_sock.send(f"L AGC OFF\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set gain (might need to be adjusted for your SDR)
        gqrx_sock.send(f"L RF {config['gain']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        logger.info(f"Configured GQRX for {satellite}")
        return True
    except Exception as e:
        logger.error(f"Error configuring GQRX for {satellite}: {e}")
        return False

def start_recording(gqrx_sock, satellite, duration_minutes):
    """Start recording in GQRX for the specified duration"""
    if satellite not in SATELLITE_CONFIGS:
        logger.error(f"No configuration available for satellite {satellite}")
        return False
    
    try:
        config = SATELLITE_CONFIGS[satellite]
        record_dir = Path(config["recording_dir"])
        record_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{satellite}_{timestamp}.wav"
        filepath = record_dir / filename
        
        # Start recording
        gqrx_sock.send(f"AOS\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        gqrx_sock.send(f"RECORD {filepath}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        logger.info(f"Started recording {satellite} to {filepath}")
        
        # Sleep for the duration of the pass
        time.sleep(duration_minutes * 60)
        
        # Stop recording
        gqrx_sock.send(f"RECORD OFF\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        gqrx_sock.send(f"LOS\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        logger.info(f"Finished recording {satellite}")
        
        # Return the recorded file path for post-processing
        return str(filepath)
    except Exception as e:
        logger.error(f"Error during recording of {satellite}: {e}")
        return None

def start_gqrx():
    """Start GQRX if it's not already running"""
    try:
        # Check if GQRX is already running
        result = subprocess.run(["pgrep", "gqrx"], capture_output=True, text=True)
        if result.returncode != 0:
            # GQRX is not running, start it
            logger.info("Starting GQRX...")
            subprocess.Popen(["gqrx"], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL,
                            start_new_session=True)
            
            # Give GQRX time to start
            time.sleep(10)
            return True
        else:
            logger.info("GQRX is already running")
            return True
    except Exception as e:
        logger.error(f"Error starting GQRX: {e}")
        return False

def main():
    """Main function"""
    ensure_directories()
    config = read_config()
    
    logger.info("Starting satellite pass automation")
    
    while True:
        try:
            # Connect to GPredict
            gpredict_sock = connect_to_gpredict(config['gpredict_host'], config['gpredict_port'])
            if not gpredict_sock:
                logger.error("Failed to connect to GPredict, retrying in 30 seconds")
                time.sleep(30)
                continue
                
            # Get next satellite pass
            logger.info("Checking for upcoming satellite passes...")
            next_pass = get_next_pass(gpredict_sock, config['satellites'], config['min_elevation'])
            gpredict_sock.close()
            
            if not next_pass:
                logger.info(f"No upcoming passes found above {config['min_elevation']} degrees. Checking again in {config['check_interval']} minutes")
                time.sleep(int(config['check_interval']) * 60)
                continue
                
            # Calculate time until next pass
            now = datetime.datetime.now()
            time_until_pass = (next_pass['aos_time'] - now).total_seconds()
            
            logger.info(f"Next pass: {next_pass['satellite']} at {next_pass['aos_time'].strftime('%Y-%m-%d %H:%M:%S')}, "
                      f"max elevation: {next_pass['max_elevation']:.1f}°, duration: {next_pass['duration']:.1f} minutes")
            
            # If the pass is more than check_interval minutes away, sleep and check again
            if time_until_pass > int(config['check_interval']) * 60:
                logger.info(f"Sleeping for {config['check_interval']} minutes before checking again")
                time.sleep(int(config['check_interval']) * 60)
                continue
                
            # If the pass is coming up soon, prepare for it
            if time_until_pass > 30:  # If we have more than 30 seconds until the pass
                logger.info(f"Waiting {time_until_pass:.0f} seconds until pass begins")
                time.sleep(time_until_pass - 30)  # Sleep until 30 seconds before the pass
                
            # Start GQRX if it's not already running
            if not start_gqrx():
                logger.error("Failed to start GQRX, skipping this pass")
                time.sleep(60)
                continue
                
            # Connect to GQRX
            gqrx_sock = connect_to_gqrx(config['gqrx_host'], config['gqrx_port'])
            if not gqrx_sock:
                logger.error("Failed to connect to GQRX, skipping this pass")
                time.sleep(60)
                continue
                
            # Configure GQRX for the satellite
            if not configure_gqrx_for_satellite(gqrx_sock, next_pass['satellite']):
                logger.error(f"Failed to configure GQRX for {next_pass['satellite']}, skipping this pass")
                gqrx_sock.close()
                time.sleep(60)
                continue
                
            # Wait until pass begins
            now = datetime.datetime.now()
            time_until_pass = (next_pass['aos_time'] - now).total_seconds()
            if time_until_pass > 0:
                logger.info(f"Waiting {time_until_pass:.0f} seconds until pass begins")
                time.sleep(time_until_pass)
                
            # Start recording
            recording_duration = min(float(next_pass['duration']), float(config['recording_length']))
            logger.info(f"Starting recording for {recording_duration:.1f} minutes")
            recorded_file = start_recording(gqrx_sock, next_pass['satellite'], recording_duration)
            
            gqrx_sock.close()
            
            if recorded_file:
                logger.info(f"Successfully recorded {next_pass['satellite']} to {recorded_file}")
                # Here you could add post-processing code to decode the recorded satellite data
            
            # Sleep for a minute before checking for the next pass
            time.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user, exiting")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
