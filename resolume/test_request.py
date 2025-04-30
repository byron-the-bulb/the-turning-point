import requests
import json

# API endpoint
url = "http://localhost:8000/trigger_video"

# Test data
test_data = {
    "name": "Sabiabin    ",
    "challenge_point": "Sabin",
    "envi_state": "Leadership",
    "emotions": {
        "Admiration": 0.5,
        "Interest": 0.75,
        "Satisfaction": 0.5,
        "Sympathy": 1.0
    }
}

def send_test_request():
    try:
        # Send POST request
        response = requests.post(url, json=test_data)
        
        # Print response
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Sending test request...")
    print("Request data:")
    print(json.dumps(test_data, indent=2))
    print("\nSending request...")
    send_test_request() 