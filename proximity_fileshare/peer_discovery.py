"""
peer_discovery.py
=================
Handles UDP broadcast-based peer discovery.
Each device announces itself on the local network every few seconds.
Other devices listen and maintain an up-to-date "nearby peers" list.
"""

import socket
import threading
import json
import time
import logging

BROADCAST_PORT = 50002
BROADCAST_INTERVAL = 3       # seconds between announcements
PEER_TIMEOUT     = 10        # seconds before a peer is considered gone

logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("discovery")


class PeerDiscovery:
    """
    Announces this node on the LAN and collects announcements from peers.

    peers dict structure:
        { "device_name": { "ip": str, "tcp_port": int, "last_seen": float } }
    """

    def __init__(self, device_name: str, tcp_port: int):
        self.device_name  = device_name
        self.tcp_port     = tcp_port
        self.peers: dict  = {}          # name -> info
        self._lock        = threading.Lock()
        self._running     = False

        # Shared sync folder announced so peers know what you have
        self._announce_payload = json.dumps({
            "device": device_name,
            "port":   tcp_port
        }).encode()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Launch broadcaster and listener threads."""
        self._running = True
        threading.Thread(target=self._broadcaster, daemon=True,
                         name="Broadcaster").start()
        threading.Thread(target=self._listener,    daemon=True,
                         name="Listener").start()
        threading.Thread(target=self._reaper,      daemon=True,
                         name="Reaper").start()
        log.info("Discovery started for device '%s' (TCP port %d)",
                 self.device_name, self.tcp_port)

    def stop(self):
        self._running = False

    def get_peers(self) -> dict:
        """Return a copy of the current peer table."""
        with self._lock:
            return dict(self.peers)

    # ------------------------------------------------------------------
    # Internal threads
    # ------------------------------------------------------------------

    def _broadcaster(self):
        """Send UDP broadcast every BROADCAST_INTERVAL seconds."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                             socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            while self._running:
                sock.sendto(self._announce_payload,
                            ("<broadcast>", BROADCAST_PORT))
                time.sleep(BROADCAST_INTERVAL)
        finally:
            sock.close()

    def _listener(self):
        """Listen for peers' UDP broadcasts."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                             socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", BROADCAST_PORT))
        sock.settimeout(1.0)
        try:
            while self._running:
                try:
                    data, addr = sock.recvfrom(1024)
                    info = json.loads(data.decode())
                    name = info.get("device")
                    port = info.get("port")
                    if name and name != self.device_name:
                        with self._lock:
                            if name not in self.peers:
                                log.info("New peer discovered: %s (%s)", name, addr[0])
                            self.peers[name] = {
                                "ip":        addr[0],
                                "tcp_port":  port,
                                "last_seen": time.time(),
                            }
                except socket.timeout:
                    pass
        finally:
            sock.close()

    def _reaper(self):
        """Remove peers that have gone silent."""
        while self._running:
            time.sleep(PEER_TIMEOUT)
            now = time.time()
            with self._lock:
                gone = [n for n, info in self.peers.items()
                        if now - info["last_seen"] > PEER_TIMEOUT]
                for n in gone:
                    log.info("Peer left: %s", n)
                    del self.peers[n]
