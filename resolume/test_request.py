import requests
import json
import time

# API endpoint
url = "http://localhost:8000/trigger_video"

# Test data - 6 different burners with EnviStates matching the metadata
test_data_list = [
    {
        "name": "Thomas",
        "challenge_point": "Hungry",
        "envi_state": "Leadership",
        "emotions": {
            "Admiration": 0.5,
            "Interest": 0.75,
            "Satisfaction": 0.5,
            "Sympathy": 1.0
        }
    },
    {
        "name": "Sarah",
        "challenge_point": "Tired",
        "envi_state": "Relaxed",
        "emotions": {
            "Awe": 1.0,
            "Calmness": 0.75,
            "Interest": 0.5
        }
    },
    {
        "name": "Miguel",
        "challenge_point": "Lost",
        "envi_state": "Courageous",
        "emotions": {
            "Awe": 0.5,
            "Excitement": 0.75,
            "Surprise": 1.0
        }
    },
    {
        "name": "Lila",
        "challenge_point": "Confused",
        "envi_state": "Enthusiastic",
        "emotions": {
            "Aesth_appreciation": 0.75,
            "Awe": 0.75,
            "Interest": 0.25,
            "Relief": 0.5
        }
    },
    {
        "name": "Jason",
        "challenge_point": "Overwhelmed",
        "envi_state": "Spontaneous",
        "emotions": {
            "Admiration": 0.25,
            "Amusement": 0.5,
            "Interest": 0.75,
            "Joy": 1.0
        }
    },
    {
        "name": "Emma",
        "challenge_point": "Disconnected",
        "envi_state": "trusting others",
        "emotions": {
            "Admiration": 1.0,
            "Aesth_appreciation": 0.75,
            "Awe": 0.5,
            "Excitement": 0.25
        }
    }
]

def send_test_request(test_data):
    try:
        # Send POST request
        response = requests.post(url, json=test_data)
        
        # Print response
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        return True
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure the server is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def send_all_test_requests():
    """Send all test requests with a delay between each"""
    success_count = 0
    
    for i, test_data in enumerate(test_data_list):
        print(f"\n=== Sending test request {i+1} of {len(test_data_list)} ===")
        print("Request data:")
        print(json.dumps(test_data, indent=2))
        print("\nSending request...")
        
        if send_test_request(test_data):
            success_count += 1
        
        # Wait a bit between requests to avoid overwhelming the server
        if i < len(test_data_list) - 1:
            print("\nWaiting 2 seconds before next request...")
            time.sleep(2)
    
    print(f"\n=== Test Summary ===")
    print(f"Successfully sent {success_count} out of {len(test_data_list)} requests")

def send_single_test_request(index=0):
    """Send just one test request by index"""
    if index < 0 or index >= len(test_data_list):
        print(f"Error: Index {index} is out of range (0-{len(test_data_list)-1})")
        return
        
    test_data = test_data_list[index]
    print(f"Sending test request for: {test_data['name']}")
    print("Request data:")
    print(json.dumps(test_data, indent=2))
    print("\nSending request...")
    send_test_request(test_data)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Send test requests to the Turning Point API")
    parser.add_argument("-s", "--single", action="store_true", help="Send only a single test request")
    parser.add_argument("-i", "--index", type=int, default=0, help="Index of single test request to send (0-5)")
    
    args = parser.parse_args()
    
    if args.single:
        # Send just one request
        send_single_test_request(args.index)
    else:
        # Default behavior: send all requests
        send_all_test_requests() 