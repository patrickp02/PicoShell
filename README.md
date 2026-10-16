# PicoShell

**PicoShell** is a lightweight UNIX-style command shell for the **Raspberry Pi Pico 2 W (RP2350)**, written in MicroPython. It provides filesystem tools, Wi-Fi/network utilities, Telnet access, script execution, GPIO/I2C controls, system monitoring, CPU clock control, and a built-in self-updater.

![PicoShell Screenshot](pico-shell.png)

## Features

- Interactive shell over USB serial or Telnet
- Wi-Fi connection using a simple persistent `config.txt`
- Filesystem navigation and file manipulation
- Python script execution directly from Pico storage
- HTTP/HTTPS file download and basic network tools
- TCP port scanning
- GPIO read/write/mode control
- I2C bus scanning
- RAM, storage, uptime, temperature, and CPU clock information
- RP2350 CPU clock adjustment from the shell
- Transactional self-update system using GitHub
- `Ctrl+C` / `exit` support to return cleanly to the MicroPython REPL for Thonny access

## Commands

### General

| Command | Description |
|---|---|
| `help`, `h` | Show PicoShell help |
| `about` | Show PicoShell version and platform info |
| `version` | Show installed PicoShell version |
| `uptime` | Show time since PicoShell started |
| `clear` | Clear the terminal |
| `exit` | Leave PicoShell and return to the MicroPython REPL |
| `reboot` | Hard reset the Pico |
| `reset` | Soft reset MicroPython |

### Filesystem

| Command | Description |
|---|---|
| `pwd` | Print current working directory |
| `ls [path]` | List files and directories |
| `cd <dir>` | Change directory |
| `mkdir <dir>` | Create a directory |
| `rmdir <dir>` | Remove an empty directory |
| `rm <file>` | Delete a file |
| `read <file>` | Print a text file |
| `cp <src> <dst>` | Copy a file |
| `mv <src> <dst>` | Move or rename a file |
| `touch <file>` | Create a file if it does not exist |
| `tree [path] [depth]` | Recursively display a directory tree |
| `write <file> <text>` | Overwrite a file with text |
| `append <file> <text>` | Append a line of text to a file |

### Scripts

| Command | Description |
|---|---|
| `run <file.py>` | Execute a Python script from Pico storage |

### Networking

| Command | Description |
|---|---|
| `wifi` | Scan/connect to Wi-Fi or disconnect from the current network |
| `ifconfig` | Show network interface configuration |
| `scan` | Scan nearby Wi-Fi networks |
| `ping <host>` | TCP-connect reachability/latency test using port 80 |
| `curl <url>` | Fetch and display content from a URL |
| `clone <url> [name]` | Download a file over HTTPS; raw GitHub URLs are supported |
| `pmap <host> [start] [end]` | Scan a TCP port range; default is 1-1024 |

> `ping` is currently a TCP connection timing test, not an ICMP echo implementation.

### Telnet

| Command | Description |
|---|---|
| `telnet launch` | Start the Telnet server |
| `telnet stop` | Stop the Telnet server |

Telnet can also be enabled automatically after Wi-Fi connects by uncommenting the Telnet startup lines in `main.py`.

### System

| Command | Description |
|---|---|
| `sysinfo` | Show MicroPython/system information |
| `dspace` | Show flash storage usage |
| `ram` | Show RAM usage |
| `freemem` | Run garbage collection and show memory before/after |
| `clock` | Show current CPU clock speed |
| `setclock <MHz>` | Set CPU frequency; PicoShell currently allows >40 MHz and <260 MHz |
| `temp` | Show the current temperature reading |
| `blink [times] [delay]` | Blink the onboard LED |

> CPU overclocking can cause instability. Use `setclock` at your own risk.

### GPIO / I2C

| Command | Description |
|---|---|
| `gpio read <pin>` | Read a GPIO pin |
| `gpio write <pin> <0\|1>` | Drive a GPIO pin low or high |
| `gpio mode <pin> <in\|out\|pullup\|pulldown>` | Configure a GPIO pin |
| `i2c scan <bus> <sda> <scl> [freq]` | Scan an I2C bus for connected devices |

