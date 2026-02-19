import json
import sqlite3
import tkinter as tk
import hashlib
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import *
from contract_generator import CONFIG_PATH, generate_contract_from_gui, load_config

DB_PATH = Path(__file__).with_name("contract_suite.db")
APP_BRAND = "AQ Creativity"
LOGO_FILE_NAME = "logo.png"
LOGO_CANDIDATES = (LOGO_FILE_NAME, "aq_creativity_logo.gif", "aq_creativity_logo.pgm", "aq_creativity_logo.ppm")

STATUS_COLORS = {
    "NEW": "#eeeeee",
    "MARKETING": "#cfe2ff",
    "LEGAL": "#ffe6cc",
    "APPROVED": "#d4edda",
    "SENT": "#e0ccff",
    "DONE": "#c6f6d5",
}

FALLBACK_VENDORS = ["Ali Tech", "Sara Beauty", "Omar Food", "Lama Travel"]


class SearchableCombo(ttk.Combobox):
    def __init__(self, master, values, **kwargs):
        super().__init__(master, values=values, **kwargs)
        self.full = list(values)
        self.bind("<KeyRelease>", self.filter)

    def set_values(self, values):
        self.full = list(values)
        self["values"] = self.full

    def filter(self, _):
        txt = self.get().lower()
        self["values"] = [v for v in self.full if txt in v.lower()] or self.full


