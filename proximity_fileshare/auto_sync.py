"""
auto_sync.py
============
The SyncEngine ties discovery + transfer together.

How it works
────────────
1. Every SYNC_INTERVAL seconds it asks the FileServer on each nearby peer
   for its file manifest.
2. For each file the peer has that we DO NOT have (or that the peer has a
   newer version of), we pull it automatically.
3. Optionally, we can also PUSH every local file to every new peer
   (one-time push when the peer is first seen).
"""

import threading
import time
import logging
import os

from peer_discovery import PeerDiscovery
from file_transfer  import FileServer, FileClient, FileIndexer, file_md5

SYNC_INTERVAL = 8   # seconds between full sync sweeps

log = logging.getLogger("sync")


class SyncEngine:

    def __init__(self,
                 device_name: str,
                 sync_folder: str,
                 tcp_port:    int  = 50001,
                 auto_push:   bool = True):

        self.device_name  = device_name
        self.sync_folder  = sync_folder
        self.tcp_port     = tcp_port
        self.auto_push    = auto_push

        self.discovery    = PeerDiscovery(device_name, tcp_port)
        self.server       = FileServer(tcp_port, sync_folder, device_name)
        self.client       = FileClient(device_name)
        self.indexer      = FileIndexer(sync_folder)

        self._seen_peers: set = set()    # for "first sight" push
        self._running         = False

        # Wire up events from FileServer
        self.server.on_event(self._on_server_event)

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    def start(self):
        log.info("Starting SyncEngine as '%s' | folder: %s | port: %d",
                 self.device_name, self.sync_folder, self.tcp_port)
        os.makedirs(self.sync_folder, exist_ok=True)
        self.server.start()
        self.discovery.start()
        self._running = True
        threading.Thread(target=self._sync_loop, daemon=True,
                         name="SyncLoop").start()

    def stop(self):
        self._running = False
        self.server.stop()
        self.discovery.stop()
        log.info("SyncEngine stopped.")

    # ──────────────────────────────────────────────
    # Manual operations (call from CLI / UI)
    # ──────────────────────────────────────────────

    def send_file_to(self, peer_name: str, file_path: str) -> bool:
        """Push a specific file to a named peer."""
        peers = self.discovery.get_peers()
        if peer_name not in peers:
            log.error("Peer '%s' not found", peer_name)
            return False
        p = peers[peer_name]
        return self.client.push_file(p["ip"], p["tcp_port"], file_path)

    def send_file_to_all(self, file_path: str):
        """Push a file to all currently visible peers."""
        for name, info in self.discovery.get_peers().items():
            log.info("Pushing '%s' to peer '%s'", file_path, name)
            self.client.push_file(info["ip"], info["tcp_port"], file_path)

    def list_peers(self):
        return self.discovery.get_peers()

    # ──────────────────────────────────────────────
    # Sync loop (pull-based)
    # ──────────────────────────────────────────────

    def _sync_loop(self):
        while self._running:
            time.sleep(SYNC_INTERVAL)
            self._do_sync()

    def _do_sync(self):
        peers = self.discovery.get_peers()
        if not peers:
            return

        local_manifest = self.indexer.manifest()

        for peer_name, info in peers.items():
            # First-time push: send all local files to the new peer
            if self.auto_push and peer_name not in self._seen_peers:
                self._seen_peers.add(peer_name)
                log.info("First contact with '%s' – pushing local files …", peer_name)
                self._push_all_to(info)

            # Pull: fetch files peer has that we need
            remote_manifest = self.client.list_remote(info["ip"], info["tcp_port"])
            for fname, rmeta in remote_manifest.items():
                need = self._should_pull(fname, rmeta, local_manifest)
                if need:
                    log.info("Pulling '%s' from peer '%s' …", fname, peer_name)
                    # Re-use push in reverse: ask peer to push, or pull directly
                    # Here we trigger a pull by requesting the peer to push to us.
                    # Simplest approach: connect and GET the file.
                    self._pull_file(info["ip"], info["tcp_port"], fname, rmeta)

    def _push_all_to(self, peer_info: dict):
        for fname in os.listdir(self.sync_folder):
            path = os.path.join(self.sync_folder, fname)
            if os.path.isfile(path):
                self.client.push_file(peer_info["ip"],
                                      peer_info["tcp_port"],
                                      path)

    def _should_pull(self, fname: str, rmeta: dict, local_manifest: dict) -> bool:
        """
        Pull if:
          • we don't have the file at all, OR
          • we have it but the remote version is newer AND has different content
        """
        if fname not in local_manifest:
            return True
        lmeta = local_manifest[fname]
        return (lmeta["md5"] != rmeta["md5"] and
                rmeta["mtime"] > lmeta["mtime"])

    def _pull_file(self, ip: str, port: int, filename: str, rmeta: dict):
        """
        Ask the remote server to push the file to us.
        We do this by sending a special "get" action.
        """
        import socket, struct, json
        from file_transfer import _send_msg, _recv_msg, _recv_exact, BUFFER_SIZE, file_md5
        import os

        request = {"action": "get", "filename": filename}
        dest_path = self.indexer.full_path(filename)

        try:
            with socket.create_connection((ip, port), timeout=10) as sock:
                _send_msg(sock, json.dumps(request).encode())
                # Server sends header first
                hdr_data = _recv_msg(sock)
                hdr = json.loads(hdr_data.decode())
                if hdr.get("status") == "not_found":
                    log.warning("Remote says '%s' not found", filename)
                    return
                file_size = hdr["size"]
                received  = 0
                with open(dest_path, "wb") as f:
                    while received < file_size:
                        chunk = sock.recv(min(BUFFER_SIZE, file_size - received))
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)
                actual_md5 = file_md5(dest_path)
                if actual_md5 != rmeta.get("md5", actual_md5):
                    log.error("MD5 mismatch pulling '%s'", filename)
                    os.remove(dest_path)
                else:
                    log.info("Pulled '%s' OK", filename)
        except Exception as e:
            log.error("Pull failed for '%s': %s", filename, e)

    # ──────────────────────────────────────────────
    # Event handler
    # ──────────────────────────────────────────────

    def _on_server_event(self, event: str, data: dict):
        if event == "received":
            print(f"\n  ✅  Received '{data['filename']}' from {data['sender']}")
        elif event == "conflict":
            print(f"\n  ⚠️   Conflict on '{data['filename']}' "
                  f"from {data['sender']} → saved as .remote")
