# ==========================================================
# 🐐 CONTRACT SUITE – GOAT VERSION (SAFE UPGRADE)
# Based EXACTLY on your working code
# Added ONLY:
#   ✅ status colors
#   ✅ filters
#   ✅ hints
# ==========================================================

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import random
from contract_generator.py import generate_contract_from_gui


CLIENTS = ["Nike", "STC", "Jarir", "Almarai"]
VENDORS = ["Ali Tech", "Sara Beauty", "Omar Food", "Lama Travel"]

tasks = {}

# ================= NEW: STATUS COLORS =================
STATUS_COLORS = {
    "NEW": "#eeeeee",
    "MARKETING": "#cfe2ff",
    "LEGAL": "#ffe6cc",
    "APPROVED": "#d4edda",
    "SENT": "#e0ccff",
    "DONE": "#c6f6d5",
}


class SearchableCombo(ttk.Combobox):
    def __init__(self, master, values, **kwargs):
        super().__init__(master, values=values, **kwargs)
        self.full = values
        self.bind("<KeyRelease>", self.filter)

    def filter(self, _):
        txt = self.get().lower()
        self["values"] = [v for v in self.full if txt in v.lower()] or self.full


root = tk.Tk()
root.title("Contract Suite – Dashboard")
root.geometry("1400x780")

left = ttk.Frame(root, width=800)
left.pack(side="left", fill="both", expand=True)

right = ttk.Frame(root, width=600)
right.pack(side="right", fill="both")


# ==========================================================
# LEFT SIDE
# ==========================================================

topbar = ttk.Frame(left)
topbar.pack(fill="x", pady=5)

ttk.Label(topbar, text="Tasks", font=("Arial", 14, "bold")).pack(side="left")

# ================= NEW: FILTER BAR =================
search_var = tk.StringVar()
status_filter = tk.StringVar(value="ALL")
brand_filter = tk.StringVar(value="ALL")

tk.Label(topbar, text="Find").pack(side="left", padx=(15,2))
tk.Entry(topbar, textvariable=search_var, width=12).pack(side="left")

tk.Label(topbar, text="Stage").pack(side="left", padx=(10,2))
ttk.Combobox(topbar,
             values=["ALL"] + list(STATUS_COLORS.keys()),
             textvariable=status_filter,
             width=10).pack(side="left")

tk.Label(topbar, text="Client").pack(side="left", padx=(10,2))
ttk.Combobox(topbar,
             values=["ALL"] + CLIENTS,
             textvariable=brand_filter,
             width=10).pack(side="left")


def new_task():

    # -------- SAVE CURRENT FIRST --------
    if current_task.get():
        save_task()

    cid = f"C{random.randint(1000,9999)}"

    tasks[cid] = {
        "brand": "",
        "amount": "",
        "type": "Pre",
        "status": "NEW",
        "subs": []
    }

    # -------- INSERT ONCE --------
    insert_row(cid)

    # -------- clear editor --------
    current_task.set(cid)

    brand_var.set("")
    amount_var.set("")
    type_var.set("Pre")
    status_var.set("NEW")

    sub_tree.delete(*sub_tree.get_children())



    insert_row(cid)


ttk.Button(topbar, text="+ New Task", command=new_task).pack(side="right")


cols = ("ID", "Brand", "Status", "Amount", "Type", "Vendors", "Created")

task_tree = ttk.Treeview(left, columns=cols, show="headings")

for c in cols:
    task_tree.heading(c, text=c)
    task_tree.column(c, width=110)

task_tree.pack(fill="both", expand=True, padx=5)

# ================= NEW: configure color tags =================
for s, color in STATUS_COLORS.items():
    task_tree.tag_configure(s, background=color)


def today():
    return datetime.now().strftime("%Y-%m-%d")


# ================= NEW: helper to insert with color =================
def insert_row(cid):
    t = tasks[cid]

    # --- SAFE GUARD: do not insert duplicates ---
    if task_tree.exists(cid):
        task_tree.item(
            cid,
            values=(cid, t["brand"], t["status"], t["amount"],
                    t["type"], len(t["subs"]), today()),
            tags=(t["status"],)
        )
        return

    task_tree.insert(
        "",
        "end",
        iid=cid,
        values=(cid, t["brand"], t["status"], t["amount"],
                t["type"], len(t["subs"]), today()),
        tags=(t["status"],)
    )