Example:

```text
gpio mode 15 out
gpio write 15 1
gpio read 15
i2c scan 0 0 1 400000
```

### Self-update

| Command | Description |
|---|---|
| `update check` | Compare the installed version against `version.txt` on GitHub |
| `update install` | Download and install a newer version, then reboot |

The updater downloads the new files first, stages them as `.new`, backs up the currently installed files as `.bak`, and only then swaps the new files into place. If installation fails during replacement, it attempts to roll the previous files back.

## Project Structure

```text
boot.py                  # Starts PicoShell at boot
main.py                  # CLI, command handlers, and dispatcher
utils.py                 # Filesystem, networking, GPIO/I2C, updater, and system helpers
config.txt               # Wi-Fi credentials
docs/
  help.txt               # Built-in help text
telnet/
  utelnetserver.py       # Lightweight Telnet server
version.txt              # Current PicoShell version
pico-shell.png           # README screenshot
```

## Getting Started

### 1. Flash MicroPython

PicoShell targets the **Raspberry Pi Pico 2 W**, not the original Pico W or non-wireless Pico 2.

Download the current MicroPython firmware for the Pico 2 W from:

https://micropython.org/download/RPI_PICO2_W/

Then:

1. Hold **BOOTSEL** while connecting the Pico 2 W to your computer.
2. The board will appear as an `RP2350` USB drive.
3. Copy the MicroPython `.uf2` file onto that drive.
4. The Pico will reboot into MicroPython.

### 2. Upload PicoShell

Copy these files/directories to the Pico filesystem:

```text
boot.py
main.py
utils.py
config.txt
version.txt
docs/
telnet/
```

### Thonny

1. Open [Thonny](https://thonny.org).
2. Select **MicroPython (Raspberry Pi Pico)** as the interpreter.
3. Upload the PicoShell files to the Pico filesystem.
4. Reset the board.

If PicoShell is running and Thonny cannot access the filesystem, press **Ctrl+C** or enter:

```text
exit
```

PicoShell will stop and return control to the normal MicroPython `>>>` REPL so Thonny can use the filesystem again.

### mpremote

Example on Linux/macOS:

```bash
mpremote connect /dev/ttyACM0 fs cp boot.py :boot.py
mpremote connect /dev/ttyACM0 fs cp main.py :main.py
mpremote connect /dev/ttyACM0 fs cp utils.py :utils.py
mpremote connect /dev/ttyACM0 fs cp config.txt :config.txt
mpremote connect /dev/ttyACM0 fs cp version.txt :version.txt
mpremote connect /dev/ttyACM0 fs cp -r docs :docs
mpremote connect /dev/ttyACM0 fs cp -r telnet :telnet
```

Replace the device path with your actual serial device, such as `COM3` on Windows.

## Wi-Fi Configuration

Create `config.txt` in the Pico root directory:

```text
SSID=Your WiFi Name
PASSWORD=YourPassword
```

The SSID may contain spaces. Do not wrap the SSID or password in quotes.

The Pico 2 W supports **2.4 GHz Wi-Fi only**. If your router uses one SSID for both 2.4 GHz and 5 GHz, the Pico will connect using the 2.4 GHz radio.

## Running PicoShell

After reset or power-on:

1. `boot.py` imports `main.py`.
2. PicoShell reads `config.txt`.
3. It attempts to connect to Wi-Fi.
4. The interactive shell starts over the USB REPL.
5. Telnet can be started with:

```text
telnet launch
```

Example prompt:

```text
Pico@rp2:/$
```

## Updating PicoShell

Once PicoShell is installed, future updates can be checked directly from the board:

```text
update check
```

If a newer version is available:

```text
update install
```

The updater pulls the current files from the `main` branch of this repository and reboots after a successful install.

## Version

Current version: **0.2.0**

## License

MIT License. See [LICENSE](LICENSE).
