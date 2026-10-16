import os
import gc
import time
import machine
import network
import platform
from machine import Pin

import utils
from telnet import utelnetserver


SAFE_BOOT_MARKER = "# PicoShell safe boot.py"
SAFE_BOOT_CONTENT = """# PicoShell safe boot.py
#
# Intentionally minimal. MicroPython initializes the built-in USB REPL and
# then runs main.py automatically. Do not bind sys.stdin with dupterm here
# and do not import main manually.
"""

DEFAULT_AP_PASSWORD = "picoshell"
WIFI_TIMEOUT_MS = 13000
AP_IP_CONFIG = (
    "192.168.4.1",
    "255.255.255.0",
    "192.168.4.1",
    "192.168.4.1",
)


def read_local_version(path="version.txt"):
    try:
        with open(path, "r") as f:
            version = f.read().strip()
        return version if version else "unknown"
    except OSError:
        return "unknown"


def read_config_option(filename, key, default=None):
    try:
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                current_key, value = line.split("=", 1)
                if current_key.strip() == key:
                    return value.strip()
    except OSError:
        return default
    return default


def config_bool(value, default=False):
    if value is None:
        return default

    value = str(value).strip().lower()
    if value in ("1", "true", "yes", "on", "y"):
        return True
    if value in ("0", "false", "no", "off", "n"):
        return False
    return default


def save_wifi_config(ssid, password, path="config.txt"):
    """Save Wi-Fi credentials while preserving PicoShell network options."""
    telnet_auto = read_config_option(path, "TELNET_AUTO", "1")
    ap_fallback = read_config_option(path, "AP_FALLBACK", "1")
    ap_password = read_config_option(path, "AP_PASSWORD", DEFAULT_AP_PASSWORD)

    staged = path + ".new"
    backup = path + ".bak"

    with open(staged, "w") as f:
        f.write("SSID={}\n".format(ssid))
        f.write("PASSWORD={}\n".format(password))
        f.write("TELNET_AUTO={}\n".format(telnet_auto))
        f.write("AP_FALLBACK={}\n".format(ap_fallback))
        f.write("AP_PASSWORD={}\n".format(ap_password))

    try:
        os.remove(backup)
    except OSError:
        pass

    had_old = False
    try:
        os.stat(path)
        os.rename(path, backup)
        had_old = True
    except OSError:
        pass

    try:
        os.rename(staged, path)
    except Exception:
        if had_old:
            try:
                os.rename(backup, path)
            except Exception:
                pass
        raise

    if had_old:
        try:
            os.remove(backup)
        except OSError:
            pass


def fallback_ap_ssid():
    try:
        uid = machine.unique_id()
        suffix = "".join("{:02X}".format(value) for value in uid[-3:])
        return "PicoShell-{}".format(suffix)
    except Exception:
        return "PicoShell-Setup"


def start_fallback_ap():
    """Start the lightweight recovery/setup AP and return True on success."""
    ap = network.WLAN(network.AP_IF)
    ssid = fallback_ap_ssid()
    password = read_config_option(
        "config.txt",
        "AP_PASSWORD",
        DEFAULT_AP_PASSWORD,
    )

    if password is None or len(password) < 8 or len(password) > 63:
        print("AP_PASSWORD must be 8-63 characters; using the default.")
        password = DEFAULT_AP_PASSWORD

    try:
        ap.active(False)
        ap.config(ssid=ssid, security=3, key=password)
        ap.active(True)
        ap.ifconfig(AP_IP_CONFIG)
        time.sleep_ms(250)
    except Exception as e:
        print("Fallback AP failed:", e)
        try:
            ap.active(False)
        except Exception:
            pass
        return False

    print("Fallback AP active.")
    print("SSID:", ssid)
    print("IP:", ap.ifconfig()[0])
    print("Connect to the AP, Telnet to the IP above, then run 'wifi setup'.")
    return True


def start_telnet_server():
    try:
        print("Starting Telnet server...")
        utelnetserver.start()
        return True
    except Exception as e:
        print("Telnet auto-start failed:", e)
        return False


