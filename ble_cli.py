import gc
import time
import bluetooth
import micropython
from micropython import const


_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)

_ADV_IND = const(0)
_ADV_DIRECT_IND = const(1)
_ADV_SCAN_IND = const(2)
_ADV_NONCONN_IND = const(3)
_ADV_SCAN_RSP = const(4)

MAX_DEVICES = const(24)
SCAN_INTERVAL_US = const(100000)
SCAN_WINDOW_US = const(30000)


@micropython.viper
def _find_ad_type(buf: ptr8, length: int, wanted: int) -> int:
    """Return payload offset for one BLE advertising-data field, or -1."""
    pos: int = 0

    while pos < length:
        field_len: int = int(buf[pos])
        if field_len == 0:
            return -1

        end: int = pos + field_len
        if end >= length:
            return -1

        if int(buf[pos + 1]) == wanted:
            return pos + 2

        pos = end + 1

    return -1


def _decode_name(adv_data):
    """Decode complete/short local name while keeping scan allocations small."""
    length = len(adv_data)

    for ad_type in (0x09, 0x08):
        pos = _find_ad_type(adv_data, length, ad_type)
        if pos >= 0:
            payload_len = adv_data[pos - 2] - 1
            if payload_len <= 0:
                return ""
            try:
                return bytes(adv_data[pos:pos + payload_len]).decode("utf-8")
            except Exception:
                return "?"

    return ""


def _format_addr(addr):
    return ":".join("{:02X}".format(value) for value in addr)


def _adv_name(adv_type):
    if adv_type == _ADV_IND:
        return "ADV"
    if adv_type == _ADV_DIRECT_IND:
        return "DIRECT"
    if adv_type == _ADV_SCAN_IND:
        return "SCAN"
    if adv_type == _ADV_NONCONN_IND:
        return "NONCONN"
    if adv_type == _ADV_SCAN_RSP:
        return "RSP"
    return str(adv_type)


