# scripts/simple_controller.py
#!/usr/bin/env python3
# Simple controller for satellite reception

import os
import sys
import time
from pathlib import Path

from satellite_tracker.common import logging
from satellite_tracker.radio import gqrx
from satellite_tracker.satellites import definitions

def main():
    """Main function for simple satellite controller"""
    logger = logging.setup_logging("simple_controller")
    
    print("\nSimple Satellite Controller")
    print("=========================\n")
    print("This script will configure GQRX for satellite reception")
    print("Make sure GQRX is running with remote control enabled (Tools > Remote Control)\n")
    
    # List available satellites
    print("Available satellites:")
    satellite_list = definitions.get_satellites_list()
    for i, sat_name in enumerate(satellite_list, 1):
        sat_config = definitions.get_satellite_config(sat_name)
        print(f"{i}. {sat_name} ({sat_config['freq']/1000000:.3f} MHz)")
    
    # Get user selection
    while True:
        selection = input("\nEnter satellite number (or 'q' to quit): ")
        if selection.lower() == 'q':
            return
        
        try:
            index = int(selection) - 1
            if 0 <= index < len(satellite_list):
                satellite_name = satellite_list[index]
                break
            else:
                print("Invalid selection, please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Get recording duration
    while True:
        try:
            duration = float(input("Enter recording duration in minutes (0.5-15): "))
            if 0.5 <= duration <= 15:
                break
            else:
                print("Duration must be between 0.5 and 15 minutes.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Start GQRX if not running
    if not gqrx.start_gqrx():
        print("Failed to start GQRX. Please start it manually and try again.")
        return
    
    # Connect to GQRX
    controller = gqrx.GqrxController()
    if not controller.connect():
        print("Failed to connect to GQRX. Make sure it's running with remote control enabled.")
        return
    
    # Configure GQRX for selected satellite
    print(f"\nConfiguring GQRX for {satellite_name}...")
    if not controller.configure_for_satellite(satellite_name):
        print("Failed to configure GQRX. Please check the log for details.")
        controller.disconnect()
        return
    
    # Start recording
    print(f"\nStarting {duration} minute recording for {satellite_name}...")
    recorded_file = controller.record_satellite(satellite_name, duration)
    
    controller.disconnect()
    
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