def start_ap_fallback(telnet_auto):
    try:
        wlan.disconnect()
    except Exception:
        pass

    try:
        wlan.active(False)
    except Exception:
        pass

    if not start_fallback_ap():
        return False

    if telnet_auto:
        start_telnet_server()
    else:
        print("Telnet auto-start disabled in config.txt")

    return True


def ensure_safe_boot_file(path="boot.py"):
    """Replace old PicoShell boot.py files that interfered with USB REPL."""
    try:
        with open(path, "r") as f:
            current = f.read()
        if SAFE_BOOT_MARKER in current:
            return False
    except OSError:
        pass

    try:
        with open(path, "w") as f:
            f.write(SAFE_BOOT_CONTENT)
        print("Migrated boot.py to USB-safe boot configuration.")
        return True
    except Exception as e:
        print("Could not migrate boot.py:", e)
        return False


TELNET_SERVER_MARKER = 'PICOSHELL_TELNET_VERSION = "0.2.2"'


def ensure_current_telnet_server(path="telnet/utelnetserver.py"):
    """One-time v0.2.1 migration so OTA can begin updating Telnet itself."""
    try:
        with open(path, "r") as f:
            current = f.read()
        if TELNET_SERVER_MARKER in current:
            return False
    except OSError:
        pass

    staged = path + ".new"
    backup = path + ".bak"
    url = utils.UPDATE_BASE + "/telnet/utelnetserver.py"

    try:
        print("Updating Telnet server...")
        utils.download_file(url, staged)

        with open(staged, "r") as f:
            staged_text = f.read()
        if TELNET_SERVER_MARKER not in staged_text:
            raise ValueError("Downloaded Telnet server is not the expected version")

        try:
            os.remove(backup)
        except Exception:
            pass

        had_old = False
        try:
            os.stat(path)
            os.rename(path, backup)
            had_old = True
        except OSError:
            pass

        try:
            os.rename(staged, path)
        except Exception:
            if had_old:
                try:
                    os.rename(backup, path)
                except Exception:
                    pass
            raise

        if had_old:
            try:
                os.remove(backup)
            except Exception:
                pass

        print("Telnet server updated. Restarting to load it...")
        return True

    except Exception as e:
        print("Telnet server migration failed:", e)
        try:
            os.remove(staged)
        except Exception:
            pass
        return False


utils.UPDATE_FILES = (
    "main.py",
    "utils.py",
    "boot.py",
    "telnet/utelnetserver.py",
    "docs/help.txt",
    "version.txt",
)

PICOSHELL_VERSION = read_local_version()
SHELL_START_MS = time.ticks_ms()

BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
RESET = "\033[0m"

wlan = network.WLAN(network.STA_IF)
sys_info = os.uname()
led = Pin("LED", Pin.OUT)

_command_count = 0


def init_network():
    """Connect using config.txt or fall back to a local setup access point."""
    telnet_auto = config_bool(
        read_config_option("config.txt", "TELNET_AUTO", "1"),
        True,
    )
    ap_fallback = config_bool(
        read_config_option("config.txt", "AP_FALLBACK", "1"),
        True,
    )

    try:
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            ap.active(False)
    except Exception:
        pass

    try:
        ssid, password = utils.read_wifi_config("config.txt")
    except OSError:
        print("config.txt not found.")
        if ap_fallback:
            start_ap_fallback(telnet_auto)
        else:
            print("AP fallback disabled.")
        return
    except Exception as e:
        print("Could not read config.txt:", e)
        if ap_fallback:
            start_ap_fallback(telnet_auto)
        else:
            print("AP fallback disabled.")
        return

    if not ssid:
        print("No Wi-Fi SSID configured.")
        if ap_fallback:
            start_ap_fallback(telnet_auto)
        else:
            print("AP fallback disabled.")
        return

    print("Initializing...")

    try:
        utils.auto_connect(ssid, password)
    except Exception as e:
        print("Wi-Fi connection failed:", e)
        if ap_fallback:
            start_ap_fallback(telnet_auto)
        return

    start = time.ticks_ms()

    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) >= WIFI_TIMEOUT_MS:
            print("Wi-Fi connection timed out.")
            if ap_fallback:
                start_ap_fallback(telnet_auto)
            else:
                print("AP fallback disabled.")
            return
        time.sleep_ms(250)

    print("Wi-Fi connected:", wlan.ifconfig()[0])

    if ensure_current_telnet_server():
        time.sleep_ms(300)
        machine.reset()

    if telnet_auto:
        start_telnet_server()
    else:
        print("Telnet auto-start disabled in config.txt")


