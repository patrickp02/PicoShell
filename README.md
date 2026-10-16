# PicoShell

**PicoShell** is a lightweight UNIX-style command shell for the **Raspberry Pi Pico 2 W (RP2350)** written in MicroPython. It provides filesystem tools, Wi-Fi/network utilities, Telnet access, script execution, GPIO/I2C controls, system monitoring, CPU clock control, and a built-in self-updater.

![PicoShell Screenshot](pico-shell.png)

## Features

- Interactive shell over USB serial or Telnet
- Headless operation with automatic Telnet startup after Wi-Fi connects
- Persistent Wi-Fi/Telnet configuration through `config.txt`
- Filesystem navigation and file manipulation
- Python script execution from Pico storage
- HTTP/HTTPS file download and basic network tools
- TCP port scanning
- GPIO read/write/mode control
- I2C bus scanning
- RAM, storage, uptime, temperature, and CPU clock information
- RP2350 CPU clock adjustment from the shell
- Transactional self-update system using GitHub
- `Ctrl+C` / `exit` support to return to the MicroPython REPL for Thonny
- USB-safe boot flow: `boot.py` no longer takes ownership of the REPL or manually imports `main.py`

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

### Networking / Telnet

| Command | Description |
|---|---|
| `wifi` | Scan/connect to Wi-Fi or disconnect from the current network |
| `ifconfig` | Show network interface configuration |
| `scan` | Scan nearby Wi-Fi networks |
| `ping <host>` | TCP-connect reachability/latency test using port 80 |
| `curl <url>` | Fetch and display content from a URL |
| `clone <url> [name]` | Download a file over HTTPS; raw GitHub URLs are supported |
| `pmap <host> [start] [end]` | Scan a TCP port range; default is 1-1024 |
| `telnet launch` | Start the Telnet server |
| `telnet stop` | Stop the Telnet server |

> `ping` is currently a TCP connection timing test, not an ICMP echo implementation.

### Scripts

| Command | Description |
|---|---|
| `run <file.py>` | Execute a Python script from Pico storage |

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

## Configuration

Create `config.txt` in the Pico root directory:

```text
SSID=Your WiFi Name
PASSWORD=YourPassword
TELNET_AUTO=1
```

`TELNET_AUTO=1` starts the Telnet listener automatically after Wi-Fi connects, which allows the Pico to run headless with only power connected. Set it to `0` if you want Telnet to remain off until `telnet launch` is entered manually.

Existing configurations without `TELNET_AUTO` remain compatible; PicoShell defaults to automatic Telnet startup.

The SSID may contain spaces. Do not wrap the SSID or password in quotes. The Pico 2 W uses 2.4 GHz Wi-Fi.

## Self-update

| Command | Description |
|---|---|
| `update check` | Compare the installed version against `version.txt` on GitHub |
| `update install` | Download and install a newer version, then reboot |

`version.txt` is the single source of truth for the installed PicoShell version.

The updater stages all new files as `.new`, backs up the installed copies as `.bak`, and swaps them only after every download succeeds. Current update targets are:

```text
main.py
utils.py
boot.py
docs/help.txt
version.txt
```

`config.txt` is intentionally **not** updated so an OTA update cannot overwrite Wi-Fi credentials or local settings.

### Upgrading from v0.2.0

The v0.2.0 updater did not include `boot.py` in its update list. v0.2.1 includes a startup migration that replaces the older REPL-binding `boot.py` with a minimal USB-safe file. Future updates also update `boot.py` directly.

## Boot / USB behavior

`boot.py` is intentionally minimal. MicroPython initializes the built-in USB REPL and automatically runs `main.py` after `boot.py`; PicoShell does not need to bind `sys.stdin` with `dupterm()` or manually `import main` from `boot.py`.

If PicoShell is running and Thonny needs the raw REPL, press **Ctrl+C** or enter:

```text
exit
```

## Project Structure

```text
boot.py                  # Minimal USB-safe boot script
main.py                  # CLI, command handlers, dispatcher, Wi-Fi/Telnet startup
utils.py                 # Filesystem, networking, GPIO/I2C, updater, and system helpers
config.txt               # Wi-Fi credentials and TELNET_AUTO setting
docs/
  help.txt               # Built-in help text
telnet/
  utelnetserver.py       # Lightweight Telnet server
version.txt              # Installed PicoShell version (single source of truth)
pico-shell.png           # README screenshot
```

## Getting Started

PicoShell targets the **Raspberry Pi Pico 2 W**.

1. Flash the current Pico 2 W MicroPython UF2.
2. Copy `boot.py`, `main.py`, `utils.py`, `config.txt`, `version.txt`, `docs/`, and `telnet/` to the Pico filesystem.
3. Fill in `config.txt`.
4. Reset the Pico.
5. PicoShell connects to Wi-Fi, starts Telnet when enabled, and starts the shell.

Example prompt:

```text
Pico@rp2:/$
```

For a headless installation, power the Pico normally and connect to its IP address on TCP port 23 after it joins Wi-Fi.

## v0.2.1 changes

- Replaced the old REPL-binding `boot.py` with a minimal USB-safe boot file.
- Added automatic Telnet startup for headless use, controlled with `TELNET_AUTO` in `config.txt`.
- Made `version.txt` the single source of truth for the installed version.
- Added `boot.py` to the OTA update set so future boot-script fixes can be delivered remotely.
- Preserved `config.txt` during OTA updates so local Wi-Fi credentials and settings are not overwritten.

## Version

Current version: **0.2.1**

## License

MIT License. See [LICENSE](LICENSE).
