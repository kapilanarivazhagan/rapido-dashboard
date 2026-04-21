import pandas as pd


# ===============================
# HELPER FUNCTIONS
# ===============================

def safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")


# ===============================
# MAIN CLEAN FUNCTION
# ===============================

def clean_data(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    # ===============================
    # COLUMN STANDARDIZATION
    # ===============================

    df.columns = df.columns.str.strip()

    # ===============================
    # DATE CLEANING
    # ===============================

    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["DATE"])

    # ===============================
    # NUMERIC CLEANING
    # ===============================

    numeric_cols = [
        "GMV", "Rides", "Total Pings",
        "Accepted Pings", "Rider Busy Pings",
        "Rider Rejected", "Net Orders", "LoginHrs"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = safe_numeric(df[col]).fillna(0)

    # ===============================
    # REMOVE DUPLICATES
    # ===============================

    df = df.drop_duplicates(subset=["Mobile", "DATE"])

    # ===============================
    # KEEP ONLY REQUIRED COLUMNS
    # ===============================

    required_cols = [
        "DATE", "City", "Mobile", "GMV", "Rides",
        "Total Pings", "Accepted Pings",
        "Rider Busy Pings", "Rider Rejected",
        "Net Orders", "LoginHrs"
    ]

    available = [c for c in required_cols if c in df.columns]
    df = df[available]

    return df