def startup_blink(times=4, delay=0.2):
    for _ in range(times):
        led.on()
        time.sleep(delay)
        led.off()
        time.sleep(delay)


def prompt():
    return "{}{}Pico@{}{}:{}{}{}$ ".format(
        BOLD,
        GREEN,
        sys_info.sysname,
        RESET,
        BLUE,
        os.getcwd(),
        RESET,
    )


def require_arg(argline, usage):
    if not argline:
        print("Usage:", usage)
        return False
    return True


def split_path_and_text(argline, usage):
    if not argline:
        print("Usage:", usage)
        return None, None

    parts = argline.split(None, 1)
    if len(parts) < 2:
        print("Usage:", usage)
        return None, None

    return parts[0], parts[1]


def format_uptime(ms):
    total_seconds = ms // 1000
    days = total_seconds // 86400
    total_seconds %= 86400
    hours = total_seconds // 3600
    total_seconds %= 3600
    minutes = total_seconds // 60
    seconds = total_seconds % 60

    if days:
        return "{}d {:02d}:{:02d}:{:02d}".format(days, hours, minutes, seconds)
    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)


def cmd_help(argline):
    try:
        with open("/docs/help.txt") as f:
            print(f.read())
    except Exception as e:
        print("Help file does not exist.", e)


def cmd_wifi(argline):
    action = argline.strip().lower() if argline else ""

    if action in ("setup", "set"):
        ssid = input("Wi-Fi SSID: ").strip()
        if not ssid:
            print("SSID cannot be empty.")
            return

        password = input("Wi-Fi password: ")

        try:
            save_wifi_config(ssid, password)
            print("Wi-Fi credentials saved to config.txt.")
            print("Run 'reboot' to try the new network.")
            print("If it fails, the PicoShell fallback AP will return.")
        except Exception as e:
            print("Could not save Wi-Fi configuration:", e)
        return

    if action:
        print("Usage: wifi [setup]")
        return

    utils.getWifi()


def cmd_ifconfig(argline):
    utils.if_config()

    try:
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            print("Access point:", ap.ifconfig())
            print("AP SSID:", ap.config("ssid"))
    except Exception as e:
        print("AP status error:", e)


def cmd_sysinfo(argline):
    utils.sysinfo()


def cmd_dspace(argline):
    utils.get_storage()


def cmd_ram(argline):
    utils.get_mem()


def cmd_freemem(argline):
    utils.get_mem()
    gc.collect()
    print("After Garbage Collection:")
    utils.get_mem()


def cmd_pwd(argline):
    print(os.getcwd())


def cmd_ls(argline):
    utils.ls(argline if argline else None)


def cmd_cd(argline):
    if require_arg(argline, "cd <dir>"):
        utils.cd(argline)


def cmd_mkdir(argline):
    if require_arg(argline, "mkdir <dir>"):
        utils.mkdir(argline)


def cmd_rmdir(argline):
    if require_arg(argline, "rmdir <dir>"):
        utils.rmdir(argline)


def cmd_rm(argline):
    if require_arg(argline, "rm <file>"):
        utils.rm(argline)


def cmd_read(argline):
    if require_arg(argline, "read <file>"):
        utils.read(argline)


