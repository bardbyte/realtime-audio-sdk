#!/bin/bash

echo "Checking Python version..."
python3 --version || { echo " Python3 is required"; exit 1; }

echo "Creating virtual environment..."
python3 -m venv venv

echo " Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Installing realtime-audio-sdk in editable mode..."
pip install -e .

echo "SDK setup complete. Virtual environment is activated."
