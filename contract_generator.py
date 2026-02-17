from docxtpl import DocxTemplate
import pandas as pd
import os
import re
from datetime import datetime
from num2words import num2words
from docx2pdf import convert
import time
import random
import shutil
import json

def generate_contract_from_gui(context):

    # reuse your existing logic variables
    global last_number
    global generated_excel_path
    global archive_dir
    global output_dir
    global temp_convert_dir


    # ===== SAME ID LOGIC =====

    brand_id = get_brand_id(context.get("brand_name", ""))

    last_number += 1

    contract_id = f"CTR{brand_id}{last_number:06d}"

    context["id"] = contract_id


    # ===== SAME TEMPLATE =====

    contract_key = re.sub(r"\s+", "_", context.get("contract_type", "").lower())

    template_path = TEMPLATE_MAP.get(contract_key, STANDARD_TEMPLATE)

    doc = DocxTemplate(template_path)


    # ===== SAVE DOCX =====

    filename = safe_filename(contract_id)

    docx_path = os.path.join(archive_dir, f"{filename}.docx")

    doc.render(context)

    doc.save(docx_path)


    # ===== PDF =====

    convert(docx_path)


    # ===== SAVE EXCEL =====

    new_row = pd.DataFrame([context])

    if os.path.exists(generated_excel_path):

        existing = pd.read_excel(generated_excel_path)

        new_row = pd.concat([existing, new_row], ignore_index=True)

    new_row.to_excel(generated_excel_path, index=False)


    return contract_id


# =================================================
# CONFIGURATION
# =================================================
excel_path = r"C:\Users\siraj\OneDrive - AQ Creativity\contracts.xlsx"
output_dir = r"C:\Users\siraj\OneDrive - AQ Creativity\CONTRACTS"
temp_convert_dir = r"C:\Users\siraj\OneDrive - AQ Creativity\TEMP"
progress_file = r"C:\Users\siraj\PycharmProjects\automation\last_row.txt"
skipped_file = r"C:\Users\siraj\PycharmProjects\automation\skipped_rows.txt"
generated_excel_path = r"C:\Users\siraj\OneDrive - AQ Creativity\generated.xlsx"
archive_dir = r"C:\Users\siraj\OneDrive - AQ Creativity\ARCHIVE"
brand_id_file = r"C:\Users\siraj\OneDrive - AQ Creativity\brand_ids.json"


START_DATA_ROW = 2
os.makedirs(output_dir, exist_ok=True)
os.makedirs(temp_convert_dir, exist_ok=True)

# =================================================
# CLEAN TEMP FOLDER (SAFETY)
# =================================================
for f in os.listdir(temp_convert_dir):
    try:
        os.remove(os.path.join(temp_convert_dir, f))
    except Exception:
        pass

# =================================================
# TEMPLATE SELECTION
# =================================================
TEMPLATE_MAP = {
    "after_pay": r"C:\Users\siraj\PycharmProjects\automation\templates\Contract template(2).docx",
    "pre_pay": r"C:\Users\siraj\PycharmProjects\automation\templates\advance payment contract .docx",
    "savola": r"C:\Users\siraj\PycharmProjects\automation\templates\Savola Contract  FULL.docx",
    "pre_savola": r"C:\Users\siraj\PycharmProjects\automation\templates\Savola Contract advance .docx",
    "crispy": r"C:\Users\siraj\PycharmProjects\automation\templates\UGC Crispy Contract  .docx",
    "santia": r"C:\Users\siraj\PycharmProjects\automation\templates\Santia Contract  (1).docx",
    "free_lancer": r"C:\Users\siraj\PycharmProjects\automation\templates\Freelancer Contract .docx",
}

STANDARD_TEMPLATE = TEMPLATE_MAP["after_pay"]

# ==========================================a=======
# RESUME POINT
# =================================================
if os.path.exists(progress_file):
    with open(progress_file, "r") as f:
        last_row = int(f.read().strip())
else:
    last_row = START_DATA_ROW - 1

# =================================================
# LOAD EXCEL
# =================================================
df = pd.read_excel(
    excel_path,
    sheet_name="Live",
    dtype=str
)

df.columns = (
    df.columns.str.strip()
    .str.lower()
    .str.replace(" ", "_")
    .str.replace(r"[()]", "", regex=True)
)

if "ad_type" in df.columns:
    df["ad_types"] = df["ad_type"]

# =================================================
# MAPS
# =================================================
PLATFORM_MAP = {
    "instagram": "إنستقرام",
    "insta": "إنستقرام",
    "tiktok": "تيك توك",
    "tik tok": "تيك توك",
    "tik": "تيك توك",
    "snapchat": "سناب شات",
    "snap chat": "سناب شات",
    "snap": "سناب شات",
    "kick": "كيك"
}

AD_TYPE_MAP = {
    "multi service": "خدمة متعددة",
    "home ad": "إعلان منزلي",
    "store visit": "إعلان زيارة"
}

