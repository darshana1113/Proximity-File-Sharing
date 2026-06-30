"""
demo_test.py
============
Simulates TWO devices on the SAME machine using separate threads and ports.

  Device A  →  port 50001  →  ./demo_A/
  Device B  →  port 50002  →  ./demo_B/

Steps
─────
1. Both devices start and discover each other via UDP broadcast
2. Device A has a pre-seeded file "notes.txt"
3. Auto-sync kicks in → Device B automatically receives "notes.txt"
4. We then manually push a second file from B to A
5. A conflict is simulated by both devices modifying the same file

Run:
    python demo_test.py
"""

import os
import time
import threading
import shutil

import file_server_get              # apply GET patch
from auto_sync import SyncEngine

# ── setup folders ───────────────────────────────────────────────
FOLDER_A = "./demo_A"
FOLDER_B = "./demo_B"

for d in (FOLDER_A, FOLDER_B):
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)

# Seed Device A with a file
with open(os.path.join(FOLDER_A, "notes.txt"), "w") as f:
    f.write("Lecture notes – Chapter 3\n" * 5)

print("=" * 55)
print("  DEMO: Proximity File Sharing System")
print("=" * 55)

# ── start both engines ──────────────────────────────────────────
engine_a = SyncEngine("Device-A", FOLDER_A, tcp_port=50001)
engine_b = SyncEngine("Device-B", FOLDER_B, tcp_port=50002)

engine_a.start()
engine_b.start()

print("[Step 1] Both devices started. Waiting for peer discovery …")
time.sleep(5)

peers_a = engine_a.list_peers()
peers_b = engine_b.list_peers()
print(f"  Device-A sees: {list(peers_a.keys())}")
print(f"  Device-B sees: {list(peers_b.keys())}")

# ── auto-sync will run in background every 8 s ──────────────────
print("\n[Step 2] Auto-sync running … (waiting 12 s for first cycle)")
time.sleep(12)

b_files = os.listdir(FOLDER_B)
print(f"  Device-B folder now contains: {b_files}")

# ── manual push B → A ───────────────────────────────────────────
print("\n[Step 3] Device-B manually pushes 'assignment.txt' → Device-A")
with open(os.path.join(FOLDER_B, "assignment.txt"), "w") as f:
    f.write("Assignment 2 – Wireless Systems\n" * 3)

ok = engine_b.send_file_to("Device-A",
                            os.path.join(FOLDER_B, "assignment.txt"))
print(f"  Push result: {'✅ OK' if ok else '❌ Failed'}")
time.sleep(2)
print(f"  Device-A folder: {os.listdir(FOLDER_A)}")

# ── conflict simulation ──────────────────────────────────────────
print("\n[Step 4] Conflict simulation: both devices edit 'shared.txt'")
# Device A writes first
with open(os.path.join(FOLDER_A, "shared.txt"), "w") as f:
    f.write("Version from Device-A\n")
time.sleep(1)
# Device B writes a different version (newer mtime)
with open(os.path.join(FOLDER_B, "shared.txt"), "w") as f:
    f.write("Version from Device-B (newer)\n")

engine_b.send_file_to("Device-A", os.path.join(FOLDER_B, "shared.txt"))
time.sleep(2)
print(f"  Device-A folder after conflict: {os.listdir(FOLDER_A)}")

# ── shutdown ─────────────────────────────────────────────────────
print("\n[Done] Shutting down …")
engine_a.stop()
engine_b.stop()
print("  Demo complete! Check ./demo_A and ./demo_B for synced files.")
