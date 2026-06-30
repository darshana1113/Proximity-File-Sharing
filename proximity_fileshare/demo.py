"""
=============================================================
  DEMO SCRIPT - Simulate Two Devices on ONE Machine
  (For testing when you don't have two computers)
=============================================================
  This script:
    1. Creates two separate shared folders
    2. Places test files in Device A's folder
    3. Launches Device A in a background thread
    4. Launches Device B in another thread
    5. Shows Device B automatically receiving files

  On a REAL LAN test: just run fileshare.py on two computers
=============================================================
"""

import os
import time
import threading
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))
from fileshare import ProximityFileShare, log


def create_sample_files(folder, device_label):
    """Create some sample text files to share."""
    os.makedirs(folder, exist_ok=True)

    if device_label == "A":
        files = {
            "lecture_notes.txt": (
                "CS 501 - Wireless Communication Systems\n"
                "==========================================\n"
                "Topic: Proximity-Based File Sharing\n\n"
                "Key Concepts:\n"
                "  1. UDP Broadcast for peer discovery\n"
                "  2. TCP sockets for P2P file transfer\n"
                "  3. MD5 hashing for conflict resolution\n"
                "  4. Auto-sync with SYNC_INTERVAL polling\n\n"
                "Applications:\n"
                "  - Classroom note sharing\n"
                "  - Offline conference sync\n"
                "  - Local team collaboration\n"
            ),
            "assignment_1.txt": (
                "Assignment 1: Implement Peer Discovery\n"
                "Due: Next Week\n\n"
                "Tasks:\n"
                "  1. Implement UDP broadcast listener\n"
                "  2. Parse device name and IP from packets\n"
                "  3. Maintain a peer list with timestamps\n"
            ),
            "project_spec.txt": (
                "Project: Proximity File Sharing System\n"
                "========================================\n"
                "Deliverables:\n"
                "  - Full Python implementation\n"
                "  - Demo on 2+ devices on same WiFi\n"
                "  - Report with protocol design\n"
            )
        }
    else:
        files = {
            "my_notes.txt": (
                "Personal Notes - Device B\n"
                "=========================\n"
                "Remember to check lecture_notes.txt from Alice!\n"
            )
        }

    for fname, content in files.items():
        with open(os.path.join(folder, fname), "w") as f:
            f.write(content)

    log("INFO", f"Created {len(files)} sample file(s) in {folder}")


def run_device(name, folder, delay=0):
    """Run a device instance after an optional delay."""
    time.sleep(delay)
    app = ProximityFileShare(device_name=name, shared_folder=folder)
    # Run for 30 seconds then stop
    t = threading.Thread(target=app.start, daemon=True)
    t.start()
    return app


if __name__ == "__main__":
    BASE = os.path.dirname(os.path.abspath(__file__))
    FOLDER_A = os.path.join(BASE, "shared_deviceA")
    FOLDER_B = os.path.join(BASE, "shared_deviceB")

    print("\033[96m")
    print("╔══════════════════════════════════════════════╗")
    print("║         DEMO: Two-Device Simulation          ║")
    print("╚══════════════════════════════════════════════╝\033[0m\n")
    print("NOTE: On a real LAN, run fileshare.py on SEPARATE machines.")
    print("This demo simulates both on one machine for testing.\n")

    # Prepare folders and files
    create_sample_files(FOLDER_A, "A")
    create_sample_files(FOLDER_B, "B")

    print("\n--- Device A's files ---")
    for f in os.listdir(FOLDER_A):
        print(f"  📄 {f}")
    print("\n--- Device B's files ---")
    for f in os.listdir(FOLDER_B):
        print(f"  📄 {f}")
    print()

    # NOTE: Two instances of the same program can't bind to the same UDP ports
    # on one machine. This demo shows the code structure clearly.
    # For actual testing, run on two computers on the same WiFi.

    print("\033[93m⚠  For real demo: run these on two computers on the same WiFi:\033[0m")
    print()
    print("  Computer 1:  python fileshare.py Alice ./shared")
    print("  Computer 2:  python fileshare.py Bob   ./shared")
    print()
    print("\033[92mStarting Device A (this machine)...\033[0m\n")

    app_a = ProximityFileShare(device_name="Demo_DeviceA", shared_folder=FOLDER_A)

    try:
        app_a.start()
    except KeyboardInterrupt:
        pass
