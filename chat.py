import os
import sys
import time
import base64
import mimetypes
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials
from firebase_admin import db


def resource_path(filename):
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / filename

    return Path(__file__).resolve().parent / filename


SERVICE_ACCOUNT_FILE = resource_path("pychat-service.json")

DATABASE_URL = (
    "https://pychat-7a057-default-rtdb.firebaseio.com/"
)

MESSAGES_PATH = "messages"

MAX_MESSAGES = 100
MAX_MESSAGE_LENGTH = 2000
MAX_IMAGE_SIZE = 1.5 * 1024 * 1024


RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
GRAY = "\033[90m"
RED = "\033[91m"


def clear_screen():
    os.system(
        "cls" if os.name == "nt" else "clear"
    )


def initialize_firebase():
    if not SERVICE_ACCOUNT_FILE.exists():
        print(
            f"{RED}"
            f"Missing Firebase credentials:"
            f"{RESET} {SERVICE_ACCOUNT_FILE}"
        )

        sys.exit(1)

    try:
        if not firebase_admin._apps:
            certificate = credentials.Certificate(
                str(SERVICE_ACCOUNT_FILE)
            )

            firebase_admin.initialize_app(
                certificate,
                {
                    "databaseURL": DATABASE_URL
                }
            )

        return db.reference(
            MESSAGES_PATH
        )

    except Exception as e:
        print(
            f"{RED}"
            f"Firebase initialization failed:"
            f"{RESET}"
        )

        print(e)

        sys.exit(1)


def validate_username(username):
    username = username.strip()

    if not username:
        return None

    if len(username) > 24:
        return None

    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_-"
    )

    if any(
        char not in allowed
        for char in username
    ):
        return None

    return username


def format_time(timestamp):
    try:
        dt = datetime.fromtimestamp(
            float(timestamp),
            timezone.utc
        ).astimezone()

        return dt.strftime(
            "%H:%M:%S"
        )

    except Exception:
        return "--:--:--"


def get_image_mime(path):
    mime_type, _ = mimetypes.guess_type(
        str(path)
    )

    if not mime_type:
        return None

    if not mime_type.startswith("image/"):
        return None

    return mime_type


def select_image():
    root = tk.Tk()

    root.withdraw()
    root.attributes(
        "-topmost",
        True
    )

    try:
        path = filedialog.askopenfilename(
            parent=root,
            title="Select image",
            filetypes=[
                (
                    "Image files",
                    "*.png *.jpg *.jpeg *.gif *.bmp *.webp"
                ),
                (
                    "PNG files",
                    "*.png"
                ),
                (
                    "JPEG files",
                    "*.jpg *.jpeg"
                ),
                (
                    "GIF files",
                    "*.gif"
                ),
                (
                    "Bitmap files",
                    "*.bmp"
                ),
                (
                    "WebP files",
                    "*.webp"
                ),
                (
                    "All files",
                    "*.*"
                )
            ]
        )

        return path

    finally:
        root.destroy()


