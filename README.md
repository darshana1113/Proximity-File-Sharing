# 📡 Proximity File Share

A Python-based proximity file sharing application that enables devices on the same local network to discover each other, exchange files, and synchronize shared folders using UDP and TCP with basic conflict resolution.


## 🌐 Overview

This project is ideal for demonstrating proximity-based communication and file transfer in a wireless networking environment. Devices broadcast their presence over UDP, connect over TCP, and synchronize files between shared folders with built-in conflict handling.

## ✨ Features

- 🔎 Automatic peer discovery on the same local network
- 📁 File synchronization between connected devices
- 📤 Manual file sending to a specific peer or all discovered peers
- ⚠️ Conflict handling using file metadata and MD5 hashing
- 🧰 No external dependencies required

## 🗂️ Project Structure

- [main.py](main.py) – interactive command-line interface
- [auto_sync.py](auto_sync.py) – sync engine that coordinates discovery and transfers
- [file_transfer.py](file_transfer.py) – TCP-based file transfer and file indexing
- [peer_discovery.py](peer_discovery.py) – UDP-based peer discovery
- [file_server_get.py](file_server_get.py) – patch to support file pull requests
- [shared_alice/](shared_alice) – sample shared folder for one device
- [shared_bob/](shared_bob) – sample shared folder for another device
- [demo.py](demo.py) and [demo_test.py](demo_test.py) – demo and test scripts

## ✅ Requirements

- Python 3.8 or higher
- Two devices connected to the same local network
- No third-party packages required

## � Demo / Output Images

You can add screenshots or output images here to showcase the project in action.

```md
c:\Users\Darshana\OneDrive\Desktop\File_Share (1).png

c:\Users\Darshana\OneDrive\Desktop\File_Share (2).png
```

> Place your image files inside an images folder in the repository and update the paths above.

## �🚀 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/proximity-fileshare.git
   cd proximity-fileshare
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies if needed:
   ```bash
   pip install -r requirements.txt
   ```

## ▶️ Usage

Run the application on two devices connected to the same network.

### Device 1
```bash
python main.py --name Alice --folder ./shared_alice --port 50001
```

### Device 2
```bash
python main.py --name Bob --folder ./shared_bob --port 50002
```

### Available commands

- `peers` – show nearby devices
- `send <file> <peer>` – send a file to a specific device
- `sendall <file>` – send a file to all discovered peers
- `ls` – list files in the current sync folder
- `help` – show command help
- `quit` – exit the program

## 🔧 How It Works

1. Each device broadcasts its presence using UDP.
2. Nearby devices are detected and stored as peers.
3. The sync engine compares local and remote file manifests.
4. Missing or newer files are transferred over TCP.
5. Conflicts are handled using file modification time and MD5 hashing.

## ⚠️ Conflict Handling

The system helps avoid accidental overwrites:

- If a file is missing remotely, it is pulled.
- If the remote copy is newer, it may replace the local copy.
- If both versions differ and the local file is newer, the system keeps the local file and saves the incoming one as a `.remote` copy.

## 🚧 Limitations

- Designed for local area networks only
- Discovery is broadcast-based and may be affected by network configuration
- No encryption or authentication is implemented yet

## 📄 License

This project is open for educational and personal use. Add a license of your choice before publishing publicly.

## 🤝 Contributing

Pull requests and improvements are welcome. If you would like to contribute, please open an issue or submit a change proposal.