# ================= NEW: FILTER FUNCTION =================
def apply_filters(*_):
    text = search_var.get().lower()

    for iid in task_tree.get_children():
        t = tasks[iid]

        visible = True

        if status_filter.get() != "ALL" and t["status"] != status_filter.get():
            visible = False

        if brand_filter.get() != "ALL" and t["brand"] != brand_filter.get():
            visible = False

        if text and text not in iid.lower() and text not in t["brand"].lower():
            visible = False

        if visible:
            task_tree.reattach(iid, "", "end")
        else:
            task_tree.detach(iid)


search_var.trace_add("write", apply_filters)
status_filter.trace_add("write", apply_filters)
brand_filter.trace_add("write", apply_filters)

def generate_contract():

    cid = current_task.get()

    if not cid:
        messagebox.showwarning("No task", "Select a task first")
        return

    t = tasks[cid]


    # ================= BUILD CONTEXT =================

    context = {}

    context["brand_name"] = t["brand"]

    context["amount"] = t["amount"]

    context["contract_type"] = (
        "pre_pay" if t["type"] == "Pre"
        else "after_pay"
    )


    # ================= CHANNEL NAME =================

    channels = []

    for sub in t["subs"]:

        vendor, channel, platforms, adtype, qty, details = sub

        for plat in platforms.split(","):

            plat = plat.strip()

            if plat and channel:

                channels.append(
                    f"{plat}: {channel}"
                )

    context["channel_name"] = ", ".join(channels)


    # ================= OTHER REQUIRED FIELDS =================

    context["platform"] = platforms if t["subs"] else ""

    context["influencer_name_as_per_license"] = vendor if t["subs"] else ""

    context["license_number"] = ""

    context["city_as_per_license"] = ""

    context["neighbourhood_as_per_license"] = ""

    context["bank_name"] = ""

    context["account_name"] = ""

    context["iban"] = ""

    context["account_number"] = ""

    context["swift_code"] = ""



    # ================= GENERATE =================

    contract_id = generate_contract_from_gui(context)


    messagebox.showinfo(
        "Success",
        f"Contract Generated\n{contract_id}"
    )

# ==========================================================
# RIGHT SIDE (UNCHANGED LOGIC)
# ==========================================================

ttk.Label(right, text="Task Editor", font=("Arial", 14, "bold")).pack(pady=5)

current_task = tk.StringVar()

info = ttk.LabelFrame(right, text="Client Info", padding=10)
info.pack(fill="x", padx=10, pady=5)

brand_var = tk.StringVar()
amount_var = tk.StringVar()
type_var = tk.StringVar(value="Pre")
status_var = tk.StringVar(value="NEW")

SearchableCombo(info, CLIENTS, textvariable=brand_var, width=20).grid(row=0, column=0)
# --- Price field (label + entry grouped) ---
price_frame = ttk.Frame(info)
price_frame.grid(row=0, column=1, padx=10)

tk.Label(price_frame, text="Price:").pack(side="left")
ttk.Entry(price_frame, textvariable=amount_var, width=10).pack(side="left")



ttk.Radiobutton(info, text="Pre", variable=type_var, value="Pre").grid(row=0, column=2)
ttk.Radiobutton(info, text="After", variable=type_var, value="After").grid(row=0, column=3)


ttk.Combobox(info,
             values=list(STATUS_COLORS.keys()),
             textvariable=status_var,
             width=12).grid(row=0, column=4, padx=5)


def save_task():
    cid = current_task.get()
    if not cid:
        return

    t = tasks[cid]
    t["brand"] = brand_var.get()
    t["amount"] = amount_var.get()
    t["type"] = type_var.get()
    t["status"] = status_var.get()

    task_tree.item(cid,
                   values=(cid, t["brand"], t["status"], t["amount"],
                           t["type"], len(t["subs"]), today()),
                   tags=(t["status"],))

    apply_filters()


ttk.Button(info, text="Save", command=save_task).grid(row=0, column=5, padx=10)
ttk.Button(info, text="Generate Contract", command=generate_contract).grid(row=0, column=6, padx=10)


# ==========================================================
# RESTORED: SUBTASKS (VENDORS)
# ==========================================================

sub_frame = ttk.LabelFrame(right, text="Vendor Subtasks", padding=10)
sub_frame.pack(fill="both", expand=True, padx=10, pady=5)

