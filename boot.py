import time
import sys
import os

def wait_for_usb(timeout=3000):
    start = time.ticks_ms()
    while not sys.stdin in (None, sys.stderr):  # Try detecting USB via REPL bound
        try:
            try:
                os.dupterm(sys.stdin)
            except Exception as e:
                print("USB REPL bind error (ignored):", e)
              # Bind USB REPL
            print("USB ready.")
            return True
        except Exception:
            pass
        if time.ticks_diff(time.ticks_ms(), start) > timeout:
            print("USB timeout. Continuing anyway.")
            return False
        time.sleep(0.1)

wait_for_usb()

print("Initializing...")

try:
    import utils
    import network
    from telnet import utelnetserver

    time.sleep(2)

    ssid, password = utils.read_wifi_config("config.txt")
    utils.auto_connect(ssid, password)
    time.sleep(5)

    if network.WLAN(network.STA_IF).isconnected():
        print("Wi-Fi connected. Starting Telnet.")
        utelnetserver.start()
    else:
        print("Wi-Fi not connected.")

except Exception as e:
    print("Boot error:", e)

# Defer all CLI/interactive logic to main.py
try:
    import main
except Exception as e:
    print("Main failed:", e)
