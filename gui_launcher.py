import sys
import os
import glob
import importlib
import threading
import time
import math
import pprint
import ctypes

# --- PATH SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(BASE_DIR, "lib")
if os.path.exists(LIB_DIR) and LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import customtkinter

try:
    import minescript
except ImportError:

    class MockMinescript:
        class EventType:
            KEY = "key"

        def echo(self, msg):
            print(f"[MINESCRIPT] {msg}")

        def execute(self, cmd):
            print(f"[EXEC] {cmd}")

        class EventQueue:
            def register_key_listener(self):
                pass

            def get(self, block=False):
                return None

        def screen_name(self):
            return None

    minescript = MockMinescript()

# --- CONFIG MANAGEMENT ---
DEFAULT_CFG = {
    "key_toggle": 344,  # R-Shift
    "shortcuts": {},  # { key_code: "script_name" }
}

CONFIG_PATH = os.path.join(BASE_DIR, "gui_config.py")


def ensure_config_exists():
    if not os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "w") as f:
                f.write(f"CONFIG = {DEFAULT_CFG}\n")
        except Exception as e:
            print(f"Error creating config: {e}")


def save_config():
    try:
        with open(CONFIG_PATH, "w") as f:
            f.write("# GUI Launcher Configuration\n")
            f.write(f"CONFIG = {pprint.pformat(CFG)}\n")
    except Exception as e:
        minescript.echo(f"Error saving config: {e}")


ensure_config_exists()

try:
    import gui_config

    importlib.reload(gui_config)
    CFG = gui_config.CONFIG
except ImportError:
    CFG = DEFAULT_CFG.copy()


def get_shortcut_key_for_script(script_name):
    for k, v in CFG.get("shortcuts", {}).items():
        if v == script_name:
            return k
    return None


def tkinter_to_glfw(keycode):
    if 48 <= keycode <= 57:
        return keycode
    if 65 <= keycode <= 90:
        return keycode
    mapping = {
        13: 257,
        27: 256,
        8: 259,
        46: 261,
        39: 262,
        37: 263,
        40: 264,
        38: 265,
        16: 340,
        17: 341,
        18: 342,
        32: 32,
        9: 258,
    }
    return mapping.get(keycode, keycode)


# --- THEME COLORS ---
COLOR_BG_SIDEBAR = "#181818"
COLOR_BG_MAIN = "#252526"
COLOR_ACCENT = "#3A9E4A"  # Minecraft Greenish
COLOR_ACCENT_HOVER = "#2E803C"
COLOR_TEXT_MAIN = "#EEEEEE"
COLOR_TEXT_DIM = "#AAAAAA"
COLOR_DANGER = "#D32F2F"
COLOR_DANGER_HOVER = "#B71C1C"

# --- CATEGORY ICONS ---
CAT_ICONS = {
    "Mining": "⛏",
    "Construction": "🧱",
    "Travel": "🚇",
    "Combat": "⚔",
    "Farming": "🌾",
    "Settings": "⚙",
    "Uncategorized": "📂",
}


class OverlayApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("BlockyTK")
        self.geometry("850x550")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.96)
        self.configure(fg_color=COLOR_BG_MAIN)
        self.geometry("+100+100")

        self.grid_columnconfigure(0, weight=0, minsize=160)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self.scripts_dir = os.path.join(BASE_DIR, "scripts")
        self.visible = False

        self.script_tree = {}
        self.categories = []

        self.view_mode = "HOME"
        self.selected_category = None
        self.current_script_meta = None
        self.current_module = None
        self.config_vars = {}

        self.running_thread = None
        self.stop_event = threading.Event()
        self.active_script_id = None
        self.binding_mode = False

        # --- UI COMPONENTS ---
        self.setup_ui()
        self.bind("<Key>", self.on_gui_key)

        # --- LOGIC ---
        self.load_scripts()  # This will call render_sidebar which needs render_home
        self.hide_overlay()

        self.event_queue = minescript.EventQueue()
        self.event_queue.register_key_listener()
        self.after(50, self.poll_minescript_events)

        # Initial render based on view_mode = "HOME"
        # Call refresh_ui AFTER load_scripts so script counts are available for home
        self.refresh_ui() 
        minescript.echo("BlockyTK loaded. Press R-Shift to toggle.")
        self.restore_game_focus()
    def restore_game_focus(self):
        """Attempts to find the Minecraft window and restore focus to it."""
        try:
            user32 = ctypes.windll.user32

            # Define callback for EnumWindows
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
            )

            def enum_window_callback(hwnd, lParam):
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True

                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value

                # Heuristic: Check for common Minecraft window titles
                # Modrinth often keeps "Minecraft" in the title
                if user32.IsWindowVisible(hwnd) and ("Minecraft" in title):
                    user32.SetForegroundWindow(hwnd)
                    return False  # Stop enumerating
                return True

            user32.EnumWindows(WNDENUMPROC(enum_window_callback), 0)
        except Exception as e:
            print(f"Failed to restore focus: {e}")

    def setup_ui(self):  # 1. Sidebar (Row 0-2, Col 0)
        self.sidebar = customtkinter.CTkFrame(
            self, fg_color=COLOR_BG_SIDEBAR, corner_radius=0, width=160
        )
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1) # Spacer pushes categories up

        self.logo_lbl = customtkinter.CTkLabel(
            self.sidebar, text="BLOCKYTK", font=("Segoe UI", 20, "bold"), text_color=COLOR_ACCENT
        )
        self.logo_lbl.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Home Button
        self.home_btn = customtkinter.CTkButton(
            self.sidebar,
            text="🏠 Home",
            anchor="w",
            fg_color="transparent",
            text_color=COLOR_TEXT_MAIN,
            hover_color="#333333",
            height=40,
            corner_radius=6,
            font=("Segoe UI", 14),
            command=self.go_home,
        )
        self.home_btn.grid(row=1, column=0, sticky="ew", pady=2, padx=5)

        # Category Container
        self.cat_frame = customtkinter.CTkScrollableFrame(
            self.sidebar, fg_color="transparent"
        )
        self.cat_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

        # 2. Header (Row 0, Col 1) - Drag Handle
        self.header = customtkinter.CTkFrame(
            self, fg_color=COLOR_BG_MAIN, height=40, corner_radius=0
        )
        self.header.grid(row=0, column=1, sticky="ew")

        self.lbl_view_title = customtkinter.CTkLabel(
            self.header,
            text="Dashboard",
            font=("Segoe UI", 18, "bold"),
            text_color=COLOR_TEXT_MAIN,
        )
        self.lbl_view_title.pack(side="left", padx=20, pady=10)

        # Draggable
        self.header.bind("<Button-1>", self.start_move)
        self.header.bind("<B1-Motion>", self.do_move)
        self.lbl_view_title.bind("<Button-1>", self.start_move)
        self.lbl_view_title.bind("<B1-Motion>", self.do_move)

        # 3. Content Area (Row 1, Col 1)
        self.content_area = customtkinter.CTkScrollableFrame(
            self, fg_color="transparent"
        )
        self.content_area.grid(row=1, column=1, sticky="nsew", padx=20, pady=10)

        # 4. Status Bar (Row 2, Col 1)
        self.status_bar = customtkinter.CTkFrame(
            self, fg_color="#1F1F1F", height=30, corner_radius=0
        )
        self.status_bar.grid(row=2, column=1, sticky="ew")

        self.lbl_status = customtkinter.CTkLabel(
            self.status_bar,
            text="Ready",
            font=("Segoe UI", 12),
            text_color=COLOR_TEXT_DIM,
        )
        self.lbl_status.pack(side="left", padx=15)

        self.lbl_hint = customtkinter.CTkLabel(
            self.status_bar,
            text="Toggle: R-Shift",
            font=("Segoe UI", 12),
            text_color="#555",
        )
        self.lbl_hint.pack(side="right", padx=15)

    # --- UI RENDERING METHODS (DEFINED EARLY TO AVOID FORWARD REFERENCE ISSUES) ---

    def clear_content(self):
        for w in self.content_area.winfo_children():
            w.destroy()

    def refresh_ui(self):
        self.render_sidebar()  # Always render sidebar to update highlights
        if self.view_mode == "HOME":
            self.render_home()
        elif self.view_mode == "BROWSER":
            self.render_browser()
        elif self.view_mode == "CONFIG":
            self.render_config()

    def render_sidebar(self):
        # Update Home button highlight
        fg_home = "#333333" if self.view_mode == "HOME" else "transparent"
        text_col_home = COLOR_ACCENT if self.view_mode == "HOME" else COLOR_TEXT_MAIN
        self.home_btn.configure(fg_color=fg_home, text_color=text_col_home)

        # Clear existing category buttons
        for w in self.cat_frame.winfo_children():
            w.destroy()

        for cat in self.categories:
            icon = CAT_ICONS.get(cat, CAT_ICONS["Uncategorized"])
            is_active = cat == self.selected_category and self.view_mode == "BROWSER"
            fg = "#333333" if is_active else "transparent"
            text_col = COLOR_ACCENT if is_active else COLOR_TEXT_MAIN

            btn = customtkinter.CTkButton(
                self.cat_frame,
                text=f"{icon}  {cat}",
                anchor="w",
                fg_color=fg,
                text_color=text_col,
                hover_color="#333333",
                height=40,
                corner_radius=6,
                font=("Segoe UI", 14),
                command=lambda c=cat: self.select_category(c),
            )
            btn.pack(fill="x", pady=2, padx=5)

    def render_home(self):
        self.clear_content()
        self.lbl_view_title.configure(text="Home")
        
        customtkinter.CTkLabel(
            self.content_area, text="Welcome to BlockyTK!", 
            font=("Segoe UI", 24, "bold"), text_color=COLOR_TEXT_MAIN
        ).pack(pady=40)

        total_scripts = sum(len(scripts) for scripts in self.script_tree.values())
        customtkinter.CTkLabel(
            self.content_area,
            text=f"Total Scripts Loaded: {total_scripts}",
            font=("Segoe UI", 16),
            text_color=COLOR_TEXT_DIM,
        ).pack(pady=10)

        active_shortcuts = len(CFG.get("shortcuts", {}))
        customtkinter.CTkLabel(
            self.content_area,
            text=f"Active Shortcuts: {active_shortcuts}",
            font=("Segoe UI", 16),
            text_color=COLOR_TEXT_DIM,
        ).pack(pady=5)

        customtkinter.CTkLabel(
            self.content_area,
            text="Use the sidebar to browse categories or manage settings.",
            font=("Segoe UI", 14),
            text_color=COLOR_TEXT_DIM,
            wraplength=400,
        ).pack(pady=20)

    def render_browser(self):
        self.clear_content()
        self.lbl_view_title.configure(text=f"{self.selected_category}")

        scripts = self.script_tree.get(self.selected_category, [])
        if not scripts:
            customtkinter.CTkLabel(
                self.content_area, text="No scripts found.", text_color="gray"
            ).pack(pady=20)
            return

        for s in scripts:
            # Card
            card = customtkinter.CTkFrame(
                self.content_area, fg_color="#333333", corner_radius=8
            )
            card.pack(fill="x", pady=5)

            # Config Button
            customtkinter.CTkButton(
                card,
                text="Configure",
                width=80,
                fg_color="transparent",
                border_width=1,
                border_color="gray",
                text_color="white",
                hover_color="#444444",
                command=lambda meta=s: self.open_config(meta),
            ).pack(side="right", padx=15)

            # Run/Stop Button
            is_running = self.active_script_id == s["id"]
            btn_text = "Stop" if is_running else "Run"
            btn_fg = COLOR_DANGER if is_running else COLOR_ACCENT
            btn_hover = COLOR_DANGER_HOVER if is_running else COLOR_ACCENT_HOVER

            customtkinter.CTkButton(
                card,
                text=btn_text,
                width=60,
                fg_color=btn_fg,
                hover_color=btn_hover,
                command=lambda meta=s: self.toggle_script(meta),
            ).pack(side="right", padx=(0, 5))

            # Text
            info_frame = customtkinter.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", padx=15, pady=15, fill="both", expand=True)

            customtkinter.CTkLabel(
                info_frame, text=s["title"], font=("Segoe UI", 16, "bold"), anchor="w"
            ).pack(fill="x")

            customtkinter.CTkLabel(
                info_frame,
                text=s["desc"],
                font=("Segoe UI", 12),
                text_color=COLOR_TEXT_DIM,
                anchor="w",
                wraplength=350,
            ).pack(fill="x")

    def render_config(self):
        self.clear_content()
        meta = self.current_script_meta
        self.lbl_view_title.configure(text=f"Config: {meta['title']}")

        # Back Button in content area
        header_frame = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))

        customtkinter.CTkButton(
            header_frame,
            text="← Back to List",
            width=100,
            fg_color="transparent",
            text_color=COLOR_ACCENT,
            anchor="w",
            hover=False,
            command=lambda: self.select_category(self.selected_category),
        ).pack(side="left")

        # Shortcut Binder
        bound_key = get_shortcut_key_for_script(meta["id"])
        btn_text = f"Shortcut: Key {bound_key}" if bound_key else "Shortcut: [None]"
        btn_col = "#444444"
        if self.binding_mode:
            btn_text = "PRESS ANY KEY TO BIND..."
            btn_col = COLOR_ACCENT

        customtkinter.CTkButton(
            header_frame,
            text=btn_text,
            width=150,
            fg_color=btn_col,
            hover_color="#555555",
            command=self.enable_binding_mode,
        ).pack(side="right")

        # Controls
        controls = meta["config"].get("controls", {})
        for key, setting in controls.items():
            row = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
            row.pack(fill="x", pady=8)

            lbl = customtkinter.CTkLabel(
                row, text=setting.get("label", key), anchor="w", font=("Segoe UI", 14)
            )
            lbl.pack(side="left", padx=5)

            stype = setting.get("type", "string")
            var = self.config_vars[key]

            if stype == "bool":
                customtkinter.CTkSwitch(
                    row, text="", variable=var, progress_color=COLOR_ACCENT
                ).pack(side="right")
            elif stype == "dropdown":
                customtkinter.CTkOptionMenu(
                    row,
                    values=setting.get("options", []),
                    variable=var,
                    fg_color="#444",
                    button_color="#555",
                ).pack(side="right")
            elif stype == "int" or stype == "float":
                customtkinter.CTkLabel(row, textvariable=var, width=40).pack(
                    side="right"
                )
                customtkinter.CTkSlider(
                    row,
                    from_=setting.get("min", 0),
                    to=setting.get("max", 100),
                    variable=var,
                    progress_color=COLOR_ACCENT,
                ).pack(side="right", fill="x", expand=True, padx=10)
            else:
                customtkinter.CTkEntry(wrapper, textvariable=var, fg_color="#333").pack(
                    side="right", fill="x", expand=True
                )

        # Action Bar
        action_frame = customtkinter.CTkFrame(self.content_area, fg_color="transparent")
        action_frame.pack(fill="x", pady=30)

        # Check running state
        is_running = self.active_script_id == meta["id"]

        if is_running:
            self.lbl_status.configure(
                text=f"Running: {meta['title']}", text_color=COLOR_ACCENT
            )
            customtkinter.CTkButton(
                action_frame,
                text="STOP SCRIPT",
                fg_color=COLOR_DANGER,
                hover_color=COLOR_DANGER_HOVER,
                height=50,
                font=("Segoe UI", 16, "bold"),
                command=self.stop_script,
            ).pack(fill="x")
            # Progress spinner
            customtkinter.CTkProgressBar(
                action_frame, mode="indeterminate", progress_color=COLOR_ACCENT
            ).pack(fill="x", pady=10)
        else:
            self.lbl_status.configure(text="Ready", text_color=COLOR_TEXT_DIM)
            customtkinter.CTkButton(
                action_frame,
                text="RUN SCRIPT",
                fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT_HOVER,
                height=50,
                font=("Segoe UI", 16, "bold"),
                command=self.run_script,
            ).pack(fill="x")

    def toggle_script(self, meta):
        script_id = meta["id"]
        if self.active_script_id == script_id:
            self.stop_script()
        elif self.active_script_id is not None:
            minescript.echo("Another script is already running. Stop it first.")
        else:
            self.current_script_meta = meta
            self.current_module = meta["module"]
            defaults = {
                k: v.get("default") for k, v in meta["config"]["controls"].items()
            }
            self.start_script_thread(defaults, script_id)

    def clear_content(self):
        for w in self.content_area.winfo_children():
            w.destroy()

    def go_home(self):
        self.view_mode = "HOME"
        self.selected_category = None
        self.refresh_ui()

    def load_scripts(self):
        self.script_tree = {}
        self.categories = []

        if not os.path.exists(self.scripts_dir):
            os.makedirs(self.scripts_dir)

        if self.scripts_dir not in sys.path:
            sys.path.insert(0, self.scripts_dir)

        script_files = glob.glob(os.path.join(self.scripts_dir, "*.py"))
        for f in script_files:
            if "__init__" in f:
                continue

            module_name = os.path.splitext(os.path.basename(f))[0]
            try:
                mod = importlib.import_module(module_name)
                importlib.reload(mod)

                if hasattr(mod, "UI_CONFIG"):
                    conf = mod.UI_CONFIG
                    cat = conf.get("category", "Uncategorized")

                    if cat not in self.script_tree:
                        self.script_tree[cat] = []
                        self.categories.append(cat)

                    meta = {
                        "id": module_name,
                        "module": mod,
                        "title": conf.get("title", module_name),
                        "desc": conf.get("description", ""),
                        "config": conf,
                    }
                    self.script_tree[cat].append(meta)
            except Exception as e:
                print(f"Failed to load {module_name}: {e}")

        self.categories.sort()
        if "Uncategorized" in self.categories:
            self.categories.remove("Uncategorized")
            self.categories.append("Uncategorized")

        self.render_sidebar()

    def select_category(self, category):
        self.selected_category = category
        self.view_mode = "BROWSER"
        self.refresh_ui()

    def open_config(self, meta):
        self.current_script_meta = meta
        self.config_vars = {}
        controls = meta["config"].get("controls", {})
        for key, setting in controls.items():
            stype = setting.get("type", "string")
            default = setting.get("default")

            if stype == "bool":
                self.config_vars[key] = customtkinter.BooleanVar(value=default)
            elif stype == "int":
                self.config_vars[key] = customtkinter.IntVar(value=default)
            elif stype == "float":
                self.config_vars[key] = customtkinter.DoubleVar(value=default)
            else:
                self.config_vars[key] = customtkinter.StringVar(
                    value=str(default) if default is not None else ""
                )

        self.view_mode = "CONFIG"
        self.refresh_ui()

    def go_back(self):
        if self.view_mode == "CONFIG":
            self.select_category(self.selected_category)
        elif self.view_mode == "BROWSER":
            self.go_home()
        else:
            self.hide_overlay()

    # --- INPUT & LOGIC ---
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        x = self.winfo_x() + (event.x - self.x)
        y = self.winfo_y() + (event.y - self.y)
        self.geometry(f"{x}+{y}")

    def toggle_overlay(self):
        if self.visible:
            self.hide_overlay()
        else:
            self.show_overlay()

    def hide_overlay(self):
        self.visible = False
        self.withdraw()

    def show_overlay(self):
        self.visible = True
        self.deiconify()
        self.attributes("-topmost", True)
        self.refresh_ui()

    def on_gui_key(self, event):
        if self.binding_mode and self.view_mode == "CONFIG":
            self.bind_shortcut(tkinter_to_glfw(event.keycode))

    def enable_binding_mode(self):
        self.binding_mode = True
        self.render_config()
        self.focus_force()

    def bind_shortcut(self, key):
        script_id = self.current_script_meta["id"]
        shortcuts = CFG.get("shortcuts", {})
        new_shortcuts = {k: v for k, v in shortcuts.items() if v != script_id}
        new_shortcuts[int(key)] = script_id
        CFG["shortcuts"] = new_shortcuts
        save_config()
        self.binding_mode = False
        self.render_config()

    def poll_minescript_events(self):
        try:
            while True:
                event = self.event_queue.get(block=False)
                if not event:
                    break
                if event.type == minescript.EventType.KEY and event.action == 1:
                    self.handle_game_key(event.key)
        except:
            pass
        self.after(20, self.poll_minescript_events)

    def handle_game_key(self, key):
        if minescript.screen_name() is None:
            if key == CFG["key_toggle"]:
                self.toggle_overlay()
            elif key in CFG.get("shortcuts", {}):
                self.run_shortcut(CFG["shortcuts"][key])

    def run_shortcut(self, script_name):
        meta = None
        for cat, list_ in self.script_tree.items():
            for s in list_:
                if s["id"] == script_name:
                    meta = s
        if not meta:
            return

        if self.running_thread and self.running_thread.is_alive():
            if self.active_script_id == script_name:
                minescript.echo(f"Stopping {script_name}...")
                self.stop_script()
            else:
                minescript.echo("Busy.")
            return

        minescript.echo(f"Starting {script_name}...")
        self.current_script_meta = meta
        self.current_module = meta["module"]

        defaults = {k: v.get("default") for k, v in meta["config"]["controls"].items()}
        self.start_script_thread(defaults, script_name)

    def run_script(self):
        if self.running_thread and self.running_thread.is_alive():
            return
        params = {k: v.get() for k, v in self.config_vars.items()}
        self.start_script_thread(params, self.current_script_meta["id"])

    def start_script_thread(self, params, script_id):
        self.stop_event.clear()
        self.active_script_id = script_id
        if self.visible:
            self.refresh_ui()

        self.running_thread = threading.Thread(
            target=self._worker,
            args=(self.current_module, params, self.stop_event),
            daemon=True,
        )
        self.running_thread.start()

    def _worker(self, mod, params, evt):
        try:
            if hasattr(mod, "run"):
                mod.run(params, evt)
        except Exception as e:
            minescript.echo(f"Error: {e}")
        finally:
            self.after(0, self._finish_run)

    def _finish_run(self):
        self.active_script_id = None
        if self.visible and self.view_mode == "CONFIG":
            self.render_config()
        elif self.visible and self.view_mode == "HOME":
            self.render_home()
        elif self.visible and self.view_mode == "BROWSER":
            self.render_browser()

    def stop_script(self):
        self.stop_event.set()


if __name__ == "__main__":
    customtkinter.set_appearance_mode("Dark")
    app = OverlayApp()
    app.mainloop()
