# Resolume OSC Controller

A Python application that controls Resolume Arena via OSC (Open Sound Control) to trigger videos based on emotional states and environmental conditions.

## Features

- FastAPI endpoint for receiving video trigger requests
- OSC communication with Resolume Arena
- Text overlay support
- Emotional state matching algorithm
- Video metadata management

## Setup

1. Install Python 3.8 or higher
2. Create a virtual environment:
   ```
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows: `.\venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Make sure Resolume Arena is running
2. Enable OSC in Resolume Arena:
   - Go to File > Preferences > OSC
   - Enable OSC
   - Set port to 7000
   - Check "Allow OSC from localhost"

## Usage

1. Start the server:
   ```
   python resolume_control.py
   ```
2. Send POST requests to `http://localhost:8000/trigger_video` with JSON body:
   ```json
   {
       "name": "user_name",
       "challenge_point": "point_name",
       "envi_state": "state_name",
       "emotions": {
           "emotion1": 0.5,
           "emotion2": 0.75
       }
   }
   ```

## Project Structure

- `resolume_control.py`: Main application file
- `video_metadata.json`: Video metadata and emotional mappings
- `requirements.txt`: Python dependencies
- `test_request.py`: Test script for sending requests

## License

MIT License 