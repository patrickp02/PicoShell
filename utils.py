import gc
import os
import socket
import ssl
import time

import machine
import network
import urequests
from machine import Pin
from telnet import utelnetserver


wlan = network.WLAN(network.STA_IF)
led = Pin("LED", Pin.OUT)

adc = machine.ADC(29)
conversion_factor = 3.3 / 4095

UPDATE_BASE = "https://raw.githubusercontent.com/patrickp02/PicoShell/main"
UPDATE_FILES = (
    "main.py",
    "utils.py",
    "docs/help.txt",
    "version.txt",
)


# ---------- Wi-Fi ----------

def auto_connect(ssid, password):
    wlan.active(True)

    if wlan.isconnected():
        return True

    wlan.connect(ssid, password)
    return True


def read_wifi_config(filename):
    config = {}

    with open(filename, "r") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()

    if "SSID" not in config:
        raise ValueError("SSID missing from config")
    if "PASSWORD" not in config:
        raise ValueError("PASSWORD missing from config")

    return config["SSID"], config["PASSWORD"]


def getWifi():
    wlan.active(True)

    if wlan.isconnected():
        essid = wlan.config("essid")
        print("Connected to:", essid)

        state = input("Would you like to disconnect from {}? [Y/N]: ".format(essid))
        if state.lower() == "y":
            wlan.disconnect()
            wlan.active(False)
            time.sleep(1)
            wlan.active(True)
            time.sleep(1)
            print("Disconnected!")
        return

    try:
        networks = wlan.scan()
    except Exception as e:
        print("Wi-Fi scan failed:", e)
        return

    print("Available Networks:")
    for item in networks:
        try:
            ssid = item[0].decode() if isinstance(item[0], bytes) else item[0]
        except Exception:
            ssid = item[0]

        print("SSID: {} Signal Strength: {}".format(ssid, item[3]))

    essid = input("Enter the network name you would like to use: ")
    password = input("Enter the password for the network: ")

    wlan.active(True)
    wlan.connect(essid, password)

    start_time = time.ticks_ms()
    timeout_ms = 100000

    while not wlan.isconnected():
        print("Connecting...", end="")
        time.sleep(1)
        print(".", end="")

        if time.ticks_diff(time.ticks_ms(), start_time) > timeout_ms:
            print("\nNetwork error!")
            return

    print("\nYou're all connected!")
    print(wlan.ifconfig())


def if_config():
    if wlan.isconnected():
        print("Connected:", wlan.ifconfig())
    else:
        print("Not connected.")
        print("IP config:", wlan.ifconfig())


def scan():
    try:
        networks = wlan.scan()
        print("Available Networks:")

        for item in networks:
            try:
                ssid = item[0].decode() if isinstance(item[0], bytes) else item[0]
            except Exception:
                ssid = item[0]

            print("SSID: {} Signal Strength: {}".format(ssid, item[3]))

    except Exception as e:
        print("Error:", e)


# ---------- Filesystem ----------

def cd(path):
    try:
        os.chdir(path)
    except OSError as e:
        print("Path does not exist:", e)


def ls(path=None):
    try:
        items = os.listdir(path) if path else os.listdir()
        print(" ".join(items))
    except OSError as e:
        print("ls error:", e)


def mkdir(path):
    try:
        os.mkdir(path)
    except OSError as e:
        print("mkdir error:", e)


def rmdir(path):
    try:
        os.rmdir(path)
    except OSError as e:
        print("rmdir error:", e)


def rm(path):
    try:
        os.remove(path)
    except OSError as e:
        print("rm error:", e)


def read(filename):
    try:
        with open(filename, "r") as f:
            print(f.read())
    except Exception as e:
        print("Error:", e)


def cp(source, destination, chunk_size=1024):
    try:
        with open(source, "rb") as src:
            with open(destination, "wb") as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
        print("{} -> {}".format(source, destination))
    except Exception as e:
        print("cp error:", e)


def mv(source, destination):
    try:
        os.rename(source, destination)
        print("{} -> {}".format(source, destination))
    except Exception as e:
        print("mv error:", e)


def touch(filename):
    try:
        with open(filename, "a"):
            pass
    except Exception as e:
        print("touch error:", e)


def _is_dir(path):
    try:
        mode = os.stat(path)[0]
        return (mode & 0x4000) != 0
    except Exception:
        return False


def tree(path=".", max_depth=8):
    if max_depth < 0:
        print("Depth must be >= 0.")
        return

    def walk(current, prefix, depth):
        if depth > max_depth:
            return

        try:
            names = os.listdir(current)
        except OSError as e:
            print(prefix + "[error: {}]".format(e))
            return

        names.sort()

        for index, name in enumerate(names):
            last = index == len(names) - 1
            branch = "`-- " if last else "|-- "
            child = current.rstrip("/") + "/" + name if current != "/" else "/" + name

            print(prefix + branch + name)

            if _is_dir(child) and depth < max_depth:
                next_prefix = prefix + ("    " if last else "|   ")
                walk(child, next_prefix, depth + 1)

    print(path)
    walk(path, "", 0)


