import socket
import network
import uos
import errno
import gc
from uio import IOBase

last_client_socket = None
server_socket = None

class TelnetWrapper(IOBase):
    def __init__(self, socket):
        self.socket = socket
        self.discard_count = 0
        self._input_buffer = b""

    def readinto(self, b):
        readbytes = 0
        for i in range(len(b)):
            byte = 0

            while byte == 0:
                if not self._input_buffer:
                    try:
                        self._input_buffer = self.socket.recv(64)
                    except OSError as e:
                        if e.args and e.args[0] == errno.EAGAIN:
                            return readbytes if readbytes else None
                        raise

                if not self._input_buffer:
                    return readbytes if readbytes else None

                byte = self._input_buffer[0]
                self._input_buffer = self._input_buffer[1:]

                if byte == 0xFF:
                    self.discard_count = 2
                    byte = 0
                elif self.discard_count > 0:
                    self.discard_count -= 1
                    byte = 0
                elif byte == 0:
                    byte = 0  # null byte, discard

            b[i] = byte
            readbytes += 1

        return readbytes

    def write(self, data):
        mv = memoryview(data)
        while len(mv):
            try:
                sent = self.socket.write(mv)
                mv = mv[sent:]
            except OSError as e:
                if e.args and e.args[0] == errno.EAGAIN:
                    continue
                raise

    def close(self):
        try:
            self.socket.close()
        except:
            pass
        self._input_buffer = b""

def accept_telnet_connect(telnet_server):
    global last_client_socket

    uos.dupterm(None)
    if last_client_socket:
        try:
            last_client_socket.close()
        except:
            pass
        last_client_socket = None

    gc.collect()

    try:
        last_client_socket, remote_addr = telnet_server.accept()
        print("Telnet connection from:", remote_addr)
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
        except:
            pass
        server_socket = None

    if last_client_socket:
        try:
            last_client_socket.close()
        except:
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
