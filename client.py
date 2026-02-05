import socket
import threading
import customtkinter
from cryptography.fernet import Fernet
import datetime
import sys
import time
import os
import struct
import subprocess
import platform
import uuid
import shutil
from tkinter import filedialog, Canvas, messagebox
from PIL import Image, ImageDraw, ImageTk, ImageOps
from plyer import notification

# --- CONFIGURATION ---
SECRET_KEY = b'8coaa93_m5y3bXjW6c8j2q9GjW6c8j2q9G7x8y9z0a1='
cipher_suite = Fernet(SECRET_KEY)
BROADCAST_PORT = 55556
CHAT_PORT = 55555
AVATAR_SIZE = (150, 150)


# --- CRASH CATCHER ---
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # Filter out common benign errors on exit
    if "invalid command name" in str(exc_value): return
    print(f"Error: {exc_value}")


sys.excepthook = handle_exception


# --- HELPER FUNCTIONS ---
def make_circle(input_path, output_path):
    try:
        img = Image.open(input_path).convert("RGBA")
        img = ImageOps.fit(img, AVATAR_SIZE, centering=(0.5, 0.5))
        big_size = (img.size[0] * 4, img.size[1] * 4)
        mask = Image.new('L', big_size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + big_size, fill=255)
        mask = mask.resize(img.size, Image.Resampling.LANCZOS)
        img.putalpha(mask)
        img.save(output_path, "PNG")
        return True
    except:
        return False


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
        try:
            packet = sock.recv(n - len(data))
            if not packet: return None
            data += packet
        except:
            return None
    return data


def open_file(path):
    if platform.system() == 'Windows':
        os.startfile(path)
    elif platform.system() == 'Darwin':
        subprocess.call(('open', path))
    else:
        subprocess.call(('xdg-open', path))


