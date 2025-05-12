# satellite_tracker/common/logging.py
#!/usr/bin/env python3
# Common logging setup

import logging
from pathlib import Path

def setup_logging(name, log_file=None, level=logging.INFO):
    """
    Configure logging for a module
    
    Args:
        name (str): Logger name
        log_file (str): Optional log file path
        level (int): Logging level
        
    Returns:
        logging.Logger: Configured logger
    """
    # Define default log file if not provided
    if log_file is None:
        log_file = str(Path.home() / f"{name.lower()}.log")
    
    # Configure handlers
    handlers = [logging.StreamHandler()]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True
    )
    
    return logging.getLogger(name)