def cmd_cp(argline):
    if not require_arg(argline, "cp <source> <destination>"):
        return
    parts = argline.split(None, 1)
    if len(parts) != 2:
        print("Usage: cp <source> <destination>")
        return
    utils.cp(parts[0], parts[1])


def cmd_mv(argline):
    if not require_arg(argline, "mv <source> <destination>"):
        return
    parts = argline.split(None, 1)
    if len(parts) != 2:
        print("Usage: mv <source> <destination>")
        return
    utils.mv(parts[0], parts[1])


def cmd_touch(argline):
    if require_arg(argline, "touch <file>"):
        utils.touch(argline)


def cmd_tree(argline):
    path = "."
    max_depth = 8

    if argline:
        parts = argline.split()
        path = parts[0]
        if len(parts) > 1:
            try:
                max_depth = int(parts[1])
            except ValueError:
                print("Depth must be an integer.")
                return

    utils.tree(path, max_depth)


def cmd_write(argline):
    filename, text = split_path_and_text(argline, "write <file> <text>")
    if filename is not None:
        utils.write_text(filename, text, append=False)


def cmd_append(argline):
    filename, text = split_path_and_text(argline, "append <file> <text>")
    if filename is not None:
        utils.write_text(filename, text, append=True)


def cmd_run(argline):
    if require_arg(argline, "run <file.py>"):
        utils.run(argline)


def cmd_clone(argline):
    if not require_arg(argline, "clone <url> [name]"):
        return
    args = argline.split()
    url = args[0]
    filename = args[1] if len(args) > 1 else url.rsplit("/", 1)[-1]
    print("Downloading {} from {}".format(filename, url))
    utils.download_file(url, filename)


def cmd_curl(argline):
    if require_arg(argline, "curl <url>"):
        utils.curl(argline)


def cmd_ping(argline):
    if require_arg(argline, "ping <host>"):
        utils.ping(argline)


def cmd_scan(argline):
    utils.scan()


def cmd_pmap(argline):
    if not require_arg(argline, "pmap <host> [start] [end]"):
        return
    parts = argline.split()
    host = parts[0]
    try:
        start = int(parts[1]) if len(parts) > 1 else 1
        end = int(parts[2]) if len(parts) > 2 else 1024
    except ValueError:
        print("Ports must be integers.")
        return
    utils.scan_ports(host, start, end)


def cmd_telnet(argline):
    if not require_arg(argline, "telnet <launch|stop>"):
        return
    utils.telnet_launch(argline.strip().lower())


def cmd_clear(argline):
    print("\033c", end="")


def cmd_about(argline):
    print("PicoShell", PICOSHELL_VERSION)
    print(platform.platform())


def cmd_version(argline):
    print("PicoShell", PICOSHELL_VERSION)


def cmd_uptime(argline):
    elapsed = time.ticks_diff(time.ticks_ms(), SHELL_START_MS)
    print("Uptime:", format_uptime(elapsed))


