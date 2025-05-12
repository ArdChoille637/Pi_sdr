# scripts/track_satellite.py
#!/usr/bin/env python3
# Main command-line interface for satellite tracking

import os
import sys
import argparse
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from satellite_tracker.common import config, logging
from satellite_tracker.radio import gqrx
from satellite_tracker.satellites import predictor, definitions
from satellite_tracker.recorder import manager
from satellite_tracker.gps import location

def main():
    """Main function for satellite tracking"""
    parser = argparse.ArgumentParser(description="Satellite Tracking System")
    
    # Main command groups
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Pass prediction commands
    predict_parser = subparsers.add_parser("predict", help="Predict satellite passes")
    predict_parser.add_argument("--update", action="store_true", help="Update pass data from GPredict")
    predict_parser.add_argument("--next", action="store_true", help="Show next pass")
    
    # Recording commands
    record_parser = subparsers.add_parser("record", help="Record satellite passes")
    record_parser.add_argument("--start", action="store_true", help="Start pass monitoring")
    record_parser.add_argument("--manual", nargs=3, metavar=("SATELLITE", "START_TIME", "DURATION"),
                             help="Manually schedule a recording (e.g. 'NOAA-15 \"2025-05-03 15:30:00\" 15')")
    
    # GQRX commands
    gqrx_parser = subparsers.add_parser("gqrx", help="Control GQRX")
    gqrx_parser.add_argument("--start", action="store_true", help="Start GQRX")
    gqrx_parser.add_argument("--configure", metavar="SATELLITE", help="Configure GQRX for satellite")
    
    # GPS commands
    gps_parser = subparsers.add_parser("gps", help="GPS location management")
    gps_parser.add_argument("--setup", action="store_true", help="Run GPS setup wizard")
    gps_parser.add_argument("--status", action="store_true", help="Show current GPS status")
    gps_parser.add_argument("--start", action="store_true", help="Start GPS integration")
    gps_parser.add_argument("--scan-bluetooth", action="store_true", help="Scan for Bluetooth devices")
    
    # List satellites
    list_parser = subparsers.add_parser("list", help="List available satellites")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Setup wizard")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Setup logging
    logger = logging.setup_logging("satellite_tracker")
    
    # Ensure directories exist
    config.ensure_directories()
    definitions.ensure_satellite_directories()
    
    # Process commands
    if args.command == "predict":
        if args.update:
            predictor.run_pass_prediction()
            print("Pass predictions updated")
        elif args.next:
            next_pass = predictor.get_next_pass_from_file()
            if next_pass:
                print(f"Next pass: {next_pass['satellite']} at {next_pass['aos_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Max elevation: {next_pass['max_elevation']:.1f}°")
                print(f"  Duration: {next_pass['duration']:.1f} minutes")
            else:
                print("No upcoming passes found")
        else:
            print("Please specify an action: --update or --next")
    
    elif args.command == "record":
        recorder = manager.RecordingManager()
        
        if args.start:
            print("Starting pass monitoring")
            recorder.start_monitoring()
            print("Monitoring started in background. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Monitoring stopped")
                recorder.stop_monitoring()
        
        elif args.manual:
            satellite_name = args.manual[0]
            start_time_str = args.manual[1]
            try:
                duration_minutes = float(args.manual[2])
            except ValueError:
                print(f"Invalid duration: {args.manual[2]}")
                return
            
            print(f"Manually scheduling recording for {satellite_name}")
            if recorder.manual_schedule_satellite(satellite_name, start_time_str, duration_minutes):
                print("Recording scheduled")
            else:
                print("Failed to schedule recording")
        
        else:
            print("Please specify an action: --start or --manual")
    
    elif args.command == "gqrx":
        if args.start:
            if gqrx.start_gqrx():
                print("GQRX started successfully")
            else:
                print("Failed to start GQRX")
        
        elif args.configure:
            satellite_name = args.configure
            if satellite_name not in definitions.get_satellites_list():
                print(f"Unknown satellite: {satellite_name}")
                print(f"Available satellites: {', '.join(definitions.get_satellites_list())}")
                return
            
            if not gqrx.start_gqrx():
                print("Failed to start GQRX")
                return
            
            controller = gqrx.GqrxController()
            if not controller.connect():
                print("Failed to connect to GQRX")
                return
            
            if controller.configure_for_satellite(satellite_name):
                print(f"GQRX configured for {satellite_name}")
            else:
                print(f"Failed to configure GQRX for {satellite_name}")
            
            controller.disconnect()
        
        else:
            print("Please specify an action: --start or --configure")
    
    elif args.command == "gps":
        if args.setup:
            location.setup_wizard()
        
        elif args.status:
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
        
        elif args.start:
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
        
        elif args.scan_bluetooth:
            location.scan_bluetooth_devices()
        
        else:
            print("Please specify an action: --setup, --status, --start or --scan-bluetooth")
    
    elif args.command == "list":
        print("Available satellites:")
        for sat_name in definitions.get_satellites_list():
            sat_config = definitions.get_satellite_config(sat_name)
            print(f"  {sat_name} - {sat_config['freq']/1000000:.3f} MHz, min_elevation: {sat_config['min_elevation']}°")
    
    elif args.command == "setup":
        print("\nSatellite Tracking System Setup Wizard")
        print("=====================================\n")
        print("This wizard will guide you through setting up the satellite tracking system.\n")
        
        # GPS setup
        print("\n--- GPS Setup ---")
        choice = input("Do you want to set up GPS integration? (y/n): ")
        if choice.lower() == 'y':
            location.setup_wizard()
        
        # GQRX setup
        print("\n--- GQRX Setup ---")
        choice = input("Do you want to test GQRX connection? (y/n): ")
        if choice.lower() == 'y':
            if gqrx.start_gqrx():
                print("GQRX started successfully")
                
                controller = gqrx.GqrxController()
                if controller.connect():
                    print("Successfully connected to GQRX")
                    controller.disconnect()
                else:
                    print("Failed to connect to GQRX")
            else:
                print("Failed to start GQRX")
        
        # Satellite tracking setup
        print("\n--- Satellite Tracking Setup ---")
        choice = input("Do you want to update satellite pass predictions? (y/n): ")
        if choice.lower() == 'y':
            predictor.run_pass_prediction()
            print("Pass predictions updated")
        
        print("\nSetup complete!")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()