class ImagePreview:

    def __init__(
        self,
        message,
        client
    ):
        self.message = message
        self.client = client

        self.window = tk.Tk()

        self.window.title(
            f"PyChat - "
            f"{message.get('content', 'Image')}"
        )

        self.window.geometry(
            "900x700"
        )

        self.window.minsize(
            500,
            400
        )

        self.window.configure(
            bg="#111111"
        )

        self.photo = None
        self.original_data = None

        self.download_running = False

        self.create_ui()
        self.load_image()

        self.window.mainloop()

    def create_ui(self):
        filename = self.message.get(
            "content",
            "image"
        )

        top = tk.Frame(
            self.window,
            bg="#111111"
        )

        top.pack(
            fill="x",
            padx=15,
            pady=(15, 5)
        )

        title = tk.Label(
            top,
            text=filename,
            bg="#111111",
            fg="white",
            font=(
                "Segoe UI",
                12,
                "bold"
            ),
            anchor="w"
        )

        title.pack(
            side="left",
            fill="x",
            expand=True
        )

        self.image_label = tk.Label(
            self.window,
            bg="#111111"
        )

        self.image_label.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=15
        )

        buttons = tk.Frame(
            self.window,
            bg="#111111"
        )

        buttons.pack(
            fill="x",
            padx=15,
            pady=(5, 15)
        )

        self.download_button = tk.Button(
            buttons,
            text="Download",
            command=self.download,
            bg="#222222",
            fg="white",
            activebackground="#333333",
            activeforeground="white",
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2"
        )

        self.download_button.pack(
            side="left"
        )

        close_button = tk.Button(
            buttons,
            text="Close",
            command=self.window.destroy,
            bg="#222222",
            fg="white",
            activebackground="#333333",
            activeforeground="white",
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2"
        )

        close_button.pack(
            side="right"
        )

        self.window.bind(
            "<Configure>",
            self.on_resize
        )

    def load_image(self):
        try:
            data = self.message.get(
                "data"
            )

            if not data:
                messagebox.showerror(
                    "PyChat",
                    "Image data is missing.",
                    parent=self.window
                )

                return

            self.original_data = (
                base64.b64decode(
                    data,
                    validate=True
                )
            )

            self.display_image()

        except Exception as e:
            messagebox.showerror(
                "PyChat",
                f"Failed to load image:\n{e}",
                parent=self.window
            )

    def display_image(self):
        if not self.original_data:
            return

        try:
            from io import BytesIO
            from PIL import Image
            from PIL import ImageTk

            image = Image.open(
                BytesIO(
                    self.original_data
                )
            )

            image.load()

            width = max(
                self.window.winfo_width() - 50,
                400
            )

            height = max(
                self.window.winfo_height() - 130,
                300
            )

            image.thumbnail(
                (
                    width,
                    height
                ),
                Image.Resampling.LANCZOS
            )

            self.photo = ImageTk.PhotoImage(
                image
            )

            self.image_label.configure(
                image=self.photo
            )

            self.image_label.image = (
                self.photo
            )

        except ImportError:
            messagebox.showerror(
                "Missing dependency",
                "Pillow is required.\n\n"
                "Install it with:\n"
                "pip install pillow",
                parent=self.window
            )

        except Exception as e:
            messagebox.showerror(
                "PyChat",
                f"Failed to display image:\n{e}",
                parent=self.window
            )

    def on_resize(self, event):
        if event.widget != self.window:
            return

        if not self.original_data:
            return

        self.display_image()

    def download(self):
        if self.download_running:
            return

        self.download_running = True

        self.download_button.config(
            state="disabled",
            text="Downloading..."
        )

        thread = threading.Thread(
            target=self.download_worker,
            daemon=True
        )

        thread.start()

    def download_worker(self):
        try:
            result = self.client.save_image(
                self.message,
                silent=True
            )

            self.window.after(
                0,
                lambda: self.download_finished(
                    result
                )
            )

        except Exception as e:
            self.window.after(
                0,
                lambda: self.download_failed(
                    str(e)
                )
            )

    def download_finished(
        self,
        result
    ):
        self.download_running = False

        self.download_button.config(
            state="normal",
            text="Download"
        )

        if not result:
            messagebox.showerror(
                "PyChat",
                "Failed to download image.",
                parent=self.window
            )

            return

        messagebox.showinfo(
            "PyChat",
            f"Image saved to:\n{result}",
            parent=self.window
        )

    def download_failed(
        self,
        error
    ):
        self.download_running = False

        self.download_button.config(
            state="normal",
            text="Download"
        )

        messagebox.showerror(
            "Download Error",
            error,
            parent=self.window
        )


