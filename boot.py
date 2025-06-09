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



try:
    import main
except Exception as e:
    print("Main failed:", e)
