import socket
import network
import uos
import errno
import gc
from uio import IOBase


# Keep this legacy marker for main.py's existing Telnet migration check.
# PicoShell release version is tracked separately in version.txt.
PICOSHELL_TELNET_VERSION = "0.2.2"
TELNET_IMPL_VERSION = "0.3.1"

IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240
ECHO = 1
SUPPRESS_GO_AHEAD = 3

RX_BUFFER_SIZE = 32
TELNET_NEGOTIATION = bytes((
    IAC, WILL, ECHO,
    IAC, WILL, SUPPRESS_GO_AHEAD,
    IAC, DO, SUPPRESS_GO_AHEAD,
))

last_client_socket = None
server_socket = None


def _send_all(sock, data):
    sent_total = 0
    data_len = len(data)

    while sent_total < data_len:
        if sent_total == 0:
            chunk = data
        else:
            # Negotiation is only 9 bytes, so this fallback slice is rare and
            # only occurs if the socket performs a partial write.
            chunk = data[sent_total:]

        sent = sock.send(chunk)
        if not sent:
            raise OSError("Telnet negotiation send failed")
        sent_total += sent


def _negotiate_telnet(sock):
    """Tell the client that the server handles echo and suppress go-ahead."""
    _send_all(sock, TELNET_NEGOTIATION)


class TelnetWrapper(IOBase):
    def __init__(self, socket):
        self.socket = socket
        # Reuse one fixed receive buffer for the life of the connection.
        # The old implementation created a new bytes object for every recv()
        # and another bytes object for every consumed character via slicing.
        self._input_buffer = bytearray(RX_BUFFER_SIZE)
        self._input_pos = 0
        self._input_len = 0
        self._telnet_state = 0

    def _refill_input_buffer(self):
        try:
            # MicroPython sockets implement the stream API directly. readinto()
            # fills our existing bytearray instead of allocating a new bytes
            # object for each receive.
            count = self.socket.readinto(self._input_buffer)
        except OSError as e:
            if e.args and e.args[0] == errno.EAGAIN:
                return 0
            raise

        if not count:
            return 0

        self._input_pos = 0
        self._input_len = count
        return count

    def _next_data_byte(self):
        while True:
            if self._input_pos >= self._input_len:
                if not self._refill_input_buffer():
                    return None

            byte = self._input_buffer[self._input_pos]
            self._input_pos += 1

            if self._telnet_state == 0:
                if byte == IAC:
                    self._telnet_state = 1
                    continue
                if byte == 0:
                    continue
                return byte

            if self._telnet_state == 1:
                if byte == IAC:
                    self._telnet_state = 0
                    return IAC
                if byte in (WILL, WONT, DO, DONT):
                    self._telnet_state = 2
                    continue
                if byte == SB:
                    self._telnet_state = 3
                    continue
                self._telnet_state = 0
                continue

            if self._telnet_state == 2:
                self._telnet_state = 0
                continue

            if self._telnet_state == 3:
                if byte == IAC:
                    self._telnet_state = 4
                continue

            if self._telnet_state == 4:
                if byte == SE:
                    self._telnet_state = 0
                else:
                    self._telnet_state = 3
                continue

    def readinto(self, b):
        readbytes = 0

        for i in range(len(b)):
            byte = self._next_data_byte()
            if byte is None:
                return readbytes if readbytes else None

            b[i] = byte
            readbytes += 1

        return readbytes

    def write(self, data):
        sent_total = 0
        data_len = len(data)

        while sent_total < data_len:
            try:
                if sent_total == 0:
                    chunk = data
                else:
                    # Most terminal writes complete in one call. Only allocate
                    # a slice when the socket actually performs a partial write.
                    chunk = data[sent_total:]

                sent = self.socket.write(chunk)
                if sent is None:
                    continue
                if not sent:
                    raise OSError("Telnet socket write failed")
                sent_total += sent
            except OSError as e:
                if e.args and e.args[0] == errno.EAGAIN:
                    continue
                raise

        return sent_total

    def close(self):
        try:
            if self.socket is not None:
                self.socket.close()
        except Exception:
            pass

        self.socket = None
        self._input_pos = 0
        self._input_len = 0
        self._telnet_state = 0


def accept_telnet_connect(telnet_server):
    global last_client_socket

    uos.dupterm(None)

    if last_client_socket:
        try:
            last_client_socket.close()
        except Exception:
            pass
        last_client_socket = None

    # Reclaim the previous wrapper and any transient terminal allocations
    # before accepting the replacement connection.
    gc.collect()

    try:
        last_client_socket, remote_addr = telnet_server.accept()
        print("Telnet connection from:", remote_addr)

        _negotiate_telnet(last_client_socket)

        last_client_socket.setblocking(False)
        wrapper = TelnetWrapper(last_client_socket)
        uos.dupterm(wrapper)

        print("[INFO] Telnet client accepted")
        print("[MEM] Free:", gc.mem_free(), "Used:", gc.mem_alloc())
    except Exception as e:
        print("[ERROR] Accept failed:", e)


def stop():
    global server_socket, last_client_socket

    uos.dupterm(None)

    if server_socket:
        try:
            server_socket.close()
        except Exception:
            pass
        server_socket = None

    if last_client_socket:
        try:
            last_client_socket.close()
        except Exception:
            pass
        last_client_socket = None

    gc.collect()
    print("[INFO] Telnet server stopped")
    print("[MEM] Free:", gc.mem_free(), "Used:", gc.mem_alloc())


def start(port=23):
    stop()

    global server_socket

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    ai = socket.getaddrinfo("0.0.0.0", port)
    addr = ai[0][4]

    server_socket.bind(addr)
    server_socket.listen(1)
    server_socket.setsockopt(socket.SOL_SOCKET, 20, accept_telnet_connect)

    # getaddrinfo() and socket setup create temporary objects; clean those up
    # while leaving the listener itself active for recovery/reconnects.
    ai = None
    addr = None
    gc.collect()

    for i in (network.AP_IF, network.STA_IF):
        wlan = network.WLAN(i)
        if wlan.active():
            print("Telnet server started on {}:{}".format(wlan.ifconfig()[0], port))

    print("[MEM] Free:", gc.mem_free(), "Used:", gc.mem_alloc())
