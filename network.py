import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import urllib3
import matplotlib.pyplot as plt
import uuid

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Bandwidth", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps – change to match your actual uplink capacity

# ── Period configuration ─────────────────────────────────────────────────────
PERIODS = {
    "Live (2 hours)":    {"hours": 2,   "avg": 0,     "name": "Live (2 hours)"},
    "Last 48 hours":     {"hours": 48,  "avg": 300,   "name": "Last 48 hours"},     # 5 min
    "Last 7 days":       {"days":  7,   "avg": 900,   "name": "Last 7 days"},       # 15 min
    "Last 30 days":      {"days":  30,  "avg": 3600,  "name": "Last 30 days"},      # 1 hour
    "Last 365 days":     {"days":  365, "avg": 86400, "name": "Last 365 days"},     # daily
}

if "period_key" not in st.session_state:
    st.session_state.period_key = f"period_{uuid.uuid4()}"

period_label = st.selectbox(
    "Time Period",
    list(PERIODS.keys()),
    index=1,
    key=st.session_state.period_key
)

period = PERIODS[period_label]
avg_sec = period["avg"]

# Time range
now = datetime.utcnow()
if "hours" in period:
    start = now - timedelta(hours=period["hours"])
else:
    start = now - timedelta(days=period["days"])
sdate = start.strftime("%Y-%m-%d-%H-%M-%S")
edate = now.strftime("%Y-%m-%d-%H-%M-%S")

SENSORS = {
    "Firstlight":         "12435",
    "NNINIX":             "12506",
    "Hurricane Electric": "12363",
    "Cogent":             "12340",
}

@st.cache_data(ttl=240)
def fetch_historic_data(sensor_id):
    url = f"{BASE}/api/historicdata.json"
    params = {
        "id": sensor_id,
        "avg": avg_sec,
        "sdate": sdate,
        "edate": edate,
        "usecaption": 1,
        "username": USER,
        "passhash": PH
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=30)
        r.raise_for_status()
        data = r.json()

        if "histdata" not in data or not data["histdata"]:
            st.warning(f"Sensor {sensor_id}: No historic data returned")
            return None, 0.0, 0.0

        df = pd.DataFrame(data["histdata"])
        df["datetime"] = pd.to_datetime(df["datetime_raw"], unit="s", utc=True)

        # Channel detection
        channels = {}
        for k in data:
            if k.startswith("item") and isinstance(data[k], dict) and "name" in data[k]:
                ch_name = data[k]["name"].strip().lower()
                ch_id = k.replace("item", "")
                channels[ch_id] = ch_name

        in_col = out_col = None
        for ch_id, name in channels.items():
            col_name = f"value{ch_id}"
            if col_name not in df.columns:
                continue
            if any(kw in name for kw in ["in", "down", "traffic in", "download", "receive", "ingress"]):
                in_col = col_name
            elif any(kw in name for kw in ["out", "up", "traffic out", "upload", "send", "egress"]):
                out_col = col_name

        if not in_col and not out_col:
            st.warning(
                f"Sensor {sensor_id}: No matching In/Out channels. "
                f"Available channel names: {list(channels.values())}"
            )
            return None, 0.0, 0.0

        # Unit conversion: bytes/sec → Mbps (most common for PRTG traffic sensors)
        # If your channels are already in Mbps, change to: divisor = 1.0
        # If kbit/s → divisor = 1000.0
        divisor = 125000.0

        df_mbps = df[["datetime"]].copy()
        peak_in = peak_out = 0.0

        if in_col:
            series = pd.to_numeric(df[in_col], errors="coerce") / divisor
            df_mbps["In (Mbps)"] = series
            peak_in = series.max()
            if pd.isna(peak_in):
                peak_in = 0.0

        if out_col:
            series = pd.to_numeric(df[out_col], errors="coerce") / divisor
            df_mbps["Out (Mbps)"] = series
            peak_out = series.max()
            if pd.isna(peak_out):
                peak_out = 0.0

        peak_in = round(float(peak_in), 2)
        peak_out = round(float(peak_out), 2)

        return df_mbps, peak_in, peak_out

    except requests.exceptions.RequestException as e:
        st.error(f"Sensor {sensor_id} – API request failed: {str(e)}")
        return None, 0.0, 0.0
    except Exception as e:
        st.error(f"Sensor {sensor_id} – Unexpected error: {str(e)}")
        return None, 0.0, 0.0


