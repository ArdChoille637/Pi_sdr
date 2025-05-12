# satellite_tracker/radio/gqrx.py
#!/usr/bin/env python3
# GQRX control interface

import socket
import subprocess
import time
import logging
from pathlib import Path
import datetime
from ..satellites import definitions

logger = logging.getLogger(__name__)

class GqrxController:
    """Interface for controlling GQRX via remote control protocol"""
    
    def __init__(self, host="localhost", port=7356):
        """
        Initialize GQRX controller
        
        Args:
            host (str): GQRX remote control host
            port (int): GQRX remote control port
        """
        self.host = host
        self.port = port
        self.sock = None
    
    def connect(self):
        """
        Connect to GQRX's remote control interface
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to GQRX at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to GQRX: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from GQRX"""
        if self.sock:
            self.sock.close()
            self.sock = None
            logger.info("Disconnected from GQRX")
    
    def send_command(self, command):
        """
        Send command to GQRX and get response
        
        Args:
            command (str): Command to send
            
        Returns:
            str: Response from GQRX, or None on error
        """
        if not self.sock:
            logger.error("Not connected to GQRX")
            return None
        
        try:
            self.sock.send(f"{command}\n".encode())
            response = self.sock.recv(1024).decode().strip()
            return response
        except Exception as e:
            logger.error(f"Error sending command to GQRX: {e}")
            return None
    
    def set_frequency(self, freq_hz):
        """
        Set GQRX frequency
        
        Args:
            freq_hz (int): Frequency in Hz
            
        Returns:
            bool: True if successful, False otherwise
        """
        response = self.send_command(f"F {freq_hz}")
        if response and response.startswith("RPRT 0"):
            logger.info(f"Set frequency to {freq_hz/1000000:.3f} MHz")
            return True
        return False
    
    def set_mode(self, mode):
        """
        Set GQRX demodulation mode
        
        Args:
            mode (str): Demodulation mode (e.g., "WFM", "FM", "AM")
            
        Returns:
            bool: True if successful, False otherwise
        """
        response = self.send_command(f"M {mode}")
        if response and response.startswith("RPRT 0"):
            logger.info(f"Set mode to {mode}")
            return True
        return False
    
    def set_filter(self, width_hz):
        """
        Set GQRX filter width
        
        Args:
            width_hz (int): Filter width in Hz
            
        Returns:
            bool: True if successful, False otherwise
        """
        response = self.send_command(f"L {width_hz}")
        if response and response.startswith("RPRT 0"):
            logger.info(f"Set filter width to {width_hz} Hz")
            return True
        return False
    
    def set_squelch(self, level_db):
        """
        Set GQRX squelch level
        
        Args:
            level_db (int): Squelch level in dB
            
        Returns:
            bool: True if successful, False otherwise
        """
        response = self.send_command(f"L SQL {level_db}")
        if response and response.startswith("RPRT 0"):
            logger.info(f"Set squelch to {level_db} dB")
            return True
        return False
    
    def set_gain(self, gain):
        """
        Set GQRX RF gain
        
        Args:
            gain (int): Gain value
            
        Returns:
            bool: True if successful, False otherwise
        """
        response = self.send_command(f"L RF {gain}")
        if response and response.startswith("RPRT 0"):
            logger.info(f"Set RF gain to {gain}")
            return True
        return False
    
    def start_recording(self, filepath):
        """
        Start recording to file
        
        Args:
            filepath (str): Output file path
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.send_command("AOS")
        response = self.send_command(f"RECORD {filepath}")
        if response and response.startswith("RPRT 0"):
            logger.info(f"Started recording to {filepath}")
            return True
        return False
    
    def stop_recording(self):
        """
        Stop recording
        
        Returns:
            bool: True if successful, False otherwise
        """
        response = self.send_command("RECORD OFF")
        if response and response.startswith("RPRT 0"):
            self.send_command("LOS")
            logger.info("Stopped recording")
            return True
        return False
    
    def configure_for_satellite(self, satellite_name):
        """
        Configure GQRX with appropriate settings for a satellite
        
        Args:
            satellite_name (str): Satellite name
            
        Returns:
            bool: True if successful, False otherwise
        """
        sat_config = definitions.get_satellite_config(satellite_name)
        if not sat_config:
            logger.error(f"No configuration available for satellite {satellite_name}")
            return False
        
        try:
            # Set frequency
            if not self.set_frequency(sat_config['freq']):
                return False
            
            # Set mode
            if not self.set_mode(sat_config['mode']):
                return False
            
            # Set filter width
            if not self.set_filter(sat_config['filter_width']):
                return False
            
            # Set squelch level
            if not self.set_squelch(sat_config['squelch']):
                return False
            
            # Set AGC off (if available in remote API)
            self.send_command("L AGC OFF")
            
            # Set gain
            if not self.set_gain(sat_config['gain']):
                return False
            
            logger.info(f"Configured GQRX for {satellite_name}")
            return True
        except Exception as e:
            logger.error(f"Error configuring GQRX for {satellite_name}: {e}")
            return False

    def record_satellite(self, satellite_name, duration_minutes):
        """
        Record a satellite pass
        
        Args:
            satellite_name (str): Satellite name
            duration_minutes (float): Recording duration in minutes
            
        Returns:
            str: Recorded file path, or None on error
        """
        sat_config = definitions.get_satellite_config(satellite_name)
        if not sat_config:
            logger.error(f"No configuration available for satellite {satellite_name}")
            return None
        
        try:
            record_dir = Path(sat_config["recording_dir"])
            record_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{satellite_name}_{timestamp}.wav"
            filepath = record_dir / filename
            
            # Start recording
            if not self.start_recording(str(filepath)):
                return None
            
            # Log recording progress
            logger.info(f"Recording {satellite_name} for {duration_minutes} minutes...")
            for i in range(int(duration_minutes * 60)):
                time.sleep(1)
                if i % 30 == 0:  # log every 30 seconds
                    mins_remaining = (duration_minutes * 60 - i) / 60
                    logger.info(f"Recording in progress, {mins_remaining:.1f} minutes remaining")
            
            # Stop recording
            if not self.stop_recording():
                logger.warning("Error stopping recording")
            
            logger.info(f"Finished recording {satellite_name}")
            
            return str(filepath)
        except Exception as e:
            logger.error(f"Error during recording of {satellite_name}: {e}")
            self.stop_recording()  # Try to stop recording on error
            return None


def start_gqrx():
    """
    Start GQRX if it's not already running
    
    Returns:
        bool: True if GQRX is running, False otherwise
    """
    try:
        # Check if GQRX is already running
        result = subprocess.run(["pgrep", "gqrx"], capture_output=True, text=True)
        if result.returncode != 0:
            # GQRX is not running, start it
            logger.info("Starting GQRX...")
            subprocess.Popen(
                ["gqrx"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
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