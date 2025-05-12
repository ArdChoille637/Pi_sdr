# satellite_tracker/gps/location.py
#!/usr/bin/env python3
# GPS location management

import os
import sys
import time
import socket
import logging
import threading
import json
from pathlib import Path
import datetime
import serial
import pynmea2
import subprocess
from ..common import config

logger = logging.getLogger(__name__)

# File to store GPS location
GPS_CONFIG_FILE = config.CONFIG_DIR / "gps_location.json"

# Default GPS configuration
DEFAULT_GPS_CONFIG = {
    'gps_connection_type': 'socket',  # 'socket', 'bluetooth', or 'serial'
    'gps_socket_host': '0.0.0.0',      # Listen on all interfaces
    'gps_socket_port': 11123,          # Default port for GPS2IP
    'gps_bluetooth_mac': '',           # Bluetooth MAC address if using BT
    'gps_bluetooth_port': '/dev/rfcomm0',  # Bluetooth serial port
    'gps_serial_port': '/dev/ttyUSB0', # Serial port if using direct GPS
    'gps_serial_baud': 9600,           # Baud rate for serial connection
    'gps_update_interval': 10,         # How often to update location in seconds
    'location_check_interval': 60,     # How often to check in daemon mode (seconds)
    'last_latitude': 0.0,              # Last known latitude
    'last_longitude': 0.0,             # Last known longitude
    'last_altitude': 0.0,              # Last known altitude
}

# Global variables
current_location = {
    'latitude': 0.0,
    'longitude': 0.0,
    'altitude': 0.0,
    'timestamp': '',
    'satellites': 0,
    'speed': 0.0,
    'valid': False
}

# Lock for thread safety when updating location
location_lock = threading.Lock()

def save_location():
    """Save current location to file"""
    with location_lock:
        with open(GPS_CONFIG_FILE, 'w') as f:
            json.dump(current_location, f, indent=2)
    
    logger.debug(f"Location saved to {GPS_CONFIG_FILE}")

def load_location():
    """Load location from file
    
    Returns:
        bool: True if location loaded successfully, False otherwise
    """
    if GPS_CONFIG_FILE.exists():
        try:
            with open(GPS_CONFIG_FILE, 'r') as f:
                saved_location = json.load(f)
                
                with location_lock:
                    current_location.update(saved_location)
                
                logger.info(f"Loaded location: {current_location['latitude']}, {current_location['longitude']}")
                return True
        except Exception as e:
            logger.error(f"Error loading location: {e}")
    
    return False

