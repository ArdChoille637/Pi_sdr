#!/usr/bin/env python3
# simple_gqrx_controller.py
# This script controls GQRX directly without requiring GPredict

import os
import sys
import time
import socket
import subprocess
import logging
from pathlib import Path
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(Path.home() / "gqrx_controller.log")),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("GQRXController")

# GQRX server settings
GQRX_HOST = "localhost"
GQRX_PORT = 7356

# Satellite configurations
SATELLITES = {
    "1": {
        "name": "NOAA-15",
        "freq": 137620000,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,  # Adjust based on your SDR
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-15")
    },
    "2": {
        "name": "NOAA-18",
        "freq": 137912500,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-18")
    },
    "3": {
        "name": "NOAA-19",
        "freq": 137100000,  # Hz
        "mode": "WFM",
        "filter_width": 45000,  # Hz
        "filter_offset": -150000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "NOAA-19")
    },
    "4": {
        "name": "METEOR-M2",
        "freq": 137100000,  # Hz - sometimes changes to 137.9 MHz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2")
    },
    "5": {
        "name": "METEOR-M2-2",
        "freq": 137900000,  # Hz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2-2")
    },
    "6": {
        "name": "METEOR-M2-3",
        "freq": 137900000,  # Hz
        "mode": "WFM",
        "filter_width": 150000,  # Hz
        "filter_offset": -120000,  # Hz
        "squelch": -150,  # dB
        "gain": 50,
        "recording_dir": str(Path.home() / "satellite_data" / "METEOR-M2-3")
    },
    "7": {
        "name": "ISS",
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
    for sat in SATELLITES.values():
        record_dir = Path(sat["recording_dir"])
        record_dir.mkdir(parents=True, exist_ok=True)
        
def connect_to_gqrx():
    """Connect to GQRX's remote control interface"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((GQRX_HOST, GQRX_PORT))
        return sock
    except Exception as e:
        logger.error(f"Error connecting to GQRX: {e}")
        return None

def configure_gqrx_for_satellite(gqrx_sock, satellite_config):
    """Configure GQRX with the appropriate settings for the satellite"""
    try:
        # Set frequency
        gqrx_sock.send(f"F {satellite_config['freq']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set mode
        gqrx_sock.send(f"M {satellite_config['mode']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set filter bandwidth
        gqrx_sock.send(f"L {satellite_config['filter_width']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set squelch level
        gqrx_sock.send(f"L SQL {satellite_config['squelch']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set AGC off (if available in remote API)
        gqrx_sock.send(f"L AGC OFF\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        # Set gain (might need to be adjusted for your SDR)
        gqrx_sock.send(f"L RF {satellite_config['gain']}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        logger.info(f"Configured GQRX for {satellite_config['name']}")
        return True
    except Exception as e:
        logger.error(f"Error configuring GQRX for {satellite_config['name']}: {e}")
        return False

def start_recording(gqrx_sock, satellite_config, duration_minutes):
    """Start recording in GQRX for the specified duration"""
    try:
        record_dir = Path(satellite_config["recording_dir"])
        record_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{satellite_config['name']}_{timestamp}.wav"
        filepath = record_dir / filename
        
        # Start recording
        gqrx_sock.send(f"AOS\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        gqrx_sock.send(f"RECORD {filepath}\n".encode())
        response = gqrx_sock.recv(1024).decode().strip()
        
        logger.info(f"Started recording {satellite_config['name']} to {filepath}")
        
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
        
        logger.info(f"Finished recording {satellite_config['name']}")
        
        # Return the recorded file path for post-processing
        return str(filepath)
    except Exception as e:
        logger.error(f"Error during recording of {satellite_config['name']}: {e}")
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

def main():
    """Main function"""
    ensure_directories()
    
    print("\nSimple GQRX Controller")
    print("======================\n")
    print("This script will configure GQRX for satellite reception")
    print("Make sure GQRX is running with remote control enabled (Tools > Remote Control)\n")
    
    # List available satellites
    print("Available satellites:")
    for key, sat in SATELLITES.items():
        print(f"{key}. {sat['name']} ({sat['freq']/1000000:.3f} MHz)")
    
    # Get user selection
    while True:
        selection = input("\nEnter satellite number (or 'q' to quit): ")
        if selection.lower() == 'q':
            return
        
        if selection in SATELLITES:
            break
        else:
            print("Invalid selection, please try again.")
    
    # Get recording duration
    while True:
        try:
            duration = float(input("Enter recording duration in minutes (1-15): "))
            if 0.5 <= duration <= 15:
                break
            else:
                print("Duration must be between 0.5 and 15 minutes.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Start GQRX if not running
    if not start_gqrx():
        print("Failed to start GQRX. Please start it manually and try again.")
        return
    
    # Connect to GQRX
    gqrx_sock = connect_to_gqrx()
    if not gqrx_sock:
        print("Failed to connect to GQRX. Make sure it's running with remote control enabled.")
        return
    
    # Configure GQRX for selected satellite
    satellite_config = SATELLITES[selection]
    print(f"\nConfiguring GQRX for {satellite_config['name']}...")
    if not configure_gqrx_for_satellite(gqrx_sock, satellite_config):
        print("Failed to configure GQRX. Please check the log for details.")
        gqrx_sock.close()
        return
    
    # Start recording
    print(f"\nStarting {duration} minute recording for {satellite_config['name']}...")
    recorded_file = start_recording(gqrx_sock, satellite_config, duration)
    
    gqrx_sock.close()
    
    if recorded_file:
        print(f"\nSuccessfully recorded to {recorded_file}")
        print("You can now process this recording with appropriate decoding software.")
    else:
        print("\nRecording failed. Please check the log for details.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