ARABIC_DAYS = {
    "Monday": "الإثنين",
    "Tuesday": "الثلاثاء",
    "Wednesday": "الأربعاء",
    "Thursday": "الخميس",
    "Friday": "الجمعة",
    "Saturday": "السبت",
    "Sunday": "الأحد"
}

# =================================================
# DATE
# =================================================
today = datetime.today()
today_date = today.strftime("%d/%m/%Y")
today_day_ar = ARABIC_DAYS.get(today.strftime("%A"), today.strftime("%A"))

# =================================================
# HELPERS
# =================================================
def safe_filename(text):
    return re.sub(r'[\\/*?:"<>|]', "", str(text)).strip()

def unique_path(path):
    base, ext = os.path.splitext(path)
    counter = 1
    new_path = path
    while os.path.exists(new_path):
        new_path = f"{base}_{counter}{ext}"
        counter += 1
    return new_path

def normalize_channel_name(raw):

    if not raw:
        return ""

    entries = [e.strip() for e in raw.split(",") if e.strip()]
    result = []

    for entry in entries:

        # Case 1: Platform + name
        if ":" in entry:

            platform_raw, name = entry.split(":", 1)

            platform_key = platform_raw.strip().lower()
            platform_ar = PLATFORM_MAP.get(platform_key, platform_raw.strip())

            name = name.strip().replace("@", "")

            result.append(f"{platform_ar}: {name}")

        # Case 2: Name only
        else:

            name = entry.replace("@", "").strip()

            result.append(f"@{name}")

    return "\n".join(result)




def get_brand_id(brand_name):
    brand_key = re.sub(r"[^A-Za-z0-9]", "", str(brand_name).upper())

    # Load existing brand IDs
    if os.path.exists(brand_id_file):
        with open(brand_id_file, "r") as f:
            brand_map = json.load(f)
    else:
        brand_map = {}

    # If brand already exists → return its ID
    if brand_key in brand_map:
        return brand_map[brand_key]

    # Assign new ID automatically
    if brand_map:
        max_id = max(int(v) for v in brand_map.values())
        new_id = str(max_id + 1)
    else:
        new_id = "1"

    brand_map[brand_key] = new_id

    # Save updated map
    with open(brand_id_file, "w") as f:
        json.dump(brand_map, f, indent=4)

    return new_id

def normalize_platform(raw):
    if not raw:
        return ""
    parts = re.split(r"[,+/&]+", raw.lower())
    result, seen = [], set()
    for p in parts:
        p = p.strip()
        if p in PLATFORM_MAP and p not in seen:
            result.append(PLATFORM_MAP[p])
            seen.add(p)
    return " و ".join(result)

def missing_reason(ctx):
    checks = {
        "influencer_name_as_per_license": "missing name",
        "license_number": "missing license",
        "bank_name": "missing bank name",
        "account_name": "missing account name",
        "iban": "missing IBAN",
        "account_number": "missing account number",
        "channel_name": "missing channel",
        "platform": "missing platform",
        "amount": "missing amount",
    }
    for k, msg in checks.items():
        if not ctx.get(k, "").strip():
            return msg
    return None

# =================================================
# PROCESS CONTRACTS
# =================================================
skipped_rows = []
start_time = time.time()
generated = 0
generated_rows = []
new_docx_files = []
last_number = 0


existing_ids = set()

if os.path.exists(generated_excel_path):
    df_existing = pd.read_excel(generated_excel_path, dtype=str)
    if "ID" in df_existing.columns:
        ids = df_existing["ID"].dropna().astype(str)
        nums = ids.str.extract(r"(\d{6})$")[0]
        nums = nums.dropna().astype(int)
        if not nums.empty:
            last_number = nums.max()
        else:
            last_number = 0
else:
    last_number = 0


