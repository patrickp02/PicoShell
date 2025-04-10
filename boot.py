import utils
import network
import time
from telnet import utelnetserver

wlan = network.WLAN(network.STA_IF)
time.sleep(3)
try:
    with open('config.txt') as f:
        ssid, password = utils.read_wifi_config('config.txt')
        utils.auto_connect(ssid, password)
        print('Initializing...')

        time.sleep(10)
        
        if wlan.isconnected():
            print("Connected! Starting telnet...")
            utelnetserver.start()
            
        else:
            print("Still trying to connect")
except OSError:
    print("config.txt not found. Skipping Wi-Fi connection.")

try: 
    print("Starting PicoShell...")
    time.sleep(2)
    import main
except Exception as e:
    print("Error:",e)
