# satellite_tracker/satellites/predictor.py
#!/usr/bin/env python3
# Satellite pass prediction functions

import json
import socket
import datetime
import logging
from pathlib import Path
import subprocess
from ..common import config
from . import definitions

logger = logging.getLogger(__name__)

def connect_to_gpredict(host, port):
    """
    Connect to GPredict's Hamlib interface
    
    Args:
        host (str): GPredict host
        port (int): GPredict port
        
    Returns:
        socket.socket: Socket connected to GPredict, or None on error
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port)))
        return sock
    except Exception as e:
        logger.error(f"Error connecting to GPredict: {e}")
        return None

def get_next_pass(gpredict_sock, satellites, min_elevation):
    """
    Get the next satellite pass from GPredict
    
    Args:
        gpredict_sock (socket.socket): Socket connected to GPredict
        satellites (str): Comma-separated list of satellite names
        min_elevation (float): Minimum elevation for a usable pass
        
    Returns:
        dict: Next pass information, or None if no passes found
    """
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

def run_pass_prediction():
    """
    Run GPredict in batch mode to get upcoming passes and save to a file
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure the directory exists
        config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Run a custom version of GPredict command that outputs pass data
        # This is a placeholder - you'll need to adapt this for your system
        logger.info("Fetching upcoming satellite passes from GPredict...")
        
        # For testing, we'll create a sample file with dummy passes
        # In a real implementation, you would call GPredict's CLI or use its output files
        sample_passes = {}
        
        now = datetime.datetime.now()
        # Create sample passes for the next 24 hours
        for satellite_name in definitions.get_satellites_list():
            # Create 2 dummy passes for each satellite
            passes = []
            for i in range(2):
                # First pass in 2 hours, second in 6 hours
                aos_time = now + datetime.timedelta(hours=2 + i*4)
                los_time = aos_time + datetime.timedelta(minutes=15)
                max_time = aos_time + datetime.timedelta(minutes=7.5)
                
                passes.append({
                    "aos": aos_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "los": los_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "max_elevation_time": max_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "max_elevation": 45 + i*10,  # Dummy elevation
                    "duration_minutes": 15
                })
            
            sample_passes[satellite_name] = passes
        
        # Write the dummy data to a file
        with open(config.PASSES_FILE, 'w') as f:
            json.dump(sample_passes, f, indent=2)
        
        logger.info(f"Pass data saved to {config.PASSES_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error getting pass data: {e}")
        return False

def get_next_pass_from_file():
    """
    Read the next satellite pass from the local file
    
    Returns:
        dict: Next pass information, or None if no passes found
    """
    if not config.PASSES_FILE.exists():
        logger.error(f"Pass data file {config.PASSES_FILE} not found")
        return None
    
    try:
        with open(config.PASSES_FILE, 'r') as f:
            all_passes = json.load(f)
        
        next_pass = None
        next_pass_time = None
        
        now = datetime.datetime.now()
        
        for satellite_name, passes in all_passes.items():
            sat_config = definitions.get_satellite_config(satellite_name)
            if not sat_config:
                continue
                
            for pass_data in passes:
                aos_time = datetime.datetime.strptime(pass_data["aos"], "%Y-%m-%d %H:%M:%S")
                los_time = datetime.datetime.strptime(pass_data["los"], "%Y-%m-%d %H:%M:%S")
                max_elevation = pass_data["max_elevation"]
                
                # Skip passes that don't meet minimum elevation requirement
                if max_elevation < sat_config["min_elevation"]:
                    continue
                
                # Check if this is an upcoming pass
                if aos_time > now and (next_pass_time is None or aos_time < next_pass_time):
                    next_pass = {
                        "satellite": satellite_name,
                        "aos_time": aos_time,
                        "los_time": los_time,
                        "duration": (los_time - aos_time).total_seconds() / 60,  # duration in minutes
                        "max_elevation": max_elevation
                    }
                    next_pass_time = aos_time
        
        return next_pass
    except Exception as e:
        logger.error(f"Error reading pass data: {e}")
        return None