class ChatClient:

    def __init__(
        self,
        username,
        firebase_reference
    ):
        self.username = username
        self.firebase_reference = (
            firebase_reference
        )

        self.messages = []

        self.message_lock = (
            threading.Lock()
        )

        self.running = True
        self.listener = None

        self.render_lock = (
            threading.Lock()
        )

    def get_messages(self):
        try:
            data = (
                self.firebase_reference
                .order_by_child(
                    "timestamp"
                )
                .limit_to_last(
                    MAX_MESSAGES
                )
                .get()
            )

            if not data:
                with self.message_lock:
                    self.messages = []

                return []

            messages = []

            if isinstance(data, dict):
                for (
                    message_id,
                    message
                ) in data.items():

                    if not isinstance(
                        message,
                        dict
                    ):
                        continue

                    message_copy = dict(
                        message
                    )

                    message_copy[
                        "_id"
                    ] = message_id

                    messages.append(
                        message_copy
                    )

            messages.sort(
                key=lambda message: float(
                    message.get(
                        "timestamp",
                        0
                    )
                )
            )

            with self.message_lock:
                self.messages = messages

            return messages

        except Exception as e:
            print(
                f"{RED}"
                f"Failed to read messages: "
                f"{e}"
                f"{RESET}"
            )

            return []

    def send_text(
        self,
        content
    ):
        content = content.strip()

        if not content:
            return

        if len(content) > MAX_MESSAGE_LENGTH:
            print(
                f"{RED}"
                f"Message too long. Maximum: "
                f"{MAX_MESSAGE_LENGTH} characters."
                f"{RESET}"
            )

            return

        message = {
            "username": self.username,
            "content": content,
            "type": "text",
            "timestamp": time.time()
        }

        try:
            self.firebase_reference.push(
                message
            )

        except Exception as e:
            print(
                f"{RED}"
                f"Failed to send message: {e}"
                f"{RESET}"
            )

    def upload_image(
        self,
        file_path
    ):
        path = Path(
            file_path.strip().strip('"')
        )

        if not path.exists():
            print(
                f"{RED}"
                "File does not exist."
                f"{RESET}"
            )

            return

        if not path.is_file():
            print(
                f"{RED}"
                "That is not a file."
                f"{RESET}"
            )

            return

        mime_type = get_image_mime(
            path
        )

        if not mime_type:
            print(
                f"{RED}"
                "File is not a supported image."
                f"{RESET}"
            )

            return

        try:
            file_size = path.stat().st_size

        except Exception as e:
            print(
                f"{RED}"
                f"Could not read file size: {e}"
                f"{RESET}"
            )

            return

        if file_size > MAX_IMAGE_SIZE:
            print(
                f"{RED}"
                "Image is too large. "
                "Maximum size is 1.5 MB."
                f"{RESET}"
            )

            return

        try:
            raw_data = path.read_bytes()

            encoded = (
                base64.b64encode(
                    raw_data
                ).decode("ascii")
            )

            message = {
                "username": self.username,
                "content": path.name,
                "type": "image",
                "mime": mime_type,
                "data": encoded,
                "timestamp": time.time()
            }

            self.firebase_reference.push(
                message
            )

            print(
                f"{GREEN}"
                f"Uploaded: {path.name}"
                f"{RESET}"
            )

        except Exception as e:
            print(
                f"{RED}"
                f"Failed to upload image: {e}"
                f"{RESET}"
            )

    def get_message(
        self,
        message_number
    ):
        with self.message_lock:
            messages = list(
                self.messages
            )

        if not messages:
            print(
                f"{RED}"
                "No messages available."
                f"{RESET}"
            )

            return None

        if (
            message_number < 1
            or message_number > len(messages)
        ):
            print(
                f"{RED}"
                f"Invalid message ID. "
                f"Use 1-{len(messages)}."
                f"{RESET}"
            )

            return None

        return messages[
            message_number - 1
        ]

    def save_image(
        self,
        message,
        silent=False
    ):
        if message.get(
            "type"
        ) != "image":

            if not silent:
                print(
                    f"{RED}"
                    "That message is not an image."
                    f"{RESET}"
                )

            return False

        data = message.get(
            "data"
        )

        if not data:
            if not silent:
                print(
                    f"{RED}"
                    "Image data is missing."
                    f"{RESET}"
                )

            return False

        filename = message.get(
            "content",
            "image.png"
        )

        filename = Path(
            filename
        ).name

        downloads = Path(
            "downloads"
        )

        downloads.mkdir(
            exist_ok=True
        )

        output_path = (
            downloads / filename
        )

        if output_path.exists():
            stem = output_path.stem
            suffix = output_path.suffix

            counter = 1

            while output_path.exists():
                output_path = (
                    downloads /
                    f"{stem}_{counter}{suffix}"
                )

                counter += 1

        try:
            decoded = (
                base64.b64decode(
                    data,
                    validate=True
                )
            )

            output_path.write_bytes(
                decoded
            )

            if not silent:
                print(
                    f"{GREEN}"
                    f"Downloaded: "
                    f"{output_path.resolve()}"
                    f"{RESET}"
                )

            return output_path.resolve()

        except Exception as e:
            if not silent:
                print(
                    f"{RED}"
                    f"Failed to download image: {e}"
                    f"{RESET}"
                )

            if silent:
                raise

            return False

    def download_image(
        self,
        message_number
    ):
        message = self.get_message(
            message_number
        )

        if not message:
            return

        self.save_image(
            message
        )

    def preview_image(
        self,
        message_number
    ):
        message = self.get_message(
            message_number
        )

        if not message:
            return

        if message.get(
            "type"
        ) != "image":

            print(
                f"{RED}"
                "That message is not an image."
                f"{RESET}"
            )

            return

        ImagePreview(
            message,
            self
        )

    def render(self):
        with self.render_lock:

            with self.message_lock:
                messages = list(
                    self.messages
                )

            clear_screen()

            print(
                f"{CYAN}{BOLD}"
                "\n"
                "╔══════════════════════════════════════════════════════╗\n"
                "║                                                      ║\n"
                "║                  PyChat CLI                          ║\n"
                "║                                                      ║\n"
                "║             FIREBASE PUBLIC CHAT                     ║\n"
                "║                                                      ║\n"
                "╚══════════════════════════════════════════════════════╝"
                f"{RESET}\n"
            )

            print(
                f"{GRAY}"
                f"Guest: {WHITE}{self.username}"
                f"{GRAY} | /help"
                f"{RESET}"
            )

            print()

            print(
                "─" * 64
            )

            if not messages:
                print(
                    f"{GRAY}"
                    "No messages yet."
                    f"{RESET}"
                )

            else:
                for (
                    index,
                    message
                ) in enumerate(
                    messages,
                    1
                ):

                    username = message.get(
                        "username",
                        "Unknown"
                    )

                    timestamp = format_time(
                        message.get(
                            "timestamp",
                            0
                        )
                    )

                    message_type = (
                        message.get(
                            "type",
                            "text"
                        )
                    )

                    print(
                        f"{GRAY}"
                        f"[{index}] "
                        f"[{timestamp}]"
                        f"{RESET} "
                        f"{GREEN}{username}"
                        f"{RESET}:"
                    )

                    if message_type == "image":

                        filename = message.get(
                            "content",
                            "image"
                        )

                        print(
                            f"  {MAGENTA}"
                            f"[IMAGE #{index}]"
                            f"{RESET} "
                            f"{filename}"
                        )

                    else:

                        content = message.get(
                            "content",
                            ""
                        )

                        print(
                            f"  {content}"
                        )

            print()

            print(
                "─" * 64
            )

            print(
                f"{GRAY}"
                "/help /upload /view /download "
                "/clear /quit"
                f"{RESET}"
            )

    def firebase_event(
        self,
        event
    ):
        if not self.running:
            return

        try:
            if event.event_type in (
                "put",
                "patch"
            ):

                self.get_messages()
                self.render()

        except Exception:
            pass

    def start_listener(self):
        try:
            self.listener = (
                self.firebase_reference.listen(
                    self.firebase_event
                )
            )

        except Exception as e:
            print(
                f"{RED}"
                f"Firebase listener failed: {e}"
                f"{RESET}"
            )

    def start(self):
        self.get_messages()
        self.render()

        listener_thread = (
            threading.Thread(
                target=self.start_listener,
                daemon=True
            )
        )

        listener_thread.start()