class ContractSuiteDB:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, brand TEXT NOT NULL DEFAULT '', amount TEXT NOT NULL DEFAULT '',
                contract_type TEXT NOT NULL DEFAULT 'auto', status TEXT NOT NULL DEFAULT 'NEW',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                vendor TEXT NOT NULL DEFAULT '', channel TEXT NOT NULL DEFAULT '', platforms TEXT NOT NULL DEFAULT '',
                ad_type TEXT NOT NULL DEFAULT 'Store Visit', qty TEXT NOT NULL DEFAULT '1', details TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                license_number TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bank_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_id INTEGER NOT NULL,
                bank_name TEXT NOT NULL, account_name TEXT NOT NULL, iban TEXT NOT NULL UNIQUE,
                account_number TEXT NOT NULL, swift_code TEXT, created_at TEXT NOT NULL,
                FOREIGN KEY(vendor_id) REFERENCES vendors(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS generated_contracts (
                contract_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, brand_name TEXT NOT NULL,
                amount TEXT NOT NULL, contract_type TEXT NOT NULL, generated_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TEXT NOT NULL,
                last_login TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_username TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()


    def _password_hash(self, password: str):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def now(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def create_task(self, task_id: str, contract_type: str = "auto", status: str = "NEW"):
        now = self.now()
        self.conn.execute("INSERT INTO tasks(id, brand, amount, contract_type, status, created_at, updated_at) VALUES (?, '', '', ?, ?, ?, ?)", (task_id, contract_type, status, now, now))
        self.conn.commit()

    def delete_task(self, task_id: str):
        # Clean dependent rows first to avoid FK failures on existing DBs.
        self.conn.execute("DELETE FROM generated_contracts WHERE task_id = ?", (task_id,))
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def upsert_task(self, task_id: str, brand: str, amount: str, contract_type: str, status: str):
        self.conn.execute("UPDATE tasks SET brand=?, amount=?, contract_type=?, status=?, updated_at=? WHERE id=?", (brand, amount, contract_type, status, self.now(), task_id))
        self.conn.commit()

    def list_tasks(self):
        return self.conn.execute(
            """
            SELECT t.id, t.brand, t.status, t.amount, t.contract_type,
                   COUNT(s.id) AS vendor_count, DATE(t.created_at) AS created_date
            FROM tasks t LEFT JOIN subtasks s ON s.task_id=t.id
            GROUP BY t.id, t.brand, t.status, t.amount, t.contract_type, t.created_at
            ORDER BY t.created_at DESC
            """
        ).fetchall()

    def get_task(self, task_id: str):
        return self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    def list_subtasks(self, task_id: str):
        return self.conn.execute("SELECT id, vendor, channel, platforms, ad_type, qty, details FROM subtasks WHERE task_id=? ORDER BY id", (task_id,)).fetchall()

    def create_subtask(self, task_id: str, vendor: str, channel: str, platforms: str, ad_type: str, qty: str, details: str):
        now = self.now()
        self.conn.execute(
            "INSERT INTO subtasks(task_id,vendor,channel,platforms,ad_type,qty,details,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (task_id, vendor, channel, platforms, ad_type, qty, details, now, now),
        )
        self.conn.commit()

    def update_subtask(self, subtask_id: int, vendor: str, channel: str, platforms: str, ad_type: str, qty: str, details: str):
        self.conn.execute(
            "UPDATE subtasks SET vendor=?, channel=?, platforms=?, ad_type=?, qty=?, details=?, updated_at=? WHERE id=?",
            (vendor, channel, platforms, ad_type, qty, details, self.now(), subtask_id),
        )
        self.conn.commit()

    def delete_subtask(self, subtask_id: int):
        self.conn.execute("DELETE FROM subtasks WHERE id=?", (subtask_id,))
        self.conn.commit()

    def log_generated_contract(self, contract_id: str, task_id: str, brand_name: str, amount: str, contract_type: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO generated_contracts(contract_id,task_id,brand_name,amount,contract_type,generated_at) VALUES (?,?,?,?,?,?)",
            (contract_id, task_id, brand_name, amount, contract_type, self.now()),
        )
        self.conn.commit()

    def list_generated_contracts_for_task(self, task_id: str):
        return self.conn.execute(
            "SELECT contract_id, generated_at FROM generated_contracts WHERE task_id=? ORDER BY generated_at DESC",
            (task_id,),
        ).fetchall()

    def get_setting(self, key: str, default: str = ""):
        row = self.conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        self.conn.execute(
            "INSERT INTO app_settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def count_users(self):
        row = self.conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        return int(row["total"]) if row else 0

    def create_user(self, username: str, password: str, role: str = "member"):
        clean_username = username.strip()
        if not clean_username:
            raise ValueError("Username is required")
        if len(password) < 4:
            raise ValueError("Password must be at least 4 characters")

        self.conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (clean_username, self._password_hash(password), role, self.now()),
        )
        self.conn.commit()

    def authenticate_user(self, username: str, password: str):
        clean_username = username.strip()
        row = self.conn.execute(
            "SELECT id, username, role FROM users WHERE username=? AND password_hash=?",
            (clean_username, self._password_hash(password)),
        ).fetchone()
        if row:
            self.conn.execute("UPDATE users SET last_login=? WHERE id=?", (self.now(), row["id"]))
            self.conn.commit()
        return row

    def reset_password_by_email(self, email: str, new_password: str):
        clean_email = email.strip().lower()
        if not clean_email:
            raise ValueError("Email is required")
        if len(new_password) < 4:
            raise ValueError("Password must be at least 4 characters")

        cur = self.conn.execute("UPDATE users SET password_hash=? WHERE lower(username)=?", (self._password_hash(new_password), clean_email))
        self.conn.commit()
        return cur.rowcount

    def reset_all_accounts(self):
        self.conn.execute("DELETE FROM users")
        self.conn.commit()

    def set_recovery_key(self, recovery_key: str):
        clean_key = recovery_key.strip()
        if len(clean_key) < 6:
            raise ValueError("Recovery key must be at least 6 characters")
        self.set_setting("recovery_key_hash", self._password_hash(clean_key))

    def has_recovery_key(self):
        return bool(self.get_setting("recovery_key_hash", ""))

    def verify_recovery_key(self, recovery_key: str):
        stored_hash = self.get_setting("recovery_key_hash", "")
        if not stored_hash:
            return False
        return stored_hash == self._password_hash(recovery_key.strip())

    def clear_recovery_key(self):
        self.conn.execute("DELETE FROM app_settings WHERE key='recovery_key_hash'")
        self.conn.commit()

    def log_audit(self, actor_username: str, action: str, entity_type: str, entity_id: str = "", details: str = ""):
        self.conn.execute(
            "INSERT INTO audit_logs(actor_username, action, entity_type, entity_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (actor_username or "unknown", action, entity_type, entity_id, details, self.now()),
        )
        self.conn.commit()

    def list_recent_audit(self, limit: int = 100):
        return self.conn.execute(
            "SELECT actor_username, action, entity_type, entity_id, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def get_license_numbers(self):
        return [r["license_number"] for r in self.conn.execute("SELECT license_number FROM vendors ORDER BY license_number").fetchall()]

    def get_vendor_name_by_license(self, license_number: str):
        row = self.conn.execute("SELECT name FROM vendors WHERE license_number=?", (license_number,)).fetchone()
        if row and row["name"] and row["name"].strip():
            return row["name"].strip()
        return ""

    def get_vendor_profile_by_name(self, vendor_name: str):
        return self.conn.execute(
            """
            SELECT v.name, v.license_number, ba.bank_name, ba.account_name, ba.iban, ba.account_number, COALESCE(ba.swift_code, '') AS swift_code
            FROM vendors v
            LEFT JOIN bank_accounts ba ON ba.vendor_id=v.id
            WHERE v.name=?
            ORDER BY ba.id DESC
            LIMIT 1
            """,
            (vendor_name,),
        ).fetchone()

    def get_vendor_names(self):
        return [r["name"] for r in self.conn.execute("SELECT DISTINCT name FROM vendors ORDER BY name").fetchall()]

    def upsert_brand(self, name: str):
        if not name:
            return
        self.conn.execute("INSERT INTO brands(name,created_at) VALUES (?,?) ON CONFLICT(name) DO NOTHING", (name, self.now()))
        self.conn.commit()

    def get_all_brands(self):
        rows = self.conn.execute("SELECT name AS brand FROM brands UNION SELECT DISTINCT brand FROM tasks WHERE brand!='' ORDER BY brand").fetchall()
        return [r["brand"] for r in rows if r["brand"]]

    def get_ibans_for_license(self, license_number: str):
        rows = self.conn.execute(
            "SELECT ba.iban FROM bank_accounts ba JOIN vendors v ON ba.vendor_id=v.id WHERE v.license_number=? ORDER BY ba.iban",
            (license_number,),
        ).fetchall()
        return [r["iban"] for r in rows]

    def get_bank_info_by_iban(self, iban: str):
        return self.conn.execute(
            "SELECT bank_name,account_name,account_number,COALESCE(swift_code,'') AS swift_code FROM bank_accounts WHERE iban=?",
            (iban,),
        ).fetchone()

    def upsert_vendor_bank(self, vendor_name: str, license_number: str, bank_name: str, account_name: str, iban: str, account_number: str, swift_code: str):
        if not license_number:
            return
        now = self.now()
        self.conn.execute(
            "INSERT INTO vendors(name,license_number,created_at) VALUES (?,?,?) ON CONFLICT(license_number) DO UPDATE SET name=excluded.name",
            (vendor_name or "", license_number, now),
        )
        vendor_id = self.conn.execute("SELECT id FROM vendors WHERE license_number=?", (license_number,)).fetchone()["id"]
        if iban:
            self.conn.execute(
                """
                INSERT INTO bank_accounts(vendor_id,bank_name,account_name,iban,account_number,swift_code,created_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(iban) DO UPDATE SET vendor_id=excluded.vendor_id, bank_name=excluded.bank_name,
                    account_name=excluded.account_name, account_number=excluded.account_number, swift_code=excluded.swift_code
                """,
                (vendor_id, bank_name or "", account_name or "", iban, account_number or "", swift_code or "", now),
            )
        self.conn.commit()

    def close(self):
        self.conn.close()


def create_task_id(existing_ids):
    nums = [int(i[1:]) for i in existing_ids if i.startswith("C") and i[1:].isdigit()]
    return f"C{(max(nums)+1 if nums else 1000):04d}"


class ContractSuiteApp:
    def __init__(self):
        self.db = ContractSuiteDB(DB_PATH)
        self.editing_subtask_id = None
        self.dashboard_window = None
        self.dashboard_rows = {}
        self.current_user = None

        self.root = tk.Tk()

        icon_path = Path(__file__).with_name("icon.png")
        if icon_path.exists():
            icon = tk.PhotoImage(file=str(icon_path))
            self.root.iconphoto(True, icon)

        self.app_title_var = tk.StringVar(value=self.db.get_setting("app_title", APP_BRAND))
        self.default_type_setting = tk.StringVar(value=self.db.get_setting("default_contract_type", "auto"))
        self.default_status_setting = tk.StringVar(value=self.db.get_setting("default_status", "NEW"))
        self.theme_setting = tk.StringVar(value=self.db.get_setting("theme_mode", "dark"))

        self.root.title(f"{self.app_title_var.get() or APP_BRAND} – Dashboard")
        self.logo_image = None
        self.apply_theme(self.theme_setting.get())
        self.root.geometry("1300x860")
        self.root.minsize(1180, 760)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.current_task = tk.StringVar()
        self.brand_var = tk.StringVar()
        self.amount_var = tk.StringVar()
        self.status_var = tk.StringVar(value="NEW")
        self.template_key_var = tk.StringVar(value="auto")
        self.available_template_keys = []

        self.search_var = tk.StringVar()
        self.status_filter = tk.StringVar(value="ALL")
        self.brand_filter = tk.StringVar(value="ALL")

        self.license_var = tk.StringVar()
        self.iban_var = tk.StringVar()
        self.vendor_name_auto_var = tk.StringVar()  # read-only autofill
        self.bank_name_var = tk.StringVar()
        self.account_name_var = tk.StringVar()
        self.account_number_var = tk.StringVar()
        self.swift_code_var = tk.StringVar()

        self.vendor_var = tk.StringVar()
        self.channel_var = tk.StringVar()
        self.type_sub_var = tk.StringVar(value="Store Visit")
        self.qty_var = tk.StringVar(value="1")
        self.detail_var = tk.StringVar()
        self.platform_vars = {}

        self._build_layout()
        self._bind_events()
        self.refresh_task_rows()
        self.refresh_brand_combo()
        self.refresh_license_combo()
        self.refresh_vendor_combo()
        self.refresh_template_dropdown()
        self.show_vendor_panel()
        self.require_login()


    def apply_theme(self, mode: str):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        if mode == "light":
            bg = "#f4f5f8"
            fg = "#1f2430"
        else:
            bg = "#1f2127"
            fg = "#e8ebf3"

        # premium controls: white fill for buttons + search/input controls in both themes
        control_bg = "#ffffff"
        control_fg = "#111111"
        border = "#d7dbe3"

        self.root.configure(bg=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TLabel", background=bg, foreground=fg)

        style.configure(
            "TButton",
            padding=6,
            background=control_bg,
            foreground=control_fg,
            bordercolor=border,
            lightcolor=control_bg,
            darkcolor=control_bg,
            relief="flat",
        )
        style.map(
            "TButton",
            background=[("active", "#f4f6fa"), ("pressed", "#eef1f6")],
            foreground=[("disabled", "#7c8696")],
        )

        style.configure(
            "TEntry",
            fieldbackground=control_bg,
            foreground=control_fg,
            insertcolor=control_fg,
            bordercolor=border,
            lightcolor=control_bg,
            darkcolor=control_bg,
        )

        style.configure(
            "TCombobox",
            fieldbackground=control_bg,
            background=control_bg,
            foreground=control_fg,
            arrowcolor=control_fg,
            bordercolor=border,
            lightcolor=control_bg,
            darkcolor=control_bg,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", control_bg)],
            background=[("readonly", control_bg)],
            foreground=[("readonly", control_fg)],
        )

        style.configure("Treeview", fieldbackground="#f7f8fb", background="#f7f8fb", foreground="#111111")
        style.configure("Treeview.Heading", background="#eef1f6", foreground="#111111")

        # non-ttk quick-menu button (☰)
        if hasattr(self, "quick_menu_button"):
            self.quick_menu_button.configure(
                bg=control_bg,
                fg=control_fg,
                activebackground="#f4f6fa",
                activeforeground=control_fg,
                relief="flat",
                highlightthickness=0,
                bd=0,
            )


    def require_login(self):
        authenticated = self.open_auth_popup(required=True)
        if authenticated:
            self.root.lift()
            return
        self.root.destroy()

    def _current_username(self):
        if self.current_user and self.current_user.get("username"):
            return self.current_user["username"]
        return "unknown"

    def _has_permission(self, action: str):
        if not self.current_user:
            return False
        role = self.current_user.get("role", "member")
        allowed = {
            "admin": {"import_export", "settings", "manage_profiles", "delete", "edit", "generate"},
            "member": {"delete", "edit", "generate"},
        }
        return action in allowed.get(role, set())

    def _require_permission(self, action: str, feature_name: str):
        if self._has_permission(action):
            return True
        role = self.current_user.get("role", "member") if self.current_user else "none"
        messagebox.showerror("Permission denied", f"{feature_name} requires permission. Current role: {role}")
        return False

    def _audit(self, action: str, entity_type: str, entity_id: str = "", details: str = ""):
        self.db.log_audit(self._current_username(), action, entity_type, entity_id, details)

    def _build_layout(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, rowspan=3, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        topbar = ttk.Frame(left)
        topbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        logo_image = self._load_top_left_logo()
        if logo_image:
            ttk.Label(topbar, image=logo_image).grid(row=0, column=0, padx=(0, 8))

        self.quick_menu_button = tk.Menubutton(
            topbar,
            text="≡",
            bg="#2a2d34",
            fg="#f4f6fb",
            activebackground="#3a3e48",
            activeforeground="#ffffff",
            relief="flat",
            font=("Arial", 11, "bold"),
            padx=8,
            pady=1,
        )
        self.quick_menu_button.grid(row=0, column=1, padx=(0, 4), sticky="w")
        ttk.Label(topbar, textvariable=self.app_title_var, font=("Arial", 14, "bold")).grid(row=0, column=2, padx=(0, 6), sticky="w")
        self.quick_actions_menu = tk.Menu(self.quick_menu_button, tearoff=0, bg="#232730", fg="#e8ebf3", activebackground="#3f4554", activeforeground="#ffffff")
        self.quick_actions_menu.add_command(label="- Import from Excel", command=self.import_excel_to_db)
        self.quick_actions_menu.add_command(label="- Export to Excel", command=self.export_db_to_excel)
        self.quick_actions_menu.add_command(label="- Open Dashboard UI", command=self.open_asana_dashboard)
        self.quick_actions_menu.add_command(label="- Open Contract Maker UI", command=self.root.lift)
        self.quick_actions_menu.add_separator()
        self.quick_actions_menu.add_command(label="- Settings", command=self.open_settings_popup)
        self.quick_actions_menu.add_command(label="- Profiles (Login / Signup)", command=self.open_auth_popup)
        self.quick_actions_menu.add_command(label="- Audit Log", command=self.open_audit_log_popup)
        self.quick_menu_button.configure(menu=self.quick_actions_menu)

        ttk.Label(topbar, text="Find").grid(row=0, column=3)
        ttk.Entry(topbar, textvariable=self.search_var, width=14).grid(row=0, column=4, padx=(4, 10))
        ttk.Label(topbar, text="Stage").grid(row=0, column=5)
        ttk.Combobox(topbar, values=["ALL"] + list(STATUS_COLORS.keys()), textvariable=self.status_filter, width=12, state="readonly").grid(row=0, column=6, padx=(4, 10))
        ttk.Label(topbar, text="Client").grid(row=0, column=7)
        self.brand_filter_combo = ttk.Combobox(topbar, values=["ALL"], textvariable=self.brand_filter, width=14, state="readonly")
        self.brand_filter_combo.grid(row=0, column=8, padx=(4, 10))
        ttk.Button(topbar, text="+ New AQ Creativity", command=self.new_task).grid(row=0, column=9, padx=(6, 6))
        ttk.Button(topbar, text="Delete AQ Creativity", command=self.delete_selected_task).grid(row=0, column=10)

        cols = ("ID", "Brand", "Status", "Amount", "Type", "Vendors", "Created")
        self.task_tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        for c in cols:
            self.task_tree.heading(c, text=c)
            self.task_tree.column(c, width=120, anchor="center")
        self.task_tree.grid(row=1, column=0, sticky="nsew")
        for s, color in STATUS_COLORS.items():
            self.task_tree.tag_configure(s, background=color)

        self.user_badge_var = tk.StringVar(value="Not signed in")
        sign_in_status = ttk.Frame(left)
        sign_in_status.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(sign_in_status, textvariable=self.user_badge_var, foreground="#4e596a").pack(side="left")

        ttk.Label(right, text="AQ Creativity Editor", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))

        info = ttk.LabelFrame(right, text="Client Info", padding=10)
        info.grid(row=1, column=0, sticky="ew")
        for c in range(10):
            info.columnconfigure(c, weight=1)

        ttk.Button(info, text="Client", command=self.show_client_panel).grid(row=0, column=0, sticky="w")
        ttk.Button(info, text="Vendor", command=self.show_vendor_panel).grid(row=0, column=1, sticky="w")

        self.brand_combo = SearchableCombo(info, [], textvariable=self.brand_var, width=20)
        self.brand_combo.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        ttk.Label(info, text="Price").grid(row=0, column=3, sticky="e")
        ttk.Entry(info, textvariable=self.amount_var, width=12).grid(row=0, column=4, sticky="w", padx=(4, 8))
        ttk.Combobox(info, values=list(STATUS_COLORS.keys()), textvariable=self.status_var, width=12, state="readonly").grid(row=0, column=5)
        ttk.Label(info, text="Template").grid(row=0, column=6, sticky="e", padx=(6, 2))
        self.template_combo = ttk.Combobox(info, textvariable=self.template_key_var, width=22, state="readonly")
        self.template_combo.grid(row=0, column=7, columnspan=3, sticky="w")

        btns = ttk.Frame(info)
        btns.grid(row=1, column=0, columnspan=10, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Add Template", command=self.add_template_popup).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Manage Templates", command=self.manage_templates_popup).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Save", command=self.save_task).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Generate Contract", command=self.generate_contract).pack(side="left")

        self.vendor_panel = ttk.Frame(right)
        self.vendor_panel.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self.vendor_panel.columnconfigure(0, weight=1)
        self.vendor_panel.rowconfigure(0, weight=1)

        self.client_panel = ttk.Frame(right)
        self.client_panel.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self.client_panel.columnconfigure(0, weight=1)
        ttk.Label(self.client_panel, text="Client subtasks panel (you said you will do this later)", foreground="#666").grid(row=0, column=0, sticky="nw")

        sub_frame = ttk.LabelFrame(self.vendor_panel, text="Vendor Subtasks", padding=10)
        sub_frame.grid(row=0, column=0, sticky="nsew")
        sub_frame.columnconfigure(0, weight=1)
        sub_frame.rowconfigure(0, weight=1)

        sub_cols = ("Vendor", "Channel", "Platforms", "Type", "Qty", "Details")
        self.sub_tree = ttk.Treeview(sub_frame, columns=sub_cols, show="headings", height=8, selectmode="extended")
        for c in sub_cols:
            self.sub_tree.heading(c, text=c)
            self.sub_tree.column(c, width=100, anchor="center")
        self.sub_tree.grid(row=0, column=0, sticky="nsew")

        sub_btns = ttk.Frame(sub_frame)
        sub_btns.grid(row=1, column=0, sticky="e", pady=(6, 0))
        ttk.Button(sub_btns, text="Remove Selected Vendors", command=self.delete_selected_subtask).pack(side="right")

        editor = ttk.LabelFrame(self.vendor_panel, text="Vendor + Bank", padding=10)
        editor.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for c in range(10):
            editor.columnconfigure(c, weight=1)

        # Row 1: Name, Platform Name, Platforms, Visit, Qty, Add Vendor
        ttk.Label(editor, text="Name").grid(row=0, column=0, sticky="w")
        self.vendor_combo = SearchableCombo(editor, FALLBACK_VENDORS, textvariable=self.vendor_var, width=16)
        self.vendor_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        ttk.Label(editor, text="Platform Name").grid(row=0, column=1, sticky="w")
        ttk.Entry(editor, textvariable=self.channel_var, width=18).grid(row=1, column=1, sticky="ew", padx=(0, 6))

        ttk.Label(editor, text="Platforms").grid(row=0, column=2, columnspan=2, sticky="w")
        platform_box = ttk.Frame(editor)
        platform_box.grid(row=1, column=2, columnspan=2, sticky="w", padx=(0, 6))
        for i, p in enumerate(["TikTok", "Instagram", "Snapchat", "YouTube"]):
            v = tk.BooleanVar()
            self.platform_vars[p] = v
            r, c = divmod(i, 2)
            ttk.Checkbutton(platform_box, text=p, variable=v).grid(row=r, column=c, sticky="w", padx=(0, 8))

        ttk.Label(editor, text="Visit").grid(row=0, column=4, sticky="w")
        ad_combo = ttk.Combobox(editor, values=["Store Visit", "Home Ad", "Multi Service"], textvariable=self.type_sub_var, width=12, state="readonly")
        ad_combo.grid(row=1, column=4, sticky="ew", padx=(6, 6))

        ttk.Label(editor, text="Qty").grid(row=0, column=5, sticky="w")
        ttk.Entry(editor, textvariable=self.qty_var, width=5).grid(row=1, column=5, sticky="w")

        self.detail_entry = ttk.Entry(editor, textvariable=self.detail_var, width=20)
        self.detail_entry.grid(row=1, column=6, sticky="ew", padx=(6, 6))
        ttk.Button(editor, text="Add / Update Vendor", command=self.add_or_update_subtask).grid(row=1, column=7, sticky="e")

        # Row 2: License, IBAN, Vendor Master Popup
        ttk.Label(editor, text="License").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.license_combo = SearchableCombo(editor, [], textvariable=self.license_var, width=16)
        self.license_combo.grid(row=3, column=0, sticky="ew", pady=(4, 0), padx=(0, 6))

        ttk.Label(editor, text="IBAN").grid(row=2, column=1, sticky="w", pady=(10, 0))
        self.iban_combo = ttk.Combobox(editor, textvariable=self.iban_var, width=28, state="readonly")
        self.iban_combo.grid(row=3, column=1, columnspan=3, sticky="ew", pady=(4, 0), padx=(0, 6))

        ttk.Button(editor, text="Vendor Master Popup", command=self.open_vendor_master_popup).grid(row=3, column=4, sticky="w", pady=(4, 0))

        # Row 3: Bank Name, Account Name, Account #, SWIFT
        ttk.Label(editor, text="Bank Name").grid(row=4, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(editor, textvariable=self.bank_name_var).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0), padx=(0, 6))

        ttk.Label(editor, text="Account Name").grid(row=4, column=2, sticky="w", pady=(10, 0))
        ttk.Entry(editor, textvariable=self.account_name_var).grid(row=5, column=2, columnspan=2, sticky="ew", pady=(4, 0), padx=(0, 6))

        ttk.Label(editor, text="Account #").grid(row=4, column=4, sticky="w", pady=(10, 0))
        ttk.Entry(editor, textvariable=self.account_number_var).grid(row=5, column=4, columnspan=2, sticky="ew", pady=(4, 0), padx=(0, 6))

        ttk.Label(editor, text="SWIFT").grid(row=4, column=6, sticky="w", pady=(10, 0))
        ttk.Entry(editor, textvariable=self.swift_code_var).grid(row=5, column=6, columnspan=2, sticky="ew", pady=(4, 0), padx=(0, 6))

        ad_combo.bind("<<ComboboxSelected>>", self.toggle_details)
        self.toggle_details()

    def show_vendor_panel(self):
        self.client_panel.grid_remove()
        self.vendor_panel.grid()

    def show_client_panel(self):
        self.vendor_panel.grid_remove()
        self.client_panel.grid()


    def _load_top_left_logo(self):
        for logo_name in LOGO_CANDIDATES:
            logo_path = Path(__file__).with_name(logo_name)
            if logo_path.exists():
                try:
                    img = tk.PhotoImage(file=str(logo_path))
                    if img.width() > 96:
                        img = img.subsample(max(1, img.width() // 96))
                    if img.height() > 96:
                        img = img.subsample(1, max(1, img.height() // 96))
                    self.logo_image = img
                    return img
                except tk.TclError:
                    continue
        return None

    def open_asana_dashboard(self):
        if self.dashboard_window and self.dashboard_window.winfo_exists():
            self.dashboard_window.lift()
            self.refresh_asana_dashboard()
            return

        self.dashboard_window = tk.Toplevel(self.root)
        self.dashboard_window.title(f"{APP_BRAND} • Dashboard")
        self.dashboard_window.geometry("1380x820")
        self.dashboard_window.configure(bg="#1f2127")

        shell = tk.Frame(self.dashboard_window, bg="#1f2127")
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(1, weight=2)
        shell.grid_columnconfigure(2, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        header = tk.Frame(shell, bg="#2a2d34", height=56)
        header.grid(row=0, column=0, columnspan=3, sticky="nsew")
        header.grid_columnconfigure(1, weight=1)
        tk.Label(header, text=f"{APP_BRAND} Workspace", bg="#2a2d34", fg="#f2f3f5", font=("Arial", 15, "bold")).grid(row=0, column=0, padx=16, pady=12, sticky="w")
        tk.Label(
            header,
            text="Contract IDs, status, vendor activity and generated contracts",
            bg="#2a2d34",
            fg="#b7bcc7",
            font=("Arial", 10),
        ).grid(row=0, column=1, sticky="w")

        nav = tk.Frame(shell, bg="#22252d", width=220)
        nav.grid(row=1, column=0, sticky="nsew")
        nav.grid_propagate(False)
        tk.Label(nav, text="Projects", bg="#22252d", fg="#97a0b2", font=("Arial", 10, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        for item in ("Overview", "List", "Board", "Timeline", "Calendar", "Dashboard"):
            fg = "#f5f7ff" if item == "Dashboard" else "#c7ccd7"
            tk.Label(nav, text=f"• {item}", bg="#22252d", fg=fg, font=("Arial", 11)).pack(anchor="w", padx=20, pady=4)
        tk.Button(nav, text="Refresh data", command=self.refresh_asana_dashboard, bg="#3f4453", fg="#ffffff", relief="flat", padx=10).pack(anchor="w", padx=16, pady=20)

        center = tk.Frame(shell, bg="#1f2127")
        center.grid(row=1, column=1, sticky="nsew", padx=(10, 8), pady=(10, 10))
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        tk.Label(center, text="Contract list", bg="#1f2127", fg="#f5f7ff", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        columns = ("ID", "Brand", "Status", "Type", "Amount", "Vendors", "Created")
        self.dashboard_tree = ttk.Treeview(center, columns=columns, show="headings", height=18)
        for col in columns:
            self.dashboard_tree.heading(col, text=col)
            self.dashboard_tree.column(col, anchor="w", width=120)
        self.dashboard_tree.grid(row=1, column=0, sticky="nsew")

        detail = tk.Frame(shell, bg="#232730")
        detail.grid(row=1, column=2, sticky="nsew", padx=(0, 10), pady=(10, 10))
        detail.grid_columnconfigure(0, weight=1)

        tk.Label(detail, text="Details", bg="#232730", fg="#f5f7ff", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.dashboard_detail_title = tk.Label(detail, text="Pick a contract ID", bg="#232730", fg="#9da5b6", font=("Arial", 10))
        self.dashboard_detail_title.grid(row=1, column=0, sticky="w", padx=12)
        self.dashboard_detail_stats = tk.Label(detail, text="", bg="#232730", fg="#d8dce6", justify="left", font=("Arial", 10))
        self.dashboard_detail_stats.grid(row=2, column=0, sticky="w", padx=12, pady=(8, 8))
        tk.Label(detail, text="Generated contracts", bg="#232730", fg="#f5f7ff", font=("Arial", 11, "bold")).grid(row=3, column=0, sticky="w", padx=12)
        self.dashboard_contracts = tk.Listbox(detail, bg="#1c2028", fg="#e8ebf3", selectbackground="#4f6ed8", height=11, borderwidth=0, highlightthickness=0)
        self.dashboard_contracts.grid(row=4, column=0, sticky="nsew", padx=12, pady=(8, 12))

        self.dashboard_tree.bind("<<TreeviewSelect>>", self.on_dashboard_task_select)
        self.refresh_asana_dashboard()

    def refresh_asana_dashboard(self):
        if not getattr(self, "dashboard_tree", None):
            return
        self.dashboard_rows = {row["id"]: row for row in self.db.list_tasks()}
        self.dashboard_tree.delete(*self.dashboard_tree.get_children())
        for row in self.dashboard_rows.values():
            self.dashboard_tree.insert(
                "",
                "end",
                iid=row["id"],
                values=(row["id"], row["brand"], row["status"], row["contract_type"], row["amount"], row["vendor_count"], row["created_date"]),
            )

        first = self.dashboard_tree.get_children()
        if first:
            self.dashboard_tree.selection_set(first[0])
            self.on_dashboard_task_select()

    def on_dashboard_task_select(self, _event=None):
        if not getattr(self, "dashboard_tree", None):
            return
        selected = self.dashboard_tree.selection()
        if not selected:
            return
        task_id = selected[0]
        row = self.dashboard_rows.get(task_id)
        if not row:
            return

        subtasks = self.db.list_subtasks(task_id)
        unique_vendors = sorted({s["vendor"] for s in subtasks if s["vendor"].strip()})
        self.dashboard_detail_title.configure(text=f"{task_id} • {row['brand'] or 'No brand'}")
        self.dashboard_detail_stats.configure(
            text=(
                f"Status: {row['status']}\n"
                f"Type: {row['contract_type']}\n"
                f"Amount: {row['amount'] or '-'}\n"
                f"Subtasks: {len(subtasks)}\n"
                f"Vendors: {', '.join(unique_vendors[:4]) or '-'}"
            )
        )

        self.dashboard_contracts.delete(0, tk.END)
        contracts = self.db.list_generated_contracts_for_task(task_id)
        if not contracts:
            self.dashboard_contracts.insert(tk.END, "No generated contracts yet")
        for c in contracts:
            self.dashboard_contracts.insert(tk.END, f"{c['generated_at']}  •  {c['contract_id']}")

    def _bind_events(self):
        self.search_var.trace_add("write", self.apply_filters)
        self.status_filter.trace_add("write", self.apply_filters)
        self.brand_filter.trace_add("write", self.apply_filters)
        self.license_var.trace_add("write", self.load_ibans_for_license)
        self.iban_var.trace_add("write", self.load_bank_info)
        self.task_tree.bind("<<TreeviewSelect>>", self.load_task)
        self.sub_tree.bind("<Double-1>", self.edit_subtask)
        self.license_combo.bind("<<ComboboxSelected>>", self.load_ibans_for_license)

    def open_auth_popup(self, required=False):
        pop = tk.Toplevel(self.root)
        pop.title("Profiles • Login / Sign Up / Reset")
        pop.transient(self.root)
        pop.grab_set()
        pop.geometry("520x430")
        pop.resizable(False, False)

        sw = pop.winfo_screenwidth()
        sh = pop.winfo_screenheight()
        x = (sw - 520) // 2
        y = (sh - 430) // 2
        pop.geometry(f"520x430+{x}+{y}")
        pop.lift()
        pop.focus_force()

        notebook = ttk.Notebook(pop)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        login_tab = ttk.Frame(notebook, padding=10)
        signup_tab = ttk.Frame(notebook, padding=10)
        notebook.add(login_tab, text="Login")
        notebook.add(signup_tab, text="Sign Up")

        reset_tab = ttk.Frame(notebook, padding=10)
        notebook.add(reset_tab, text="Reset Password")

        login_user = tk.StringVar()
        login_pass = tk.StringVar()

        ttk.Label(login_tab, text="Email").grid(row=0, column=0, sticky="w", pady=(4, 2))
        login_user_entry = ttk.Entry(login_tab, textvariable=login_user)
        login_user_entry.grid(row=1, column=0, sticky="ew")
        ttk.Label(login_tab, text="Password").grid(row=2, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(login_tab, textvariable=login_pass, show="*").grid(row=3, column=0, sticky="ew")
        login_tab.columnconfigure(0, weight=1)

        signup_user = tk.StringVar()
        signup_pass = tk.StringVar()
        signup_pass2 = tk.StringVar()

        ttk.Label(signup_tab, text="Email").grid(row=0, column=0, sticky="w", pady=(4, 2))
        ttk.Entry(signup_tab, textvariable=signup_user).grid(row=1, column=0, sticky="ew")
        ttk.Label(signup_tab, text="Password").grid(row=2, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(signup_tab, textvariable=signup_pass, show="*").grid(row=3, column=0, sticky="ew")
        ttk.Label(signup_tab, text="Confirm password").grid(row=4, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(signup_tab, textvariable=signup_pass2, show="*").grid(row=5, column=0, sticky="ew")

        signup_recovery = tk.StringVar()
        signup_recovery2 = tk.StringVar()
        ttk.Label(signup_tab, text="Recovery key (first account only)").grid(row=6, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(signup_tab, textvariable=signup_recovery, show="*").grid(row=7, column=0, sticky="ew")
        ttk.Label(signup_tab, text="Confirm recovery key").grid(row=8, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(signup_tab, textvariable=signup_recovery2, show="*").grid(row=9, column=0, sticky="ew")
        signup_tab.columnconfigure(0, weight=1)

        reset_email = tk.StringVar()
        reset_pass = tk.StringVar()
        reset_pass2 = tk.StringVar()

        ttk.Label(reset_tab, text="Email").grid(row=0, column=0, sticky="w", pady=(4, 2))
        ttk.Entry(reset_tab, textvariable=reset_email).grid(row=1, column=0, sticky="ew")
        ttk.Label(reset_tab, text="New password").grid(row=2, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(reset_tab, textvariable=reset_pass, show="*").grid(row=3, column=0, sticky="ew")
        ttk.Label(reset_tab, text="Confirm password").grid(row=4, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(reset_tab, textvariable=reset_pass2, show="*").grid(row=5, column=0, sticky="ew")
        reset_tab.columnconfigure(0, weight=1)

        if self.db.count_users() == 0:
            status_text = "No profiles yet. Create the first admin account in Sign Up tab."
            notebook.select(signup_tab)
        else:
            status_text = "Log in to continue."
        status_var = tk.StringVar(value=status_text)
        ttk.Label(pop, textvariable=status_var, foreground="#5d6878").pack(anchor="w", padx=14, pady=(0, 8))

        result = {"ok": False}

        def _finish_login(user_row):
            self.current_user = dict(user_row)
            self.user_badge_var.set(f"Signed in: {self.current_user['username']} ({self.current_user.get('role','member')})")
            self._audit("login", "profile", self.current_user['username'])
            result["ok"] = True
            pop.destroy()

        def _login(*_):
            user_row = self.db.authenticate_user(login_user.get().strip().lower(), login_pass.get())
            if not user_row:
                status_var.set("Invalid username or password.")
                return
            _finish_login(user_row)

        def _signup():
            if signup_pass.get() != signup_pass2.get():
                status_var.set("Passwords do not match.")
                return
            try:
                clean_email = signup_user.get().strip().lower()
                if "@" not in clean_email:
                    status_var.set("Enter a valid email address.")
                    return
                first_user = self.db.count_users() == 0
                role = "admin" if first_user else "member"
                recovery_key_entered = signup_recovery.get().strip() or signup_recovery2.get().strip()

                if first_user:
                    if signup_recovery.get() != signup_recovery2.get():
                        status_var.set("Recovery keys do not match.")
                        return
                    self.db.set_recovery_key(signup_recovery.get())
                elif recovery_key_entered and not self.db.has_recovery_key():
                    if signup_recovery.get() != signup_recovery2.get():
                        status_var.set("Recovery keys do not match.")
                        return
                    self.db.set_recovery_key(signup_recovery.get())

                self.db.create_user(clean_email, signup_pass.get(), role=role)
                self._audit("create_profile", "profile", clean_email, details=f"role={role}")
                status_var.set("Profile created. Log in now.")
                login_user.set(clean_email)
                login_pass.set(signup_pass.get())
                notebook.select(login_tab)
            except sqlite3.IntegrityError:
                status_var.set("Username already exists.")
            except ValueError as exc:
                status_var.set(str(exc))

        def _reset_password():
            if reset_pass.get() != reset_pass2.get():
                status_var.set("Reset passwords do not match.")
                return
            try:
                email = reset_email.get().strip().lower()
                if "@" not in email:
                    status_var.set("Enter a valid email address.")
                    return
                updated = self.db.reset_password_by_email(email, reset_pass.get())
                if updated == 0:
                    status_var.set("No profile found for that email.")
                    return
                self._audit("reset_password", "profile", email)
                status_var.set("Password reset. You can now log in.")
                login_user.set(email)
                login_pass.set(reset_pass.get())
                notebook.select(login_tab)
            except ValueError as exc:
                status_var.set(str(exc))

        recovery = ttk.LabelFrame(pop, text="Admin Recovery", padding=8)
        recovery.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(
            recovery,
            text="Enter your recovery key to reset all accounts and re-create admin.",
            foreground="#a84d00",
            wraplength=470,
            justify="left",
        ).pack(anchor="w")

        recovery_key_var = tk.StringVar()
        ttk.Entry(recovery, textvariable=recovery_key_var, show="*").pack(fill="x", pady=(6, 4))

        def _reset_all_accounts():
            if not self.db.has_recovery_key():
                status_var.set("No recovery key is set yet. Create/set one from Sign Up first.")
                return
            if not self.db.verify_recovery_key(recovery_key_var.get()):
                status_var.set("Invalid recovery key.")
                return
            if not messagebox.askyesno(
                "Reset all accounts",
                "This will DELETE all profiles and logins. Continue?",
                parent=pop,
            ):
                return
            self.db.reset_all_accounts()
            self.db.clear_recovery_key()
            self.current_user = None
            self.user_badge_var.set("Not signed in")
            status_var.set("All accounts removed. Create a new admin in Sign Up tab and set a new recovery key.")
            notebook.select(signup_tab)
            self._audit("reset_all_accounts", "profile")

        ttk.Button(recovery, text="Reset Using Recovery Key", command=_reset_all_accounts).pack(anchor="e", pady=(2, 0))

        btns = ttk.Frame(pop)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Log In", command=_login).pack(side="right")
        ttk.Button(btns, text="Sign Up", command=_signup).pack(side="right", padx=(0, 8))
        ttk.Button(btns, text="Reset Password", command=_reset_password).pack(side="right", padx=(0, 8))

        if required:
            ttk.Button(btns, text="Exit app", command=pop.destroy).pack(side="left")
        else:
            ttk.Button(btns, text="Close", command=pop.destroy).pack(side="left")

        def _submit_by_tab(_event=None):
            tab = notebook.select()
            if tab == str(login_tab):
                _login()
            elif tab == str(signup_tab):
                _signup()
            else:
                _reset_password()

        pop.bind("<Return>", _submit_by_tab)
        pop.protocol("WM_DELETE_WINDOW", pop.destroy)
        login_user_entry.focus_set()
        pop.wait_window()
        return result["ok"]

    def open_audit_log_popup(self):
        if not self._require_permission("settings", "Audit Log"):
            return
        pop = tk.Toplevel(self.root)
        pop.title("Audit Log")
        pop.transient(self.root)
        pop.geometry("900x420")

        cols = ("When", "User", "Action", "Entity", "ID", "Details")
        tree = ttk.Treeview(pop, columns=cols, show="headings")
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=130 if col != "Details" else 250, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for row in self.db.list_recent_audit(300):
            tree.insert(
                "",
                "end",
                values=(row["created_at"], row["actor_username"], row["action"], row["entity_type"], row["entity_id"], row["details"]),
            )

    def open_vendor_master_popup(self):
        if not self._require_permission("edit", "Vendor master update"):
            return
        pop = tk.Toplevel(self.root)
        pop.title("Vendor Master")
        pop.transient(self.root)
        pop.grab_set()
        pop.geometry("520x260")
        pop.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 520) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 260) // 2
        pop.geometry(f"520x260+{x}+{y}")

        name_v = tk.StringVar(value=self.vendor_name_auto_var.get() or self.vendor_var.get())
        lic_v = tk.StringVar(value=self.license_var.get())
        iban_v = tk.StringVar(value=self.iban_var.get())
        bank_v = tk.StringVar(value=self.bank_name_var.get())
        accn_v = tk.StringVar(value=self.account_name_var.get())
        acct_v = tk.StringVar(value=self.account_number_var.get())
        swift_v = tk.StringVar(value=self.swift_code_var.get())

        frame = ttk.Frame(pop, padding=12)
        frame.pack(fill="both", expand=True)
        labels = [
            ("Vendor Name", name_v), ("License", lic_v), ("IBAN", iban_v),
            ("Bank Name", bank_v), ("Account Name", accn_v), ("Account #", acct_v), ("SWIFT", swift_v),
        ]
        for i, (lab, var) in enumerate(labels):
            ttk.Label(frame, text=lab).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(frame, textvariable=var, width=36).grid(row=i, column=1, sticky="ew", pady=2)

        frame.columnconfigure(1, weight=1)

        def _save():
            if not lic_v.get().strip():
                messagebox.showwarning("Missing license", "License is required", parent=pop)
                return
            self.db.upsert_vendor_bank(name_v.get().strip(), lic_v.get().strip(), bank_v.get().strip(), accn_v.get().strip(), iban_v.get().strip(), acct_v.get().strip(), swift_v.get().strip())
            self.license_var.set(lic_v.get().strip())
            self.vendor_name_auto_var.set(name_v.get().strip())
            self.vendor_var.set(name_v.get().strip())
            self.iban_var.set(iban_v.get().strip())
            self.bank_name_var.set(bank_v.get().strip())
            self.account_name_var.set(accn_v.get().strip())
            self.account_number_var.set(acct_v.get().strip())
            self.swift_code_var.set(swift_v.get().strip())
            self.refresh_license_combo()
            self.refresh_vendor_combo()
            self._audit("upsert_vendor_master", "vendor", lic_v.get().strip(), details=f"vendor={name_v.get().strip()}")
            pop.destroy()

        ttk.Button(frame, text="Save", command=_save).grid(row=len(labels), column=1, sticky="e", pady=(10, 0))

    def import_excel_to_db(self):
        if not self._require_permission("import_export", "Import Excel"):
            return
        file_path = filedialog.askopenfilename(title="Select Excel file", filetypes=[("Excel files", "*.xlsx *.xls")])
        if not file_path:
            return
        try:
            import pandas as pd
        except Exception:
            messagebox.showerror("Missing dependency", "Please install pandas/openpyxl first: pip install pandas openpyxl")
            return

        try:
            df = pd.read_excel(file_path, dtype=str).fillna("")
            df = df.rename(columns={c: c.strip().lower().replace(" ", "_").replace("(", "").replace(")", "") for c in df.columns})

            def col(*names):
                for n in names:
                    if n in df.columns:
                        return n
                return None

            brand_c = col("brand", "brand_name")
            vendor_c = col("vendor", "vendor_name", "name", "influencer_name_as_per_license", "influencer_name_as_per_license_")
            lic_c = col("license", "license_number")
            iban_c = col("iban")
            bank_c = col("bank_name")
            accn_c = col("account_name")
            acct_c = col("account_number")
            swift_c = col("swift", "swift_code")

            imported = 0
            for _, row in df.iterrows():
                brand = row[brand_c].strip() if brand_c else ""
                vendor = row[vendor_c].strip() if vendor_c else ""
                lic = row[lic_c].strip() if lic_c else ""
                iban = row[iban_c].strip() if iban_c else ""
                bank = row[bank_c].strip() if bank_c else ""
                accn = row[accn_c].strip() if accn_c else ""
                acct = row[acct_c].strip() if acct_c else ""
                swift = row[swift_c].strip() if swift_c else ""
                if brand:
                    self.db.upsert_brand(brand)
                if lic:
                    self.db.upsert_vendor_bank(vendor, lic, bank, accn, iban, acct, swift)
                    imported += 1

            self.refresh_brand_combo()
            self.refresh_license_combo()
            self.refresh_vendor_combo()
            self._audit("import_excel", "database", details=f"rows={imported} file={file_path}")
            messagebox.showinfo("Import complete", f"Imported/updated {imported} vendor license records from Excel.")
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc))

    def export_db_to_excel(self):
        if not self._require_permission("import_export", "Export Excel"):
            return
        file_path = filedialog.asksaveasfilename(
            title="Export to Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not file_path:
            return
        try:
            import pandas as pd
        except Exception:
            messagebox.showerror("Missing dependency", "Please install pandas/openpyxl first: pip install pandas openpyxl")
            return

        try:
            tasks = [dict(r) for r in self.db.list_tasks()]
            vendors = [
                dict(r)
                for r in self.db.conn.execute(
                    """
                    SELECT v.name, v.license_number, ba.bank_name, ba.account_name, ba.iban, ba.account_number, COALESCE(ba.swift_code,'') AS swift_code
                    FROM vendors v
                    LEFT JOIN bank_accounts ba ON ba.vendor_id=v.id
                    ORDER BY v.name, v.license_number
                    """
                ).fetchall()
            ]
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                pd.DataFrame(tasks).to_excel(writer, index=False, sheet_name="contracts")
                pd.DataFrame(vendors).to_excel(writer, index=False, sheet_name="vendors")
            self._audit("export_excel", "database", details=f"tasks={len(tasks)} vendors={len(vendors)} file={file_path}")
            messagebox.showinfo("Export complete", "Data exported to Excel successfully.")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def refresh_template_dropdown(self):
        try:
            conf = load_config()
            keys = sorted(conf.get("template_map", {}).keys())
        except Exception:
            keys = []

        self.available_template_keys = keys
        values = ["auto"] + keys
        self.template_combo["values"] = values
        if self.template_key_var.get() not in values:
            self.template_key_var.set(self.default_type_setting.get() if self.default_type_setting.get() in values else "auto")

    def add_template_popup(self):
        if not self._require_permission("settings", "Add template"):
            return

        pop = tk.Toplevel(self.root)
        pop.title("Add Template")
        pop.transient(self.root)
        pop.grab_set()
        pop.geometry("540x180")

        frame = ttk.Frame(pop, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        key_var = tk.StringVar()
        path_var = tk.StringVar()

        ttk.Label(frame, text="Template key").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=key_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="DOCX template file").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=path_var).grid(row=1, column=1, sticky="ew", pady=4)

        def _browse():
            fp = filedialog.askopenfilename(title="Select template", filetypes=[("Word template", "*.docx")])
            if fp:
                path_var.set(fp)

        ttk.Button(frame, text="Browse", command=_browse).grid(row=1, column=2, padx=(8, 0))

        def _save():
            key = key_var.get().strip().lower().replace(" ", "_")
            path = path_var.get().strip()
            if not key or not path:
                messagebox.showwarning("Missing data", "Template key and path are required")
                return
            if not Path(path).exists():
                messagebox.showerror("Invalid path", "Selected template file does not exist")
                return

            conf = load_config()
            conf.setdefault("template_map", {})[key] = path
            CONFIG_PATH.write_text(json.dumps(conf, indent=2, ensure_ascii=False), encoding="utf-8")
            self.refresh_template_dropdown()
            self.template_key_var.set(key)
            self._audit("add_template", "template", key, details=path)
            pop.destroy()

        btns = ttk.Frame(frame)
        btns.grid(row=2, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=pop.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Save", command=_save).pack(side="left")

    def _save_template_config(self, conf):
        CONFIG_PATH.write_text(json.dumps(conf, indent=2, ensure_ascii=False), encoding="utf-8")

    def manage_templates_popup(self):
        if not self._require_permission("settings", "Manage templates"):
            return

        pop = tk.Toplevel(self.root)
        pop.title("Manage Templates")
        pop.transient(self.root)
        pop.grab_set()
        pop.geometry("680x360")

        frame = ttk.Frame(pop, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(frame)
        list_frame.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        ttk.Label(list_frame, text="Template keys").pack(anchor="w")
        key_list = tk.Listbox(list_frame, width=24, exportselection=False)
        key_list.pack(fill="y", expand=True, pady=(6, 0))

        edit_frame = ttk.LabelFrame(frame, text="Template Details", padding=10)
        edit_frame.grid(row=0, column=1, sticky="nsew")
        edit_frame.columnconfigure(1, weight=1)

        key_var = tk.StringVar()
        path_var = tk.StringVar()
        rename_var = tk.StringVar()

        ttk.Label(edit_frame, text="Current key").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(edit_frame, textvariable=key_var, state="readonly").grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(edit_frame, text="Rename key to").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(edit_frame, textvariable=rename_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(edit_frame, text="Template path").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(edit_frame, textvariable=path_var).grid(row=2, column=1, sticky="ew", pady=4)

        def _browse_path():
            fp = filedialog.askopenfilename(title="Select template", filetypes=[("Word template", "*.docx")])
            if fp:
                path_var.set(fp)

        ttk.Button(edit_frame, text="Browse", command=_browse_path).grid(row=2, column=2, padx=(8, 0))

        def _load_keys(selected_key=""):
            conf = load_config()
            keys = sorted(conf.get("template_map", {}).keys())
            key_list.delete(0, tk.END)
            for k in keys:
                key_list.insert(tk.END, k)
            target = selected_key if selected_key in keys else (keys[0] if keys else "")
            if target:
                idx = keys.index(target)
                key_list.selection_clear(0, tk.END)
                key_list.selection_set(idx)
                key_list.activate(idx)
                _load_selected()
            else:
                key_var.set("")
                rename_var.set("")
                path_var.set("")

        def _selected_key():
            sel = key_list.curselection()
            if not sel:
                return ""
            return key_list.get(sel[0])

        def _load_selected(_event=None):
            skey = _selected_key()
            conf = load_config()
            tmap = conf.get("template_map", {})
            key_var.set(skey)
            rename_var.set(skey)
            path_var.set(tmap.get(skey, ""))

        key_list.bind("<<ListboxSelect>>", _load_selected)

        def _update_template():
            old_key = _selected_key()
            if not old_key:
                messagebox.showwarning("No selection", "Select a template key first")
                return

            new_key = rename_var.get().strip().lower().replace(" ", "_")
            new_path = path_var.get().strip()
            if not new_key or not new_path:
                messagebox.showwarning("Missing data", "Rename key and template path are required")
                return
            if not Path(new_path).exists():
                messagebox.showerror("Invalid path", "Template file path does not exist")
                return

            conf = load_config()
            tmap = conf.setdefault("template_map", {})
            if old_key not in tmap:
                messagebox.showerror("Missing key", "Selected template key no longer exists")
                return

            # rename/update
            del tmap[old_key]
            tmap[new_key] = new_path

            if conf.get("standard_template_key") == old_key:
                conf["standard_template_key"] = new_key
            if self.default_type_setting.get() == old_key:
                self.default_type_setting.set(new_key)
                self.db.set_setting("default_contract_type", new_key)

            self._save_template_config(conf)
            self.refresh_template_dropdown()
            self.template_key_var.set(new_key)
            self._audit("update_template", "template", old_key, details=f"renamed_to={new_key};path={new_path}")
            _load_keys(new_key)

        def _delete_template():
            del_key = _selected_key()
            if not del_key:
                messagebox.showwarning("No selection", "Select a template key first")
                return
            if not messagebox.askyesno("Delete template", f"Delete template '{del_key}'?"):
                return

            conf = load_config()
            tmap = conf.setdefault("template_map", {})
            if del_key not in tmap:
                messagebox.showerror("Missing key", "Selected template key no longer exists")
                return

            if len(tmap) <= 1:
                messagebox.showerror("Blocked", "At least one template must remain")
                return

            del tmap[del_key]
            remaining_keys = sorted(tmap.keys())
            if conf.get("standard_template_key") == del_key:
                conf["standard_template_key"] = remaining_keys[0]
            if self.default_type_setting.get() == del_key:
                self.default_type_setting.set("auto")
                self.db.set_setting("default_contract_type", "auto")
            if self.template_key_var.get() == del_key:
                self.template_key_var.set("auto")

            self._save_template_config(conf)
            self.refresh_template_dropdown()
            self._audit("delete_template", "template", del_key)
            _load_keys()

        btns = ttk.Frame(edit_frame)
        btns.grid(row=3, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Update", command=_update_template).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Delete", command=_delete_template).pack(side="left")

        _load_keys(self.template_key_var.get())

    def open_settings_popup(self):
        if not self._require_permission("settings", "Settings"):
            return
        pop = tk.Toplevel(self.root)
        pop.title("App Settings")
        pop.transient(self.root)
        pop.grab_set()
        pop.geometry("420x240")

        frame = ttk.Frame(pop, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        title_v = tk.StringVar(value=self.app_title_var.get())
        default_type_v = tk.StringVar(value=self.default_type_setting.get())
        default_status_v = tk.StringVar(value=self.default_status_setting.get())
        theme_v = tk.StringVar(value=self.theme_setting.get())

        ttk.Label(frame, text="App title").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=title_v).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Default template").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(frame, textvariable=default_type_v, values=["auto"] + self.available_template_keys, state="readonly", width=20).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Default status").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(frame, textvariable=default_status_v, values=list(STATUS_COLORS.keys()), state="readonly", width=12).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Theme").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(frame, textvariable=theme_v, values=["dark", "light"], state="readonly", width=12).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="These defaults are used when creating a new AQ Creativity task.", foreground="#666").grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        def _save():
            app_title = (title_v.get().strip() or APP_BRAND)
            self.db.set_setting("app_title", app_title)
            self.db.set_setting("default_contract_type", default_type_v.get().strip() or "auto")
            self.db.set_setting("default_status", default_status_v.get().strip() or "NEW")
            self.db.set_setting("theme_mode", theme_v.get().strip() or "dark")

            self.app_title_var.set(app_title)
            self.default_type_setting.set(default_type_v.get().strip() or "auto")
            self.default_status_setting.set(default_status_v.get().strip() or "NEW")
            self.theme_setting.set(theme_v.get().strip() or "dark")
            self.apply_theme(self.theme_setting.get())
            self.root.title(f"{self.app_title_var.get()} – Dashboard")
            self._audit("update_settings", "app_settings", details=f"title={app_title};theme={self.theme_setting.get()}")
            pop.destroy()

        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(btns, text="Cancel", command=pop.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Save", command=_save).pack(side="left")

    def refresh_brand_combo(self):
        brands = self.db.get_all_brands()
        self.brand_combo.set_values(brands)
        self.brand_filter_combo["values"] = ["ALL"] + brands
        if self.brand_filter.get() not in ["ALL"] + brands:
            self.brand_filter.set("ALL")

    def refresh_license_combo(self):
        self.license_combo.set_values(self.db.get_license_numbers())

    def refresh_vendor_combo(self):
        self.vendor_combo.set_values(self.db.get_vendor_names() or FALLBACK_VENDORS)

    def load_ibans_for_license(self, *_):
        lic = self.license_var.get().strip()
        if not lic:
            self.vendor_name_auto_var.set("")
            self.iban_combo["values"] = []
            self.iban_var.set("")
            self.bank_name_var.set("")
            self.account_name_var.set("")
            self.account_number_var.set("")
            self.swift_code_var.set("")
            return

        vendor_name = self.db.get_vendor_name_by_license(lic)
        if vendor_name:
            self.vendor_name_auto_var.set(vendor_name)
            self.vendor_var.set(vendor_name)
        else:
            # keep editable vendor name if DB has no explicit name for this license
            self.vendor_name_auto_var.set(self.vendor_var.get().strip())

        ibans = self.db.get_ibans_for_license(lic)
        self.iban_combo["values"] = ibans
        if ibans and not self.iban_var.get().strip():
            self.iban_var.set(ibans[0])
        elif not ibans:
            self.iban_var.set("")

    def load_bank_info(self, *_):
        iban = self.iban_var.get().strip()
        if not iban:
            return
        row = self.db.get_bank_info_by_iban(iban)
        if row:
            self.bank_name_var.set(row["bank_name"])
            self.account_name_var.set(row["account_name"])
            self.account_number_var.set(row["account_number"])
            self.swift_code_var.set(row["swift_code"])

    def refresh_task_rows(self):
        self.task_tree.delete(*self.task_tree.get_children())
        for row in self.db.list_tasks():
            self.task_tree.insert("", "end", iid=row["id"], values=(row["id"], row["brand"], row["status"], row["amount"], row["contract_type"], row["vendor_count"], row["created_date"]), tags=(row["status"],))
        self.apply_filters()

    def apply_filters(self, *_):
        text, status, brand = self.search_var.get().lower(), self.status_filter.get(), self.brand_filter.get()
        for row in self.db.list_tasks():
            iid = row["id"]
            visible = not (
                (status != "ALL" and row["status"] != status)
                or (brand != "ALL" and row["brand"] != brand)
                or (text and text not in iid.lower() and text not in row["brand"].lower())
            )
            if visible and self.task_tree.exists(iid):
                self.task_tree.reattach(iid, "", "end")
            elif self.task_tree.exists(iid):
                self.task_tree.detach(iid)

    def new_task(self):
        if not self._require_permission("edit", "Create task"):
            return
        if self.current_task.get():
            self.save_task(silent=True)
        task_id = create_task_id([r["id"] for r in self.db.list_tasks()])
        self.db.create_task(task_id, self.default_type_setting.get() or "auto", self.default_status_setting.get() or "NEW")
        self.refresh_task_rows()
        self.current_task.set(task_id)
        self.brand_var.set("")
        self.amount_var.set("")
        self.template_key_var.set(self.default_type_setting.get() or "auto")
        self.status_var.set(self.default_status_setting.get() or "NEW")
        self.sub_tree.delete(*self.sub_tree.get_children())
        self.clear_subtask_editor()
        self._audit("create_task", "task", task_id)

    def delete_selected_task(self):
        if not self._require_permission("delete", "Delete tasks"):
            return
        selected = list(self.task_tree.selection())
        if not selected:
            messagebox.showwarning("No task", "Select one or more tasks to delete")
            return
        if not messagebox.askyesno("Delete task(s)", f"Delete {len(selected)} selected task(s) and all their vendors?"):
            return

        deleted = 0
        for tid in selected:
            if self.db.get_task(tid):
                self.db.delete_task(tid)
                self._audit("delete_task", "task", tid)
                deleted += 1

        if self.current_task.get() in selected:
            self.current_task.set("")
            self.brand_var.set("")
            self.amount_var.set("")
            self.sub_tree.delete(*self.sub_tree.get_children())
            self.clear_subtask_editor()

        self.refresh_task_rows()
        self.refresh_brand_combo()
        messagebox.showinfo("Deleted", f"Deleted {deleted} task(s).")

    def save_task(self, silent=False):
        if not self._require_permission("edit", "Save task"):
            return
        tid = self.current_task.get()
        if not tid:
            return
        self.db.upsert_task(tid, self.brand_var.get().strip(), self.amount_var.get().strip(), self.template_key_var.get().strip() or "auto", self.status_var.get().strip() or "NEW")
        self.db.upsert_brand(self.brand_var.get().strip())
        self._audit("update_task", "task", tid, details=f"brand={self.brand_var.get().strip()}")
        self.refresh_task_rows()
        self.refresh_brand_combo()
        if not silent:
            messagebox.showinfo("Saved", f"Task {tid} saved.")

    def load_task(self, _event=None):
        sel = self.task_tree.selection()
        if not sel:
            return
        tid = sel[0]
        row = self.db.get_task(tid)
        if not row:
            return
        self.current_task.set(tid)
        self.brand_var.set(row["brand"])
        self.amount_var.set(row["amount"])
        self.template_key_var.set(row["contract_type"] or "auto")
        self.status_var.set(row["status"])
        self.refresh_subtasks(tid)
        self.clear_subtask_editor()

    def refresh_subtasks(self, task_id):
        self.sub_tree.delete(*self.sub_tree.get_children())
        for sub in self.db.list_subtasks(task_id):
            self.sub_tree.insert("", "end", iid=str(sub["id"]), values=(sub["vendor"], sub["channel"], sub["platforms"], sub["ad_type"], sub["qty"], sub["details"]))

    def clear_subtask_editor(self):
        self.editing_subtask_id = None
        self.vendor_var.set("")
        self.channel_var.set("")
        self.type_sub_var.set("Store Visit")
        self.qty_var.set("1")
        self.detail_var.set("")
        self.license_var.set("")
        self.vendor_name_auto_var.set("")
        self.iban_var.set("")
        self.bank_name_var.set("")
        self.account_name_var.set("")
        self.account_number_var.set("")
        self.swift_code_var.set("")
        for v in self.platform_vars.values():
            v.set(False)
        self.toggle_details()

    def add_or_update_subtask(self):
        if not self._require_permission("edit", "Edit vendor subtasks"):
            return
        tid = self.current_task.get()
        if not tid:
            messagebox.showwarning("Select task first", "Pick a task on the left")
            return
        plats = [p for p, v in self.platform_vars.items() if v.get()]
        payload = (self.vendor_var.get().strip(), self.channel_var.get().strip(), ", ".join(plats), self.type_sub_var.get().strip() or "Store Visit", self.qty_var.get().strip() or "1", self.detail_var.get().strip())
        if self.editing_subtask_id is None:
            self.db.create_subtask(tid, *payload)
            self._audit("create_subtask", "subtask", tid, details=f"vendor={payload[0]}")
        else:
            self.db.update_subtask(self.editing_subtask_id, *payload)
            self._audit("update_subtask", "subtask", str(self.editing_subtask_id), details=f"vendor={payload[0]}")
        self.refresh_subtasks(tid)
        self.refresh_task_rows()

    def delete_selected_subtask(self):
        if not self._require_permission("delete", "Delete vendor subtasks"):
            return
        selected = list(self.sub_tree.selection())
        if not selected:
            messagebox.showwarning("No vendor", "Select one or more vendor rows to remove")
            return
        if not messagebox.askyesno("Remove vendors", f"Delete {len(selected)} selected vendor row(s)?"):
            return
        for sid in selected:
            self.db.delete_subtask(int(sid))
            self._audit("delete_subtask", "subtask", str(sid))
        tid = self.current_task.get()
        if tid:
            self.refresh_subtasks(tid)
        self.refresh_task_rows()

    def edit_subtask(self, _event):
        sel = self.sub_tree.selection()
        if not sel:
            return
        values = self.sub_tree.item(sel[0], "values")
        self.editing_subtask_id = int(sel[0])
        self.vendor_var.set(values[0])
        self.channel_var.set(values[1])
        for p in self.platform_vars:
            self.platform_vars[p].set(p in values[2])
        self.type_sub_var.set(values[3])
        self.qty_var.set(values[4])
        self.detail_var.set(values[5])
        self.toggle_details()

    def toggle_details(self, *_):
        if self.type_sub_var.get() == "Multi Service":
            self.detail_entry.grid()
        else:
            self.detail_entry.grid_remove()
            self.detail_var.set("")

    def _validate_generation_context(self, task, subtask, context):
        required = {
            "brand": task["brand"].strip(),
            "amount": task["amount"].strip(),
            "vendor": subtask["vendor"].strip(),
            "channel": subtask["channel"].strip(),
            "platform": subtask["platforms"].strip(),
            "license": context["license_number"].strip(),
            "iban": context["iban"].strip(),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            return f"Vendor '{subtask['vendor'] or '-'}' is missing: {', '.join(missing)}"
        return None

    def _context_for_subtask(self, task, subtask):
        platforms = [p.strip() for p in subtask["platforms"].split(",") if p.strip()]
        channels = [f"{plat}: {subtask['channel']}" for plat in platforms if subtask["channel"].strip()]

        profile = self.db.get_vendor_profile_by_name(subtask["vendor"].strip())
        license_number = profile["license_number"] if profile and profile["license_number"] else self.license_var.get().strip()
        bank_name = profile["bank_name"] if profile and profile["bank_name"] else self.bank_name_var.get().strip()
        account_name = profile["account_name"] if profile and profile["account_name"] else self.account_name_var.get().strip()
        iban = profile["iban"] if profile and profile["iban"] else self.iban_var.get().strip()
        account_number = profile["account_number"] if profile and profile["account_number"] else self.account_number_var.get().strip()
        swift_code = profile["swift_code"] if profile and profile["swift_code"] else self.swift_code_var.get().strip()

        ad_types = f"{subtask['ad_type']}, {subtask['qty']}" if subtask["qty"] else subtask["ad_type"]

        return {
            "brand_name": task["brand"],
            "amount": task["amount"],
            "contract_type": (task["contract_type"].strip() if task["contract_type"].strip() not in {"", "auto"} else "after_pay"),
            "channel_name": ", ".join(channels),
            "platform": ", ".join(sorted(set(platforms))),
            "ad_types": ad_types,
            "influencer_name_as_per_license": subtask["vendor"],
            "license_number": license_number,
            "city_as_per_license": "",
            "neighbourhood_as_per_license": "",
            "bank_name": bank_name,
            "account_name": account_name,
            "iban": iban,
            "account_number": account_number,
            "swift_code": swift_code,
        }

    def generate_contract(self):
        if not self._require_permission("generate", "Generate contract"):
            return
        tid = self.current_task.get()
        if not tid:
            messagebox.showwarning("No task", "Select a task first")
            return
        self.save_task(silent=True)
        task = self.db.get_task(tid)
        subtasks = self.db.list_subtasks(tid)
        if not task:
            messagebox.showerror("Missing task", "Task data was not found in database")
            return
        if not subtasks:
            messagebox.showwarning("No vendors", "Add vendors before generating contracts")
            return

        selected_ids = {int(i) for i in self.sub_tree.selection() if str(i).isdigit()}
        target_subtasks = [s for s in subtasks if not selected_ids or s["id"] in selected_ids]

        failures = []
        generated_ids = []
        for subtask in target_subtasks:
            context = self._context_for_subtask(task, subtask)
            error = self._validate_generation_context(task, subtask, context)
            if error:
                failures.append(error)
                continue

            try:
                cid = generate_contract_from_gui(context)
                self.db.log_generated_contract(cid, tid, task["brand"], task["amount"], task["contract_type"])
                self._audit("generate_contract", "contract", cid, details=f"task={tid};vendor={subtask['vendor']}")
                generated_ids.append(cid)
            except Exception as exc:
                failures.append(f"Vendor '{subtask['vendor'] or '-'}' failed: {exc}")

        if generated_ids:
            summary = "\n".join(generated_ids[:10])
            if len(generated_ids) > 10:
                summary += f"\n... +{len(generated_ids)-10} more"
            messagebox.showinfo("Success", f"Generated {len(generated_ids)} contract(s):\n{summary}")

        if failures:
            messagebox.showwarning("Generation issues", "\n".join(failures[:12]))

    def on_close(self):
        self.db.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ContractSuiteApp().run()
