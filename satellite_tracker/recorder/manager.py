# satellite_tracker/recorder/manager.py
#!/usr/bin/env python3
# Recording management for satellite passes

import logging
import datetime
import time
import threading
from pathlib import Path
from ..common import config
from ..radio import gqrx
from ..satellites import predictor, definitions

logger = logging.getLogger(__name__)

class RecordingManager:
    """Manager for scheduling and recording satellite passes"""
    
    def __init__(self, gqrx_host="localhost", gqrx_port=7356):
        """
        Initialize recording manager
        
        Args:
            gqrx_host (str): GQRX remote control host
            gqrx_port (int): GQRX remote control port
        """
        self.gqrx_host = gqrx_host
        self.gqrx_port = gqrx_port
        self.controller = None
        self.running = False
        self.current_recording = None
        self.recording_thread = None
    
    def connect_to_gqrx(self):
        """
        Connect to GQRX
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        # Start GQRX if not running
        if not gqrx.start_gqrx():
            logger.error("Failed to start GQRX")
            return False
        
        # Connect to GQRX
        self.controller = gqrx.GqrxController(self.gqrx_host, self.gqrx_port)
        if not self.controller.connect():
            logger.error("Failed to connect to GQRX")
            return False
        
        return True
    
    def disconnect_from_gqrx(self):
        """Disconnect from GQRX"""
        if self.controller:
            self.controller.disconnect()
            self.controller = None
    
    def schedule_recording(self, pass_data, recording_margin=1):
        """
        Schedule a recording for a satellite pass
        
        Args:
            pass_data (dict): Pass information
            recording_margin (float): Minutes to add before and after the pass
            
        Returns:
            dict: Scheduled recording information or None on error
        """
        try:
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
                return None
            
            recording_info = {
                "satellite": pass_data["satellite"],
                "start_time": start_time,
                "end_time": end_time,
                "duration": total_duration,
                "max_elevation": pass_data["max_elevation"]
            }
            
            return recording_info
        except Exception as e:
            logger.error(f"Error scheduling recording: {e}")
            return None
    
    def execute_recording(self, recording_info):
        """
        Execute a scheduled recording
        
        Args:
            recording_info (dict): Recording information
            
        Returns:
            str: Recorded file path, or None on error
        """
        try:
            # Calculate time until start
            now = datetime.datetime.now()
            seconds_until_start = (recording_info["start_time"] - now).total_seconds()
            
            # Wait until it's time to start (with a 30 second buffer for setup)
            if seconds_until_start > 30:
                logger.info(f"Waiting {seconds_until_start-30:.1f} seconds until setup for pass")
                time.sleep(seconds_until_start - 30)
            
            # Connect to GQRX
            if not self.connect_to_gqrx():
                logger.error("Failed to connect to GQRX for recording")
                return None
            
            # Configure GQRX for the satellite
            satellite_name = recording_info["satellite"]
            if not self.controller.configure_for_satellite(satellite_name):
                logger.error(f"Failed to configure GQRX for {satellite_name}")
                self.disconnect_from_gqrx()
                return None
            
            # Wait until the actual start time
            now = datetime.datetime.now()
            seconds_until_start = (recording_info["start_time"] - now).total_seconds()
            if seconds_until_start > 0:
                logger.info(f"Waiting final {seconds_until_start:.1f} seconds until recording starts")
                time.sleep(seconds_until_start)
            
            # Start recording
            logger.info(f"Starting recording for {satellite_name}")
            self.current_recording = recording_info
            
            # Record the satellite
            recorded_file = self.controller.record_satellite(
                satellite_name, 
                recording_info["duration"]
            )
            
            self.current_recording = None
            self.disconnect_from_gqrx()
            
            if recorded_file:
                logger.info(f"Successfully recorded {satellite_name} to {recorded_file}")
                # Here you could add code to post-process the recording
                return recorded_file
            else:
                logger.error(f"Failed to record {satellite_name}")
                return None
        
        except Exception as e:
            logger.error(f"Error executing recording: {e}")
            self.current_recording = None
            self.disconnect_from_gqrx()
            return None
    
    def start_recording_in_thread(self, recording_info):
        """
        Start a recording in a separate thread
        
        Args:
            recording_info (dict): Recording information
            
        Returns:
            bool: True if thread started, False otherwise
        """
        if self.recording_thread and self.recording_thread.is_alive():
            logger.warning("Recording already in progress")
            return False
        
        logger.info(f"Starting recording thread for {recording_info['satellite']}")
        self.recording_thread = threading.Thread(
            target=self.execute_recording,
            args=(recording_info,)
        )
        self.recording_thread.daemon = True
        self.recording_thread.start()
        return True
    
    def monitor_passes(self, check_interval=300):
        """
        Monitor for upcoming passes and schedule recordings
        
        Args:
            check_interval (int): How often to check for passes, in seconds
        """
        logger.info(f"Starting pass monitoring with {check_interval}s interval")
        self.running = True
        
        try:
            while self.running:
                # Update pass predictions
                predictor.run_pass_prediction()
                
                # Get configuration
                conf = config.read_config()
                recording_margin = float(conf.get('recording_margin', 1))
                
                # Get next pass
                next_pass = predictor.get_next_pass_from_file()
                
                if not next_pass:
                    logger.info("No upcoming passes found")
                    logger.info(f"Sleeping for {check_interval} seconds before checking again")
                    time.sleep(check_interval)
                    continue
                
                logger.info(f"Next pass: {next_pass['satellite']} at {next_pass['aos_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"  Max elevation: {next_pass['max_elevation']:.1f}°")
                logger.info(f"  Duration: {next_pass['duration']:.1f} minutes")
                
                # Calculate time until next pass
                now = datetime.datetime.now()
                time_until_pass = (next_pass['aos_time'] - now).total_seconds() / 60  # minutes
                
                # If the pass is more than check_interval away, sleep and check again
                if time_until_pass > (check_interval / 60):
                    logger.info(f"Pass is {time_until_pass:.1f} minutes away")
                    logger.info(f"Sleeping for {check_interval} seconds before checking again")
                    time.sleep(check_interval)
                    continue
                
                # If the pass is coming up soon, schedule it
                recording_info = self.schedule_recording(next_pass, recording_margin)
                
                if recording_info:
                    self.start_recording_in_thread(recording_info)
                
                # Sleep for a minute before checking again
                time.sleep(60)
        
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
        except Exception as e:
            logger.error(f"Error in pass monitoring: {e}")
        finally:
            self.running = False
    
    def start_monitoring(self, check_interval=300):
        """
        Start monitoring for passes in a separate thread
        
        Args:
            check_interval (int): How often to check for passes, in seconds
            
        Returns:
            bool: True if monitoring started, False otherwise
        """
        if self.running:
            logger.warning("Monitoring already running")
            return False
        
        logger.info("Starting pass monitoring thread")
        monitor_thread = threading.Thread(
            target=self.monitor_passes,
            args=(check_interval,)
        )
        monitor_thread.daemon = True
        monitor_thread.start()
        return True
    
    def stop_monitoring(self):
        """Stop monitoring for passes"""
        self.running = False
        logger.info("Stopping pass monitoring")
    
    def manual_schedule_satellite(self, satellite_name, start_time_str, duration_minutes):
        """
        Manually schedule a satellite recording
        
        Args:
            satellite_name (str): Satellite name
            start_time_str (str): Start time in YYYY-MM-DD HH:MM:SS format
            duration_minutes (float): Recording duration in minutes
            
        Returns:
            bool: True if scheduled successfully, False otherwise
        """
        if satellite_name not in definitions.get_satellites_list():
            logger.error(f"Unknown satellite: {satellite_name}")
            return False
        
        try:
            # Parse the start time
            start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.error(f"Invalid time format: {start_time_str}")
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
        recording_info = self.schedule_recording(pass_data, 0)  # No margin for manual scheduling
        
        if recording_info:
            return self.start_recording_in_thread(recording_info)
        
        return False