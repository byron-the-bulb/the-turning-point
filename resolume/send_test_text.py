#!/usr/bin/env python3

"""
Simple script to send test OSC messages to Resolume:
1. Update text overlay using group addressing
2. Trigger videos using layer addressing
"""

from pythonosc import udp_client
import argparse
import time

def send_test_messages(ip_address, port=7000, text=None, full_test=False):
    try:
        # Create OSC client
        print(f"Creating OSC client for {ip_address}:{port}")
        client = udp_client.SimpleUDPClient(ip_address, port)
        
        # 1. Test the text overlay using GROUP addressing
        print(f"\n=== Testing text overlay (using GROUP addressing) ===")
        
        # GROUP addressing for text overlays
        text_address = "/composition/groups/3/video/effects/textblock/effect/text/params/lines"
        
        # Use provided text or default
        if text is None:
            text = "Testing text overlay (GROUP addressing)"
        
        print(f"Sending OSC message:")
        print(f"  Address: {text_address}")
        print(f"  Value: '{text}'")
        
        # Send the text message
        client.send_message(text_address, text)
        print("OSC text message sent successfully!")
        
        # 2. Test video in layer 1 using LAYER addressing
        time.sleep(1)  # small delay between commands
        print(f"\n=== Testing Layer 1 video (using LAYER addressing) ===")
        
        # LAYER addressing for video triggering
        video_address_1 = "/composition/layers/1/clips/2/connect"
        print(f"Sending OSC message to trigger video in Layer 1:")
        print(f"  Address: {video_address_1}")
        print(f"  Value: 1")
        
        # Send the video trigger message
        client.send_message(video_address_1, 1)
        print("OSC video trigger sent to Layer 1!")
        
        if full_test:
            # 3. Test video in layer 2 using LAYER addressing
            time.sleep(3)  # wait to see the first video
            print(f"\n=== Testing Layer 2 video (using LAYER addressing) ===")
            
            # LAYER addressing for video triggering
            video_address_2 = "/composition/layers/2/clips/2/connect"
            print(f"Sending OSC message to trigger video in Layer 2:")
            print(f"  Address: {video_address_2}")
            print(f"  Value: 1")
            
            # Send the video trigger message for layer 2
            client.send_message(video_address_2, 1)
            
            # Set text in layer 2 using GROUP addressing
            print(f"\n=== Testing Layer 2 text overlay (using SQUARE addressing) ===")
            text_address_2 = "/composition/square/video/effects/textblock/effect/text/params/lines"
            client.send_message(text_address_2, "LAYER 2 TEXT (SQUARE addressing)")
            print("Text overlay set for Layer 2!")
            
            # 4. Test video in layer 3 using LAYER addressing
            time.sleep(3)  # wait to see the second video
            print(f"\n=== Testing Layer 3 video (using LAYER addressing) ===")
            
            # LAYER addressing for video triggering
            video_address_3 = "/composition/layers/3/clips/2/connect"
            print(f"Sending OSC message to trigger video in Layer 3:")
            print(f"  Address: {video_address_3}")
            print(f"  Value: 1")
            
            # Send the video trigger message for layer 3
            client.send_message(video_address_3, 1)
            
            # Set text overlay for layer 3 using GROUP addressing
            print(f"\n=== Testing Layer 3 text overlay (using GROUP addressing) ===")
            client.send_message(text_address, "LAYER 3 TEXT (GROUP addressing)")
            print("Text overlay set for Layer 3!")
            
            # 5. Test stopping layers
            if input("\nTest stopping layers? (y/n): ").lower() == 'y':
                print("\n=== Testing layer clearing by triggering empty column 1 ===")
                
                # Clear layer 3 by triggering empty column 1
                clear_address_3 = "/composition/layers/3/clips/1/connect"
                client.send_message(clear_address_3, 1)
                print("Cleared layer 3 by triggering empty column 1")
                
                time.sleep(1)
                
                # Clear layer 2 by triggering empty column 1
                clear_address_2 = "/composition/layers/2/clips/1/connect"
                client.send_message(clear_address_2, 1)
                print("Cleared layer 2 by triggering empty column 1")
                
                time.sleep(1)
                
                # For layer 1, trigger splash screen (also in column 1)
                clear_address_1 = "/composition/layers/1/clips/1/connect"
                client.send_message(clear_address_1, 1)
                print("Triggered splash screen in layer 1 (column 1)")
        
        return True
    except Exception as e:
        print(f"Error sending OSC messages: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send test OSC messages to Resolume")
    parser.add_argument("--ip", required=True, help="IP address of the Resolume computer")
    parser.add_argument("--port", type=int, default=7000, help="OSC port (default: 7000)")
    parser.add_argument("--text", help="Text to send (default: 'Testing text overlay (GROUP addressing)')")
    parser.add_argument("--full", action="store_true", help="Run a full test of all layers")
    
    args = parser.parse_args()
    send_test_messages(args.ip, args.port, args.text, args.full) 