#!/usr/bin/env python3
# satellite_pass_scheduler.py
# This script checks for upcoming satellite passes and automates recording with GQRX

import os
import sys
import time
import socket
import subprocess
import logging
import json
from pathlib import Path
import datetime
import configparser
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(Path.home() / "satellite_scheduler.log")),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("SatelliteScheduler")

# GQRX server settings
GQRX_HOST = "localhost"
GQRX_PORT = 7356

# Configuration
CONFIG_DIR = Path.home() / ".config" / "satellite_scheduler"
CONFIG_FILE = CONFIG_DIR / "config.ini"
PASSES_FILE = CONFIG_DIR / "upcoming_passes.json"

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

def ensure_directories():
    """Ensure all necessary directories exist"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    for sat_name, config in SATELLITES.items():
        record_dir = Path(config["recording_dir"])
        record_dir.mkdir(parents=True, exist_ok=True)
        
def read_config():
    """Read configuration from config file"""
    config = configparser.ConfigParser()
    
    if not CONFIG_FILE.exists():
        # Create default config
        config['DEFAULT'] = {
            'check_interval': '15',      # minutes
            'recording_margin': '1',     # minutes to add before and after pass
            'ground_station_lat': '0.0',
            'ground_station_lon': '0.0',
            'ground_station_alt': '0',
            'enabled_satellites': 'NOAA-15,NOAA-18,NOAA-19,METEOR-M2,METEOR-M2-3,ISS'
        }
        
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        
        logger.info(f"Created default configuration at {CONFIG_FILE}")
    else:
        config.read(CONFIG_FILE)
    
    return config['DEFAULT']

def connect_to_gqrx():
    """Connect to GQRX's remote control interface"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((GQRX_HOST, GQRX_PORT))
        return sock
    except Exception as e:
        logger.error(f"Error connecting to GQRX: {e}")
        return None

def configure_gqrx_for_satellite(gqrx_sock, satellite_name):
    """Configure GQRX with the appropriate settings for the satellite"""
    if satellite_name not in SATELLITES:
        logger.error(f"No configuration available for satellite {satellite_name}")
        return False
    
    try:
        config = SATELLITES[satellite_name]
        
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
        
        logger.info(f"Configured GQRX for {satellite_name}")
        return True
    except Exception as e:
        logger.error(f"Error configuring GQRX for {satellite_name}: {e}")
        return False

