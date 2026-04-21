import pandas as pd


def _safe_number(row, key, default=0):
    value = row.get(key, default)
    if pd.isna(value):
        return default
    return value


def _format_inr(value):
    amount = int(round(abs(value), 0))
    return f"{chr(8377)}{amount:,}"


def _arrow(value):
    return chr(8593) if value >= 0 else chr(8595)


def _highlight(value):
    return f"<strong>{value}</strong>"


def _absolute_delta(current, change_pct):
    current    = float(current or 0)
    change_pct = float(change_pct or 0)
    if change_pct == -100:
        previous = 0
    else:
        previous = current / (1 + (change_pct / 100))
    return current - previous


def _movement(value, up_word, down_word):
    return up_word if value >= 0 else down_word


def _city_title(city):
    if str(city).lower() == "all":
        return "All Cities"
    return str(city).title()


# ===============================
# ISSUE LOGIC (RAPIDO-SPECIFIC)
# ===============================

def _issue_from_changes(completion_change, missed_change, drivers_change, earnings_change, orders_change_abs):

    # Priority 1: Completion down + missed high → conversion loss
    if completion_change < -1 and missed_change > 5:
        return "Low completion is limiting order conversion"

    # Priority 2: Drivers up but avg orders low → utilization weak
    if drivers_change > 5 and earnings_change < (drivers_change * 0.5):
        return "Driver utilization is weak despite supply increase"

    # Priority 3: Earnings + orders both up → demand growth
    if earnings_change > 3 and orders_change_abs > 0:
        return "Strong demand growth is driving earnings"

    # Priority 4: Isolated completion drop
    if completion_change < -2:
        return "Low completion is limiting order conversion"

    # Priority 5: High missed alone
    if missed_change > 10:
        return "High missed orders are impacting revenue conversion"

    # Priority 6: Low driver supply
    if drivers_change < -5:
        return "Low driver supply is limiting growth"

    return "Performance stable with minor fluctuations"


# ===============================
# ACTION LOGIC
# ===============================

def _action_from_issue(issue, earnings_delta, earnings, missed, avg_orders, drivers):

    recovery = max(abs(earnings_delta) * 0.65, earnings * 0.04, 5000)
    unlock   = _highlight(_format_inr(recovery))

    if "missed" in issue:
        missed_10pct = max(int(missed * 0.10), 1)
        missed_earn  = _highlight(_format_inr(earnings * 0.08))
        return (
            f"Reducing missed orders by 10% (~{missed_10pct} orders) can recover "
            f"~{missed_earn} in earnings. Focus on acceptance rate and rider response time."
        )

    if "completion" in issue:
        return (
            f"Improve acceptance rate and reduce missed orders to "
            f"increase completion by ~2%. This can recover ~{unlock} in earnings."
        )

    if "utilization" in issue:
        if drivers and avg_orders:
            target_orders = int(avg_orders * 1.15)
            return (
                f"Improve driver utilization by increasing orders per driver from "
                f"{int(avg_orders)} to {target_orders}. Better allocation can unlock ~{unlock}."
            )
        return f"Improve driver utilization by increasing orders per driver to unlock ~{unlock}."

    if "demand growth" in issue:
        return (
            f"Capitalise on demand momentum by ensuring supply availability "
            f"during peak hours. Protect high-demand corridors to sustain growth."
        )

    return f"Tune supply allocation and protect high-performing routes to unlock ~{unlock} in earnings."


# ===============================
# TREND LINE
# ===============================

def _trend_line(city, direction):
    city_name = _city_title(city)
    if direction == "downward":
        return f"Earnings are trending downward over the last 7 days in {city_name}."
    return f"Earnings are trending upward over the last 7 days in {city_name}."


# ===============================
# BUILD ONE INSIGHT
# ===============================

