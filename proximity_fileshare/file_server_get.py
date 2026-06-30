"""
file_server_get.py  (patch – monkey-patches FileServer to support "get" action)
===========================================================
When auto_sync.py calls _pull_file(), the server needs to handle action="get".
This module patches FileServer._handle() to support it.

Import this ONCE before starting the SyncEngine:
    import file_server_get   # noqa
"""

import json
import os
import logging
from file_transfer import FileServer, _send_msg, _recv_msg, BUFFER_SIZE, file_md5

log = logging.getLogger("transfer")

_original_handle = FileServer._handle   # keep reference


def _patched_handle(self, conn, addr):
    try:
        header = json.loads(_recv_msg(conn).decode())
        action = header.get("action")

        if action == "list":
            manifest = self.indexer.manifest()
            _send_msg(conn, json.dumps(manifest).encode())

        elif action == "push":
            self._receive_file(conn, header)

        elif action == "get":
            filename = os.path.basename(header.get("filename", ""))
            path     = self.indexer.full_path(filename)
            if not os.path.isfile(path):
                _send_msg(conn, json.dumps({"status": "not_found"}).encode())
                return
            file_size = os.path.getsize(path)
            md5       = file_md5(path)
            mtime     = os.path.getmtime(path)
            hdr = {"status": "ok", "size": file_size, "md5": md5, "mtime": mtime}
            _send_msg(conn, json.dumps(hdr).encode())
            sent = 0
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(BUFFER_SIZE), b""):
                    conn.sendall(chunk)
                    sent += len(chunk)
            log.info("Served '%s' (%d bytes) to %s", filename, sent, addr[0])
        else:
            _send_msg(conn, json.dumps({"status": "unknown_action"}).encode())

    except Exception as e:
        log.error("Error handling connection from %s: %s", addr, e)
    finally:
        conn.close()


FileServer._handle = _patched_handle   # apply patch