class BLEManager:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.devices = []
        self.conn_handle = None
        self.conn_addr_type = None
        self.conn_addr = None

        self.services = []
        self.characteristics = []

        self._scan_done = True
        self._connect_done = True
        self._service_done = True
        self._char_done = True
        self._read_done = True
        self._write_done = True

        self._read_value = None
        self._read_status = None
        self._write_status = None

        self.ble.active(True)
        self.ble.irq(self._irq)

    def _irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data

            # The IRQ owns addr/adv_data buffers, so copy addresses we retain.
            for device in self.devices:
                if device[0] == addr_type and device[1] == addr:
                    # Active-scan response often contains the name even when the
                    # first advertisement did not. Update only once to avoid
                    # continuous object churn while scanning.
                    if not device[3]:
                        name = _decode_name(adv_data)
                        if name:
                            device[3] = name
                    return

            if len(self.devices) >= MAX_DEVICES:
                return

            name = _decode_name(adv_data)
            self.devices.append([
                addr_type,
                bytes(addr),
                rssi,
                name,
                adv_type,
            ])

        elif event == _IRQ_SCAN_DONE:
            self._scan_done = True

        elif event == _IRQ_PERIPHERAL_CONNECT:
            conn_handle, addr_type, addr = data
            self.conn_handle = conn_handle
            self.conn_addr_type = addr_type
            self.conn_addr = bytes(addr)
            self._connect_done = True

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            conn_handle, _, _ = data
            if self.conn_handle == conn_handle:
                self.conn_handle = None
                self.conn_addr_type = None
                self.conn_addr = None
                self.services = []
                self.characteristics = []
            self._connect_done = True

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            conn_handle, start_handle, end_handle, uuid = data
            if conn_handle == self.conn_handle:
                self.services.append((start_handle, end_handle, str(uuid)))

        elif event == _IRQ_GATTC_SERVICE_DONE:
            conn_handle, status = data
            if conn_handle == self.conn_handle:
                self._service_done = True

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            conn_handle, def_handle, value_handle, properties, uuid = data
            if conn_handle == self.conn_handle:
                self.characteristics.append((
                    def_handle,
                    value_handle,
                    properties,
                    str(uuid),
                ))

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            conn_handle, status = data
            if conn_handle == self.conn_handle:
                self._char_done = True

        elif event == _IRQ_GATTC_READ_RESULT:
            conn_handle, value_handle, char_data = data
            if conn_handle == self.conn_handle:
                self._read_value = bytes(char_data)

        elif event == _IRQ_GATTC_READ_DONE:
            conn_handle, value_handle, status = data
            if conn_handle == self.conn_handle:
                self._read_status = status
                self._read_done = True

        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            if conn_handle == self.conn_handle:
                self._write_status = status
                self._write_done = True

    def _wait(self, attr, timeout_ms):
        start = time.ticks_ms()
        while not getattr(self, attr):
            if time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
                return False
            time.sleep_ms(20)
        return True

    def scan(self, seconds=5):
        if seconds < 1 or seconds > 30:
            print("Scan duration must be 1-30 seconds.")
            return

        if self.conn_handle is not None:
            print("Disconnect before scanning.")
            return

        self.devices = []
        self._scan_done = False
        gc.collect()

        duration_ms = seconds * 1000
        print("Scanning for BLE devices for {}s...".format(seconds))

        try:
            self.ble.gap_scan(
                duration_ms,
                SCAN_INTERVAL_US,
                SCAN_WINDOW_US,
                True,
            )
        except Exception as e:
            self._scan_done = True
            print("BLE scan failed:", e)
            return

        if not self._wait("_scan_done", duration_ms + 1500):
            try:
                self.ble.gap_scan(None)
            except Exception:
                pass
            print("BLE scan timed out.")

        gc.collect()
        self.print_devices()

    def print_devices(self):
        if not self.devices:
            print("No BLE devices cached. Run 'ble scan' first.")
            return

        print("#  RSSI  Type     Address             Name")
        for index, device in enumerate(self.devices):
            addr_type, addr, rssi, name, adv_type = device
            addr_label = "P" if addr_type == 0 else "R"
            display_name = name if name else "-"
            print(
                "{}  {}  {}/{}  {}  {}".format(
                    index,
                    rssi,
                    addr_label,
                    _adv_name(adv_type),
                    _format_addr(addr),
                    display_name,
                )
            )

        if len(self.devices) >= MAX_DEVICES:
            print("Device cache full ({} entries).".format(MAX_DEVICES))

    def connect(self, index, timeout_ms=7000):
        if self.conn_handle is not None:
            print("Already connected to", _format_addr(self.conn_addr))
            return

        if index < 0 or index >= len(self.devices):
            print("Device index out of range. Run 'ble devices'.")
            return

        device = self.devices[index]
        addr_type, addr = device[0], device[1]
        self._connect_done = False

        print("Connecting to {}...".format(_format_addr(addr)))
        try:
            self.ble.gap_connect(addr_type, addr, 5000)
        except Exception as e:
            self._connect_done = True
            print("BLE connect failed:", e)
            return

        if not self._wait("_connect_done", timeout_ms):
            try:
                self.ble.gap_connect(None)
            except Exception:
                pass
            print("BLE connection timed out.")
            return

        if self.conn_handle is None:
            print("BLE connection failed.")
            return

        print(
            "Connected: {} (handle {})".format(
                _format_addr(self.conn_addr),
                self.conn_handle,
            )
        )

    def disconnect(self):
        if self.conn_handle is None:
            print("No BLE device connected.")
            return

        handle = self.conn_handle
        try:
            result = self.ble.gap_disconnect(handle)
        except Exception as e:
            print("BLE disconnect failed:", e)
            return

        if result is False:
            print("Connection handle was not active.")
        else:
            print("Disconnect requested.")

    def status(self):
        try:
            addr_type, local_addr = self.ble.config("mac")
            print("BLE active:", self.ble.active())
            print("Local address:", _format_addr(local_addr))
        except Exception:
            print("BLE active:", self.ble.active())

        if self.conn_handle is None:
            print("Connection: none")
        else:
            print("Connection:", _format_addr(self.conn_addr))
            print("Handle:", self.conn_handle)

        print("Cached devices:", len(self.devices))
        print("Free RAM:", gc.mem_free(), "bytes")

    def discover_services(self, timeout_ms=7000):
        if self.conn_handle is None:
            print("Connect to a BLE device first.")
            return

        self.services = []
        self._service_done = False

        try:
            self.ble.gattc_discover_services(self.conn_handle)
        except Exception as e:
            self._service_done = True
            print("Service discovery failed:", e)
            return

        if not self._wait("_service_done", timeout_ms):
            print("Service discovery timed out.")
            return

        if not self.services:
            print("No GATT services found.")
            return

        print("#  Handles       UUID")
        for index, service in enumerate(self.services):
            print(
                "{}  {}-{}  {}".format(
                    index,
                    service[0],
                    service[1],
                    service[2],
                )
            )

    def discover_characteristics(self, service_index, timeout_ms=7000):
        if self.conn_handle is None:
            print("Connect to a BLE device first.")
            return

        if service_index < 0 or service_index >= len(self.services):
            print("Service index out of range. Run 'ble services' first.")
            return

        start_handle, end_handle, _ = self.services[service_index]
        self.characteristics = []
        self._char_done = False

        try:
            self.ble.gattc_discover_characteristics(
                self.conn_handle,
                start_handle,
                end_handle,
            )
        except Exception as e:
            self._char_done = True
            print("Characteristic discovery failed:", e)
            return

        if not self._wait("_char_done", timeout_ms):
            print("Characteristic discovery timed out.")
            return

        if not self.characteristics:
            print("No GATT characteristics found.")
            return

        print("Def  Value  Props   UUID")
        for item in self.characteristics:
            print(
                "{}  {}  0x{:04X}  {}".format(
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                )
            )

    def read(self, value_handle, timeout_ms=5000):
        if self.conn_handle is None:
            print("Connect to a BLE device first.")
            return

        self._read_value = None
        self._read_status = None
        self._read_done = False

        try:
            self.ble.gattc_read(self.conn_handle, value_handle)
        except Exception as e:
            self._read_done = True
            print("GATT read failed:", e)
            return

        if not self._wait("_read_done", timeout_ms):
            print("GATT read timed out.")
            return

        if self._read_status not in (None, 0):
            print("GATT read status:", self._read_status)
            return

        data = self._read_value if self._read_value is not None else b""
        print("Hex:", "".join("{:02x}".format(value) for value in data))
        try:
            print("Text:", data.decode("utf-8"))
        except Exception:
            pass

    def write(self, value_handle, payload, timeout_ms=5000):
        if self.conn_handle is None:
            print("Connect to a BLE device first.")
            return

        self._write_status = None
        self._write_done = False

        try:
            # mode=1 asks the peripheral to acknowledge the write.
            self.ble.gattc_write(self.conn_handle, value_handle, payload, 1)
        except Exception as e:
            self._write_done = True
            print("GATT write failed:", e)
            return

        if not self._wait("_write_done", timeout_ms):
            print("GATT write timed out.")
            return

        if self._write_status == 0:
            print("GATT write acknowledged.")
        else:
            print("GATT write status:", self._write_status)

    def off(self):
        if self.conn_handle is not None:
            try:
                self.ble.gap_disconnect(self.conn_handle)
                time.sleep_ms(50)
            except Exception:
                pass

        try:
            self.ble.gap_scan(None)
        except Exception:
            pass

        self.ble.active(False)
        self.devices = []
        self.services = []
        self.characteristics = []
        self.conn_handle = None
        self.conn_addr = None
        self.conn_addr_type = None
        gc.collect()
        print("BLE radio disabled.")

    def on(self):
        self.ble.active(True)
        self.ble.irq(self._irq)
        print("BLE radio enabled.")