def write_text(filename, text, append=False):
    mode = "a" if append else "w"

    try:
        with open(filename, mode) as f:
            f.write(text)
            if append:
                f.write("\n")
        print("Wrote", filename)
    except Exception as e:
        print("write error:", e)


def run(script_name):
    try:
        with open(script_name, "r") as file:
            script_content = file.read()

        code_obj = compile(script_content, script_name, "exec")

        scope = {
            "__name__": "__main__",
            "input": input,
            "print": print,
        }

        exec(code_obj, scope)
        del code_obj
        del script_content
        gc.collect()

    except OSError:
        print("Error: {} not found.".format(script_name))
    except Exception as e:
        print("Error running {}: {}".format(script_name, e))


# ---------- Networking ----------

def ping(host, count=4, timeout=1):
    try:
        addr_info = socket.getaddrinfo(host, 80)
        addr = addr_info[0][-1][0]

        print("Pinging {} ({}) with {} packets:".format(host, addr, count))

        for _ in range(count):
            start_time = time.ticks_ms()
            s = socket.socket()
            s.settimeout(timeout)

            try:
                s.connect((addr, 80))
                elapsed = time.ticks_diff(time.ticks_ms(), start_time)
                print("Reply from {}: time={}ms".format(addr, elapsed))
            except OSError:
                print("Request timed out for", host)
            finally:
                try:
                    s.close()
                except Exception:
                    pass

            time.sleep(1)

    except Exception as e:
        print("Error:", e)


def curl(url):
    response = None

    try:
        response = urequests.get(url)
        print(response.text)
    except Exception as e:
        print("Error:", e)
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        gc.collect()


def fetch_text(url, max_bytes=4096):
    response = None

    try:
        response = urequests.get(url)

        if response.status_code != 200:
            raise OSError("HTTP {}".format(response.status_code))

        data = response.text

        if len(data) > max_bytes:
            raise ValueError("Response too large")

        return data
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        gc.collect()