def cmd_clock(argline):
    print("CPU Clock:", machine.freq() // 1_000_000, "MHz")


def cmd_setclock(argline):
    if not require_arg(argline, "setclock <MHz>"):
        return
    try:
        mhz = int(argline)
    except ValueError:
        print("Clock speed must be an integer.")
        return
    utils.overclock(mhz)


def cmd_temp(argline):
    temp = utils.read_temp()
    if temp is not None:
        print("CPU Temp: {:.2f} °C".format(temp))


def cmd_blink(argline):
    if not argline:
        utils.blink()
        return
    parts = argline.split()
    try:
        times = int(parts[0])
        delay = float(parts[1]) if len(parts) > 1 else 0.2
        utils.blink(times, delay)
    except ValueError:
        print("Usage: blink [times] [delay_seconds]")


def cmd_gpio(argline):
    if not require_arg(argline, "gpio <read PIN | write PIN 0|1 | mode PIN in|out|pullup|pulldown>"):
        return
    parts = argline.split()
    action = parts[0].lower()
    try:
        if action == "read" and len(parts) == 2:
            pin = int(parts[1])
            print(utils.gpio_read(pin))
        elif action == "write" and len(parts) == 3:
            pin = int(parts[1])
            value = int(parts[2])
            utils.gpio_write(pin, value)
        elif action == "mode" and len(parts) == 3:
            pin = int(parts[1])
            mode = parts[2].lower()
            utils.gpio_mode(pin, mode)
        else:
            print("Usage: gpio <read PIN | write PIN 0|1 | mode PIN in|out|pullup|pulldown>")
    except ValueError:
        print("GPIO pin/value must be an integer where required.")


def cmd_i2c(argline):
    if not require_arg(argline, "i2c scan <bus> <sda_pin> <scl_pin> [freq_hz]"):
        return
    parts = argline.split()
    if len(parts) not in (4, 5) or parts[0].lower() != "scan":
        print("Usage: i2c scan <bus> <sda_pin> <scl_pin> [freq_hz]")
        return
    try:
        bus = int(parts[1])
        sda_pin = int(parts[2])
        scl_pin = int(parts[3])
        freq = int(parts[4]) if len(parts) == 5 else 400000
    except ValueError:
        print("Bus, pins, and frequency must be integers.")
        return
    utils.i2c_scan(bus, sda_pin, scl_pin, freq)


def cmd_update(argline):
    action = argline.strip().lower() if argline else "check"
    if action == "check":
        utils.update_check(PICOSHELL_VERSION)
    elif action == "install":
        utils.update_install(PICOSHELL_VERSION)
    else:
        print("Usage: update [check|install]")


def cmd_reboot(argline):
    print("Rebooting.")
    time.sleep_ms(100)
    machine.reset()


def cmd_reset(argline):
    print("Soft resetting.")
    time.sleep_ms(100)
    machine.soft_reset()


COMMANDS = {
    "help": cmd_help,
    "h": cmd_help,
    "wifi": cmd_wifi,
    "ifconfig": cmd_ifconfig,
    "sysinfo": cmd_sysinfo,
    "dspace": cmd_dspace,
    "ram": cmd_ram,
    "freemem": cmd_freemem,
    "pwd": cmd_pwd,
    "ls": cmd_ls,
    "cd": cmd_cd,
    "mkdir": cmd_mkdir,
    "rmdir": cmd_rmdir,
    "rm": cmd_rm,
    "read": cmd_read,
    "cp": cmd_cp,
    "mv": cmd_mv,
    "touch": cmd_touch,
    "tree": cmd_tree,
    "write": cmd_write,
    "append": cmd_append,
    "run": cmd_run,
    "clone": cmd_clone,
    "curl": cmd_curl,
    "ping": cmd_ping,
    "scan": cmd_scan,
    "pmap": cmd_pmap,
    "telnet": cmd_telnet,
    "clear": cmd_clear,
    "about": cmd_about,
    "version": cmd_version,
    "uptime": cmd_uptime,
    "clock": cmd_clock,
    "setclock": cmd_setclock,
    "temp": cmd_temp,
    "blink": cmd_blink,
    "gpio": cmd_gpio,
    "i2c": cmd_i2c,
    "update": cmd_update,
    "reboot": cmd_reboot,
    "reset": cmd_reset,
}


def run_shell():
    global _command_count
    startup_blink()
    while True:
        try:
            line = input(prompt()).strip()
            if not line:
                continue
            parts = line.split(None, 1)
            command = parts[0].lower()
            argline = parts[1].strip() if len(parts) > 1 else ""
            if command == "exit":
                print("Leaving PicoShell.")
                break
            handler = COMMANDS.get(command)
            if handler is None:
                print("Unknown command:", command)
                continue
            handler(argline)
            _command_count += 1
            if _command_count % 5 == 0:
                gc.collect()
        except KeyboardInterrupt:
            print("\nPicoShell stopped. Returning to MicroPython REPL.")
            break
        except Exception as e:
            print("CLI ERROR:", e)


ensure_safe_boot_file()
init_network()
run_shell()