# 🏢 Office LAN Chat

A secure, real-time desktop messaging application designed for internal office networks. Built with Python, this application features a centralized Server Admin Panel and multiple Client instances that communicate via encrypted sockets.

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![GUI](https://img.shields.io/badge/GUI-CustomTkinter-green.svg)
![License](https://img.shields.io/badge/License-MIT-orange.svg)

## ✨ Features

### 🔒 Security & Privacy
* **End-to-End Encryption:** All messages are encrypted using Fernet (AES) before transmission.
* **Local Network Only:** Operates entirely on LAN; no data leaves the office network.

### 🖥️ Client (Employee App)
* **Real-Time Messaging:** Instant message delivery with practically zero latency.
* **File Sharing:** Send documents and images directly through the chat window.
* **Profile Customization:** Crop and upload custom avatars.
* **Message Management:** Edit and unsend messages.
* **Notifications:** Desktop pop-up notifications for new messages.
* **Modern UI:** Sleek "Dark Mode" interface built with CustomTkinter.

### 🛠️ Server (Admin Panel)
* **User Management:** Create, delete, and manage Employee IDs.
* **Live Logs:** View server activity and connection logs in real-time.
* **History Management:** Database storage (SQLite) with options to clear chat history remotely.

---

## 🚀 How to Use

### Option 1: Download the App (No Python Required)
If you just want to use the application, you don't need to install Python.
1.  Go to the **[Releases](https://github.com/YOUR_USERNAME/Office-Lan-Chat/releases)** tab on the right.
2.  Download `OfficeChat_Server.exe` (for the admin) and `OfficeChat_Client.exe` (for employees).
3.  Run the Server first, then run the Clients.

### Option 2: Run from Source Code
If you are a developer and want to modify the code:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/Office-Lan-Chat.git](https://github.com/YOUR_USERNAME/Office-Lan-Chat.git)
    cd Office-Lan-Chat
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Server:**
    ```bash
    python server.py
    ```

4.  **Run the Client:**
    ```bash
    python client.py
    ```

---

## 🛠️ Technologies Used

* **Language:** Python 3.10+
* **GUI Framework:** CustomTkinter (Modern wrapper for Tkinter)
* **Networking:** Native Python `socket` and `threading` libraries.
* **Encryption:** `cryptography` (Fernet symmetric encryption).
* **Database:** SQLite3 (for storing users and message history).
* **Image Processing:** Pillow (PIL).

---

## ⚠️ Important Configuration Note
The application currently uses a hardcoded `SECRET_KEY` in the source code for demonstration purposes. 
**For production environments:** Please generate a new key using `Fernet.generate_key()` and update the `SECRET_KEY` variable in both `server.py` and `client.py` to ensure security.

---

## 📸 Screenshots
*(You can upload screenshots to your repo and link them here later!)*

---

**Created by [Your Name]** *Open Source Project for Portfolio Demonstration*