def parse_nmea(nmea_string):
    """
    Parse NMEA string and update current location
    
    Args:
        nmea_string (str): NMEA sentence to parse
        
    Returns:
        bool: True if location updated, False otherwise
    """
    try:
        nmea_string = nmea_string.strip()
        if not nmea_string.startswith('):
            return False
        
        try:
            msg = pynmea2.parse(nmea_string)
        except pynmea2.ParseError:
            return False
        
        with location_lock:
            # GGA message contains latitude, longitude, altitude
            if isinstance(msg, pynmea2.GGA):
                if msg.latitude and msg.longitude:
                    current_location['latitude'] = msg.latitude
                    current_location['longitude'] = msg.longitude
                    current_location['altitude'] = msg.altitude if msg.altitude else 0.0
                    current_location['satellites'] = msg.num_sats if msg.num_sats else 0
                    current_location['timestamp'] = str(datetime.datetime.now())
                    current_location['valid'] = True
                    return True
            
            # VTG message contains speed information
            elif isinstance(msg, pynmea2.VTG):
                if msg.spd_over_grnd_kmph:
                    current_location['speed'] = float(msg.spd_over_grnd_kmph)
                    return True
        
        return False
    
    except Exception as e:
        logger.error(f"Error parsing NMEA string: {e}")
        return False

def socket_gps_reader(host, port):
    """Read GPS data from a socket connection"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind((host, port))
        sock.listen(1)
        logger.info(f"Listening for GPS data on {host}:{port}")
        
        while True:
            conn, addr = sock.accept()
            logger.info(f"Connected to {addr}")
            
            try:
                buffer = ""
                while True:
                    data = conn.recv(1024).decode('utf-8', errors='ignore')
                    if not data:
                        break
                    
                    buffer += data
                    lines = buffer.split('\n')
                    buffer = lines.pop()
                    
                    for line in lines:
                        if parse_nmea(line):
                            save_location()
            
            except Exception as e:
                logger.error(f"Error reading from socket: {e}")
            finally:
                conn.close()
                logger.info("Connection closed")
    
    except Exception as e:
        logger.error(f"Socket error: {e}")
    finally:
        sock.close()

def bluetooth_gps_reader(port):
    """Read GPS data from a Bluetooth serial connection"""
    try:
        ser = serial.Serial(port, 9600, timeout=5)
        logger.info(f"Connected to Bluetooth GPS on {port}")
        
        buffer = ""
        while True:
            try:
                data = ser.readline().decode('utf-8', errors='ignore')
                if parse_nmea(data):
                    save_location()
            except Exception as e:
                logger.error(f"Error reading from Bluetooth: {e}")
                time.sleep(1)
    
    except Exception as e:
        logger.error(f"Bluetooth error: {e}")

def serial_gps_reader(port, baud):
    """Read GPS data from a direct serial connection"""
    try:
        ser = serial.Serial(port, baud, timeout=5)
        logger.info(f"Connected to serial GPS on {port} at {baud} baud")
        
        while True:
            try:
                data = ser.readline().decode('utf-8', errors='ignore')
                if parse_nmea(data):
                    save_location()
            except Exception as e:
                logger.error(f"Error reading from serial: {e}")
                time.sleep(1)
    
    except Exception as e:
        logger.error(f"Serial error: {e}")

def setup_bluetooth_connection(mac_address, port='/dev/rfcomm0'):
    """
    Set up Bluetooth connection to GPS device
    
    Args:
        mac_address (str): Bluetooth MAC address
        port (str): Serial port to bind to
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First check if the rfcomm port already exists
        if Path(port).exists():
            logger.info(f"Bluetooth port {port} already exists")
            return True
        
        # Bind the Bluetooth device to a serial port
        logger.info(f"Setting up Bluetooth connection to {mac_address} on {port}")
        
        # Remove existing bindings
        subprocess.run(['sudo', 'rfcomm', 'release', port], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        
        # Create new binding
        result = subprocess.run(['sudo', 'rfcomm', 'bind', port, mac_address],
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Failed to bind Bluetooth device: {result.stderr}")
            return False
        
        logger.info(f"Successfully bound Bluetooth device {mac_address} to {port}")
        return True
    
    except Exception as e:
        logger.error(f"Error setting up Bluetooth: {e}")
        return False

def get_current_location():
    """
    Get the current GPS location
    
    Returns:
        dict: Current location information
    """
    with location_lock:
        return current_location.copy()

def update_satellite_config(location):
    """
    Update satellite tracking config with current location
    
    Args:
        location (dict): Location information
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conf = config.read_config()
        
        # Update ground station location
        conf_data = {
            'ground_station_lat': str(location['latitude']),
            'ground_station_lon': str(location['longitude']),
            'ground_station_alt': str(location['altitude'])
        }
        
        config.update_config(conf_data)
        
        logger.info(f"Updated satellite tracking config with location: {location['latitude']}, {location['longitude']}")
        return True
    except Exception as e:
        logger.error(f"Error updating satellite config: {e}")
        return False

def location_update_daemon(check_interval=60):
    """
    Background daemon to periodically update satellite tracking config with latest GPS location
    
    Args:
        check_interval (int): How often to check location in seconds
    """
    logger.info(f"Starting location update daemon with {check_interval}s interval")
    
    while True:
        try:
            location = get_current_location()
            
            if location['valid']:
                update_satellite_config(location)
            
            time.sleep(check_interval)
        
        except Exception as e:
            logger.error(f"Error in location update daemon: {e}")
            time.sleep(check_interval)

def start_gps_listener(gps_config):
    """
    Start the appropriate GPS listener based on configuration
    
    Args:
        gps_config (dict): GPS configuration
        
    Returns:
        bool: True if started successfully, False otherwise
    """
    connection_type = gps_config.get('gps_connection_type', 'socket')
    
    if connection_type == 'socket':
        host = gps_config.get('gps_socket_host', '0.0.0.0')
        port = int(gps_config.get('gps_socket_port', 11123))
        
        logger.info(f"Starting socket GPS listener on {host}:{port}")
        
        # Start in a separate thread
        gps_thread = threading.Thread(target=socket_gps_reader, args=(host, port))
        gps_thread.daemon = True
        gps_thread.start()
        
    elif connection_type == 'bluetooth':
        mac_address = gps_config.get('gps_bluetooth_mac', '')
        port = gps_config.get('gps_bluetooth_port', '/dev/rfcomm0')
        
        if not mac_address:
            logger.error("No Bluetooth MAC address configured")
            return False
        
        logger.info(f"Setting up Bluetooth connection to {mac_address}")
        if setup_bluetooth_connection(mac_address, port):
            # Start in a separate thread
            gps_thread = threading.Thread(target=bluetooth_gps_reader, args=(port,))
            gps_thread.daemon = True
            gps_thread.start()
        else:
            logger.error("Failed to set up Bluetooth connection")
            return False
        
    elif connection_type == 'serial':
        port = gps_config.get('gps_serial_port', '/dev/ttyUSB0')
        baud = int(gps_config.get('gps_serial_baud', 9600))
        
        logger.info(f"Starting serial GPS listener on {port} at {baud} baud")
        
        # Start in a separate thread
        gps_thread = threading.Thread(target=serial_gps_reader, args=(port, baud))
        gps_thread.daemon = True
        gps_thread.start()
    
    else:
        logger.error(f"Unknown GPS connection type: {connection_type}")
        return False
    
    # Start the location update daemon
    update_interval = int(gps_config.get('location_check_interval', 60))
    daemon_thread = threading.Thread(target=location_update_daemon, args=(update_interval,))
    daemon_thread.daemon = True
    daemon_thread.start()
    
    return True

def setup_wizard():
    """
    Interactive setup wizard for GPS integration
    
    Returns:
        dict: Updated GPS configuration
    """
    # Load current config
    conf = config.read_config()
    gps_config = {}
    
    # Extract GPS-specific settings
    for key in DEFAULT_GPS_CONFIG:
        if key in conf:
            gps_config[key] = conf[key]
        else:
            gps_config[key] = DEFAULT_GPS_CONFIG[key]
    
    print("\n=== GPS Integration Setup ===\n")
    show_iphone_instructions()
    
    print("\nSetup Options:")
    print("1. Use WiFi (Socket) connection (easiest)")
    print("2. Use Bluetooth connection")
    print("3. Use direct serial GPS (not using iPhone)")
    
    choice = input("\nSelect connection type (1-3): ")
    
    if choice == '1':
        gps_config['gps_connection_type'] = 'socket'
        host = input("Listen on which interface (default: 0.0.0.0 = all interfaces): ") or '0.0.0.0'
        port = input("Port to listen on (default: 11123): ") or '11123'
        
        gps_config['gps_socket_host'] = host
        gps_config['gps_socket_port'] = port
        
        print(f"\nConfigured to listen for GPS data on {host}:{port}")
        print("Make sure to set GPS2IP to Socket Mode with the same port number")
        
    elif choice == '2':
        gps_config['gps_connection_type'] = 'bluetooth'
        mac = input("Bluetooth MAC address of iPhone (format: XX:XX:XX:XX:XX:XX): ")
        port = input("Bluetooth serial port to use (default: /dev/rfcomm0): ") or '/dev/rfcomm0'
        
        gps_config['gps_bluetooth_mac'] = mac
        gps_config['gps_bluetooth_port'] = port
        
        print(f"\nConfigured to connect to Bluetooth device {mac} on {port}")
        print("Make sure to pair your iPhone with the Raspberry Pi first")
        print("Enable BLE Peripheral mode in GPS2IP")
        
    elif choice == '3':
        gps_config['gps_connection_type'] = 'serial'
        port = input("Serial port of GPS device (default: /dev/ttyUSB0): ") or '/dev/ttyUSB0'
        baud = input("Baud rate (default: 9600): ") or '9600'
        
        gps_config['gps_serial_port'] = port
        gps_config['gps_serial_baud'] = baud
        
        print(f"\nConfigured to connect to serial GPS on {port} at {baud} baud")
        
    else:
        print("Invalid choice, using default (WiFi/Socket)")
        gps_config['gps_connection_type'] = 'socket'
    
    # Update check intervals
    update_interval = input("\nHow often to check for location updates (seconds, default: 60): ") or '60'
    gps_config['location_check_interval'] = update_interval
    
    # Save configuration
    config.update_config(gps_config, section='GPS')
    
    print("\nConfiguration saved.")
    
    return gps_config

def show_iphone_instructions():
    """Show instructions for setting up GPS2IP on iPhone"""
    print("\nInstructions for setting up GPS2IP on iPhone:\n")
    print("1. Install GPS2IP or GPS2IP Lite from the App Store")
    print("2. Open GPS2IP and go to the Settings page")
    print("3. Set up the connection method:")
    print("   - For Bluetooth LE: Enable 'BLE Peripheral'")
    print("   - For WiFi: Enable 'Socket Mode', set port to 11123")
    print("4. Go back to the main screen and enable GPS2IP")
    print("5. Note the IP address displayed on the screen")
    print("\nIf using Bluetooth:")
    print("1. Pair your iPhone with the Raspberry Pi from Bluetooth settings")
    print("2. Note the Bluetooth MAC address of your iPhone")
    print("\nIf using WiFi:")
    print("1. Make sure your iPhone and Raspberry Pi are on the same WiFi network")
    print("2. Use the IP address displayed in GPS2IP\n")

def scan_bluetooth_devices():
    """
    Scan for available Bluetooth devices
    
    Returns:
        list: List of discovered Bluetooth devices
    """
    try:
        import subprocess
        print("Scanning for Bluetooth devices...")
        
        # Make sure Bluetooth is powered on
        subprocess.run(['sudo', 'bluetoothctl', 'power', 'on'])
        
        # Start scanning
        subprocess.run(['sudo', 'bluetoothctl', 'scan', 'on'], timeout=10)
        
        # Get list of devices
        result = subprocess.run(['sudo', 'bluetoothctl', 'devices'], 
                               capture_output=True, text=True)
        
        devices = result.stdout.strip().split('\n')
        
        print("\nAvailable Bluetooth devices:")
        for i, device in enumerate(devices, 1):
            print(f"{i}. {device}")
        
        print("\nNote the MAC address (format: XX:XX:XX:XX:XX:XX) of your iPhone")
        print("You can use this MAC address in the setup wizard")
        
        # Stop scanning
        subprocess.run(['sudo', 'bluetoothctl', 'scan', 'off'])
        
        return devices
        
    except Exception as e:
        print(f"Error scanning for Bluetooth devices: {e}")
        return []
