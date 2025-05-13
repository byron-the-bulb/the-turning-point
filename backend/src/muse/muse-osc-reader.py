from datetime import datetime
from pythonosc import dispatcher
from pythonosc import osc_server

ip = "192.168.1.13"  # Try localhost first; change to your local IP if needed
port = 8000  # Adjust based on Protokol or Muse app settings

def eeg_handler(address: str, *args):
    dateTimeObj = datetime.now()
    printStr = dateTimeObj.strftime("%Y-%m-%d %H:%M:%S.%f")
    for arg in args:
        printStr += "," + str(arg)
    print(printStr)

def debug_handler(address: str, *args):
    print(f"Received OSC message: {address}, Args: {args}")

if __name__ == "__main__":
    dispatcher = dispatcher.Dispatcher()
    dispatcher.map("/muse/eeg", eeg_handler)  # Specific handler for EEG
    dispatcher.map("/*", debug_handler)  # Catch all OSC messages for debugging

    server = osc_server.ThreadingOSCUDPServer((ip, port), dispatcher)
    print(f"Listening on UDP: {ip}:{port}")
    server.serve_forever()