_manager = None


def _get_manager():
    global _manager
    if _manager is None:
        _manager = BLEManager()
    elif not _manager.ble.active():
        _manager.on()
    return _manager


def _parse_hex(text):
    compact = text.replace(" ", "").replace(":", "").replace("-", "")
    if compact.startswith("0x"):
        compact = compact[2:]
    if not compact or len(compact) % 2:
        raise ValueError("hex data must contain full bytes")

    out = bytearray(len(compact) // 2)
    for i in range(len(out)):
        out[i] = int(compact[i * 2:i * 2 + 2], 16)
    return out


def command(argline):
    parts = argline.split(None, 2) if argline else []
    action = parts[0].lower() if parts else "status"

    manager = _get_manager()

    if action == "scan":
        try:
            seconds = int(parts[1]) if len(parts) > 1 else 5
        except ValueError:
            print("Usage: ble scan [seconds]")
            return
        manager.scan(seconds)

    elif action in ("devices", "list"):
        manager.print_devices()

    elif action == "connect":
        if len(parts) < 2:
            print("Usage: ble connect <device_index>")
            return
        try:
            index = int(parts[1])
        except ValueError:
            print("Device index must be an integer from 'ble devices'.")
            return
        manager.connect(index)

    elif action == "disconnect":
        manager.disconnect()

    elif action == "status":
        manager.status()

    elif action == "services":
        manager.discover_services()

    elif action in ("chars", "characteristics"):
        if len(parts) < 2:
            print("Usage: ble chars <service_index>")
            return
        try:
            service_index = int(parts[1])
        except ValueError:
            print("Service index must be an integer from 'ble services'.")
            return
        manager.discover_characteristics(service_index)

    elif action == "read":
        if len(parts) < 2:
            print("Usage: ble read <value_handle>")
            return
        try:
            handle = int(parts[1], 0)
        except ValueError:
            print("Handle must be an integer (decimal or 0xHEX).")
            return
        manager.read(handle)

    elif action == "write":
        if len(parts) < 3:
            print("Usage: ble write <value_handle> <text>")
            return
        try:
            handle = int(parts[1], 0)
        except ValueError:
            print("Handle must be an integer (decimal or 0xHEX).")
            return
        manager.write(handle, parts[2].encode("utf-8"))

    elif action == "writehex":
        if len(parts) < 3:
            print("Usage: ble writehex <value_handle> <hex_bytes>")
            return
        try:
            handle = int(parts[1], 0)
            payload = _parse_hex(parts[2])
        except ValueError as e:
            print("Invalid hex write:", e)
            return
        manager.write(handle, payload)

    elif action == "off":
        manager.off()

    elif action == "on":
        manager.on()

    else:
        print("BLE commands:")
        print("  ble scan [seconds]")
        print("  ble devices")
        print("  ble connect <device_index>")
        print("  ble disconnect")
        print("  ble status")
        print("  ble services")
        print("  ble chars <service_index>")
        print("  ble read <value_handle>")
        print("  ble write <value_handle> <text>")
        print("  ble writehex <value_handle> <hex_bytes>")
        print("  ble on | off")