def print_help():
    print()

    print(
        f"{CYAN}{BOLD}"
        "PYCHAT COMMANDS"
        f"{RESET}"
    )

    print()

    print(
        f"{WHITE}/help{RESET}"
        "                  Show commands"
    )

    print(
        f"{WHITE}/upload{RESET}"
        "                 Open image picker"
    )

    print(
        f"{WHITE}/upload <path>{RESET}"
        "         Upload image directly"
    )

    print(
        f"{WHITE}/view <id>{RESET}"
        "             Preview an image"
    )

    print(
        f"{WHITE}/download <id>{RESET}"
        "        Download an image"
    )

    print(
        f"{WHITE}/clear{RESET}"
        "                 Clear terminal"
    )

    print(
        f"{WHITE}/quit{RESET}"
        "                  Exit PyChat"
    )

    print()

    print(
        f"{GRAY}"
        "Type a normal message to send it."
        f"{RESET}"
    )

    print()


def welcome_screen():
    clear_screen()

    print(
        f"{CYAN}{BOLD}"
        "\n"
        "╔══════════════════════════════════════════════════════╗\n"
        "║                                                      ║\n"
        "║                  PyChat CLI                          ║\n"
        "║                                                      ║\n"
        "║             FIREBASE PUBLIC CHAT                     ║\n"
        "║                                                      ║\n"
        "╚══════════════════════════════════════════════════════╝"
        f"{RESET}\n"
    )


