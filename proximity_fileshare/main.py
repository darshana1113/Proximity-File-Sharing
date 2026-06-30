"""
main.py
=======
Entry-point for the Proximity-Based Automatic File Sharing system.

Usage
-----
    python main.py --name "Laptop-A" --folder ./shared_files --port 50001
    python main.py --name "Laptop-B" --folder ./shared_files --port 50002

Interactive commands (once running)
-------------------------------------
    peers               – list nearby devices
    send <file> <peer>  – push a specific file to a named peer
    sendall <file>      – push a file to ALL visible peers
    ls                  – list local sync folder
    help                – show this menu
    quit / exit         – stop
"""

import argparse
import os
import sys
import time
import logging

import file_server_get   # apply FileServer GET patch  (must be before auto_sync import)
from auto_sync import SyncEngine


def parse_args():
    p = argparse.ArgumentParser(
        description="Proximity-Based Automatic File Sharing")
    p.add_argument("--name",   required=True,
                   help="Unique device name on this network")
    p.add_argument("--folder", default="./sync_folder",
                   help="Folder to watch and share  (default: ./sync_folder)")
    p.add_argument("--port",   type=int, default=50001,
                   help="TCP port for file transfer   (default: 50001)")
    p.add_argument("--no-auto-push", action="store_true",
                   help="Disable automatic push to new peers")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Enable verbose logging")
    return p.parse_args()


def print_banner(name, folder, port):
    print("=" * 55)
    print("  📡  Proximity File Sharing – Wireless Comm Project")
    print("=" * 55)
    print(f"  Device : {name}")
    print(f"  Folder : {os.path.abspath(folder)}")
    print(f"  Port   : {port}")
    print("=" * 55)
    print("  Type 'help' for available commands")
    print()


def interactive_loop(engine: SyncEngine):
    while True:
        try:
            raw = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting …")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd   = parts[0].lower()

        # ── peers ───────────────────────────────────────────────
        if cmd == "peers":
            peers = engine.list_peers()
            if not peers:
                print("  (no peers detected yet)")
            else:
                print(f"  {'Name':<20} {'IP':<16} {'Port'}")
                print("  " + "-" * 44)
                for name, info in peers.items():
                    print(f"  {name:<20} {info['ip']:<16} {info['tcp_port']}")

        # ── send <file> <peer> ───────────────────────────────────
        elif cmd == "send":
            if len(parts) < 3:
                print("  Usage: send <filepath> <peer_name>")
                continue
            fpath, peer = parts[1], parts[2]
            if not os.path.isfile(fpath):
                # Try inside sync folder
                fpath2 = os.path.join(engine.sync_folder, parts[1])
                if os.path.isfile(fpath2):
                    fpath = fpath2
                else:
                    print(f"  File not found: {parts[1]}")
                    continue
            ok = engine.send_file_to(peer, fpath)
            print("  ✅ Sent!" if ok else "  ❌ Failed.")

        # ── sendall <file> ───────────────────────────────────────
        elif cmd == "sendall":
            if len(parts) < 2:
                print("  Usage: sendall <filepath>")
                continue
            fpath = parts[1]
            if not os.path.isfile(fpath):
                fpath2 = os.path.join(engine.sync_folder, parts[1])
                if os.path.isfile(fpath2):
                    fpath = fpath2
                else:
                    print(f"  File not found: {parts[1]}")
                    continue
            engine.send_file_to_all(fpath)

        # ── ls ───────────────────────────────────────────────────
        elif cmd == "ls":
            folder = engine.sync_folder
            files  = [f for f in os.listdir(folder)
                      if os.path.isfile(os.path.join(folder, f))]
            if not files:
                print("  (sync folder is empty)")
            else:
                for f in sorted(files):
                    size = os.path.getsize(os.path.join(folder, f))
                    print(f"  {f}  ({size:,} bytes)")

        # ── help ─────────────────────────────────────────────────
        elif cmd == "help":
            print(__doc__)

        # ── quit / exit ──────────────────────────────────────────
        elif cmd in ("quit", "exit", "q"):
            print("Stopping engine …")
            break

        else:
            print(f"  Unknown command: '{cmd}'.  Type 'help' for options.")

    engine.stop()


def main():
    args = parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level,
                        format="[%(asctime)s] %(levelname)s  %(name)s – %(message)s",
                        datefmt="%H:%M:%S")

    print_banner(args.name, args.folder, args.port)

    engine = SyncEngine(
        device_name  = args.name,
        sync_folder  = args.folder,
        tcp_port     = args.port,
        auto_push    = not args.no_auto_push,
    )
    engine.start()

    # Give discovery a moment to warm up
    print("  ⏳  Listening for nearby peers …")
    time.sleep(2)

    interactive_loop(engine)


if __name__ == "__main__":
    main()
