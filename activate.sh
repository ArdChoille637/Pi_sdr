#!/bin/bash
# Script to activate the virtual environment and set up the environment

# Path to your virtual environment
VENV_PATH="$(pwd)/.venv"

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Print confirmation
echo "Virtual environment activated!"
echo "Python path: $(which python)"
echo "Python version: $(python --version)"

# Optional: Set any environment variables needed
# export CUSTOM_VARIABLE=value

# Optional: Change to a specific working directory
# cd specific_directory

echo "Ready to work on satellite tracking project!"
