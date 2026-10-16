import socket
import network
import uos
import errno
import gc
from uio import IOBase


PICOSHELL_TELNET_VERSION = "0.2.2"

IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240
ECHO = 1
SUPPRESS_GO_AHEAD = 3

last_client_socket = None
server_socket = None


def _send_all(sock, data):
    sent_total = 0
    while sent_total < len(data):
        sent = sock.send(data[sent_total:])
        if not sent:
            raise OSError("Telnet negotiation send failed")
        sent_total += sent


def _negotiate_telnet(sock):
    """Tell the client that the server handles echo and suppress go-ahead."""
    _send_all(
        sock,
        bytes((
            IAC, WILL, ECHO,
            IAC, WILL, SUPPRESS_GO_AHEAD,
            IAC, DO, SUPPRESS_GO_AHEAD,
        )),
    )


class TelnetWrapper(IOBase):
    def __init__(self, socket):
        self.socket = socket
        self._input_buffer = b""
        self._telnet_state = 0

    def _next_data_byte(self):
        while True:
            if not self._input_buffer:
                try:
                    self._input_buffer = self.socket.recv(64)
                except OSError as e:
                    if e.args and e.args[0] == errno.EAGAIN:
                        return None
                    raise

                if not self._input_buffer:
                    return None

            byte = self._input_buffer[0]
            self._input_buffer = self._input_buffer[1:]

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
        mv = memoryview(data)

        while len(mv):
            try:
                sent = self.socket.write(mv)
                if sent is None:
                    continue
                mv = mv[sent:]
            except OSError as e:
                if e.args and e.args[0] == errno.EAGAIN:
                    continue
                raise

    def close(self):
        try:
            self.socket.close()
        except Exception:
            pass
        self._input_buffer = b""


def accept_telnet_connect(telnet_server):
    global last_client_socket

    uos.dupterm(None)

    if last_client_socket:
        try:
            last_client_socket.close()
        except Exception:
            pass
        last_client_socket = None

    gc.collect()

    try:
        last_client_socket, remote_addr = telnet_server.accept()
        print("Telnet connection from:", remote_addr)

        _negotiate_telnet(last_client_socket)

        last_client_socket.setblocking(False)
        uos.dupterm(TelnetWrapper(last_client_socket))

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

    for i in (network.AP_IF, network.STA_IF):
        wlan = network.WLAN(i)
        if wlan.active():
            print("Telnet server started on {}:{}".format(wlan.ifconfig()[0], port))