# --- CROPPER ---
class ImageCropperDialog(customtkinter.CTkToplevel):
    def __init__(self, parent, image_path, result_path):
        super().__init__(parent)
        self.title("Crop Profile Picture")
        self.geometry("500x600")
        self.grab_set()
        self.result_path = result_path
        self.cropped_ok = False
        self.view_size = 400
        try:
            self.pil_image = Image.open(image_path)
        except:
            self.destroy(); return
        self.orig_width, self.orig_height = self.pil_image.size
        self.scale = self.view_size / min(self.orig_width, self.orig_height)
        self.offset_x = 0;
        self.offset_y = 0
        pad_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        pad_frame.pack(pady=20)
        self.canvas = Canvas(pad_frame, width=self.view_size, height=self.view_size, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack()
        self.canvas.create_oval(2, 2, self.view_size, self.view_size, outline="#00D26A", width=4, tags="overlay")
        customtkinter.CTkLabel(self, text="Drag to Move • Scroll to Zoom", text_color="gray").pack(pady=5)
        btn_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        customtkinter.CTkButton(btn_frame, text="Cancel", fg_color="#444", command=self.destroy).pack(side="left",
                                                                                                      padx=10)
        customtkinter.CTkButton(btn_frame, text="Save", fg_color="#008069", command=self.save_crop).pack(side="right",
                                                                                                         padx=10)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.redraw()
        self.wait_window()

    def on_mouse_down(self, event):
        self.last_x = event.x; self.last_y = event.y

    def on_mouse_drag(self, event):
        dx = event.x - self.last_x;
        dy = event.y - self.last_y
        self.offset_x += dx;
        self.offset_y += dy
        self.last_x = event.x;
        self.last_y = event.y
        self.redraw()

    def on_mouse_wheel(self, event):
        if event.num == 5 or event.delta < 0:
            zoom = 0.9
        else:
            zoom = 1.1
        new_scale = self.scale * zoom
        if (self.orig_width * new_scale < self.view_size) or (self.orig_height * new_scale < self.view_size): return
        self.scale = new_scale
        self.offset_x = self.offset_x * zoom + (self.view_size / 2) * (1 - zoom)
        self.offset_y = self.offset_y * zoom + (self.view_size / 2) * (1 - zoom)
        self.redraw()

    def redraw(self):
        w = int(self.orig_width * self.scale);
        h = int(self.orig_height * self.scale)
        try:
            resized = self.pil_image.resize((w, h), Image.Resampling.BILINEAR)
            self.tk_image = ImageTk.PhotoImage(resized)
            cx = self.view_size / 2 + self.offset_x;
            cy = self.view_size / 2 + self.offset_y
            self.canvas.delete("image")
            self.canvas.create_image(cx, cy, anchor="center", image=self.tk_image, tags="image")
            self.canvas.tag_raise("overlay")
        except:
            pass

    def save_crop(self):
        cx_view = self.view_size / 2;
        cy_view = self.view_size / 2
        img_cx_view = cx_view + self.offset_x;
        img_cy_view = cy_view + self.offset_y
        vec_x = cx_view - img_cx_view;
        vec_y = cy_view - img_cy_view
        orig_vec_x = vec_x / self.scale;
        orig_vec_y = vec_y / self.scale
        orig_center_x = self.orig_width / 2;
        orig_center_y = self.orig_height / 2
        final_center_x = orig_center_x + orig_vec_x;
        final_center_y = orig_center_y + orig_vec_y
        radius = (self.view_size / 2) / self.scale
        crop_box = (final_center_x - radius, final_center_y - radius, final_center_x + radius, final_center_y + radius)
        cropped = self.pil_image.crop(crop_box)
        temp_path = self.result_path + "_temp.png"
        cropped.save(temp_path)
        if make_circle(temp_path, self.result_path):
            try:
                os.remove(temp_path)
            except:
                pass
            self.cropped_ok = True
            self.destroy()


# --- MAIN APP (SINGLE WINDOW ARCHITECTURE) ---
class ChatApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("480x750")
        self.title("Office Chat")
        self.resizable(False, False)

        # --- SHARED STATE ---
        self.sock = None
        self.nickname = None
        self.final_avatar_path = None
        self.download_dir = os.path.join(os.getcwd(), "Downloads")
        self.avatar_dir = os.path.join(os.getcwd(), "Avatars")

        # Chat State
        self.msg_widgets = {}
        self.msg_labels = {}
        self.edited_labels = {}
        self.avatar_cache = {}
        self.active_menu_window = None
        self.editing_msg_id = None
        self.running = True
        self.is_scanning = False

        # Ensure Directories
        for d in [self.download_dir, self.avatar_dir]:
            if not os.path.exists(d): os.makedirs(d)

        # Fonts
        self.font_msg = customtkinter.CTkFont(family="Segoe UI", size=15)
        self.font_time = customtkinter.CTkFont(family="Segoe UI", size=10)
        self.font_tiny = customtkinter.CTkFont(family="Segoe UI", size=9, slant="italic")
        self.font_menu = customtkinter.CTkFont(family="Segoe UI", size=14, weight="bold")

        # Initial View
        self.build_login_screen()

        # Cleanup on exit
        self.protocol("WM_DELETE_WINDOW", self.on_app_close)

    def on_app_close(self):
        self.running = False
        try:
            self.sock.close()
        except:
            pass
        self.destroy()
        sys.exit(0)

    # --- UI SWAPPER ---
    def clear_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

    # ==========================
    #      LOGIN SCREEN
    # ==========================
    def build_login_screen(self):
        self.clear_screen()
        self.geometry("400x550")

        container = customtkinter.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        customtkinter.CTkLabel(container, text="Employee Login", font=("Segoe UI", 24, "bold")).pack(pady=40)

        customtkinter.CTkButton(container, text="Select Profile Picture", fg_color="#444",
                                command=self.pick_avatar_logic).pack(pady=10)
        self.avatar_preview = customtkinter.CTkLabel(container, text="", text_color="gray")
        self.avatar_preview.pack(pady=5)

        self.entry_id = customtkinter.CTkEntry(container, placeholder_text="Worker ID", width=250)
        self.entry_id.pack(pady=10)

        self.lbl_status = customtkinter.CTkLabel(container, text="", text_color="yellow")
        self.lbl_status.pack(pady=5)

        self.btn_connect = customtkinter.CTkButton(container, text="Connect", fg_color="#2A3942", width=250,
                                                   command=self.start_login_process)
        self.btn_connect.pack(pady=30)

        self.entry_ip = customtkinter.CTkEntry(container, placeholder_text="Manual Server IP (Optional)", width=250)
        self.entry_ip.pack(pady=10)

    # --- LOGIN LOGIC ---
    def pick_avatar_logic(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if not path: return
        uid = uuid.uuid4().hex[:8]
        target = os.path.join(self.avatar_dir, f"temp_{uid}.png")
        cropper = ImageCropperDialog(self, path, target)
        if cropper.cropped_ok:
            self.final_avatar_path = target
            try:
                img = Image.open(target)
                ctk_img = customtkinter.CTkImage(img, size=(80, 80))
                self.avatar_preview.configure(image=ctk_img, text="")
            except:
                pass

    def start_login_process(self):
        worker_id = self.entry_id.get()
        if not worker_id:
            self.lbl_status.configure(text="Enter Worker ID!", text_color="red")
            return

        self.btn_connect.configure(state="disabled", text="Connecting...")
        threading.Thread(target=self.login_thread, args=(worker_id,), daemon=True).start()

    def login_thread(self, worker_id):
        # 1. Find IP
        target_ip = self.entry_ip.get()
        if not target_ip:
            # Auto-Scan
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.settimeout(2.0)
                s.sendto(b'DISCOVER_CHAT', ('255.255.255.255', BROADCAST_PORT))
                data, addr = s.recvfrom(1024)
                if data == b'CHAT_HERE':
                    target_ip = addr[0]
            except:
                pass

        if not target_ip:
            self.after(0, lambda: self.login_failed("Server not found"))
            return

        # 2. Connect & Auth
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target_ip, CHAT_PORT))

            send_packet(sock, f"LOGIN:{worker_id}".encode('ascii'))
            resp = recv_packet(sock)

            if not resp:
                self.after(0, lambda: self.login_failed("Connection rejected"))
                sock.close()
                return

            decoded = resp.decode('ascii')
            if decoded.startswith("LOGIN_OK:"):
                self.nickname = decoded.split(":")[1]
                self.sock = sock

                # *** CRITICAL FIX: REMOVE TIMEOUT FOR CHAT ***
                self.sock.settimeout(None)

                self.after(0, self.setup_chat_session)
            else:
                self.after(0, lambda: self.login_failed("Invalid ID"))
                sock.close()

        except Exception as e:
            self.after(0, lambda: self.login_failed(str(e)))

    def login_failed(self, reason):
        self.lbl_status.configure(text=reason, text_color="red")
        self.btn_connect.configure(state="normal", text="Connect")

    def setup_chat_session(self):
        if self.final_avatar_path:
            dest = os.path.join(self.avatar_dir, f"{self.nickname}_avatar.png")
            try:
                shutil.copy(self.final_avatar_path, dest)
            except:
                pass

        real_av = os.path.join(self.avatar_dir, f"{self.nickname}_avatar.png")
        if os.path.exists(real_av):
            threading.Thread(target=self.upload_avatar_bg, args=(real_av,), daemon=True).start()

        self.build_chat_screen()
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def upload_avatar_bg(self, path):
        try:
            sz = os.path.getsize(path)
            send_packet(self.sock, f"AVATAR:{self.nickname}:{sz}".encode('ascii'))
            with open(path, "rb") as f:
                send_packet(self.sock, f.read())
        except:
            pass

    # ==========================
    #      CHAT SCREEN
    # ==========================
    def build_chat_screen(self):
        self.clear_screen()
        self.geometry("480x750")

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # Header
        head = customtkinter.CTkFrame(self, corner_radius=0, fg_color="#008069")
        head.grid(row=0, column=0, sticky="ew")
        customtkinter.CTkLabel(head, text=f"Logged in as: {self.nickname}", font=("Segoe UI", 18, "bold"),
                               text_color="white").pack(padx=15, pady=15, side="left")

        # Area
        self.chat_area = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.chat_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.chat_area.bind("<Button-1>", lambda e: self.close_menu())

        # Input
        inp = customtkinter.CTkFrame(self, corner_radius=25, fg_color="transparent")
        inp.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        customtkinter.CTkButton(inp, text="+", width=40, height=50, fg_color="#2A3942", font=("Segoe UI", 24),
                                command=self.send_file_action).pack(side="left", padx=5)
        self.msg_entry = customtkinter.CTkEntry(inp, placeholder_text="Type...", height=50, border_width=0,
                                                corner_radius=25, fg_color="#2A3942", text_color="white",
                                                font=self.font_msg)
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.msg_entry.bind("<Return>", self.send_msg_action)

        self.btn_send = customtkinter.CTkButton(inp, text="➤", width=55, height=50, fg_color="#00A884",
                                                command=self.send_msg_action)
        self.btn_send.pack(side="right")

    # --- CHAT ACTIONS ---
    def send_msg_action(self, event=None):
        txt = self.msg_entry.get()
        if not txt:
            if self.editing_msg_id: self.stop_edit_mode()
            return

        if self.editing_msg_id:
            send_packet(self.sock, cipher_suite.encrypt(f"EDIT|{self.editing_msg_id}|{txt}".encode('ascii')))
            self.stop_edit_mode()
        else:
            mid = str(uuid.uuid4())
            send_packet(self.sock, cipher_suite.encrypt(f"MSG|{mid}|{self.nickname}: {txt}".encode('ascii')))
            self.msg_entry.delete(0, 'end')

    def send_file_action(self):
        path = filedialog.askopenfilename()
        if not path: return
        fname = os.path.basename(path);
        size = os.path.getsize(path);
        mid = str(uuid.uuid4())
        try:
            send_packet(self.sock, f"FILE:{self.nickname}:{fname}:{size}:{mid}".encode('ascii'))
            with open(path, "rb") as f:
                send_packet(self.sock, f.read())
            self.add_bubble("Me", path, True, mid, True)
        except:
            pass

    # --- RECEIVE LOOP ---
    def receive_loop(self):
        while self.running:
            try:
                packet = recv_packet(self.sock)
                if not packet: break

                # Handlers
                if packet.startswith(b'AVATAR:'):
                    try:
                        head = packet.decode('ascii')
                        _, nick, size = head.split(":")
                        data = recv_packet(self.sock)
                        with open(os.path.join(self.avatar_dir, f"{nick}_avatar.png"), "wb") as f:
                            f.write(data)
                    except:
                        pass
                    continue

                if packet.startswith(b'FILE:'):
                    try:
                        head = packet.decode('ascii')
                        parts = head.split(':')
                        sender, fname, mid = parts[1], parts[2], parts[4]
                        if len(parts) > 5: fname = ":".join(parts[2:-2])
                        data = recv_packet(self.sock)
                        with open(os.path.join(self.download_dir, fname), "wb") as f:
                            f.write(data)
                        if sender != self.nickname:
                            self.after(0, lambda s=sender, p=os.path.join(self.download_dir, fname),
                                                 i=mid: self.add_bubble(s, p, False, i, True))
                    except:
                        pass
                    continue

                try:
                    decrypted = cipher_suite.decrypt(packet).decode('ascii')

                    if decrypted == "CLEAR_ALL":
                        self.after(0, self.do_clear_screen)
                        continue

                    if decrypted.startswith("MSG|"):
                        _, mid, content = decrypted.split("|", 2)
                        sender, msg = content.split(": ", 1)
                        is_self = (sender == self.nickname)
                        self.after(0, lambda s=sender, m=msg, f=is_self, i=mid: self.add_bubble(s, m, f, i))
                        if not is_self: self.show_notif(sender, msg)

                    elif decrypted.startswith("DEL|"):
                        _, mid = decrypted.split("|", 1)
                        self.after(0, lambda i=mid: self.do_delete_bubble(i))

                    elif decrypted.startswith("EDIT|"):
                        _, mid, txt = decrypted.split("|", 2)
                        self.after(0, lambda i=mid, t=txt: self.do_update_bubble(i, t))

                except:
                    pass
            except:
                break

        if self.running: self.after(0, self.on_server_disconnect)

    def on_server_disconnect(self):
        messagebox.showerror("Error", "Disconnected from Server")
        self.on_app_close()

    # --- UI UPDATES ---
    def do_clear_screen(self):
        for w in self.msg_widgets.values(): w.destroy()
        self.msg_widgets.clear();
        self.msg_labels.clear();
        self.edited_labels.clear()

    def do_delete_bubble(self, mid):
        if mid in self.msg_widgets: self.msg_widgets[mid].destroy()

    def do_update_bubble(self, mid, txt):
        if mid in self.msg_labels:
            self.msg_labels[mid].configure(text=txt)
            if mid in self.edited_labels: self.edited_labels[mid].configure(text="edited")

    def add_bubble(self, sender, content, is_self, msg_id, is_file=False):
        try:
            color = "#005C4B" if is_self else "#202C33"
            align = "e" if is_self else "w"
            name_col = "#34B7F1" if is_self else "#00D26A"

            container = customtkinter.CTkFrame(self.chat_area, fg_color="transparent")
            container.pack(pady=5, fill="x", anchor=align)
            self.msg_widgets[msg_id] = container

            # Avatar
            av_path = os.path.join(self.avatar_dir, f"{sender}_avatar.png")
            if os.path.exists(av_path):
                try:
                    img = Image.open(av_path).convert("RGBA")
                    img = ImageOps.fit(img, (35, 35), centering=(0.5, 0.5))
                    mask = Image.new('L', (35, 35), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, 35, 35), fill=255)
                    img.putalpha(mask)
                    ctk_img = customtkinter.CTkImage(img, size=(35, 35))
                    lbl = customtkinter.CTkLabel(container, text="", image=ctk_img)
                    lbl.pack(side="right" if is_self else "left", padx=5, anchor="n")
                    self.avatar_cache[msg_id] = ctk_img
                except:
                    pass

            bubble = customtkinter.CTkFrame(container, fg_color=color, corner_radius=12)
            bubble.pack(side="right" if is_self else "left", anchor="nw")

            customtkinter.CTkLabel(bubble, text="Me" if is_self else sender, font=("Segoe UI", 13, "bold"),
                                   text_color=name_col).grid(row=0, column=0, sticky="w", padx=12, pady=(6, 0))

            if is_file:
                btn = customtkinter.CTkButton(bubble, text=f"📄 {os.path.basename(content)}", fg_color="#2A3942",
                                              hover_color="#3b4a54", width=200, anchor="w",
                                              command=lambda p=content: open_file(p))
                btn.grid(row=1, column=0, padx=12, pady=4)
            else:
                lbl = customtkinter.CTkLabel(bubble, text=content, font=self.font_msg, text_color="white",
                                             wraplength=280, justify="left")
                lbl.grid(row=1, column=0, padx=12, pady=4)
                self.msg_labels[msg_id] = lbl

            ft = customtkinter.CTkFrame(bubble, fg_color="transparent")
            ft.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))
            self.edited_labels[msg_id] = customtkinter.CTkLabel(ft, text="", font=self.font_tiny, text_color="gray")
            self.edited_labels[msg_id].pack(side="left")
            customtkinter.CTkLabel(ft, text=datetime.datetime.now().strftime("%H:%M"), font=self.font_time,
                                   text_color="gray").pack(side="right")

            if is_self:
                bubble.bind("<Button-3>", lambda e: self.show_context_menu(e, msg_id, content))
                if not is_file: self.msg_labels[msg_id].bind("<Button-3>",
                                                             lambda e: self.show_context_menu(e, msg_id, content))

            self.chat_area._parent_canvas.yview_moveto(1.0)
        except Exception as e:
            print(e)

    def show_context_menu(self, event, msg_id, content):
        self.close_menu()
        menu = customtkinter.CTkToplevel(self)
        menu.wm_overrideredirect(True)
        menu.geometry(f"120x80+{event.x_root}+{event.y_root}")
        menu.attributes('-topmost', True)
        f = customtkinter.CTkFrame(menu, corner_radius=5, border_width=1, border_color="gray")
        f.pack(fill="both", expand=True)
        customtkinter.CTkButton(f, text="Edit", fg_color="transparent", hover_color="#444",
                                command=lambda: [self.start_edit_mode(msg_id, content), self.close_menu()]).pack(
            fill="x")
        customtkinter.CTkButton(f, text="Unsend", fg_color="transparent", hover_color="#500", text_color="red",
                                command=lambda: [self.delete_message(msg_id), self.close_menu()]).pack(fill="x")
        self.active_menu_window = menu
        menu.bind("<FocusOut>", lambda e: self.close_menu())
        menu.focus_force()

    def close_menu(self):
        if self.active_menu_window:
            self.active_menu_window.destroy()
            self.active_menu_window = None

    def start_edit_mode(self, mid, txt):
        if mid in self.msg_labels: txt = self.msg_labels[mid].cget("text")
        self.editing_msg_id = mid
        self.msg_entry.delete(0, 'end')
        self.msg_entry.insert(0, txt)
        self.msg_entry.focus()
        self.msg_entry.configure(border_color="cyan", border_width=2)
        self.btn_send.configure(text="✓")

    def stop_edit_mode(self):
        self.editing_msg_id = None
        self.msg_entry.delete(0, 'end')
        self.msg_entry.configure(border_width=0)
        self.btn_send.configure(text="➤")

    def show_notif(self, sender, message):
        if not self.focus_displayof():
            try:
                notification.notify(title=f"Msg from {sender}", message=message, app_name="Chat", timeout=3)
            except:
                pass


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()