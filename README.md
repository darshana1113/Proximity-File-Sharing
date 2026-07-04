<div align="center">
📡 Proximity File Share

A Python-based proximity file sharing application that enables devices on the same local network to discover each other, exchange files, and synchronize shared folders using UDP and TCP with basic conflict resolution.

Show Image
Show Image
Show Image
Show Image
Show Image

</div>

📑 Table of Contents


Overview
Features
Project Structure
Requirements
Demo / Output Images
Installation
Usage
How It Works
Conflict Handling
Limitations
License
Contributing



🌐 Overview

This project is ideal for demonstrating proximity-based communication and file transfer in a wireless networking environment. Devices broadcast their presence over UDP, connect over TCP, and synchronize files between shared folders with built-in conflict handling.

✨ Features


🔎 Automatic peer discovery on the same local network
📁 File synchronization between connected devices
📤 Manual file sending to a specific peer or all discovered peers
⚠️ Conflict handling using file metadata and MD5 hashing
🧰 No external dependencies required


🗂️ Project Structure

<details>
<summary><b>Click to view file structure</b></summary>
FileDescriptionmain.pyInteractive command-line interfaceauto_sync.pySync engine that coordinates discovery and transfersfile_transfer.pyTCP-based file transfer and file indexingpeer_discovery.pyUDP-based peer discoveryfile_server_get.pyPatch to support file pull requestsshared_alice/Sample shared folder for one deviceshared_bob/Sample shared folder for another devicedemo.py / demo_test.pyDemo and test scripts

</details>
✅ Requirements


Python 3.8 or higher
Two devices connected to the same local network
No third-party packages required


🖼️ Demo / Output Images

<details>
<summary><b>Click to view screenshots</b></summary>
Show Image
Show Image


Place your image files inside an Images folder in the repository and update the paths above.



</details>
🚀 Installation

<details>
<summary><b>Click to expand setup steps</b></summary>

Clone the repository:


bash   git clone https://github.com/your-username/proximity-fileshare.git
   cd proximity-fileshare


Create and activate a virtual environment (optional but recommended):


bash   python -m venv .venv
   .venv\Scripts\activate


Install dependencies if needed:


bash   pip install -r requirements.txt

</details>
▶️ Usage

Run the application on two devices connected to the same network.

<details open>
<summary><b>Device 1</b></summary>
bashpython main.py --name Alice --folder ./shared_alice --port 50001

</details>
<details open>
<summary><b>Device 2</b></summary>
bashpython main.py --name Bob --folder ./shared_bob --port 50002

</details>
Available commands

CommandDescriptionpeersShow nearby devicessend <file> <peer>Send a file to a specific devicesendall <file>Send a file to all discovered peerslsList files in the current sync folderhelpShow command helpquitExit the program

🔧 How It Works


Each device broadcasts its presence using UDP.
Nearby devices are detected and stored as peers.
The sync engine compares local and remote file manifests.
Missing or newer files are transferred over TCP.
Conflicts are handled using file modification time and MD5 hashing.


⚠️ Conflict Handling

<details>
<summary><b>Click to see how conflicts are resolved</b></summary>
The system helps avoid accidental overwrites:


If a file is missing remotely, it is pulled.
If the remote copy is newer, it may replace the local copy.
If both versions differ and the local file is newer, the system keeps the local file and saves the incoming one as a .remote copy.


</details>
🚧 Limitations


[!NOTE]


Designed for local area networks only
Discovery is broadcast-based and may be affected by network configuration
No encryption or authentication is implemented yet




📄 License

This project is licensed under the MIT License. You are free to use, modify, and distribute this project for educational and learning purposes with appropriate attribution.

🤝 Contributing

Pull requests and improvements are welcome. If you would like to contribute, please open an issue or submit a change proposal.