def login():
    welcome_screen()

    while True:
        username = input(
            f"{GREEN}> {RESET}"
            "Choose guest username: "
        )

        username = validate_username(
            username
        )

        if username:
            return username

        print(
            f"{RED}"
            "Invalid username."
            f"{RESET}"
        )

        print(
            f"{GRAY}"
            "Use 1-24 characters: "
            "letters, numbers, _ or -."
            f"{RESET}"
        )


def command_loop(
    client
):
    while client.running:

        try:
            command = input(
                f"{GREEN}> {RESET}"
            ).strip()

        except KeyboardInterrupt:
            client.running = False
            break

        except EOFError:
            client.running = False
            break

        if not command:
            continue

        if command == "/help":
            client.render()
            print_help()
            continue

        if command == "/clear":
            client.render()
            continue

        if command == "/quit":
            client.running = False

            print(
                f"\n{GRAY}"
                "Goodbye."
                f"{RESET}"
            )

            break

        if command == "/upload":

            selected = select_image()

            if selected:
                client.upload_image(
                    selected
                )

                client.get_messages()
                client.render()

            continue

        if command.startswith(
            "/upload "
        ):

            file_path = (
                command.split(
                    " ",
                    1
                )[1].strip()
            )

            client.upload_image(
                file_path
            )

            client.get_messages()
            client.render()

            continue

        if command == "/view":

            print(
                f"{RED}"
                "Usage: /view <id>"
                f"{RESET}"
            )

            continue

        if command.startswith(
            "/view "
        ):

            value = (
                command.split(
                    " ",
                    1
                )[1].strip()
            )

            try:
                message_number = int(
                    value
                )

                client.preview_image(
                    message_number
                )

            except ValueError:
                print(
                    f"{RED}"
                    "Usage: /view <id>"
                    f"{RESET}"
                )

            continue

        if command == "/download":

            print(
                f"{RED}"
                "Usage: /download <id>"
                f"{RESET}"
            )

            continue

        if command.startswith(
            "/download "
        ):

            value = (
                command.split(
                    " ",
                    1
                )[1].strip()
            )

            try:
                message_number = int(
                    value
                )

                client.download_image(
                    message_number
                )

            except ValueError:
                print(
                    f"{RED}"
                    "Usage: /download <id>"
                    f"{RESET}"
                )

            continue

        client.send_text(
            command
        )


def main():
    username = login()

    print(
        f"\n{GRAY}"
        "Connecting to Firebase..."
        f"{RESET}"
    )

    firebase_reference = (
        initialize_firebase()
    )

    client = ChatClient(
        username,
        firebase_reference
    )

    client.start()

    command_loop(
        client
    )


if __name__ == "__main__":
    main()
