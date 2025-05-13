import unittest
import requests
import time
import json
import numpy as np
from unittest.mock import patch, MagicMock
import threading
import sys
import os

# Set up the mock before importing muse_api
# This ensures the mocks are in place before any BoardShim is initialized
from unittest.mock import patch, MagicMock

# Mock classes for BrainFlow
mock_board_ids = MagicMock()
mock_board_ids.MUSE_S_BOARD = 38
mock_board_shim = MagicMock()
mock_board_shim.get_sampling_rate = MagicMock(return_value=256)
mock_board_shim.get_eeg_channels = MagicMock(return_value=[0, 1, 2, 3])
mock_filter_types = MagicMock()
mock_filter_types.BUTTERWORTH = MagicMock(value=1)
mock_data_filter = MagicMock()

# Apply the mocks
sys.modules['brainflow.board_shim'] = MagicMock()
sys.modules['brainflow.board_shim'].BoardShim = mock_board_shim
sys.modules['brainflow.board_shim'].BrainFlowInputParams = MagicMock
sys.modules['brainflow.board_shim'].BoardIds = mock_board_ids
sys.modules['brainflow.data_filter'] = MagicMock()
sys.modules['brainflow.data_filter'].DataFilter = mock_data_filter
sys.modules['brainflow.data_filter'].FilterTypes = mock_filter_types

# Define API base URL
API_BASE_URL = "http://localhost:8000"

class MockMuseServer:
    """Class to start/stop the Muse API server with mocks in place"""
    
    def __init__(self):
        self.server_process = None
    
    def start(self):
        """Start the Muse API server in a separate thread"""
        # Import here after mocks are set up
        import muse_api
        
        # Create a thread to run the server
        self.server_thread = threading.Thread(
            target=lambda: muse_api.uvicorn.run(muse_api.app, host="0.0.0.0", port=8000),
            daemon=True
        )
        self.server_thread.start()
        
        # Wait for server to start
        time.sleep(2)
        print("Mock Muse API server started")
    
    def stop(self):
        """Clean up resources"""
        # The server thread is daemon, so it will be terminated when the main thread exits
        print("Mock Muse API server stopped")


class TestMuseAPI(unittest.TestCase):
    """Test the Muse API endpoints with mocked BrainFlow components"""
    
    @classmethod
    def setUpClass(cls):
        """Set up the mock server before all tests"""
        # Configure mock board behavior
        mock_board_instance = MagicMock()
        mock_board_instance.is_prepared = MagicMock(return_value=True)
        mock_board_instance.prepare_session = MagicMock()
        mock_board_instance.start_stream = MagicMock()
        mock_board_instance.stop_stream = MagicMock()
        mock_board_instance.release_session = MagicMock()
        
        # Generate synthetic EEG data for testing
        def fake_get_current_board_data(num_samples):
            channels = 4
            # Create a 2D array with random data to simulate EEG data
            # Shape: [channels, samples]
            return np.random.rand(channels, num_samples) * 100  # Scale to realistic μV values
        
        mock_board_instance.get_current_board_data = fake_get_current_board_data
        
        # Set the mock to be returned when BoardShim is instantiated
        mock_board_shim.side_effect = [mock_board_instance]
        
        # Start the mock server
        cls.server = MockMuseServer()
        cls.server.start()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are done"""
        cls.server.stop()
    
    def test_1_root_endpoint(self):
        """Test the root endpoint"""
        response = requests.get(f"{API_BASE_URL}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Muse EEG API is running")
        print("✅ Root endpoint test passed")
    
    def test_2_status_endpoint(self):
        """Test the status endpoint (is headband connected)"""
        response = requests.get(f"{API_BASE_URL}/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["connected"])
        print("✅ Status endpoint test passed")
    
    def test_3_start_recording(self):
        """Test starting the recording"""
        response = requests.post(f"{API_BASE_URL}/start")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Recording started")
        print("✅ Start recording endpoint test passed")
    
    def test_4_stop_recording(self):
        """Test stopping the recording and retrieving distilled summary"""
        # First make sure recording is started
        requests.post(f"{API_BASE_URL}/start")
        
        # Wait a bit to collect some data
        time.sleep(1)
        
        # Stop recording
        response = requests.post(f"{API_BASE_URL}/stop")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Recording stopped")
        self.assertGreater(data["samples"], 0)
        self.assertIn("distilled_summary", data)
        
        # Print detailed info about the returned data
        print(f"✅ Stop recording endpoint test passed")
        print(f"✅ Received {data['samples']} samples of EEG data")
        print(f"✅ Received distilled summary")
        
        # Check if the distilled summary contains expected information
        summary = data.get("distilled_summary", "")
        self.assertTrue(isinstance(summary, str))
        
        # The summary should include information about brain wave bands
        for band in ["Alpha", "Beta", "Theta", "Gamma"]:
            self.assertIn(band, summary, f"Summary should include information about {band} waves")
            
        print(f"✅ Distilled summary contains all expected brain wave information")
        
    def run_all_tests(self):
        """Run all tests in sequence"""
        self.test_1_root_endpoint()
        self.test_2_status_endpoint()
        self.test_3_start_recording()
        self.test_4_stop_recording()
        print("✅ All tests passed successfully!")


if __name__ == "__main__":
    try:
        # Either run as a test suite
        if len(sys.argv) > 1 and sys.argv[1] == "--unittest":
            unittest.main(argv=['first-arg-is-ignored'])
        # Or run tests sequentially with prettier output
        else:
            tester = TestMuseAPI()
            tester.setUpClass()
            try:
                tester.run_all_tests()
            finally:
                tester.tearDownClass()
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
