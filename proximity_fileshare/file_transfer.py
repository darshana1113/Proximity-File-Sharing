"""
file_transfer.py
================
TCP-based file transfer.

  FileServer  – listens for incoming file push requests
  FileClient  – sends a file to a remote FileServer
  FileIndexer – builds a manifest of local files (name + mtime + size + hash)
                used for conflict resolution
"""

import socket
import struct
import os
import hashlib
import json
import threading
import logging
import time

BUFFER_SIZE   = 64 * 1024        # 64 KB read/write chunks
HEADER_FMT    = "!I"             # 4-byte big-endian uint (length prefix)
HEADER_SIZE   = struct.calcsize(HEADER_FMT)

log = logging.getLogger("transfer")


# ───────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────

def _send_msg(sock: socket.socket, data: bytes):
    """Length-prefix a message and send it."""
    sock.sendall(struct.pack(HEADER_FMT, len(data)) + data)

def _recv_msg(sock: socket.socket) -> bytes:
    """Receive a length-prefixed message."""
    raw = _recv_exact(sock, HEADER_SIZE)
    length = struct.unpack(HEADER_FMT, raw)[0]
    return _recv_exact(sock, length)

def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from socket."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("Socket closed unexpectedly")
        buf += chunk
    return buf

def file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(BUFFER_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


# ───────────────────────────────────────────────
# File Indexer
# ───────────────────────────────────────────────

class FileIndexer:
    """
    Scans a folder and produces a manifest:
      { filename: { "size": int, "mtime": float, "md5": str } }
    """

    def __init__(self, folder: str):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)

    def manifest(self) -> dict:
        result = {}
        for fname in os.listdir(self.folder):
            path = os.path.join(self.folder, fname)
            if os.path.isfile(path):
                result[fname] = {
                    "size":  os.path.getsize(path),
                    "mtime": os.path.getmtime(path),
                    "md5":   file_md5(path),
                }
        return result

    def full_path(self, filename: str) -> str:
        return os.path.join(self.folder, filename)


# ───────────────────────────────────────────────
# File Server  (runs on receiving device)
# ───────────────────────────────────────────────

class FileServer:
    """
    Listens on a TCP port.
    Protocol per connection:
      1. Client sends JSON header  { "action": "push" | "list",
                                     "filename": str,  "size": int,
                                     "md5": str, "sender": str }
      2. For "push" : client streams raw bytes; server saves file
         For "list" : server sends back JSON manifest
      3. Server sends JSON response { "status": "ok" | "conflict" | ... }
    """

    def __init__(self, port: int, sync_folder: str, device_name: str):
        self.port         = port
        self.indexer      = FileIndexer(sync_folder)
        self.device_name  = device_name
        self._sock        = None
        self._running     = False
        self._callbacks   = []      # optional: (event, data) hooks for the UI

    def on_event(self, cb):
        """Register a callback(event:str, data:dict)."""
        self._callbacks.append(cb)

    def _emit(self, event, data=None):
        for cb in self._callbacks:
            try:
                cb(event, data or {})
            except Exception:
                pass

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", self.port))
        self._sock.listen(10)
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True,
                         name="FileServer").start()
        log.info("File server listening on port %d", self.port)

    def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()

    # ── accept loop ──────────────────────────────

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._sock.accept()
                threading.Thread(target=self._handle,
                                 args=(conn, addr),
                                 daemon=True).start()
            except OSError:
                break

    def _handle(self, conn: socket.socket, addr):
        try:
            header = json.loads(_recv_msg(conn).decode())
            action = header.get("action")

            if action == "list":
                manifest = self.indexer.manifest()
                _send_msg(conn, json.dumps(manifest).encode())

            elif action == "push":
                self._receive_file(conn, header)

        except Exception as e:
            log.error("Error handling connection from %s: %s", addr, e)
        finally:
            conn.close()

    # ── receive a file ────────────────────────────

    def _receive_file(self, conn: socket.socket, header: dict):
        filename  = os.path.basename(header["filename"])   # sanitise
        file_size = header["size"]
        remote_md5 = header.get("md5", "")
        sender    = header.get("sender", "unknown")

        dest_path = self.indexer.full_path(filename)

        # Conflict check: file exists AND content differs AND remote is older
        conflict = self._detect_conflict(dest_path, header)
        if conflict:
            log.warning("Conflict detected for '%s' – keeping local copy, "
                        "saving remote as *.remote", filename)
            dest_path += ".remote"
            self._emit("conflict", {"filename": filename, "sender": sender})

        log.info("Receiving '%s' (%d bytes) from %s …", filename, file_size, sender)
        received = 0
        with open(dest_path, "wb") as f:
            while received < file_size:
                chunk = conn.recv(min(BUFFER_SIZE, file_size - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)

        # Verify integrity
        actual_md5 = file_md5(dest_path)
        if remote_md5 and actual_md5 != remote_md5:
            log.error("MD5 mismatch for '%s'! File may be corrupt.", filename)
            _send_msg(conn, json.dumps({"status": "md5_error"}).encode())
            os.remove(dest_path)
        else:
            log.info("Saved '%s' OK", filename)
            _send_msg(conn, json.dumps({"status": "ok"}).encode())
            self._emit("received", {"filename": filename, "sender": sender})

    def _detect_conflict(self, local_path: str, header: dict) -> bool:
        if not os.path.exists(local_path):
            return False
        local_md5    = file_md5(local_path)
        remote_md5   = header.get("md5", "")
        remote_mtime = header.get("mtime", 0)
        local_mtime  = os.path.getmtime(local_path)
        # Different content AND local file is newer → conflict
        return (local_md5 != remote_md5) and (local_mtime > remote_mtime)


# ───────────────────────────────────────────────
# File Client  (runs on sending device)
# ───────────────────────────────────────────────

class FileClient:
    """
    Connects to a remote FileServer and either:
      • pushes a file  (action="push")
      • queries remote manifest  (action="list")
    """

    def __init__(self, device_name: str):
        self.device_name = device_name

    def push_file(self, ip: str, port: int, file_path: str) -> bool:
        """
        Send a file to (ip, port).
        Returns True on success.
        """
        filename  = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        md5       = file_md5(file_path)
        mtime     = os.path.getmtime(file_path)

        header = {
            "action":   "push",
            "filename": filename,
            "size":     file_size,
            "md5":      md5,
            "mtime":    mtime,
            "sender":   self.device_name,
        }

        try:
            with socket.create_connection((ip, port), timeout=10) as sock:
                _send_msg(sock, json.dumps(header).encode())

                sent = 0
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(BUFFER_SIZE), b""):
                        sock.sendall(chunk)
                        sent += len(chunk)
                        pct = sent / file_size * 100
                        print(f"\r  Sending {filename}: {pct:5.1f}%", end="", flush=True)
                print()  # newline after progress

                response = json.loads(_recv_msg(sock).decode())
                if response.get("status") == "ok":
                    log.info("Pushed '%s' to %s successfully", filename, ip)
                    return True
                else:
                    log.error("Push failed: %s", response)
                    return False
        except Exception as e:
            log.error("Failed to push '%s' to %s:%d – %s", filename, ip, port, e)
            return False

    def list_remote(self, ip: str, port: int) -> dict:
        """
        Ask the remote server for its file manifest.
        Returns a dict or {} on failure.
        """
        try:
            with socket.create_connection((ip, port), timeout=5) as sock:
                _send_msg(sock, json.dumps({"action": "list"}).encode())
                data = _recv_msg(sock)
                return json.loads(data.decode())
        except Exception as e:
            log.error("Could not list remote %s:%d – %s", ip, port, e)
            return {}
