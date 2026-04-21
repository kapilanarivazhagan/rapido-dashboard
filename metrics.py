import pandas as pd

BASE_KPI_KEYS = (
    "earnings",
    "avg_earnings",
    "completion",
    "orders",
    "avg_orders",
    "missed",
    "active_pct"
)


# ===============================
# HELPERS
# ===============================

def _safe_div(numerator, denominator):
    return (numerator / denominator) if denominator else 0


def pct_change(today, yday):
    if yday == 0:
        return 0
    return round(((today - yday) / yday) * 100, 1)


# ===============================
# FILTER DATA
# ===============================

def filter_data(df, target_date):
    target_date = pd.to_datetime(target_date).normalize()
    dates = pd.to_datetime(df["DATE"], errors="coerce").dt.normalize()
    return df[dates == target_date].copy()


# ===============================
# KPI CALCULATION
# ===============================

def calculate_kpis(df):

    if df.empty:
        return {key: 0 for key in BASE_KPI_KEYS}

    # ---- EARNINGS ----
    gmv = df["GMV"].sum()

    # ---- DRIVERS REPORTED (active = GMV > 0) ----
    total_drivers = df["Mobile"].nunique()
    active_drivers = df[df["GMV"] > 0]["Mobile"].nunique()
    active_pct = (active_drivers / total_drivers * 100) if total_drivers else 0
    driver_count = max(active_drivers, 1)

    # ---- AVG EARNINGS ----
    avg_earnings = _safe_div(gmv, driver_count)

    # ---- ORDERS = Accepted Pings ----
    orders = df["Accepted Pings"].sum()

    # ---- NET ORDERS ----
    net_orders = df["Net Orders"].sum()

    # ---- COMPLETION = Net Orders / Accepted Pings (capped at 100%) ----
    completion = min(_safe_div(net_orders, orders) * 100, 100.0)

    # ---- AVG ORDERS = Net Orders / Drivers Reported ----
    avg_orders = _safe_div(net_orders, driver_count)

    # ---- MISSED ORDERS = Accepted Pings - Net Orders ----
    missed = max(int(orders - net_orders), 0)

    return {
        "earnings":    int(round(gmv, 0)),
        "avg_earnings": int(round(avg_earnings, 0)),
        "completion":  float(round(completion, 1)),
        "orders":      int(orders),
        "avg_orders":  int(round(avg_orders, 0)),
        "missed":      missed,
        "active_riders": int(active_drivers),
        "active_pct":  round(active_pct)
    }


# ===============================
# CHANGE CALCULATION
# ===============================

def calculate_changes(today_kpis, yday_kpis):

    changes = {}

    for key in BASE_KPI_KEYS:
        today = today_kpis.get(key, 0) or 0
        yday  = yday_kpis.get(key, 0) or 0

        if yday == 0:
            changes[f"{key}_change"] = 0.0
        else:
            changes[f"{key}_change"] = round(((today - yday) / yday) * 100, 1)

    changes["orders_change_abs"] = (
        (today_kpis.get("orders", 0) or 0)
        - (yday_kpis.get("orders", 0) or 0)
    )

    return changes


# ===============================
# CITY-WISE AGGREGATION
# ===============================

def city_metrics(df):

    if df.empty:
        return pd.DataFrame()

    agg_dict = {
        "GMV":           "sum",
        "Accepted Pings": "sum",
        "Net Orders":     "sum",
        "Rider Rejected": "sum",
        "LoginHrs":       "mean",
    }

    available = {k: v for k, v in agg_dict.items() if k in df.columns}
    city_df = df.groupby("City").agg(available).reset_index()

    # Compute total drivers:
    total = df.groupby("City")["Mobile"].nunique().reset_index()
    total.rename(columns={"Mobile": "Total Drivers"}, inplace=True)

    # Compute active riders:
    active = df[df["GMV"] > 0].groupby("City")["Mobile"].nunique().reset_index()
    active.rename(columns={"Mobile": "Active Riders"}, inplace=True)

    # Merge into city_df:
    city_df = city_df.merge(total, on="City", how="left")
    city_df = city_df.merge(active, on="City", how="left")

    # Fill nulls:
    city_df["Active Riders"] = city_df["Active Riders"].fillna(0)
    city_df["Total Drivers"] = city_df["Total Drivers"].fillna(0)

    # Calculate %:
    city_df["Active %"] = (
        city_df["Active Riders"] / city_df["Total Drivers"].replace(0, 1) * 100
    ).round(0).fillna(0)

    # Alias for downstream calculations
    city_df["Drivers Reported"] = city_df["Active Riders"].astype(int)

    # Derived
    driver_count = city_df["Drivers Reported"].clip(lower=1)
    city_df["Earnings"]      = city_df["GMV"]
    city_df["trips"]         = city_df["Net Orders"]
    city_df["avg_earnings"]  = (city_df["GMV"] / driver_count).round(0).astype(int)
    city_df["missed_orders"] = (city_df["Accepted Pings"] - city_df["Net Orders"]).clip(lower=0).astype(int)

    # Completion = Net Orders / Accepted Pings (capped at 100%)
    accepted_clip = city_df["Accepted Pings"].clip(lower=1)
    city_df["completion_pct"] = ((city_df["Net Orders"] / accepted_clip) * 100).clip(upper=100).round(1)

    # Avg Trips = Net Orders / Drivers Reported
    city_df["avg_trips"] = (
        city_df["Net Orders"] / city_df["Drivers Reported"].replace(0, 1)
    ).round(0).astype(int)

    # Rename for compatibility with insights
    city_df.rename(columns={
        "Accepted Pings": "Completed Orders",
        "Rider Rejected": "missed_notifs_overall",
        "Net Orders":     "Net Orders",
        "GMV":            "GMV_raw",
    }, inplace=True)

    return city_df


