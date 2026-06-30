"""
=============================================================
  Proximity-Based Automatic File Sharing System
  Wireless Communication Systems Project
=============================================================
  Modules:
    1. Peer Discovery     - UDP broadcast on LAN
    2. P2P Socket         - Direct TCP file transfer
    3. Auto Sync Logic    - Detect & queue missing files
    4. Conflict Resolution- MD5 hash comparison
=============================================================
"""

import socket
import threading
import os
import json
import hashlib
import time
import struct
import shutil
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
#               CONFIGURATION
# ─────────────────────────────────────────────
DISCOVERY_PORT   = 50000          # UDP broadcast port
TRANSFER_PORT    = 50001          # TCP file transfer port
BROADCAST_INTERVAL = 3           # seconds between broadcasts
SYNC_INTERVAL    = 10            # seconds between full sync cycles
CHUNK_SIZE       = 4096          # bytes per file chunk
BUFFER_SIZE      = 65535         # UDP buffer size
DISCOVER_MSG     = "PROXSHARE_DISCOVER"
HANDSHAKE_MSG    = "PROXSHARE_HELLO"

# ─────────────────────────────────────────────
#               UTILITY FUNCTIONS
# ─────────────────────────────────────────────

def get_local_ip():
    """Get the machine's LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

def get_broadcast_address():
    """Compute broadcast address from local IP (assumes /24 subnet)."""
    ip = get_local_ip()
    parts = ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.255"

def compute_md5(filepath):
    """Compute MD5 hash of a file for conflict detection."""
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def get_file_mtime(filepath):
    """Return file modification timestamp."""
    try:
        return os.path.getmtime(filepath)
    except Exception:
        return 0

def log(tag, message, color_code="\033[97m"):
    """Colored console logger."""
    reset = "\033[0m"
    colors = {
        "INFO":     "\033[96m",   # Cyan
        "DISC":     "\033[92m",   # Green
        "SYNC":     "\033[93m",   # Yellow
        "SEND":     "\033[94m",   # Blue
        "RECV":     "\033[95m",   # Magenta
        "CONFLICT": "\033[91m",   # Red
        "SUCCESS":  "\033[92m",   # Green
        "ERROR":    "\033[91m",   # Red
    }
    c = colors.get(tag, color_code)
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{c}[{ts}] [{tag:8s}] {message}{reset}")


# ─────────────────────────────────────────────
#         MODULE 1: PEER DISCOVERY (UDP)
# ─────────────────────────────────────────────

class PeerDiscovery:
    """
    Broadcasts UDP packets on the LAN so other devices running
    this program can discover each other automatically.

    Protocol:
      Broadcast → "PROXSHARE_DISCOVER:<device_name>:<ip>:<port>"
      Response  → "PROXSHARE_HELLO:<device_name>:<ip>:<port>"
    """

    def __init__(self, device_name, on_peer_found):
        self.device_name   = device_name
        self.local_ip      = get_local_ip()
        self.on_peer_found = on_peer_found   # callback(ip, name)
        self.peers         = {}              # {ip: {name, last_seen}}
        self.running       = False

        # UDP socket for broadcasting
        self.broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.broadcast_sock.settimeout(1)

        # UDP socket for listening
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.listen_sock.bind(("", DISCOVERY_PORT))
        self.listen_sock.settimeout(1)

    def _broadcast_loop(self):
        """Continuously broadcast presence on the network."""
        broadcast_addr = get_broadcast_address()
        msg = f"{DISCOVER_MSG}:{self.device_name}:{self.local_ip}:{TRANSFER_PORT}"
        while self.running:
            try:
                self.broadcast_sock.sendto(
                    msg.encode(),
                    (broadcast_addr, DISCOVERY_PORT)
                )
            except Exception as e:
                log("ERROR", f"Broadcast failed: {e}")
            time.sleep(BROADCAST_INTERVAL)

    def _listen_loop(self):
        """Listen for broadcasts from other devices."""
        while self.running:
            try:
                data, addr = self.listen_sock.recvfrom(BUFFER_SIZE)
                msg = data.decode().strip()
                sender_ip = addr[0]

                # Ignore our own broadcasts
                if sender_ip == self.local_ip:
                    continue

                if msg.startswith(DISCOVER_MSG):
                    parts = msg.split(":")
                    if len(parts) >= 3:
                        peer_name = parts[1]
                        peer_ip   = parts[2]

                        # New peer found!
                        if peer_ip not in self.peers:
                            log("DISC", f"📡 New peer found: {peer_name} @ {peer_ip}")
                            self.peers[peer_ip] = {
                                "name": peer_name,
                                "last_seen": time.time()
                            }
                            self.on_peer_found(peer_ip, peer_name)
                        else:
                            # Update last seen
                            self.peers[peer_ip]["last_seen"] = time.time()

            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    log("ERROR", f"Listen error: {e}")

        # Clean up stale peers (not seen in 15s)
        self._cleanup_peers()

    def _cleanup_peers(self):
        now = time.time()
        stale = [ip for ip, info in self.peers.items()
                 if now - info["last_seen"] > 15]
        for ip in stale:
            log("DISC", f"📴 Peer gone: {self.peers[ip]['name']} @ {ip}")
            del self.peers[ip]

    def start(self):
        self.running = True
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
        threading.Thread(target=self._listen_loop,    daemon=True).start()
        log("INFO", f"🔍 Discovery started. Broadcasting as '{self.device_name}' on {self.local_ip}")

    def stop(self):
        self.running = False
        self.broadcast_sock.close()
        self.listen_sock.close()

    def get_peers(self):
        return dict(self.peers)


# ─────────────────────────────────────────────
#   MODULE 2: FILE TRANSFER SERVER (TCP P2P)
# ─────────────────────────────────────────────

class FileTransferServer:
    """
    TCP server that handles incoming file transfer requests.

    Protocol (binary):
      1. Client sends JSON header (4-byte length prefix + JSON bytes)
         { "type": "FILE_LIST_REQUEST" }
         { "type": "FILE_REQUEST", "filename": "notes.txt" }
      2. Server responds with JSON + binary data
    """

    def __init__(self, shared_folder, device_name):
        self.shared_folder = shared_folder
        self.device_name   = device_name
        self.running       = False
        self.server_sock   = None

    def _send_json(self, conn, data):
        """Send a JSON object prefixed with 4-byte length."""
        payload = json.dumps(data).encode()
        length  = struct.pack("!I", len(payload))
        conn.sendall(length + payload)

    def _recv_json(self, conn):
        """Receive a length-prefixed JSON object."""
        raw_len = self._recv_exact(conn, 4)
        if not raw_len:
            return None
        length = struct.unpack("!I", raw_len)[0]
        data   = self._recv_exact(conn, length)
        if not data:
            return None
        return json.loads(data.decode())

    def _recv_exact(self, conn, n):
        """Read exactly n bytes from socket."""
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _handle_client(self, conn, addr):
        """Handle a single peer connection."""
        try:
            request = self._recv_json(conn)
            if not request:
                return

            req_type = request.get("type")

            # ── Request: List all files ──
            if req_type == "FILE_LIST_REQUEST":
                file_list = self._get_file_metadata()
                self._send_json(conn, {
                    "type":    "FILE_LIST_RESPONSE",
                    "device":  self.device_name,
                    "files":   file_list
                })
                log("INFO", f"📋 Sent file list ({len(file_list)} files) to {addr[0]}")

            # ── Request: Send a specific file ──
            elif req_type == "FILE_REQUEST":
                filename = request.get("filename")
                filepath = os.path.join(self.shared_folder, filename)

                if not os.path.exists(filepath):
                    self._send_json(conn, {"type": "ERROR", "msg": "File not found"})
                    return

                filesize = os.path.getsize(filepath)
                md5      = compute_md5(filepath)
                mtime    = get_file_mtime(filepath)

                # Send metadata header
                self._send_json(conn, {
                    "type":     "FILE_RESPONSE",
                    "filename": filename,
                    "size":     filesize,
                    "md5":      md5,
                    "mtime":    mtime
                })

                # Stream file in chunks
                sent = 0
                with open(filepath, "rb") as f:
                    while chunk := f.read(CHUNK_SIZE):
                        conn.sendall(chunk)
                        sent += len(chunk)

                log("SEND", f"📤 Sent '{filename}' ({filesize:,} bytes) to {addr[0]}")

        except Exception as e:
            log("ERROR", f"Client handler error ({addr[0]}): {e}")
        finally:
            conn.close()

    def _get_file_metadata(self):
        """Return list of {name, size, md5, mtime} for all files in shared folder."""
        files = []
        for fname in os.listdir(self.shared_folder):
            fpath = os.path.join(self.shared_folder, fname)
            if os.path.isfile(fpath):
                files.append({
                    "name":  fname,
                    "size":  os.path.getsize(fpath),
                    "md5":   compute_md5(fpath),
                    "mtime": get_file_mtime(fpath)
                })
        return files

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("", TRANSFER_PORT))
        self.server_sock.listen(10)
        self.server_sock.settimeout(1)
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        log("INFO", f"🖥️  File server listening on port {TRANSFER_PORT}")

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server_sock.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr),
                    daemon=True
                ).start()
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    log("ERROR", f"Accept error: {e}")

    def stop(self):
        self.running = False
        if self.server_sock:
            self.server_sock.close()


# ─────────────────────────────────────────────
#   MODULE 3: FILE TRANSFER CLIENT (TCP P2P)
# ─────────────────────────────────────────────

class FileTransferClient:
    """
    TCP client that connects to a peer and downloads files.
    """

    def __init__(self, shared_folder):
        self.shared_folder = shared_folder

    def _send_json(self, conn, data):
        payload = json.dumps(data).encode()
        length  = struct.pack("!I", len(payload))
        conn.sendall(length + payload)

    def _recv_json(self, conn):
        raw_len = self._recv_exact(conn, 4)
        if not raw_len:
            return None
        length = struct.unpack("!I", raw_len)[0]
        data   = self._recv_exact(conn, length)
        if not data:
            return None
        return json.loads(data.decode())

    def _recv_exact(self, conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def get_peer_file_list(self, peer_ip):
        """Connect to peer and get their file list."""
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(5)
            conn.connect((peer_ip, TRANSFER_PORT))
            self._send_json(conn, {"type": "FILE_LIST_REQUEST"})
            response = self._recv_json(conn)
            conn.close()
            if response and response.get("type") == "FILE_LIST_RESPONSE":
                return response.get("files", [])
        except Exception as e:
            log("ERROR", f"Failed to get file list from {peer_ip}: {e}")
        return []

    def download_file(self, peer_ip, filename, expected_size):
        """Download a specific file from a peer."""
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(30)
            conn.connect((peer_ip, TRANSFER_PORT))
            self._send_json(conn, {"type": "FILE_REQUEST", "filename": filename})

            meta = self._recv_json(conn)
            if not meta or meta.get("type") != "FILE_RESPONSE":
                log("ERROR", f"Bad response for '{filename}' from {peer_ip}")
                conn.close()
                return False

            save_path = os.path.join(self.shared_folder, filename)
            filesize  = meta["size"]
            received  = 0

            with open(save_path, "wb") as f:
                while received < filesize:
                    chunk = conn.recv(min(CHUNK_SIZE, filesize - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)

                    # Progress bar
                    pct  = (received / filesize) * 100
                    bars = int(pct / 5)
                    bar  = "█" * bars + "░" * (20 - bars)
                    print(f"\r  \033[94m[{bar}] {pct:5.1f}% — {filename}\033[0m", end="")

            print()  # newline after progress bar
            conn.close()

            if received == filesize:
                log("RECV", f"📥 Downloaded '{filename}' ({filesize:,} bytes) from {peer_ip}")
                return True
            else:
                log("ERROR", f"Incomplete download: {filename} ({received}/{filesize})")
                os.remove(save_path)
                return False

        except Exception as e:
            log("ERROR", f"Download failed for '{filename}': {e}")
            return False


# ─────────────────────────────────────────────
#  MODULE 4 & 5: AUTO SYNC + CONFLICT RESOLUTION
# ─────────────────────────────────────────────

class SyncEngine:
    """
    Periodically compares local files with each discovered peer
    and downloads any missing or outdated files.

    Conflict Resolution Strategy:
      - If peer has a file you don't → Download it
      - If both have same filename but different MD5:
          → Keep the NEWER version (by mtime)
          → If mtimes equal → Save peer's version as 'filename.conflict_<ip>'
    """

    def __init__(self, shared_folder, transfer_client, peer_discovery):
        self.shared_folder   = shared_folder
        self.client          = transfer_client
        self.discovery       = peer_discovery
        self.running         = False
        self.synced_files    = set()   # track what we've already synced

    def _get_local_file_map(self):
        """Return {filename: {md5, mtime}} for local shared folder."""
        fmap = {}
        for fname in os.listdir(self.shared_folder):
            fpath = os.path.join(self.shared_folder, fname)
            if os.path.isfile(fpath):
                fmap[fname] = {
                    "md5":   compute_md5(fpath),
                    "mtime": get_file_mtime(fpath),
                    "size":  os.path.getsize(fpath)
                }
        return fmap

    def sync_with_peer(self, peer_ip, peer_name):
        """
        Full sync cycle with one peer:
          1. Fetch peer's file list
          2. Compare with local files
          3. Download missing files
          4. Resolve conflicts
        """
        log("SYNC", f"🔄 Syncing with {peer_name} ({peer_ip})...")

        peer_files  = self.client.get_peer_file_list(peer_ip)
        local_files = self._get_local_file_map()

        if not peer_files:
            log("SYNC", f"  No files or unreachable: {peer_name}")
            return

        downloaded = 0
        conflicts  = 0

        for pf in peer_files:
            fname    = pf["name"]
            peer_md5 = pf["md5"]
            peer_mtime = pf.get("mtime", 0)
            peer_size  = pf["size"]

            # ── Case 1: File doesn't exist locally → Download ──
            if fname not in local_files:
                log("SYNC", f"  ➕ Missing file: '{fname}' — downloading...")
                if self.client.download_file(peer_ip, fname, peer_size):
                    downloaded += 1

            # ── Case 2: File exists but different content ──
            elif local_files[fname]["md5"] != peer_md5:
                local_mtime = local_files[fname]["mtime"]

                if peer_mtime > local_mtime:
                    # Peer has newer version → overwrite local
                    log("CONFLICT", f"  🔀 CONFLICT: '{fname}' — peer version is newer → overwriting")
                    if self.client.download_file(peer_ip, fname, peer_size):
                        conflicts += 1

                elif peer_mtime == local_mtime:
                    # Same timestamp, different content → save both
                    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
                    cname = f"{os.path.splitext(fname)[0]}.conflict_{ts}{os.path.splitext(fname)[1]}"
                    log("CONFLICT", f"  ⚠️  CONFLICT: '{fname}' — saving peer copy as '{cname}'")
                    # Temporarily change target filename
                    orig_path = os.path.join(self.shared_folder, fname)
                    conf_path = os.path.join(self.shared_folder, cname)
                    if self.client.download_file(peer_ip, fname, peer_size):
                        # Move just-downloaded file to conflict name
                        shutil.move(orig_path, conf_path)
                        conflicts += 1
                else:
                    # Local version is newer → keep local
                    log("SYNC", f"  ✅ '{fname}' — local version is newer, keeping")

            # ── Case 3: Same MD5 → already in sync ──
            else:
                pass  # in sync, nothing to do

        log("SUCCESS", f"  ✔ Sync done with {peer_name}: {downloaded} downloaded, {conflicts} conflicts resolved")

    def _sync_loop(self):
        """Background loop: sync with all known peers every SYNC_INTERVAL seconds."""
        time.sleep(3)  # brief startup delay
        while self.running:
            peers = self.discovery.get_peers()
            if peers:
                for peer_ip, info in peers.items():
                    self.sync_with_peer(peer_ip, info["name"])
            else:
                log("SYNC", "📭 No peers found yet — waiting...")
            time.sleep(SYNC_INTERVAL)

    def trigger_sync_with(self, peer_ip, peer_name):
        """Immediately sync with a newly discovered peer."""
        threading.Thread(
            target=self.sync_with_peer,
            args=(peer_ip, peer_name),
            daemon=True
        ).start()

    def start(self):
        self.running = True
        threading.Thread(target=self._sync_loop, daemon=True).start()
        log("INFO", f"⚙️  Sync engine started (interval: {SYNC_INTERVAL}s)")

    def stop(self):
        self.running = False


# ─────────────────────────────────────────────
#              MAIN APPLICATION
# ─────────────────────────────────────────────

class ProximityFileShare:
    """
    Main entry point. Ties together all modules:
      Discovery → on_peer_found → immediate sync
      Background sync loop → periodic re-sync
    """

    def __init__(self, device_name, shared_folder):
        self.device_name   = device_name
        self.shared_folder = os.path.abspath(shared_folder)

        # Ensure shared folder exists
        os.makedirs(self.shared_folder, exist_ok=True)

        log("INFO", "=" * 55)
        log("INFO", "  Proximity-Based Automatic File Sharing System")
        log("INFO", "=" * 55)
        log("INFO", f"  Device Name  : {device_name}")
        log("INFO", f"  Local IP     : {get_local_ip()}")
        log("INFO", f"  Shared Folder: {self.shared_folder}")
        log("INFO", f"  Files present: {len(os.listdir(self.shared_folder))}")
        log("INFO", "=" * 55)

        # Wire up modules
        self.transfer_server = FileTransferServer(self.shared_folder, device_name)
        self.transfer_client = FileTransferClient(self.shared_folder)
        self.discovery       = PeerDiscovery(device_name, self._on_peer_found)
        self.sync_engine     = SyncEngine(
            self.shared_folder,
            self.transfer_client,
            self.discovery
        )

    def _on_peer_found(self, peer_ip, peer_name):
        """Called immediately when a new peer is discovered."""
        log("DISC", f"🤝 Initiating immediate sync with new peer: {peer_name}")
        self.sync_engine.trigger_sync_with(peer_ip, peer_name)

    def start(self):
        """Start all modules."""
        self.transfer_server.start()
        self.discovery.start()
        self.sync_engine.start()

        log("INFO", "✅ System running. Press Ctrl+C to stop.\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        log("INFO", "\n🛑 Shutting down...")
        self.sync_engine.stop()
        self.discovery.stop()
        self.transfer_server.stop()
        log("INFO", "👋 Goodbye!")


# ─────────────────────────────────────────────
#                   ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("\033[96m")
    print("╔══════════════════════════════════════════════╗")
    print("║   Proximity-Based Automatic File Sharing     ║")
    print("║   Wireless Communication Systems Project     ║")
    print("╚══════════════════════════════════════════════╝")
    print("\033[0m")

    # Accept device name and folder from command line, or prompt
    if len(sys.argv) == 3:
        name   = sys.argv[1]
        folder = sys.argv[2]
    else:
        name   = input("Enter device name (e.g. Laptop_Alice): ").strip() or "Device_1"
        folder = input("Enter shared folder path (e.g. ./shared): ").strip() or "./shared"

    app = ProximityFileShare(device_name=name, shared_folder=folder)
    app.start()
