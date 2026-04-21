import gspread
import pandas as pd
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials


# ===============================
# DATE LOGIC
# ===============================
def get_auto_date():
    # Always return D-1 (no Sunday skip for Rapido)
    return (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")


def get_last_n_dates(target_date, n=7):
    target = datetime.strptime(target_date, "%Y-%m-%d")

    return [
        (target - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(n)
    ]


# ===============================
# CONNECT TO GOOGLE SHEET
# ===============================
def connect_sheet(sheet_id, credentials_path):

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=scope
    )

    client = gspread.authorize(creds)

    print("🔄 Checking accessible sheets...\n")

    for s in client.openall():
        print("   -", s.title)

    sheet = client.open_by_key(sheet_id)

    print(f"\n✅ Connected to: {sheet.title}")

    return sheet


# ===============================
# LOAD RAPIDO DATA
# ===============================
def load_rapido_data(sheet, dates):

    print("\n📄 Scanning worksheets...\n")

    all_data = []

    for ws in sheet.worksheets():

        raw_name = ws.title
        name = raw_name.lower().strip()
        name = name.replace("\n", "").replace("\xa0", "")

        # ===============================
        # MATCH TARGET SHEETS
        # ===============================
        if "yard ops" not in name:
            continue

        if "blr" in name:
            city = "bangalore"
        elif "chn" in name:
            city = "chennai"
        elif "hyd" in name:
            city = "hyderabad"
        else:
            continue

        print(f"📄 Loading: {raw_name} ({city})")

        data = ws.get_all_values()

        if not data:
            print("⚠️ Empty sheet")
            continue

        headers = data[0]

        # fix blank headers
        # fix blank + duplicate headers
        clean_headers = []
        seen = {}

        for i, h in enumerate(headers):

            col = h.strip() if h.strip() != "" else f"col_{i}"

            # handle duplicates
            if col in seen:
                seen[col] += 1  
                col = f"{col}_{seen[col]}"
            else:
                seen[col] = 0

            clean_headers.append(col)

        rows = data[1:]

        df = pd.DataFrame(rows, columns=clean_headers)

        # ===============================
        # CLEAN DATE COLUMN
        # ===============================
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")

        # ===============================
        # FILTER REQUIRED DATES
        # ===============================
        df = df[df["DATE"].dt.strftime("%Y-%m-%d").isin(dates)]

        print(f"   ✅ Rows loaded: {len(df)}")

        # ===============================
        # ADD CITY
        # ===============================
        df["City"] = city

        all_data.append(df)

    # ===============================
    # COMBINE ALL
    # ===============================
    if not all_data:
        print("\n❌ No data loaded")
        return pd.DataFrame()

    final_df = pd.concat(all_data, ignore_index=True)

    print(f"\n✅ Total rows loaded: {len(final_df)}")

    return final_df