def add_city_changes(city_data, df_today, df_yday):

    city_data = city_data.copy()

    for key in BASE_KPI_KEYS:
        city_data[f"{key}_change"] = 0.0
    city_data["orders_change_abs"] = 0

    if city_data.empty:
        return city_data

    for idx, row in city_data.iterrows():
        city = row["City"]
        t_kpis = calculate_kpis(df_today[df_today["City"] == city])
        y_kpis = calculate_kpis(df_yday[df_yday["City"] == city])
        changes = calculate_changes(t_kpis, y_kpis)
        for k, v in changes.items():
            city_data.at[idx, k] = v

    return city_data


# ===============================
# 7-DAY TREND (SAME PATTERN AS PORTER)
# ===============================

def get_last_7_days_earnings(df, target_date):

    trend_df = df.copy()
    target_date = pd.to_datetime(target_date).normalize()
    trend_df["DATE"] = pd.to_datetime(trend_df["DATE"], errors="coerce").dt.normalize()
    trend_df = trend_df.dropna(subset=["DATE"])

    # No Sunday filter for Rapido

    if trend_df.empty:
        return pd.DataFrame(columns=["Order Date", "City", "Earnings"])

    last_7 = trend_df[
        (trend_df["DATE"] <= target_date)
        & (trend_df["DATE"] >= target_date - pd.Timedelta(days=6))
    ]

    trend = (
        last_7
        .groupby(["DATE", "City"], as_index=False)["GMV"]
        .sum()
        .rename(columns={"DATE": "Order Date", "GMV": "Earnings"})
        .sort_values("Order Date")
    )

    trend = trend[trend["Earnings"] > 0]

    # All Cities line
    total = (
        trend
        .groupby("Order Date")["Earnings"]
        .sum()
        .reset_index()
    )
    total["City"] = "All Cities"

    return pd.concat([trend, total], ignore_index=True)


def get_city_driver_earnings(df, target_date):

    df_copy = df.copy()
    target_date = pd.to_datetime(target_date).normalize()
    df_copy["DATE"] = pd.to_datetime(df_copy["DATE"], errors="coerce").dt.normalize()

    today_df = df_copy[df_copy["DATE"] == target_date]

    result = (
        today_df
        .groupby("City")
        .agg(
            Earnings=("GMV", "sum"),
        )
        .reset_index()
    )

    active = today_df[today_df["GMV"] > 0].groupby("City")["Mobile"].nunique().reset_index()
    active.rename(columns={"Mobile": "Drivers Reported"}, inplace=True)
    result = result.merge(active, on="City", how="left")
    result["Drivers Reported"] = result["Drivers Reported"].fillna(0).astype(int)

    return result


def add_trend_context(city_data, earnings_trend):

    city_data = city_data.copy()
    city_data["first_day_earnings"] = 0
    city_data["last_day_earnings"]  = 0
    city_data["trend_direction"]    = "flat"

    if isinstance(earnings_trend, pd.DataFrame) and not earnings_trend.empty:
        trend_df = earnings_trend.copy()
        trend_df["city"]  = trend_df["City"].astype(str)
        trend_df["date"]  = pd.to_datetime(trend_df["Order Date"], errors="coerce")
        trend_df["earnings"] = trend_df["Earnings"]
    else:
        return city_data

    for idx, row in city_data.iterrows():
        city = row["City"]
        ct = trend_df[trend_df["city"] == city].sort_values("date")
        if ct.empty:
            continue
        first = int(ct.iloc[0]["earnings"])
        last  = int(ct.iloc[-1]["earnings"])
        direction = "upward" if last > first else ("downward" if last < first else "flat")
        city_data.at[idx, "first_day_earnings"] = first
        city_data.at[idx, "last_day_earnings"]  = last
        city_data.at[idx, "trend_direction"]    = direction

    return city_data


# ===============================
# CHART PREP
# ===============================

def prepare_charts(df, target_date):

    chart_df = df.copy()
    chart_df["DATE"] = pd.to_datetime(chart_df["DATE"], errors="coerce")
    chart_df = chart_df.dropna(subset=["DATE"])

    city_earnings_trend  = get_last_7_days_earnings(chart_df, target_date)
    driver_earnings_chart = get_city_driver_earnings(chart_df, target_date)

    return {
        "city_earnings_trend":  city_earnings_trend,
        "driver_earnings_chart": driver_earnings_chart,
    }


# ===============================
# MAIN BUILD
# ===============================

def build_metrics(df, target_date):

    target_date = pd.to_datetime(target_date)
    yday = target_date - pd.Timedelta(days=1)

    df_today = filter_data(df, target_date)
    df_yday  = filter_data(df, yday)

    kpis_today = calculate_kpis(df_today)
    kpis_yday  = calculate_kpis(df_yday)

    yday_values = {f"{k}_yday": kpis_yday.get(k, 0) for k in BASE_KPI_KEYS}
    changes     = calculate_changes(kpis_today, kpis_yday)
    kpis = {**kpis_today, **yday_values, **changes}

    charts    = prepare_charts(df, target_date)
    city_data = city_metrics(df_today)
    city_data = add_city_changes(city_data, df_today, df_yday)
    city_data = add_trend_context(city_data, charts["city_earnings_trend"])

    return {
        "kpis":      kpis,
        "city_data": city_data,
        "charts":    charts,
    }