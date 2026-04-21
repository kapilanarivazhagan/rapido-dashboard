from datetime import datetime
from html import escape
import json


def format_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("&#128202; Rapido Report - %d %B")


def format_inr(val):
    return f"{chr(8377)}{int(val):,}"


def _json_records(data):
    if data is None:
        return []

    if isinstance(data, list):
        records = data
    else:
        records = data.to_dict(orient="records")

    clean_records = []

    for record in records:
        clean = {}
        for key, value in record.items():
            if value != value:  # NaN check
                clean[key] = None
            else:
                clean[key] = value
        clean_records.append(clean)

    return clean_records


def _chart_payload(trend):
    records = _json_records(trend)

    if not records:
        return {"labels": [], "datasets": []}

    date_keys = sorted({
        record["Order Date"].strftime("%Y-%m-%d")
        if hasattr(record["Order Date"], "strftime")
        else str(record["Order Date"])[:10]
        for record in records
    })

    labels = []
    for date_key in date_keys:
        dt = datetime.strptime(date_key, "%Y-%m-%d")
        labels.append(dt.strftime("%b %d (%a)"))

    cities   = sorted({str(record["City"]) for record in records})
    datasets = []

    for city in cities:
        city_records = {}
        for record in records:
            record_city = str(record["City"])
            raw_date    = record["Order Date"]
            date_key    = raw_date.strftime("%Y-%m-%d") if hasattr(raw_date, "strftime") else str(raw_date)[:10]
            if record_city == city:
                city_records[date_key] = int(round(record["Earnings"], 0))

        datasets.append({
            "label": city,
            "data":  [city_records.get(dk, None) for dk in date_keys],
        })

    return {"labels": labels, "datasets": datasets}


def _allow_strong(text):
    safe = escape(str(text))
    return (
        safe
        .replace("&lt;strong&gt;",  "<strong>")
        .replace("&lt;/strong&gt;", "</strong>")
    )


def _insight_text(text):
    return _allow_strong(text)


# ===============================
# CHANGE FORMAT
# ===============================

def fmt_change(change, metric):
    change = float(change or 0)
    if change == 0:
        return "0.0%"
    arrow = "&#8593;" if change > 0 else "&#8595;"
    return f"{arrow} {abs(change):.1f}%"


def change_class(change, metric):
    change = float(change or 0)
    if change == 0:
        return "change neutral"
    if metric == "missed":
        good = change < 0
    else:
        good = change > 0
    tone = "positive" if good else "negative"
    return f"change {tone}"


# ===============================
# MAIN HTML GENERATOR
# ===============================

