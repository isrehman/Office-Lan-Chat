import socket
import threading
import customtkinter
from cryptography.fernet import Fernet
import struct
import datetime
import sqlite3
import time

# --- CONFIGURATION ---
SECRET_KEY = b'8coaa93_m5y3bXjW6c8j2q9GjW6c8j2q9G7x8y9z0a1='
cipher_suite = Fernet(SECRET_KEY)
BROADCAST_PORT = 55556
CHAT_PORT = 55555


# --- DATABASE MANAGER ---
class DatabaseManager:
    def __init__(self, db_name="server_data.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                msg_id TEXT PRIMARY KEY,
                sender TEXT,
                content TEXT,
                timestamp TEXT,
                is_file INTEGER,
                is_edited INTEGER DEFAULT 0
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                nickname TEXT
            )
        """)
        self.conn.commit()

    def add_user(self, user_id, nickname):
        try:
            self.cursor.execute("INSERT INTO users VALUES (?, ?)", (user_id, nickname))
            self.conn.commit()
            return True
        except:
            return False

    def remove_user(self, user_id):
        self.cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        self.conn.commit()

    def get_user_name(self, user_id):
        self.cursor.execute("SELECT nickname FROM users WHERE user_id=?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_all_users(self):
        self.cursor.execute("SELECT * FROM users")
        return self.cursor.fetchall()

    def save_message(self, msg_id, sender, content, is_file=0):
        try:
            ts = datetime.datetime.now().strftime("%H:%M")
            self.cursor.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, 0)",
                                (msg_id, sender, content, ts, is_file))
            self.conn.commit()
        except:
            pass

    def delete_message(self, msg_id):
        self.cursor.execute("DELETE FROM messages WHERE msg_id=?", (msg_id,))
        self.conn.commit()

    def edit_message(self, msg_id, new_text):
        self.cursor.execute("UPDATE messages SET content=?, is_edited=1 WHERE msg_id=?", (new_text, msg_id))
        self.conn.commit()

    def clear_all_chats(self):
        self.cursor.execute("DELETE FROM messages")
        self.conn.commit()

    def get_chat_history(self):
        self.cursor.execute("SELECT * FROM messages")
        return self.cursor.fetchall()


db = DatabaseManager()


# --- NETWORK HELPERS ---
def send_packet(sock, data_bytes):
    try:
        length = struct.pack('>I', len(data_bytes))
        sock.sendall(length + data_bytes)
    except:
        pass


def recv_packet(sock):
    try:
        raw_len = recv_all(sock, 4)
        if not raw_len: return None
        msg_len = struct.unpack('>I', raw_len)[0]
        return recv_all(sock, msg_len)
    except:
        return None


def recv_all(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet: return None
        data += packet
    return data


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80)); IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


# --- SERVER LOGIC ---
class ChatServer:
    def __init__(self, ip, gui_log_callback):
        self.ip = ip
        self.log = gui_log_callback
        self.clients = []
        self.running = True

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # CRITICAL FIX: Reuse Address to prevent "Address already in use" errors
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # CRITICAL FIX: Bind to 0.0.0.0 to accept connections from ANY IP
        try:
            self.server.bind(('0.0.0.0', CHAT_PORT))
        except Exception as e:
            self.log(f"❌ Error binding port: {e}")
            return

        self.server.listen()

        self.log(f"✅ Server Started.")
        self.log(f"➡ Local IP: {self.ip}")
        self.log("Waiting for workers...")

        threading.Thread(target=self.discovery_responder, daemon=True).start()

        while self.running:
            try:
                client, address = self.server.accept()
                threading.Thread(target=self.handle_login, args=(client, address)).start()
            except:
                break

    def discovery_responder(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind(('', BROADCAST_PORT))
        while self.running:
            try:
                data, addr = udp.recvfrom(1024)
                if data == b'DISCOVER_CHAT': udp.sendto(b'CHAT_HERE', addr)
            except:
                break

    def broadcast(self, packet, source_client=None):
        for client in self.clients:
            if client != source_client:
                send_packet(client, packet)

    def handle_login(self, client, address):
        try:
            packet = recv_packet(client)
            if not packet:
                client.close()
                return

            decoded = packet.decode('ascii')
            if decoded.startswith("LOGIN:"):
                user_id = decoded.split(":")[1]
                nickname = db.get_user_name(user_id)

                if nickname:
                    self.log(f"🔑 Login Success: {nickname} ({address[0]})")
                    response = f"LOGIN_OK:{nickname}"
                    send_packet(client, response.encode('ascii'))

                    time.sleep(0.2)
                    history = db.get_chat_history()
                    for row in history:
                        msg_id, sender, content, ts, is_file, is_edited = row
                        if is_file:
                            full = f"MSG|{msg_id}|System: [File History]: {content}"
                            send_packet(client, cipher_suite.encrypt(full.encode('ascii')))
                        else:
                            full = f"MSG|{msg_id}|{sender}: {content}"
                            send_packet(client, cipher_suite.encrypt(full.encode('ascii')))

                    self.clients.append(client)
                    self.handle_client(client)
                else:
                    self.log(f"⛔ Login Failed: Unknown ID {user_id}")
                    send_packet(client, b"LOGIN_FAIL")
                    client.close()
        except Exception as e:
            client.close()

    def handle_client(self, client):
        while self.running:
            try:
                packet = recv_packet(client)
                if not packet: break

                if packet.startswith(b'FILE:') or packet.startswith(b'AVATAR:'):
                    self.broadcast(packet)
                    file_data = recv_packet(client)
                    self.broadcast(file_data)
                else:
                    try:
                        decrypted = cipher_suite.decrypt(packet).decode('ascii')
                        if decrypted == "CLEAR_ALL":
                            db.clear_all_chats()
                            self.log("⚠ ADMIN: Chat Database Cleared")
                            for c in self.clients: send_packet(c, packet)
                            continue

                        if decrypted.startswith("MSG|"):
                            _, msg_id, content_full = decrypted.split("|", 2)
                            sender, msg = content_full.split(": ", 1)
                            db.save_message(msg_id, sender, msg, 0)
                        elif decrypted.startswith("DEL|"):
                            _, msg_id = decrypted.split("|", 1)
                            db.delete_message(msg_id)
                        elif decrypted.startswith("EDIT|"):
                            _, msg_id, new_text = decrypted.split("|", 2)
                            db.edit_message(msg_id, new_text)

                        for c in self.clients: send_packet(c, packet)
                    except:
                        pass
            except:
                if client in self.clients: self.clients.remove(client); client.close()
                break


# --- ADMIN GUI ---
customtkinter.set_appearance_mode("Dark")
customtkinter.set_default_color_theme("green")


class ServerWindow(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("700x500")
        self.title("Company Server - Admin Panel")
        self.resizable(False, False)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        customtkinter.CTkLabel(self, text="SERVER ADMIN", font=("Segoe UI", 24, "bold"), text_color="#00D26A").grid(
            row=0, column=0, columnspan=2, pady=20)

        # LOGS
        log_frame = customtkinter.CTkFrame(self)
        log_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        customtkinter.CTkLabel(log_frame, text="System Logs", font=("Segoe UI", 14, "bold")).pack(pady=5)
        self.log_box = customtkinter.CTkTextbox(log_frame, width=300, height=300, state="disabled")
        self.log_box.pack(padx=5, pady=5, fill="both", expand=True)
        customtkinter.CTkButton(log_frame, text="🗑 Clear Chat History", fg_color="#802020", hover_color="#501010",
                                command=self.clear_chat_action).pack(pady=10)

        # USERS
        user_frame = customtkinter.CTkFrame(self)
        user_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        customtkinter.CTkLabel(user_frame, text="Worker Management", font=("Segoe UI", 14, "bold")).pack(pady=5)

        self.id_entry = customtkinter.CTkEntry(user_frame, placeholder_text="New ID (e.g. 101)")
        self.id_entry.pack(pady=5)
        self.name_entry = customtkinter.CTkEntry(user_frame, placeholder_text="Worker Name (e.g. John)")
        self.name_entry.pack(pady=5)
        customtkinter.CTkButton(user_frame, text="+ Add Worker", command=self.add_worker).pack(pady=5)

        self.user_list = customtkinter.CTkTextbox(user_frame, width=250, height=150)
        self.user_list.pack(pady=10, padx=5)
        self.refresh_user_list()

        self.del_id_entry = customtkinter.CTkEntry(user_frame, placeholder_text="ID to Remove")
        self.del_id_entry.pack(pady=(20, 5))
        customtkinter.CTkButton(user_frame, text="Remove Worker", fg_color="#cf6679", hover_color="#a84355",
                                command=self.remove_worker).pack(pady=5)

        self.start_server()

    def log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def start_server(self):
        my_ip = get_local_ip()
        self.server_logic = ChatServer(my_ip, self.log)
        threading.Thread(target=self.server_logic.start, daemon=True).start()

    def clear_chat_action(self):
        db.clear_all_chats()
        self.log("⚠ ADMIN CLEARED CHATS")
        if self.server_logic:
            packet = cipher_suite.encrypt(b"CLEAR_ALL")
            for client in self.server_logic.clients:
                send_packet(client, packet)

    def add_worker(self):
        uid = self.id_entry.get()
        name = self.name_entry.get()
        if uid and name:
            if db.add_user(uid, name):
                self.log(f"Added Worker: {name} (ID: {uid})")
                self.id_entry.delete(0, 'end')
                self.name_entry.delete(0, 'end')
                self.refresh_user_list()
            else:
                self.log("Error: ID already exists")

    def remove_worker(self):
        uid = self.del_id_entry.get()
        if uid:
            db.remove_user(uid)
            self.log(f"Removed Worker ID: {uid}")
            self.del_id_entry.delete(0, 'end')
            self.refresh_user_list()

    def refresh_user_list(self):
        self.user_list.configure(state="normal")
        self.user_list.delete("0.0", "end")
        users = db.get_all_users()
        for u in users:
            self.user_list.insert("end", f"ID: {u[0]} | {u[1]}\n")
        self.user_list.configure(state="disabled")


if __name__ == "__main__":
    app = ServerWindow()
    app.mainloop()