def download_file(url, filename):
    if not url.startswith("https://"):
        raise ValueError("clone currently supports https:// URLs only")

    without_scheme = url[8:]
    slash = without_scheme.find("/")

    if slash == -1:
        host = without_scheme
        path = "/"
    else:
        host = without_scheme[:slash]
        path = without_scheme[slash:]

    addr = socket.getaddrinfo(host, 443)[0][-1]
    raw_sock = socket.socket()
    sock = None

    try:
        raw_sock.connect(addr)
        sock = ssl.wrap_socket(raw_sock, server_hostname=host)

        request = (
            "GET {} HTTP/1.0\r\n"
            "Host: {}\r\n"
            "User-Agent: PicoShell\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(path, host)

        sock.write(request.encode())

        header_buffer = b""

        while b"\r\n\r\n" not in header_buffer:
            data = sock.read(256)

            if not data:
                raise OSError("Connection closed before HTTP headers completed")

            header_buffer += data

            if len(header_buffer) > 8192:
                raise OSError("HTTP headers too large")

        headers, body_start = header_buffer.split(b"\r\n\r\n", 1)

        status_line = headers.split(b"\r\n", 1)[0]
        if b" 200 " not in status_line:
            raise OSError("HTTP request failed: {}".format(status_line))

        with open(filename, "wb") as f:
            if body_start:
                f.write(body_start)

            while True:
                data = sock.read(1024)
                if not data:
                    break
                f.write(data)

    finally:
        try:
            if sock is not None:
                sock.close()
            else:
                raw_sock.close()
        except Exception:
            pass

        gc.collect()


def scan_ports(ip, start=1, end=1024):
    if start < 1 or end > 65535 or start > end:
        print("Invalid port range.")
        return

    print("Scanning {} from port {} to {}...".format(ip, start, end))
    found = False

    for port in range(start, end + 1):
        s = socket.socket()
        s.settimeout(0.2)

        try:
            s.connect((ip, port))
            print("Port {}: OPEN".format(port))
            found = True
        except OSError:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass

    if not found:
        print("No open ports detected.")


def telnet_launch(action):
    if action == "launch":
        utelnetserver.start()
    elif action == "stop":
        utelnetserver.stop()
        gc.collect()
    else:
        print("Usage: telnet <launch|stop>")


# ---------- GPIO / I2C ----------

def _validate_gpio(pin):
    if pin < 0 or pin > 29:
        raise ValueError("GPIO must be between 0 and 29")


def gpio_mode(pin, mode):
    _validate_gpio(pin)

    if mode == "in":
        Pin(pin, Pin.IN)
    elif mode == "out":
        Pin(pin, Pin.OUT)
    elif mode == "pullup":
        Pin(pin, Pin.IN, Pin.PULL_UP)
    elif mode == "pulldown":
        Pin(pin, Pin.IN, Pin.PULL_DOWN)
    else:
        print("Mode must be in, out, pullup, or pulldown.")
        return

    print("GPIO {} mode set to {}".format(pin, mode))


def gpio_read(pin):
    _validate_gpio(pin)
    p = Pin(pin, Pin.IN)
    return p.value()


def gpio_write(pin, value):
    _validate_gpio(pin)

    if value not in (0, 1):
        print("GPIO value must be 0 or 1.")
        return

    p = Pin(pin, Pin.OUT)
    p.value(value)
    print("GPIO {} = {}".format(pin, value))


def i2c_scan(bus, sda_pin, scl_pin, freq=400000):
    _validate_gpio(sda_pin)
    _validate_gpio(scl_pin)

    try:
        i2c = machine.I2C(
            bus,
            sda=Pin(sda_pin),
            scl=Pin(scl_pin),
            freq=freq,
        )
        devices = i2c.scan()

        if not devices:
            print("No I2C devices found.")
            return

        print("I2C devices:")
        for addr in devices:
            print("  0x{:02X}".format(addr))

    except Exception as e:
        print("I2C error:", e)


# ---------- Self-update ----------

def _version_tuple(version):
    try:
        parts = version.strip().split(".")
        return tuple(int(part) for part in parts)
    except Exception:
        return None


def get_remote_version():
    url = UPDATE_BASE + "/version.txt"
    try:
        return fetch_text(url, 64).strip()
    except Exception as e:
        print("Could not read remote version.txt:", e)
        return None


def update_check(local_version):
    remote = get_remote_version()
    if remote is None:
        print("Update manifest is not available yet.")
        print("Push version.txt with the new PicoShell files before using update.")
        return False

    print("Local: ", local_version)
    print("Remote:", remote)

    local_t = _version_tuple(local_version)
    remote_t = _version_tuple(remote)

    if local_t is None or remote_t is None:
        print("Could not compare version numbers.")
        return False

    if remote_t > local_t:
        print("Update available.")
        return True

    if remote_t == local_t:
        print("PicoShell is up to date.")
        return False

    print("Remote version is older than this build; update blocked.")
    return False


def _ensure_parent_dir(path):
    if "/" not in path:
        return

    parent = path.rsplit("/", 1)[0]
    if not parent:
        return

    try:
        os.stat(parent)
    except OSError:
        os.mkdir(parent)


def update_install(local_version):
    if not wlan.isconnected():
        print("Wi-Fi is not connected.")
        return

    remote = get_remote_version()
    if remote is None:
        print("Update cancelled.")
        return

    local_t = _version_tuple(local_version)
    remote_t = _version_tuple(remote)

    if local_t is None or remote_t is None:
        print("Invalid version format. Update cancelled.")
        return

    if remote_t <= local_t:
        print("No newer version available.")
        return

    print("Updating PicoShell {} -> {}".format(local_version, remote))

    staged = []

    try:
        for path in UPDATE_FILES:
            _ensure_parent_dir(path)
            staged_path = path + ".new"
            url = UPDATE_BASE + "/" + path

            print("Downloading", path)
            download_file(url, staged_path)
            staged.append((path, staged_path))

    except Exception as e:
        print("Update download failed:", e)
        for _, staged_path in staged:
            try:
                os.remove(staged_path)
            except Exception:
                pass
        return

    backups = []

    try:
        for path, staged_path in staged:
            backup = path + ".bak"

            try:
                os.remove(backup)
            except Exception:
                pass

            try:
                os.stat(path)
                os.rename(path, backup)
                backups.append((path, backup))
            except OSError:
                pass

            os.rename(staged_path, path)

    except Exception as e:
        print("Install failed; attempting rollback:", e)

        for path, backup in backups:
            try:
                os.remove(path)
            except Exception:
                pass

            try:
                os.rename(backup, path)
            except Exception:
                pass

        return

    for _, backup in backups:
        try:
            os.remove(backup)
        except Exception:
            pass

    print("Update installed successfully.")
    print("Rebooting...")
    time.sleep_ms(500)
    machine.reset()


# ---------- System / hardware ----------

def overclock(clock):
    decide = input(
        "WARNING! Overclocking can cause instability. "
        "Would you like to proceed? [Y/N]: "
    )

    if decide.lower() != "y":
        return

    if clock <= 40:
        print("Clock speed is set too low!")
        return

    if clock >= 300:
        print("Clock speed is set too high!")
        return

    machine.freq(clock * 1_000_000)
    print("Clock speed set to {} MHz".format(clock))


def get_storage():
    stats = os.statvfs("/")
    block_size = stats[0]
    total_blocks = stats[2]
    free_blocks = stats[3]

    total = (block_size * total_blocks) // 1024
    free = (block_size * free_blocks) // 1024
    used = total - free

    print("Storage:")
    print("  Total: {} KB".format(total))
    print("  Used:  {} KB".format(used))
    print("  Free:  {} KB".format(free))


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
        print("ERROR:", e)
        return None


def get_mem():
    free = gc.mem_free()
    used = gc.mem_alloc()
    total = used + free

    print("Free:", free / 1024, "kilobytes")
    print("Used:", used / 1024, "kilobytes")
    print("Total:", total / 1024, "kilobytes")


def sysinfo():
    print(" ".join(os.uname()))
