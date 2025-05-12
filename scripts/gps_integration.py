# scripts/gps_integration.py
#!/usr/bin/env python3
# GPS integration for satellite tracking

import os
import sys
import time
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from satellite_tracker.common import config, logging
from satellite_tracker.gps import location

def main():
    """Main function for GPS integration"""
    parser = argparse.ArgumentParser(description="GPS Integration for Satellite Tracking")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    parser.add_argument("--start", action="store_true", help="Start GPS integration")
    parser.add_argument("--status", action="store_true", help="Show current GPS status")
    parser.add_argument("--scan-bluetooth", action="store_true", help="Scan for Bluetooth devices")
    args = parser.parse_args()
    
    # Setup logging
    logger = logging.setup_logging("gps_integration")
    
    # Ensure directories exist
    config.ensure_directories()
    
    if args.scan_bluetooth:
        location.scan_bluetooth_devices()
        return
    
    if args.setup:
        location.setup_wizard()
        return
    
    if args.status:
        location.load_location()
        current_loc = location.get_current_location()
        
        print("\nCurrent GPS Status:")
        print(f"Valid: {'Yes' if current_loc['valid'] else 'No'}")
        print(f"Latitude: {current_loc['latitude']}")
        print(f"Longitude: {current_loc['longitude']}")
        print(f"Altitude: {current_loc['altitude']} m")
        print(f"Satellites: {current_loc['satellites']}")
        print(f"Speed: {current_loc['speed']} km/h")
        print(f"Timestamp: {current_loc['timestamp']}")
        return
    
    if args.start:
        # Read GPS config
        conf = config.read_config()
        
        # Extract GPS-specific settings
        gps_config = {}
        for key in location.DEFAULT_GPS_CONFIG:
            if key in conf:
                gps_config[key] = conf[key]
            else:
                gps_config[key] = location.DEFAULT_GPS_CONFIG[key]
        
        print(f"Starting GPS integration using {gps_config['gps_connection_type']} connection")
        
        if location.start_gps_listener(gps_config):
            print("GPS integration started successfully")
            print("Press Ctrl+C to stop")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nGPS integration stopped")
        else:
            print("Failed to start GPS integration")
        
        return
    
    # If no arguments provided, show help
    parser.print_help()

if __name__ == "__main__":
    main()