sub_cols = ("Vendor", "Channel", "Platforms", "Type", "Qty", "Details")

sub_tree = ttk.Treeview(sub_frame, columns=sub_cols, show="headings", height=8)

for c in sub_cols:
    sub_tree.heading(c, text=c)
    sub_tree.column(c, width=100)

sub_tree.pack(fill="both", expand=True)

# ---------- Vendor editor state ----------
vendor_var = tk.StringVar()
channel_var = tk.StringVar()

platform_vars = {}

type_sub_var = tk.StringVar(value="Store Visit")
qty_var = tk.StringVar(value="1")
detail_var = tk.StringVar()

editing_index = None

def add_subtask():
    global editing_index

    cid = current_task.get()
    if not cid:
        messagebox.showwarning("Select task first", "Pick a task on the left")
        return

    plats = [p for p, v in platform_vars.items() if v.get()]

    values = (
        vendor_var.get(),
        channel_var.get(),
        ", ".join(plats),
        type_sub_var.get(),
        qty_var.get(),
        detail_var.get()
    )

    if editing_index is None:
        tasks[cid]["subs"].append(values)
    else:
        tasks[cid]["subs"][editing_index] = values
        editing_index = None

    # Refresh vendor table
    sub_tree.delete(*sub_tree.get_children())
    for s in tasks[cid]["subs"]:
        sub_tree.insert("", "end", values=s)

    # Clear editor
    vendor_var.set("")
    channel_var.set("")
    qty_var.set("1")
    detail_var.set("")
    for v in platform_vars.values():
        v.set(False)

    save_task()


# ---------- Inline vendor editor ----------
editor = ttk.Frame(right)
editor.pack(fill="x", padx=10, pady=5)

SearchableCombo(editor, VENDORS, textvariable=vendor_var, width=18)\
    .grid(row=0, column=0, padx=(0,5))

ttk.Entry(editor, textvariable=channel_var, width=18)\
    .grid(row=0, column=1, padx=(0,10))

platforms = ["TikTok", "Instagram", "Snapchat", "YouTube"]

for i, p in enumerate(platforms):
    v = tk.BooleanVar()
    platform_vars[p] = v
    ttk.Checkbutton(editor, text=p, variable=v)\
        .grid(row=0, column=i+2)

ad_combo = ttk.Combobox(
    editor,
    values=["Store Visit", "Home Ad", "Multi Service"],
    textvariable=type_sub_var,
    width=12
)
ad_combo.grid(row=0, column=6)

ttk.Entry(editor, textvariable=qty_var, width=5)\
    .grid(row=0, column=7)

detail_entry = ttk.Entry(editor, textvariable=detail_var, width=20)
detail_entry.grid(row=0, column=8)



def toggle_details(*_):
    if type_sub_var.get() == "Multi Service":
        detail_entry.grid()
    else:
        detail_entry.grid_remove()
        detail_var.set("")

ad_combo.bind("<<ComboboxSelected>>", toggle_details)
toggle_details()

ttk.Button(editor, text="Add / Update Vendor", command=add_subtask)\
    .grid(row=0, column=9, padx=5)


def edit_subtask(event):
    global editing_index

    sel = sub_tree.selection()
    if not sel:
        return

    item = sel[0]
    values = sub_tree.item(item, "values")

    # Save index
    editing_index = sub_tree.index(item)

    # Load values into editor
    vendor_var.set(values[0])
    channel_var.set(values[1])

    # Platforms
    for p in platform_vars:
        platform_vars[p].set(p in values[2])

    type_sub_var.set(values[3])
    qty_var.set(values[4])
    detail_var.set(values[5])

sub_tree.bind("<Double-1>", edit_subtask)




def load_task(event):
    sel = task_tree.selection()
    if not sel:
        return

    cid = sel[0]
    current_task.set(cid)

    t = tasks[cid]

    brand_var.set(t["brand"])
    amount_var.set(t["amount"])
    type_var.set(t["type"])
    status_var.set(t["status"])

    # -------- FIX: refresh vendor list --------
    sub_tree.delete(*sub_tree.get_children())

    for s in t["subs"]:
        sub_tree.insert("", "end", values=s)



task_tree.bind("<<TreeviewSelect>>", load_task)


root.mainloop()