def generate_html(report_data, date):

    kpis      = report_data["kpis"]
    city_data = report_data["city_data"]
    charts    = report_data.get("charts", {})
    insights  = report_data["insights"]

    # ===============================
    # CITY KPI JSON
    # ===============================
    city_kpi = {}
    for _, row in city_data.iterrows():
        drivers     = int(row.get("Drivers Reported", 0) or 0)
        driver_count = max(drivers, 1)
        earnings_raw = float(row.get("Earnings", 0) or 0)
        orders_raw   = int(row.get("Net Orders", 0) or 0)   
        completion   = float(row.get("completion_pct", 0) or 0)
        missed       = int(row.get("missed_orders", 0) or 0)

        active_riders = int(row.get("Active Riders", 0) or 0)
        active_pct    = int(row.get("Active %", 0) or 0)

        city_kpi[row["City"]] = {
            "earnings":          format_inr(earnings_raw),
            "orders":            orders_raw,
            "completion":        int(round(completion)),
            "drivers":           f"{active_riders} ({active_pct}%)",
            "missed":            missed,
            "avg_earnings":      format_inr(earnings_raw / driver_count),
            "avg_orders":        int((row.get("Net Orders", 0) or 0) / driver_count),
            "earnings_change":   float(row.get("earnings_change",   0) or 0),
            "avg_earnings_change": float(row.get("avg_earnings_change", 0) or 0),
            "completion_change": float(row.get("completion_change", 0) or 0),
            "orders_change":     float(row.get("orders_change",     0) or 0),
            "orders_change_abs": int(row.get("orders_change_abs",   0) or 0),
            "avg_orders_change": float(row.get("avg_orders_change", 0) or 0),
            "active_pct_change": float(row.get("active_pct_change", 0) or 0),
            "missed_change":     float(row.get("missed_change",     0) or 0),
        }

    city_kpi_json = json.dumps(city_kpi, ensure_ascii=False)

    driver_earnings_raw     = charts.get("driver_earnings_chart")
    driver_earnings_records = _json_records(driver_earnings_raw) if driver_earnings_raw is not None else []

    chart_json = json.dumps(
        {
            "cityEarningsTrend":   _chart_payload(charts.get("city_earnings_trend")),
            "city_driver_earnings": driver_earnings_records,
        },
        ensure_ascii=False,
    )

    # ===============================
    # INSIGHTS HTML
    # ===============================
    insights_html = ""
    for ins in insights:
        city_key    = escape(str(ins["city"]).lower())
        city_label  = escape(str(ins.get("city_label", "All Cities" if city_key == "all" else str(ins["city"]).title())))
        what_changed      = ins.get("what_changed", {})
        key_issue         = _insight_text(ins.get("key_issue", ins.get("what", "")))
        action_plan       = _insight_text(ins.get("action_plan", ins.get("action", "")))
        trend_line        = _insight_text(ins.get("trend_line",  ins.get("why",    "")))
        earnings_change   = _insight_text(what_changed.get("earnings",   "Earnings —"))
        completion_change = _insight_text(what_changed.get("completion", "Completion —"))
        orders_change     = _insight_text(what_changed.get("orders",     "Trips —").replace("Orders", "Trips"))

        insights_html += f"""
        <article class="insight-card" data-city="{city_key}">
            <div class="insight-city">&#128205; {city_label}</div>

            <div class="insight-block">
                <div class="insight-label">&#9888; Key Issue:</div>
                <p>{key_issue}</p>
            </div>

            <div class="insight-block">
                <div class="insight-label">&#128202; What Changed:</div>
                <div class="change-story">
                    <p>{earnings_change}</p>
                    <p>{completion_change}</p>
                    <p>{orders_change}</p>
                </div>
                <p class="trend-line">&#128200; {trend_line}</p>
            </div>

            <div class="insight-block">
                <div class="insight-label">&#128640; Action Plan:</div>
                <p>{action_plan}</p>
            </div>
        </article>
        """

    options = "".join([
        f'<option value="{escape(str(c))}">{escape(str(c).title())}</option>'
        for c in city_data["City"]
    ])

    # ===============================
    # KPI VALUES (for JS filterCity)
    # ===============================
    e_val   = format_inr(kpis['earnings'])
    ae_val  = format_inr(kpis['avg_earnings'])
    c_val   = f"{int(kpis['completion'])}%"
    d_val   = f"{int(kpis.get('active_riders', 0))} ({int(kpis.get('active_pct', 0))}%)"
    o_val   = int(kpis['orders'])
    ao_val  = int(kpis['avg_orders'])
    m_val   = int(kpis['missed'])

    e_chg   = kpis['earnings_change']
    ae_chg  = kpis.get('avg_earnings_change', 0)
    c_chg   = kpis['completion_change']
    d_chg   = kpis.get('active_pct_change', 0)
    o_chg   = kpis['orders_change']
    ao_chg  = kpis.get('avg_orders_change', 0)
    m_chg   = kpis['missed_change']

    # ===============================
    # FULL HTML
    # ===============================
    html = f"""
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapido Report - {date}</title>
    <meta name="description" content="Rapido fleet performance report for {date}. City-wise earnings, orders, completion and driver insights.">

    <style>

    * {{
        box-sizing: border-box;
    }}

    html,
    body {{
        height: 100%;
        margin: 0;
        overflow-x: hidden;
        overflow-y: auto;
    }}

    body {{
        font-family: Arial, sans-serif;
        background:
        linear-gradient(rgba(10,10,20,0.45), rgba(10,10,20,0.7)),
        url("Ready-for-migrating-to-an-electric-vehicle-fleet.jpg");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    .app-shell {{
        display: flex;
        flex-direction: column;
        height: 100vh;
        min-height: 100vh;
    }}

    .header {{
        flex: 0 0 auto;
        text-align: center;
        padding: 14px 16px 8px;
        font-size: 30px;
        font-weight: 900;
        color: #ffffff;
        letter-spacing: 0.06em;
        text-shadow: 0 2px 10px rgba(0,0,0,0.6);
    }}

    .filter {{
        flex: 0 0 auto;
        text-align: center;
        padding-bottom: 8px;
    }}

    select {{
        min-width: 170px;
        padding: 7px 11px;
        border-radius: 6px;
        background: rgba(15,23,42,0.84);
        color: white;
        border: 1px solid rgba(148,163,184,0.28);
        outline: none;
    }}

    .dashboard-viewport {{
        flex: 1 1 auto;
        min-height: 0;
        padding: 0 14px 10px;
        overflow: hidden;
    }}

    .dashboard-track {{
        display: grid;
        grid-template-columns: 25% 75%;
        grid-template-rows: 1fr 1fr;
        gap: 12px;
        height: 100%;
        min-height: 0;
    }}

    .page {{
        min-width: 0;
        min-height: 0;
    }}

    .kpi-page {{
        grid-column: 1;
        grid-row: 1 / span 2;
    }}

    .insights-page {{
        grid-column: 2;
        grid-row: 1;
    }}

    .chart-page {{
        grid-column: 2;
        grid-row: 2;
    }}

    .section-panel {{
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        background: rgba(15,23,42,0.18);
        border: 1px solid rgba(148,163,184,0.12);
        border-radius: 8px;
        backdrop-filter: blur(14px);
        padding: 10px;
    }}

    .section-title {{
        color: #ffffff;
        flex: 0 0 auto;
        margin: 0 0 8px;
        padding-bottom: 7px;
        border-bottom: 1px solid rgba(148,163,184,0.2);
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }}

    /* KPI PANEL */
    .kpi-stack {{
        flex: 1 1 auto;
        min-height: 0;
        display: grid;
        grid-template-rows: repeat(7, 1fr);
        gap: 7px;
    }}

    .kpi-card {{
        display: grid;
        grid-template-columns: minmax(86px, 1fr) minmax(72px, auto) minmax(66px, auto);
        align-items: center;
        gap: 8px;
        min-height: 0;
        background: rgba(30,41,59,0.35);
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 8px;
        padding: 8px 10px;
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 24px rgba(2,6,23,0.16);
    }}

    .kpi-card .label {{
        min-width: 0;
        color: #e2e8f0;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-align: left;
        text-transform: uppercase;
        white-space: normal;
    }}

    .kpi-card .value {{
        color: #f8fafc;
        font-size: 18px;
        font-weight: 800;
        line-height: 1;
        text-align: center;
        white-space: nowrap;
    }}

    /* KPI VALUE COLORS */
    .kpi-card.earnings .value   {{ color: #4ade80; }}
    .kpi-card.avg .value        {{ color: #38bdf8; }}
    .kpi-card.completion .value {{ color: #60a5fa; }}
    .kpi-card.orders .value     {{ color: #fbbf24; }}
    .kpi-card.drivers .value    {{ color: #a78bfa; }}
    .kpi-card.missed .value     {{ color: #f87171; }}

    .change {{
        color: #94a3b8;
        font-size: 14px;
        font-weight: 700;
        text-align: right;
        text-shadow: 0 0 10px currentColor;
        white-space: nowrap;
    }}

    .change.positive {{
        color: #4ade80;
        text-shadow: 0 0 8px rgba(74,222,128,0.6);
    }}

    .change.negative {{
        color: #f87171;
        text-shadow: 0 0 8px rgba(248,113,113,0.6);
    }}

    .change.neutral {{
        color: #94a3b8;
        text-shadow: none;
    }}

    .earnings   {{ border-left: 4px solid #4ade80; }}
    .completion {{ border-left: 4px solid #60a5fa; }}
    .orders     {{ border-left: 4px solid #fbbf24; }}
    .drivers    {{ border-left: 4px solid #a78bfa; }}
    .avg        {{ border-left: 4px solid #38bdf8; }}
    .missed     {{ border-left: 4px solid #f87171; }}

    /* INSIGHTS */
    .insights-list {{
        flex: 1 1 auto;
        min-height: 0;
    }}

    .insights {{
        height: 100%;
        overflow-y: auto;
        padding-right: 6px;
    }}

    .insight-card {{
        min-height: 100%;
        background: rgba(30,41,59,0.32);
        border: 1px solid rgba(148,163,184,0.16);
        border-radius: 8px;
        padding: 16px;
        line-height: 1.35;
        margin-bottom: 10px;
    }}

    .insight-card:last-child {{
        margin-bottom: 0;
    }}

    .insight-city {{
        margin-bottom: 12px;
        color: #bfdbfe;
        font-size: 15px;
        font-weight: 800;
        text-transform: uppercase;
    }}

    .insight-block {{
        margin-bottom: 13px;
    }}

    .insight-block:last-child {{
        margin-bottom: 0;
    }}

    .insight-label {{
        color: #ffffff;
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 0.04em;
        margin-bottom: 5px;
    }}

    .insight-block p {{
        margin: 0;
        font-size: 14px;
        color: #e2e8f0;
        font-weight: 400;
    }}

    .change-story p {{
        margin: 0 0 6px;
        font-size: 14px;
        color: #f1f5f9;
    }}

    .change-story p:last-child {{
        margin-bottom: 0;
    }}

    .trend-line {{
        margin-top: 7px !important;
        color: #cbd5f5 !important;
        font-size: 13px !important;
    }}

    strong {{
        color: #f8fafc;
    }}

    /* CHART */
    .chart-card {{
        display: flex;
        flex-direction: column;
        flex: 1 1 auto;
        min-height: 0;
        height: 100%;
        background: rgba(30,41,59,0.28);
        border: 1px solid rgba(148,163,184,0.16);
        border-radius: 8px;
        padding: 10px;
    }}

    .chart-container {{
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        gap: 10px;
        width: 100%;
        height: 100%;
    }}

    .chart-half {{
        flex: 1 1 0;
        min-width: 0;
        min-height: 0;
        display: flex;
        flex-direction: column;
    }}

    .chart-half-title {{
        flex: 0 0 auto;
        color: #94a3b8;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }}

    .chart-half canvas {{
        flex: 1 1 auto;
        min-height: 0;
    }}

    canvas {{
        display: block;
        width: 100% !important;
        height: 100% !important;
    }}

    .empty-chart {{
        color: #94a3b8;
        font-size: 14px;
    }}

    .mobile-dots {{
        display: none;
        flex: 0 0 auto;
    }}

    .footer {{
        flex: 0 0 auto;
        text-align: center;
        padding: 7px;
        border-top: 1px solid rgba(148,163,184,0.18);
        color: #94a3b8;
        font-size: 11px;
    }}

    @media (max-width: 920px) {{
        .app-shell {{
            height: auto;
            min-height: 100vh;
        }}

        .header {{
            padding-top: 10px;
            font-size: 21px;
        }}

        .filter {{
            padding-bottom: 6px;
        }}

        .dashboard-viewport {{
            padding: 0;
            overflow-y: visible;
        }}

        .dashboard-track {{
            display: flex;
            width: 300%;
            gap: 0;
            transform: translateX(0);
            transition: transform 280ms ease;
        }}

        .page,
        .kpi-page,
        .insights-page,
        .chart-page {{
            grid-column: auto;
            grid-row: auto;
            flex: 0 0 100vw;
            width: 100vw;
            height: auto;
            padding: 0 10px;
        }}

        .chart-container {{
            flex-direction: column;
            gap: 20px;
        }}

        .chart-half {{
            height: 300px;
            flex: none;
        }}

        .kpi-card {{
            grid-template-columns: minmax(92px, 1fr) minmax(72px, auto) minmax(68px, auto);
        }}

        .insight-block p,
        .change-story p {{
            font-size: 13px;
        }}

        canvas {{
            min-height: 0;
        }}

        .mobile-dots {{
            display: flex;
            justify-content: center;
            gap: 8px;
            padding: 6px 0;
        }}

        .dot-indicator {{
            width: 7px;
            height: 7px;
            border-radius: 999px;
            background: rgba(148,163,184,0.36);
            border: none;
            padding: 0;
        }}

        .dot-indicator.active {{
            width: 22px;
            background: #60a5fa;
        }}

        .footer {{
            display: block;
            font-size: 10px;
            padding: 6px;
            text-align: center;
            color: #94a3b8;
            border-top: 1px solid rgba(148,163,184,0.18);
            background: rgba(15,23,42,0.9);
            position: static;
        }}
    }}

    </style>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2"></script>
    <script>

    const cityData  = {city_kpi_json};
    const chartData = {chart_json};
    const chartColors = ["#4ade80", "#60a5fa", "#fbbf24", "#a78bfa", "#38bdf8", "#f87171", "#fb7185", "#34d399"];

    const chartConfig = {{
        type: "line",
        data: {{
            labels: chartData.cityEarningsTrend.labels,
            datasets: chartData.cityEarningsTrend.datasets.map((dataset, index) => {{
                if (dataset.label === "All Cities") {{
                    return {{
                        label: "All Cities",
                        data: dataset.data,
                        borderColor: "#ffffff",
                        borderWidth: 3,
                        borderDash: [6, 4],
                        spanGaps: true,
                        pointRadius: function(ctx) {{
                            const value = ctx.raw;
                            const data = ctx.dataset.data.filter(v => v !== null);
                            const max = Math.max(...data);
                            const min = Math.min(...data);
                            if (value === max || value === min) return 6;
                            return 0;
                        }},
                        pointBackgroundColor: function(ctx) {{
                            const value = ctx.raw;
                            const data = ctx.dataset.data.filter(v => v !== null);
                            const max = Math.max(...data);
                            const min = Math.min(...data);
                            if (value === max) return "#4ade80";
                            if (value === min) return "#f87171";
                            return "#ffffff";
                        }}
                    }};
                }}

                const color = chartColors[index % chartColors.length];
                return {{
                    label: dataset.label,
                    data: dataset.data,
                    borderColor: color,
                    backgroundColor: color,
                    spanGaps: true,
                    pointRadius: function(ctx) {{
                        const value = ctx.raw;
                        const data = ctx.dataset.data.filter(item => item !== null);
                        const max = Math.max(...data);
                        const min = Math.min(...data);
                        if (value === max || value === min) return 6;
                        return 3;
                    }},
                    pointBackgroundColor: function(ctx) {{
                        const value = ctx.raw;
                        const data = ctx.dataset.data.filter(item => item !== null);
                        const max = Math.max(...data);
                        const min = Math.min(...data);
                        if (value === max) return "#4ade80";
                        if (value === min) return "#f87171";
                        return ctx.dataset.borderColor;
                    }}
                }};
            }})
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{
                intersect: false,
                mode: "nearest"
            }},
            elements: {{
                line: {{ tension: 0.4, borderWidth: 3 }},
                point: {{ radius: 4, hoverRadius: 7 }}
            }},
            plugins: {{
                legend: {{
                    labels: {{
                        color: "#e2e8f0",
                        boxWidth: 12,
                        font: {{ size: 11 }}
                    }}
                }},
                tooltip: {{
                    callbacks: {{
                        label: function(context) {{
                            return context.dataset.label + ": \u20b9" + context.raw.toLocaleString();
                        }}
                    }}
                }},
                datalabels: {{ display: false }}
            }},
            scales: {{
                x: {{
                    ticks: {{ color: "#94a3b8", maxRotation: 0, autoSkip: true }},
                    grid:  {{ color: "rgba(148,163,184,0.1)" }}
                }},
                y: {{
                    display: false,
                    beginAtZero: true,
                    ticks: {{
                        color: "#cbd5e1",
                        callback: function(value) {{ return "\u20b9" + value.toLocaleString(); }}
                    }},
                    grid: {{ color: "rgba(148,163,184,0.12)" }}
                }}
            }}
        }},
        plugins: [ChartDataLabels]
    }};

    let activePage = 0;
    let touchStartX = 0;

    function formatChange(change, metric) {{
        const n = Number(change) || 0;
        if (n === 0) return {{ text: "0.0%", tone: "neutral" }};
        const isGood = metric === "missed" ? n < 0 : n > 0;
        const tone   = isGood ? "positive" : "negative";
        const arrow  = n > 0 ? "&#8593;" : "&#8595;";
        return {{ text: `${{arrow}} ${{Math.abs(n).toFixed(1)}}%`, tone }};
    }}

    function setKpi(id, value, change, metric) {{
        document.getElementById(id).innerText = value;
        const el    = document.getElementById(`${{id}}_change`);
        const state = formatChange(change, metric);
        el.className = `change ${{state.tone}}`;
        el.innerHTML = state.text;
    }}

    function filterInsights(city) {{
        document.querySelectorAll(".insight-card").forEach((card) => {{
            const cardCity = card.getAttribute("data-city");
            card.style.display = cardCity === city ? "block" : "none";
        }});
    }}

    function filterCity() {{
        const city = document.getElementById("cityFilter").value;
        const d    = city === "all" ? null : cityData[city];

        setKpi("earnings",    city === "all" ? "{e_val}"  : d.earnings,    city === "all" ? {e_chg}  : d.earnings_change,   "earnings");
        setKpi("avg_earnings",city === "all" ? "{ae_val}" : d.avg_earnings, city === "all" ? {ae_chg} : d.avg_earnings_change, "avg_earnings");
        setKpi("completion",  city === "all" ? "{c_val}"  : d.completion + "%", city === "all" ? {c_chg}  : d.completion_change,  "completion");
        setKpi("drivers",     city === "all" ? "{d_val}"  : d.drivers,     city === "all" ? {d_chg}  : d.active_pct_change,    "drivers");
        setKpi("orders",      city === "all" ? "{o_val}"  : d.orders,      city === "all" ? {o_chg}  : d.orders_change,     "orders");
        setKpi("avg_orders",  city === "all" ? "{ao_val}" : d.avg_orders,  city === "all" ? {ao_chg} : d.avg_orders_change, "avg_orders");
        setKpi("missed",      city === "all" ? "{m_val}"  : d.missed,      city === "all" ? {m_chg}  : d.missed_change,     "missed");
        filterInsights(city);
    }}

    function setPage(page) {{
        activePage = Math.max(0, Math.min(2, page));
        const track = document.getElementById("dashboardTrack");
        if (window.matchMedia("(max-width: 920px)").matches) {{
            track.style.transform = `translateX(-${{activePage * 100}}vw)`;
        }} else {{
            track.style.transform = "";
        }}
        document.querySelectorAll(".dot-indicator").forEach((dot, index) => {{
            dot.classList.toggle("active", index === activePage);
        }});
    }}

    function initSwipe() {{
        const viewport = document.getElementById("dashboardViewport");
        viewport.addEventListener("touchstart", (e) => {{
            touchStartX = e.touches[0].clientX;
        }}, {{ passive: true }});
        viewport.addEventListener("touchend", (e) => {{
            const deltaX = e.changedTouches[0].clientX - touchStartX;
            if (Math.abs(deltaX) < 45) return;
            setPage(activePage + (deltaX < 0 ? 1 : -1));
        }}, {{ passive: true }});
        window.addEventListener("resize", () => setPage(activePage));
    }}

    function drawCityEarningsChart() {{
        const canvas   = document.getElementById("cityEarningsChart");
        const labels   = chartData.cityEarningsTrend.labels   || [];
        const datasets = chartData.cityEarningsTrend.datasets || [];

        if (!labels.length || !datasets.length) {{
            const empty = document.createElement("div");
            empty.className = "empty-chart";
            empty.textContent = "7-day earnings trend unavailable";
            canvas.replaceWith(empty);
            return;
        }}

        new Chart(canvas, chartConfig);
    }}

    function drawDriverChart() {{
        const canvas = document.getElementById("driverChart");
        if (!canvas) return;

        const rows = chartData.city_driver_earnings || [];
        if (!rows.length) {{
            const empty = document.createElement("div");
            empty.className = "empty-chart";
            empty.textContent = "Driver earnings data unavailable";
            canvas.replaceWith(empty);
            return;
        }}

        const cities   = rows.map(r => r.City);
        const earnings = rows.map(r => r.Earnings || 0);
        const drivers  = rows.map(r => r["Drivers Reported"] || 0);

        new Chart(canvas, {{
            type: "bar",
            data: {{
                labels: cities,
                datasets: [
                    {{
                        label: "Earnings",
                        data: earnings,
                        backgroundColor: "rgba(74,222,128,0.7)",
                        borderColor: "#4ade80",
                        borderWidth: 1,
                        yAxisID: "yEarnings"
                    }},
                    {{
                        label: "Drivers Reported",
                        data: drivers,
                        backgroundColor: "rgba(167,139,250,0.7)",
                        borderColor: "#a78bfa",
                        borderWidth: 1,
                        yAxisID: "yDrivers"
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{
                            color: "#e2e8f0",
                            boxWidth: 12,
                            font: {{ size: 10 }}
                        }}
                    }},
                    tooltip: {{
                        displayColors: false,
                        callbacks: {{
                            title: function() {{ return null; }},
                            label: function(ctx) {{
                                const index = ctx.dataIndex;
                                const city  = ctx.chart.data.labels[index];
                                const earn  = ctx.chart.data.datasets[0].data[index];
                                const drv   = ctx.chart.data.datasets[1].data[index];
                                let fe = earn >= 100000
                                    ? (earn / 100000).toFixed(1) + "L"
                                    : (earn / 1000).toFixed(1) + "K";
                                const cityCap = city.charAt(0).toUpperCase() + city.slice(1);
                                return [
                                    "City: " + cityCap,
                                    "Drivers: " + drv.toLocaleString("en-IN"),
                                    "Earnings: \u20b9" + fe
                                ];
                            }}
                        }}
                    }},
                    datalabels: {{
                        display: true,
                        align: "end",
                        anchor: "end",
                        color: "#e2e8f0",
                        font: {{ size: 10, weight: "bold" }},
                        formatter: function(value, ctx) {{
                            if (ctx.dataset.label === "Earnings") {{
                                if (value >= 100000) return (value / 100000).toFixed(1) + "L";
                                return (value / 1000).toFixed(1) + "K";
                            }}
                            return value.toLocaleString("en-IN");
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: "#94a3b8", font: {{ size: 10 }} }},
                        grid:  {{ color: "rgba(148,163,184,0.1)" }}
                    }},
                    yEarnings: {{
                        type: "linear",
                        position: "left",
                        display: false,
                        beginAtZero: true
                    }},
                    yDrivers: {{
                        type: "linear",
                        position: "right",
                        display: false,
                        beginAtZero: true,
                        grid: {{ drawOnChartArea: false }}
                    }}
                }}
            }},
            plugins: [ChartDataLabels]
        }});
    }}

    document.addEventListener("DOMContentLoaded", () => {{
        filterCity();
        initSwipe();
        setPage(0);
        drawCityEarningsChart();
        drawDriverChart();
    }});

    </script>

    </head>

    <body>
    <div class="app-shell">

        <div class="header">
            {format_date(date)}
        </div>

        <div class="filter">
            <select id="cityFilter" onchange="filterCity()">
                <option value="all">All Cities</option>
                {options}
            </select>
        </div>

        <main class="dashboard-viewport" id="dashboardViewport">
            <div class="dashboard-track" id="dashboardTrack">

                <section class="page kpi-page">
                    <div class="section-panel">
                        <h3 class="section-title">KPI</h3>

                        <div class="kpi-stack">
                            <div class="kpi-card earnings">
                                <span class="label">Earnings</span>
                                <span class="value" id="earnings">{e_val}</span>
                                <span class="{change_class(e_chg, 'earnings')}" id="earnings_change">{fmt_change(e_chg, 'earnings')}</span>
                            </div>

                            <div class="kpi-card avg">
                                <span class="label">Avg Earnings</span>
                                <span class="value" id="avg_earnings">{ae_val}</span>
                                <span class="{change_class(ae_chg, 'avg_earnings')}" id="avg_earnings_change">{fmt_change(ae_chg, 'avg_earnings')}</span>
                            </div>

                            <div class="kpi-card completion">
                                <span class="label">Completion %</span>
                                <span class="value" id="completion">{c_val}</span>
                                <span class="{change_class(c_chg, 'completion')}" id="completion_change">{fmt_change(c_chg, 'completion')}</span>
                            </div>

                            <div class="kpi-card drivers">
                                <span class="label">Active Riders</span>
                                <span class="value" id="drivers">{d_val}</span>
                                <span class="{change_class(d_chg, 'drivers')}" id="drivers_change">{fmt_change(d_chg, 'drivers')}</span>
                            </div>

                            <div class="kpi-card orders">
                                <span class="label">Trips</span>
                                <span class="value" id="orders">{o_val}</span>
                                <span class="{change_class(o_chg, 'orders')}" id="orders_change">{fmt_change(o_chg, 'orders')}</span>
                            </div>

                            <div class="kpi-card avg">
                                <span class="label">Avg Trips</span>
                                <span class="value" id="avg_orders">{ao_val}</span>
                                <span class="{change_class(ao_chg, 'avg_orders')}" id="avg_orders_change">{fmt_change(ao_chg, 'avg_orders')}</span>
                            </div>

                            <div class="kpi-card missed">
                                <span class="label">Missed Trips</span>
                                <span class="value" id="missed">{m_val}</span>
                                <span class="{change_class(m_chg, 'missed')}" id="missed_change">{fmt_change(m_chg, 'missed')}</span>
                            </div>
                        </div>
                    </div>
                </section>

                <section class="page insights-page">
                    <div class="section-panel">
                        <h3 class="section-title">Insights</h3>
                        <div class="insights insights-list">
                            {insights_html}
                        </div>
                    </div>
                </section>

                <section class="page chart-page">
                    <div class="section-panel">
                        <h3 class="section-title">Charts</h3>
                        <div class="chart-card">
                            <div class="chart-container">
                                <div class="chart-half">
                                    <div class="chart-half-title">&#128200; City Earnings &mdash; Last 7 Days</div>
                                    <canvas id="cityEarningsChart" aria-label="City vs Earnings last 7 days line chart"></canvas>
                                </div>
                                <div class="chart-half">
                                    <div class="chart-half-title">&#128101; Drivers vs Earnings by City</div>
                                    <canvas id="driverChart" aria-label="Drivers reported vs earnings per city bar chart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

            </div>
        </main>

        <div class="mobile-dots">
            <button class="dot-indicator active" onclick="setPage(0)" aria-label="Show KPI"></button>
            <button class="dot-indicator"        onclick="setPage(1)" aria-label="Show Insights"></button>
            <button class="dot-indicator"        onclick="setPage(2)" aria-label="Show Charts"></button>
        </div>

        <div class="footer">
            Kapilan A &bull; Data Scientist &bull; Fyn Mobility
        </div>

    </div>
    </body>
    </html>
    """

    return html
