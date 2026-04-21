import sys
from datetime import datetime, timedelta

from data_loader import connect_sheet, load_rapido_data, get_auto_date, get_last_n_dates
from config import SHEET_ID, CREDENTIALS_PATH, MODE, MANUAL_DATE
from cleaner import clean_data
from metrics import build_metrics
from ai_insights import generate_city_insights, format_insights
from html_template import generate_html


# ===============================
# DATE LOGIC
# ===============================

def resolve_date():
    if len(sys.argv) > 2 and sys.argv[1] == "--date":
        return sys.argv[2]
    if MODE == "manual":
        return MANUAL_DATE
    return get_auto_date()


# ===============================
# MAIN PIPELINE
# ===============================

def run(target_date: str):

    print(f"\n📅 Target Date: {target_date}")

    # ---- Load ----
    dates = get_last_n_dates(target_date, 7)
    sheet = connect_sheet(SHEET_ID, CREDENTIALS_PATH)
    df    = load_rapido_data(sheet, dates)

    print(f"\n📊 Total rows loaded: {len(df)}")

    if df.empty:
        print("❌ No data — aborting.")
        return

    # ---- Clean ----
    clean_df = clean_data(df)
    print(f"✅ Clean rows: {len(clean_df)}")

    # ---- Build metrics (today + yday + charts + city breakdown) ----
    result = build_metrics(clean_df, target_date)

    # ---- Debug print KPIs ----
    print("\n🔝 KPI Summary")
    for k, v in result["kpis"].items():
        print(f"  {k}: {v}")

    # ---- Insights ----
    insights  = generate_city_insights(result["city_data"])
    formatted = format_insights(insights)

    print("\n🧠 Insights")
    for line in formatted:
        print(f"  {line[:120]}")

    # ---- Generate HTML ----
    html_content = generate_html(
        {
            "kpis":      result["kpis"],
            "charts":    result["charts"],
            "city_data": result["city_data"],
            "insights":  insights,
        },
        target_date,
    )

    # ---- Save ----
    filename = "rapido_report.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ HTML saved: {filename}")


# ===============================
# ENTRY POINT
# ===============================

if __name__ == "__main__":
    run(resolve_date())