# ────────────────────────────────────────────────────────────────
st.title("PRTG Bandwidth Dashboard")
st.caption(f"Period: **{period_label}**  |  Averaging: **{avg_sec if avg_sec > 0 else 'raw'} seconds**")

total_in = total_out = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]

    for col, (name, sid) in zip(cols, pair):
        with col:
            st.subheader(name)

            df, peak_in, peak_out = fetch_historic_data(sid)
            total_in += peak_in
            total_out += peak_out

            st.metric("Peak In",  f"{peak_in:,.1f} Mbps")
            st.metric("Peak Out", f"{peak_out:,.1f} Mbps")

            if df is not None and not df.empty:
                df_long = df.melt(
                    id_vars=["datetime"],
                    var_name="Direction",
                    value_name="Mbps"
                ).dropna(subset=["Mbps"])

                fig = px.line(
                    df_long,
                    x="datetime",
                    y="Mbps",
                    color="Direction",
                    title=f"{name} Traffic",
                    color_discrete_map={
                        "In (Mbps)":  "#00c853",   # bright green
                        "Out (Mbps)": "#d81b60"    # magenta/red
                    },
                    labels={"datetime": "Time", "Mbps": "Mbps"}
                )

                fig.update_layout(
                    height=550,
                    hovermode="x unified",
                    legend_title_text="",
                    xaxis_title="",
                    yaxis_title="Mbps",
                    template="plotly_dark",   # change to "plotly_white" for light mode
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )

                fig.update_traces(line=dict(width=2.2))

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No graph data available for this period")

st.markdown("## Combined Peak Bandwidth Across All Circuits")
st.markdown("")

col1, col2 = st.columns([3.2, 1])

with col1:
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(
        ["Peak In", "Peak Out"],
        [total_in, total_out],
        color=["#00c853", "#d81b60"],
        width=0.48,
        edgecolor="white",
        linewidth=2.2
    )

    current_max = max(total_in, total_out, 1)
    ax.set_ylim(0, current_max * 1.18)

    ax.set_ylabel("Mbps", fontsize=15, fontweight="bold")
    ax.set_title(f"Total Combined Peak – {period_label}", fontsize=22, fontweight="bold", pad=25)
    ax.set_facecolor("#0e1117")
    fig.patch.set_facecolor("#0e1117")

    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)

    ax.tick_params(colors="white", labelsize=13)
    ax.grid(axis="y", alpha=0.18, color="white", linestyle="--")

    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + (current_max * 0.025),
            f"{height:,.0f}",
            ha="center", va="bottom",
            fontsize=26, fontweight="bold", color="white"
        )

    st.pyplot(fig, use_container_width=True)

with col2:
    cap = TOTAL_CAPACITY if TOTAL_CAPACITY > 0 else 1
    pct_in = (total_in / cap) * 100
    pct_out = (total_out / cap) * 100

    st.metric("**Total Inbound Peak**",  f"{total_in:,.0f} Mbps")
    st.metric("**Total Outbound Peak**", f"{total_out:,.0f} Mbps")

    st.divider()
    st.markdown("### Circuit Utilization")

    st.caption(f"Inbound ({pct_in:.1f}%)")
    st.progress(min(pct_in / 100, 1.0))

    st.caption(f"Outbound ({pct_out:.1f}%)")
    st.progress(min(pct_out / 100, 1.0))

    st.caption(f"Design Capacity: {TOTAL_CAPACITY:,.0f} Mbps")
