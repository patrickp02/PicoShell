import network
import time
import os
import socket
import urequests
import gc
from telnet import utelnetserver
import ssl
import machine
from machine import Pin


adc = machine.ADC(29)
conversion_factor = 3.3 / 4095
wlan = network.WLAN(network.STA_IF)
led = Pin("LED", Pin.OUT) 
def auto_connect(ssid,password):
    wlan.active(True)
    wlan.connect(ssid,password)

def read_wifi_config(filename):
    config = {}
    with open(filename, 'r') as file:
        for line in file:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                config[key.strip()] = value.strip()
    return config['SSID'], config['PASSWORD']
def overclock(clock):
    decide = input("WARNING! Overclocking can cause instability. Would you like to proceed?[Y/N]: ")
    if decide.lower() == 'y':
        if clock > 40 and clock < 260:
            machine.freq(clock * 1_000_000)
            print("Clock speed set to " + str(clock))
        else:
            if clock < 40:
                print("Clock speed is set too low!")
            else:
                print("Clock speed is set too high!")
    
def get_storage():
    stats = os.statvfs("/")
    block_size = stats[0]
    total_blocks = stats[2]
    free_blocks = stats[3]

    total = (block_size * total_blocks) // 1024
    free = (block_size * free_blocks) // 1024
    used = total - free

    print("Storage:")
    print(f"  Total: {total} KB")
    print(f"  Used:  {used} KB")
    print(f"  Free:  {free} KB")

def getWifi():
    global wlan
    wlan.active(True)

    if wlan.isconnected():
        essid = wlan.config('essid')  
        print("Connected to: ",essid) 
        state = input(f"Would you like to disconnect from {essid}? [Y/N]: ")
        
        if state == 'Y' or state == 'y':
            wlan.disconnect()
            wlan.active(False)     # Hard disables the Wi-Fi chip
            time.sleep(1)          # Give it a sec to settle
            wlan.active(True)  
            time.sleep(1)
            print("Disconnected!")
            return
        
        else:
            return

    while not wlan.isconnected():
        networks = wlan.scan()  
        print("Available Networks:")
        for network in networks:
            print(f"SSID: {network[0]} Signal Strength: {network[3]}")

        essid = input("Enter the network name you would like to use: ")
        password = input("Enter the password for the network: ")

        if isinstance(password, str):
            wlan.active(True)   
            wlan.connect(essid, password)  # Attempt to connect
        else:
            print("Password must be a string!")

        # Wait until the device is connected
        start_time = time.ticks_ms()  # Get the current time
        while not wlan.isconnected():
            print("Connecting...", end="")  # Print without a new line
            time.sleep(1)  # Wait for 1 second
            print(".", end="")  # Add a dot every second
            timed = time.ticks_diff(time.ticks_ms(), start_time)  # Check elapsed time
            if timed > 100000:  # Timeout after 100 seconds
                print("Network error!")
                break

    # Once connected
    if wlan.isconnected():
        print("You're all connected!")
        print(wlan.ifconfig())  # Print the network configuration 

def cd(dir):
    try:
        os.chdir(dir)
    except OSError:
        print("Path does not exist!")
        print("Error: " + str(OSError))

def ls():
    
    print(" ".join(os.listdir()))
def run(script_name):
    try:
        # Check if the file exists
        if script_name in os.listdir():
            with open(script_name, "r") as file:
                script_content = file.read()
                code_obj = compile(script_content, script_name,'exec')
                exec(code_obj, {
                    "__name__": "__main__",
                    "input": input,
                    "print": print,
                })
                del code_obj
            
        else:
            print(f"Error: {script_name} not found.")
    except Exception as e:
            print(f"Error running {script_name}: {e}")

def if_config():
    print(" ".join(wlan.ifconfig()))
    if wlan.isconnected():
        print("Connected:", wlan.ifconfig())
    else:
        print("Not connected (IP config stale)")
    
def read(fName):
    try:
        with open (fName) as f:
            print(f.read())
        
    except Exception as e:
        print("Error: ",e)
    
    
def ping(host, count=4, timeout=1):
    try:
        # Resolve host to get address info
        addr_info = socket.getaddrinfo(host, 80)
        addr = addr_info[0][-1][0]  # Extract the IP address from the tuple
        print(f"Pinging {host} ({addr}) with {count} packets:")

        for i in range(count):
            start_time = time.ticks_ms()  

            
            s = socket.socket()
            s.settimeout(timeout)

            try:
                s.connect((addr, 80))
                end_time = time.ticks_ms()  
                elapsed_time = time.ticks_diff(end_time, start_time) 
                print(f"Reply from {addr}: time={elapsed_time}ms")
            except OSError:  
                print(f"Request timed out for {host}")

            s.close()
            time.sleep(1)

    except Exception as e:
        print(f"Error: {e}")

def curl(url):
    try:   
        response = urequests.get(url)
        print(response.text)
        response.close()
    except Exception as e:
        print("Error: " , e)
    finally:
        gc.collect()

def telnet_launch(tel):
    if tel == 'launch':
        utelnetserver.start()
    if tel == 'stop':
        utelnetserver.stop()
        gc.collect()

def download_file(url, filename):
    _, _, host, path = url.split('/', 3)
    addr = socket.getaddrinfo(host, 443)[0][-1]

    s = socket.socket()
    s.connect(addr)
    s = ssl.wrap_socket(s, server_hostname=host)

    req = f"GET /{path} HTTP/1.0\r\nHost: {host}\r\n\r\n"
    s.write(req.encode())

    header_passed = False
    with open(filename, 'w') as f:
        while True:
            data = s.read(1024)
            if data:
                content = data.decode()
                if not header_passed:
                    if "\r\n\r\n" in content:
                        content = content.split("\r\n\r\n", 1)[1]
                        header_passed = True
                    else:
                        continue
                f.write(content)
            else:
                break
    s.close()

def scan():
    try:
        networks = wlan.scan()  
        print("Available Networks:")
        for network in networks:
            print(f"SSID: {network[0]} Signal Strength: {network[3]}")
    except Exception as e:
        print("Error: ", e)
        
def scan_ports(ip, start=1, end=1024):
    print(f"Scanning {ip} from port {start} to {end}...")
    found = False
    for port in range(start, end + 1):
        try:
            s = socket.socket()
            s.settimeout(0.2)  
            s.connect((ip, port))
            print(f"Port {port}: OPEN")
            found = True
            s.close()
        except:
            pass
    if not found:
        print("No open ports detected.")
        
def blink(times=3, delay=0.2):
    for _ in range(times):
        led.toggle()
        time.sleep(delay)
        led.toggle()
        time.sleep(delay)

def read_temp():
    try:
        raw = adc.read_u16() * conversion_factor
        temp = (27 - (raw - 0.706) / 0.001721) / 10  
        return temp
    except Exception as e:
        print("ERROR:",e)

def mkdir(dir):os.mkdir(dir)

def rmdir(dir):os.rmdir(dir)

def rm(file):os.remove(file)

def sysinfo():print(" ".join(os.uname()))




    
    
        
    

    
    
    