for excel_row in range(last_row + 1, len(df) + START_DATA_ROW):
    row = df.iloc[excel_row - START_DATA_ROW]
    context = {k: str(v).strip() for k, v in row.fillna("").items()}

    # ===== SKIP CHECK =====
    reason = missing_reason(context)
    if reason:
        skipped_rows.append(excel_row)
        with open(skipped_file, "a", encoding="utf-8") as f:
            f.write(f"Row {excel_row} skipped – {reason}\n")
        with open(progress_file, "w") as f:
            f.write(str(excel_row))
        continue

    # ===== TEMPLATE SELECTION =====
    contract_key = re.sub(r"\s+", "_", context.get("contract_type", "").lower())
    template_path = TEMPLATE_MAP.get(contract_key, STANDARD_TEMPLATE)
    doc = DocxTemplate(template_path)

    # ===== CONTEXT SETUP =====
    full_name = context["influencer_name_as_per_license"]
    parts = full_name.split()
    context["name"] = full_name
    context["license_name"] = full_name
    context["name_2"] = f"{parts[0]} {parts[-1]}" if len(parts) >= 2 else full_name
    context["channel_name"] = normalize_channel_name(context["channel_name"])
    context["platform"] = normalize_platform(context["platform"])
    context["platform_smart"] = context["platform"]

    raw_ad = context.get("ad_types", "")
    if raw_ad:
        pieces = [p.strip() for p in raw_ad.split(",")]
        key = pieces[0].lower()
        qty = pieces[1] if len(pieces) > 1 and pieces[1].isdigit() else ""
        ad_ar = AD_TYPE_MAP.get(key, pieces[0])
        context["ad_types"] = f'{ad_ar} "{qty}"' if qty else ad_ar

    context["date"] = today_date
    context["day"] = f"({today_day_ar})"

    # ===== AMOUNT PROCESSING (HALALA + RTL) =====
    raw_amount = context.get("amount", "").replace(",", "").strip()
    if not raw_amount or raw_amount == ".":
        skipped_rows.append(excel_row)
        with open(skipped_file, "a", encoding="utf-8") as f:
            f.write(f"Row {excel_row} skipped – invalid amount\n")
        with open(progress_file, "w") as f:
            f.write(str(excel_row))
        continue

    if "." in raw_amount:
        r_str, h_str = raw_amount.split(".", 1)
        h_str = (h_str + "00")[:2]
    else:
        r_str = raw_amount
        h_str = "00"

    if not r_str.isdigit() or not h_str.isdigit():
        skipped_rows.append(excel_row)
        with open(skipped_file, "a", encoding="utf-8") as f:
            f.write(f"Row {excel_row} skipped – non-numeric amount\n")
        with open(progress_file, "w") as f:
            f.write(str(excel_row))
        continue

    r = int(r_str)
    h = int(h_str)
    amount_words = num2words(r, lang="ar") + " ريال سعودي"
    if h > 0:
        amount_words += " و " + num2words(h, lang="ar") + " هللة"

    amount_number = f"({r}.{h_str})" if h > 0 else f"({r})"
    RTL_START = "\u202B"
    RTL_END = "\u202C"
    context["Amount_full"] = RTL_START + f"{amount_number} {amount_words}" + RTL_END

    # ===== SAVE DOCX =====
    brand_id = get_brand_id(context.get("brand_name", ""))

    last_number += 1
    contract_id = f"CTR{brand_id}{last_number:06d}"

    context["id"] = contract_id
    context["date"] = today_date

    filename = safe_filename(contract_id)
    os.makedirs(archive_dir, exist_ok=True)
    docx_path = os.path.join(archive_dir, f"{filename}.docx")
    docx_path = unique_path(docx_path)

    doc.render(context)
    doc.save(docx_path)
    new_docx_files.append(docx_path)

    # ===== COLLECT GENERATED ROW =====
    output_row = context.copy()
    output_row["id"] = contract_id
    output_row["date"] = today_date
    generated_rows.append(output_row)

    # ===== PROGRESS UPDATE =====
    with open(progress_file, "w") as f:
        f.write(str(excel_row))

    print(f"[{excel_row}] {full_name} — {context.get('brand_name','')} — {context.get('amount','')} SAR ✔")
    generated += 1


# =================================================
# PDF CONVERSION (ONLY NEW FILES)
# =================================================
# =================================================
# PDF CONVERSION (TRUE BATCH)
# =================================================

if new_docx_files:

    # Copy only new files into temp folder
    for docx_file in new_docx_files:
        shutil.copy(
            docx_file,
            os.path.join(temp_convert_dir, os.path.basename(docx_file))
        )

    # Batch convert entire temp folder
    convert(temp_convert_dir)

    # Move generated PDFs
    today_folder = os.path.join(output_dir, today.strftime("%Y-%m-%d"))
    os.makedirs(today_folder, exist_ok=True)

    for f in os.listdir(temp_convert_dir):
        full_path = os.path.join(temp_convert_dir, f)

        if f.lower().endswith(".pdf"):
            os.replace(
                full_path,
                os.path.join(today_folder, f)
            )
        else:
            os.remove(full_path)


# =================================================
# END-OF-RUN SUMMARY
# =================================================
elapsed = round(time.time() - start_time, 2)
print("\n📊 RUN SUMMARY")
print(f"Generated: {generated}")
print(f"Skipped: {len(skipped_rows)}")
print(f"Time: {elapsed} seconds")

generated_df = pd.DataFrame(generated_rows)

ordered_cols = [
    "id",
    "influencer_name_as_per_license",
    "license_number",
    "city_as_per_license",
    "neighbourhood_as_per_license",
    "brand_name",
    "platform",
    "channel_name",
    "ad_types",
    "amount",
    "bank_name",
    "account_name",
    "iban",
    "account_number",
    "swift_code",
    "contract_type",
    "date",
]

generated_df = generated_df.reindex(columns=ordered_cols)

# =================================================
# WRITE GENERATED OUTPUT TO SEPARATE EXCEL
# =================================================

if os.path.exists(generated_excel_path):
    existing_df = pd.read_excel(generated_excel_path, dtype=str)
    generated_df = pd.concat([existing_df, generated_df], ignore_index=True)

generated_df.to_excel(
    generated_excel_path,
    index=False
)


# =================================================
# AUTO-OPEN OUTPUT FOLDER
# =================================================
os.startfile(output_dir)

print("🎉 DONE — ALL CONTRACTS GENERATED SAFELY")