def start_recording(gqrx_sock, satellite_name, duration_minutes):
    """Start recording in GQRX for the specified duration"""
    if satellite_name not in SATELLITES:
        logger.error(f"No configuration available for satellite {satellite_name}")
        return False
    
    try:
        config = SATELLITES[satellite_name]
        record_dir = Path(config["recording_dir"])
        record_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{satellite_name}_{timestamp}.wav"
        filepath = record_dir / filename
        
        # Start recording
        gqrx_sock.send(f"AOS\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        gqrx_sock.send(f"RECORD {filepath}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        logger.info(f"Started recording {satellite_name} to {filepath}")
        
        # Sleep for the duration of the pass
        logger.info(f"Recording for {duration_minutes} minutes...")
        for i in range(int(duration_minutes * 60)):
            time.sleep(1)
            if i % 30 == 0:  # log every 30 seconds
                mins_remaining = (duration_minutes * 60 - i) / 60
                logger.info(f"Recording in progress, {mins_remaining:.1f} minutes remaining")
        
        # Stop recording
        gqrx_sock.send(f"RECORD OFF\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        gqrx_sock.send(f"LOS\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        logger.info(f"Finished recording {satellite_name}")
        
        # Return the recorded file path for post-processing
        return str(filepath)
    except Exception as e:
        logger.error(f"Error during recording of {satellite_name}: {e}")
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
            logger.info("Waiting 10 seconds for GQRX to start up...")
            time.sleep(10)
            return True
        else:
            logger.info("GQRX is already running")
            return True
    except Exception as e:
        logger.error(f"Error starting GQRX: {e}")
        return False

def run_gpredict_and_get_passes():
    """Run GPredict in batch mode to get upcoming passes and save to a file"""
    try:
        # Ensure the directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Run a custom version of GPredict command that outputs pass data
        # This is a placeholder - you'll need to adapt this for your system
        logger.info("Fetching upcoming satellite passes from GPredict...")
        
        # For testing, we'll create a sample file with dummy passes
        # In a real implementation, you would call GPredict's CLI or use its output files
        sample_passes = {}
        
        now = datetime.datetime.now()
        # Create sample passes for the next 24 hours
        for satellite_name in SATELLITES.keys():
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
        with open(PASSES_FILE, 'w') as f:
            json.dump(sample_passes, f, indent=2)
        
        logger.info(f"Pass data saved to {PASSES_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error getting pass data: {e}")
        return False

def get_next_pass_from_file():
    """Read the next satellite pass from the local file"""
    if not PASSES_FILE.exists():
        logger.error(f"Pass data file {PASSES_FILE} not found")
        return None
    
    try:
        with open(PASSES_FILE, 'r') as f:
            all_passes = json.load(f)
        
        next_pass = None
        next_pass_time = None
        
        now = datetime.datetime.now()
        
        for satellite_name, passes in all_passes.items():
            if satellite_name not in SATELLITES:
                continue
                
            for pass_data in passes:
                aos_time = datetime.datetime.strptime(pass_data["aos"], "%Y-%m-%d %H:%M:%S")
                los_time = datetime.datetime.strptime(pass_data["los"], "%Y-%m-%d %H:%M:%S")
                max_elevation = pass_data["max_elevation"]
                
                # Skip passes that don't meet minimum elevation requirement
                if max_elevation < SATELLITES[satellite_name]["min_elevation"]:
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

def schedule_recording(pass_data, recording_margin=1):
    """Schedule a recording for a satellite pass"""
    # Add a margin before and after the pass
    start_time = pass_data["aos_time"] - datetime.timedelta(minutes=recording_margin)
    end_time = pass_data["los_time"] + datetime.timedelta(minutes=recording_margin)
    total_duration = (end_time - start_time).total_seconds() / 60
    
    logger.info(f"Scheduling recording for {pass_data['satellite']}")
    logger.info(f"  Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  End: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Duration: {total_duration:.1f} minutes")
    logger.info(f"  Max Elevation: {pass_data['max_elevation']:.1f} degrees")
    
    # Calculate time until start
    now = datetime.datetime.now()
    seconds_until_start = (start_time - now).total_seconds()
    
    if seconds_until_start < 0:
        logger.warning(f"Pass for {pass_data['satellite']} has already started!")
        return False
    
    # Wait until it's time to start
    logger.info(f"Waiting for {seconds_until_start:.1f} seconds until pass begins")
    
    # If more than 5 minutes away, check again in 5 minutes
    # This prevents the script from blocking for too long
    if seconds_until_start > 300:
        return False
    
    # Wait until 30 seconds before the start
    if seconds_until_start > 30:
        time.sleep(seconds_until_start - 30)
    
    # Start GQRX
    if not start_gqrx():
        logger.error("Failed to start GQRX")
        return False
    
    # Connect to GQRX
    gqrx_sock = connect_to_gqrx()
    if not gqrx_sock:
        logger.error("Failed to connect to GQRX")
        return False
    
    # Configure GQRX
    if not configure_gqrx_for_satellite(gqrx_sock, pass_data["satellite"]):
        logger.error(f"Failed to configure GQRX for {pass_data['satellite']}")
        gqrx_sock.close()
        return False
    
    # Wait until the actual start time
    seconds_until_start = (start_time - datetime.datetime.now()).total_seconds()
    if seconds_until_start > 0:
        logger.info(f"Waiting final {seconds_until_start:.1f} seconds until recording starts")
        time.sleep(seconds_until_start)
    
    # Start recording
    recorded_file = start_recording(gqrx_sock, pass_data["satellite"], total_duration)
    
    gqrx_sock.close()
    
    if recorded_file:
        logger.info(f"Successfully recorded {pass_data['satellite']} to {recorded_file}")
        # Here you could add code to post-process the recording
        return True
    else:
        logger.error(f"Failed to record {pass_data['satellite']}")
        return False

def manual_schedule_satellite(satellite_name, start_time_str, duration_minutes):
    """Manually schedule a satellite recording"""
    if satellite_name not in SATELLITES:
        logger.error(f"Unknown satellite: {satellite_name}")
        print(f"Unknown satellite: {satellite_name}")
        print(f"Available satellites: {', '.join(SATELLITES.keys())}")
        return False
    
    try:
        # Parse the start time
        start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error(f"Invalid time format: {start_time_str}")
        print(f"Invalid time format: {start_time_str}")
        print("Use format: YYYY-MM-DD HH:MM:SS")
        return False
    
    # Create a pass data structure
    pass_data = {
        "satellite": satellite_name,
        "aos_time": start_time,
        "los_time": start_time + datetime.timedelta(minutes=duration_minutes),
        "duration": duration_minutes,
        "max_elevation": 90  # Assume maximum elevation for manual scheduling
    }
    
    # Schedule the recording
    return schedule_recording(pass_data, recording_margin=0)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Satellite Pass Scheduler")
    parser.add_argument("--check", action="store_true", help="Check for upcoming passes")
    parser.add_argument("--update", action="store_true", help="Update pass data from GPredict")
    parser.add_argument("--schedule", action="store_true", help="Schedule the next pass")
    parser.add_argument("--manual", nargs=3, metavar=("SATELLITE", "START_TIME", "DURATION"),
                      help="Manually schedule a recording (e.g. 'NOAA-15 \"2025-05-03 15:30:00\" 15')")
    parser.add_argument("--list", action="store_true", help="List available satellites")
    args = parser.parse_args()
    
    ensure_directories()
    config = read_config()
    
    if args.list:
        print("Available satellites:")
        for sat_name, sat_config in SATELLITES.items():
            print(f"  {sat_name} - {sat_config['freq']/1000000:.3f} MHz, min_elevation: {sat_config['min_elevation']}°")
        return
    
    if args.manual:
        satellite_name = args.manual[0]
        start_time_str = args.manual[1]
        try:
            duration_minutes = float(args.manual[2])
        except ValueError:
            print(f"Invalid duration: {args.manual[2]}")
            return
        
        manual_schedule_satellite(satellite_name, start_time_str, duration_minutes)
        return
    
    if args.update:
        run_gpredict_and_get_passes()
        return
    
    if args.check:
        next_pass = get_next_pass_from_file()
        if next_pass:
            print(f"Next pass: {next_pass['satellite']} at {next_pass['aos_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Max elevation: {next_pass['max_elevation']:.1f}°")
            print(f"  Duration: {next_pass['duration']:.1f} minutes")
        else:
            print("No upcoming passes found")
        return
    
    if args.schedule:
        next_pass = get_next_pass_from_file()
        if next_pass:
            print(f"Scheduling next pass: {next_pass['satellite']} at {next_pass['aos_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            schedule_recording(next_pass, float(config.get('recording_margin', 1)))
        else:
            print("No upcoming passes found")
        return
    
    # If no arguments provided, run in continuous monitoring mode
    logger.info("Starting satellite pass scheduler in continuous mode")
    logger.info(f"Checking for passes every {config['check_interval']} minutes")
    
    while True:
        try:
            # Update pass data periodically
            run_gpredict_and_get_passes()
            
            # Get next pass
            next_pass = get_next_pass_from_file()
            
            if not next_pass:
                logger.info("No upcoming passes found")
                logger.info(f"Sleeping for {config['check_interval']} minutes before checking again")
                time.sleep(int(config['check_interval']) * 60)
                continue
                
            logger.info(f"Next pass: {next_pass['satellite']} at {next_pass['aos_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  Max elevation: {next_pass['max_elevation']:.1f}°")
            logger.info(f"  Duration: {next_pass['duration']:.1f} minutes")
            
            # Calculate time until next pass
            now = datetime.datetime.now()
            time_until_pass = (next_pass['aos_time'] - now).total_seconds() / 60  # minutes
            
            # If the pass is more than check_interval minutes away, sleep and check again
            if time_until_pass > float(config['check_interval']):
                logger.info(f"Pass is {time_until_pass:.1f} minutes away")
                logger.info(f"Sleeping for {config['check_interval']} minutes before checking again")
                time.sleep(int(config['check_interval']) * 60)
                continue
                
            # If the pass is coming up soon, schedule it
            schedule_recording(next_pass, float(config.get('recording_margin', 1)))
            
            # After recording, sleep for a minute before checking again
            time.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user, exiting")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
