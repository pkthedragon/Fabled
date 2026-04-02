"""net.py — LAN networking for Fabled (TCP, newline-delimited JSON)."""
import socket
import threading
import queue
import json

LAN_PORT = 55667
LAN_PROBE_MESSAGE = b"FABLED_PROBE"
LAN_PROBE_REPLY = b"FABLED_HERE"


def probe_lan_host(host_ip: str, timeout: float = 0.2) -> bool:
    host_ip = str(host_ip or "").strip()
    if not host_ip:
        return False
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.settimeout(timeout)
        probe.sendto(LAN_PROBE_MESSAGE, (host_ip, LAN_PORT))
        reply, _ = probe.recvfrom(64)
        return reply == LAN_PROBE_REPLY
    except Exception:
        return False
    finally:
        probe.close()


class _Connection:
    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._inbox: queue.Queue = queue.Queue()
        self._t = threading.Thread(target=self._recv_loop, daemon=True)
        self._t.start()

    def _recv_loop(self):
        buf = ""
        while True:
            try:
                chunk = self._sock.recv(4096).decode("utf-8", errors="replace")
                if not chunk:
                    self._inbox.put({"type": "_disconnect"})
                    return
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            self._inbox.put(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            except Exception:
                self._inbox.put({"type": "_disconnect"})
                return

    def send(self, msg: dict):
        try:
            self._sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        except Exception:
            pass

    def poll(self) -> list:
        msgs = []
        while True:
            try:
                msgs.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return msgs

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass


class LANHost:
    """Binds a server socket and accepts one client connection."""
    def __init__(self):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("", LAN_PORT))
        self._server.listen(1)
        self._server.settimeout(0.05)
        self._probe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._probe_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._probe_socket.bind(("", LAN_PORT))
        self._probe_socket.settimeout(0.05)
        self._conn: _Connection = None
        self.connected = False
        self._t = threading.Thread(target=self._accept_loop, daemon=True)
        self._probe_t = threading.Thread(target=self._probe_loop, daemon=True)
        self._t.start()
        self._probe_t.start()

    def _accept_loop(self):
        while True:
            try:
                sock, _ = self._server.accept()
                self._conn = _Connection(sock)
                self.connected = True
                return
            except socket.timeout:
                continue
            except Exception:
                return

    def _probe_loop(self):
        while True:
            try:
                payload, addr = self._probe_socket.recvfrom(64)
                if payload == LAN_PROBE_MESSAGE:
                    self._probe_socket.sendto(LAN_PROBE_REPLY, addr)
            except socket.timeout:
                continue
            except Exception:
                return

    def send(self, msg: dict):
        if self._conn:
            self._conn.send(msg)

    def poll(self) -> list:
        return self._conn.poll() if self._conn else []

    def local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "unknown"

    def close(self):
        try:
            self._server.close()
        except Exception:
            pass
        try:
            self._probe_socket.close()
        except Exception:
            pass
        if self._conn:
            self._conn.close()


class LANClient:
    """Connects to a LAN host."""
    def __init__(self):
        self._conn: _Connection = None
        self.connected = False
        self.error: str = ""
        self._connecting = False

    def connect_async(self, host_ip: str):
        """Start a background connection attempt."""
        if self._connecting:
            return
        self._connecting = True
        def _try():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((host_ip.strip(), LAN_PORT))
                sock.settimeout(None)
                self._conn = _Connection(sock)
                self.connected = True
            except Exception as e:
                self.error = str(e)
            finally:
                self._connecting = False
        threading.Thread(target=_try, daemon=True).start()

    def send(self, msg: dict):
        if self._conn:
            self._conn.send(msg)

    def poll(self) -> list:
        return self._conn.poll() if self._conn else []

    def close(self):
        if self._conn:
            self._conn.close()