def _build_insight(row, city_count=1):

    city              = str(row.get("City", "all"))
    earnings          = float(_safe_number(row, "Earnings"))
    earnings_change   = float(_safe_number(row, "earnings_change"))
    completion_change = float(_safe_number(row, "completion_change"))
    orders_change_abs = int(_safe_number(row, "orders_change_abs"))
    missed_change     = float(_safe_number(row, "missed_change"))
    drivers_change    = float(_safe_number(row, "drivers_change"))
    missed            = float(_safe_number(row, "missed_orders", 0))
    avg_orders        = float(_safe_number(row, "avg_orders", 0))
    drivers           = float(_safe_number(row, "Drivers Reported", 0))
    trend_direction   = str(row.get("trend_direction", "upward"))

    earnings_delta = _absolute_delta(earnings, earnings_change)

    issue = _issue_from_changes(
        completion_change, missed_change, drivers_change,
        earnings_change, orders_change_abs
    )

    city_suffix   = f" across {city_count} cities" if city == "all" else ""
    issue_display = f"{issue}{city_suffix}"

    earnings_direction   = _movement(earnings_delta, "increased", "declined")
    completion_direction = _movement(completion_change, "increased", "decreased")
    orders_direction     = _movement(orders_change_abs, "increased", "dropped")

    earnings_cause       = "driven by higher accepted pings" if orders_change_abs > 0 else "despite order activity"
    completion_impl      = "affecting conversion efficiency" if completion_change < 0 else "reflecting improved conversion"
    orders_impact        = "impacting revenue positively" if earnings_delta > 0 else "putting pressure on revenue"

    what_changed = {
        "earnings": (
            f"Earnings {_arrow(earnings_delta)} {earnings_direction} by "
            f"{_highlight(_format_inr(earnings_delta))}, {earnings_cause}."
        ),
        "completion": (
            f"Completion {_arrow(completion_change)} {completion_direction} "
            f"by {_highlight(f'{abs(completion_change):.1f}%')}, {completion_impl}."
        ),
        "orders": (
            f"Orders {_arrow(orders_change_abs)} {orders_direction} by "
            f"{_highlight(f'{abs(orders_change_abs):,}')}, {orders_impact}."
        ),
    }

    action_plan = _action_from_issue(issue, earnings_delta, earnings, missed, avg_orders, drivers)
    trend_line  = _trend_line(city, trend_direction)

    return {
        "city":        city,
        "city_label":  _city_title(city),
        "key_issue":   issue_display,
        "what_changed": what_changed,
        "action_plan": action_plan,
        "trend_line":  trend_line,
        # Compat aliases
        "what":   issue_display,
        "why":    trend_line,
        "action": action_plan,
        "actionable_recommendation": action_plan,
    }


# ===============================
# COMBINED ALL-CITIES ROW
# ===============================

def _combined_row(city_df):

    city_count    = len(city_df)
    total_earnings = city_df["Earnings"].sum()
    total_orders  = city_df["Completed Orders"].sum() if "Completed Orders" in city_df.columns else 0
    total_missed  = city_df["missed_orders"].sum() if "missed_orders" in city_df.columns else 0
    total_drivers = city_df["Drivers Reported"].sum() if "Drivers Reported" in city_df.columns else 0

    def weighted_change(column):
        if column not in city_df.columns or not total_earnings:
            return 0
        return (city_df[column].fillna(0) * city_df["Earnings"].fillna(0)).sum() / total_earnings

    first_day = city_df.get("first_day_earnings", pd.Series([0])).sum()
    last_day  = city_df.get("last_day_earnings",  pd.Series([0])).sum()
    direction = "downward" if last_day < first_day else "upward"

    avg_orders = total_orders / max(total_drivers, 1)

    return {
        "City":               "all",
        "Earnings":           total_earnings,
        "Completed Orders":   total_orders,
        "missed_orders":      total_missed,
        "Drivers Reported":   total_drivers,
        "avg_orders":         round(avg_orders, 1),
        "earnings_change":    weighted_change("earnings_change"),
        "completion_change":  weighted_change("completion_change"),
        "orders_change":      weighted_change("orders_change"),
        "orders_change_abs":  city_df.get("orders_change_abs", pd.Series([0])).sum(),
        "missed_change":      weighted_change("missed_change"),
        "drivers_change":     weighted_change("drivers_change"),
        "first_day_earnings": first_day,
        "last_day_earnings":  last_day,
        "trend_direction":    direction,
    }, city_count


# ============================================================
# MAIN INSIGHT GENERATOR
# ============================================================

def generate_city_insights(city_df: pd.DataFrame):

    insights = []

    if city_df.empty:
        return insights

    combined, city_count = _combined_row(city_df)
    insights.append(_build_insight(combined, city_count=city_count))

    for _, row in city_df.iterrows():
        insights.append(_build_insight(row, city_count=1))

    return insights


# ============================================================
# FORMAT FOR DISPLAY
# ============================================================

def format_insights(insights):

    formatted = []

    for ins in insights:
        changed = ins["what_changed"]
        text = (
            f"{ins['city_label']} -> "
            f"Issue: {ins['key_issue']} | "
            f"{changed['earnings']} {changed['completion']} {changed['orders']} | "
            f"Action: {ins['action_plan']}"
        )
        formatted.append(text)

    return formatted
