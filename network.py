import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import uuid
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps - adjust as needed

if "period_key" not in st.session_state:
    st.session_state.period_key = f"period_{uuid.uuid4()}"

period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key=st.session_state.period_key
)

graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}[period]

# For short periods: use channel max (PRTG computes over recent data)
# For longer: use historicdata with avg
use_historic = period in ["Last 7 days", "Last 30 days", "Last 365 days"]

period_deltas = {
    "Live (2 hours)": timedelta(hours=2),
    "Last 48 hours":  timedelta(hours=48),
    "Last 7 days":    timedelta(days=7),
    "Last 30 days":   timedelta(days=30),
    "Last 365 days":  timedelta(days=365)
}
delta = period_deltas[period]

now = datetime.now()
edate = now.strftime("%Y-%m-%d-%H-%M-%S")
sdate = (now - delta).strftime("%Y-%m-%d-%H-%M-%S")

# Avg only for historic (seconds); short periods skip
avg_interval = 300 if use_historic else 0  # 5 min for longer periods

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

@st.cache_data(ttl=300)
def get_traffic_stats(sensor_id, use_hist, sdate=None, edate=None, avg=0):
    divisor = 10_000_000  # raw bit/s → Mbps; test/adjust if needed (try 1_000_000 if too small)

    if not use_hist:
        # Short periods: channel overview (max over recent, reliable for live)
        url = f"{BASE}/api/table.json"
        params = {
            "content": "channels",
            "id": sensor_id,
            "columns": "name,minimum_raw,maximum_raw,lastvalue_raw",
            "username": USER,
            "passhash": PH
        }
        try:
            resp = requests.get(url, params=params, verify=False, timeout=20).json()
            channels = resp.get("channels", [])
            if not channels:
                return 0.0, 0.0, 0.0, 0.0

            in_min = in_max = out_min = out_max = 0.0
            for ch in channels:
                name = ch.get("name", "").strip().lower()
                min_raw = float(ch.get("minimum_raw", 0)) / divisor
                max_raw = float(ch.get("maximum_raw", 0)) / divisor

                if "traffic in" in name or "in" in name or "down" in name or "rx" in name:
                    in_min = min(in_min, min_raw) if in_min else min_raw
                    in_max = max(in_max, max_raw)
                elif "traffic out" in name or "out" in name or "up" in name or "tx" in name:
                    out_min = min(out_min, min_raw) if out_min else min_raw
                    out_max = max(out_max, max_raw)

            return round(in_min, 2), round(in_max, 2), round(out_min, 2), round(out_max, 2)
        except:
            return 0.0, 0.0, 0.0, 0.0

    else:
        # Longer periods: historicdata min/max from buckets
        url = f"{BASE}/api/historicdata.json"
        params = {
            "id": sensor_id,
            "sdate": sdate,
            "edate": edate,
            "avg": avg,
            "usecaption": 1,
            "username": USER,
            "passhash": PH
        }
        try:
            resp = requests.get(url, params=params, verify=False, timeout=30).json()
            histdata = resp.get("histdata", [])
            if not histdata:
                st.caption(f"No hist data for {sensor_id} ({period})")
                return 0.0, 0.0, 0.0, 0.0

            raw_keys = [k for k in histdata[0] if k.lower().endswith("_raw")]

            in_raw_keys = [k for k in raw_keys if any(w in k.lower() for w in ["in", "down", "rx", "receive"])]
            out_raw_keys = [k for k in raw_keys if any(w in k.lower() for w in ["out", "up", "tx", "transmit"])]

            if not in_raw_keys or not out_raw_keys:
                st.caption(f"No matching keys for {sensor_id}")
                return 0.0, 0.0, 0.0, 0.0

            in_values = [float(item.get(k, 0)) for item in histdata for k in in_raw_keys if item.get(k)]
            out_values = [float(item.get(k, 0)) for item in histdata for k in out_raw_keys if item.get(k)]

            in_values = [v for v in in_values if v > 0]  # ignore 0s for meaningful min
            out_values = [v for v in out_values if v > 0]

            in_min = min(in_values) / divisor if in_values else 0
            in_max = max(in_values) / divisor if in_values else 0
            out_min = min(out_values) / divisor if out_values else 0
            out_max = max(out_values) / divisor if out_values else 0

            return round(in_min, 2), round(in_max, 2), round(out_min, 2), round(out_max, 2)
        except Exception as e:
            st.caption(f"Hist error {sensor_id}: {str(e)}")
            return 0.0, 0.0, 0.0, 0.0


@st.cache_data(ttl=300)
def get_graph_image(sensor_id, graphid):
    url = f"{BASE}/chart.png"
    params = {
        "id": sensor_id,
        "graphid": graphid,
        "width": 1800,
        "height": 800,
        "bgcolor": "1e1e1e",
        "fontcolor": "ffffff",
        "username": USER,
        "passhash": PH
    }
    try:
        resp = requests.get(url, params=params, verify=False, timeout=15)
        return Image.open(BytesIO(resp.content)) if resp.status_code == 200 else None
    except:
        return None

# ────────────────────────────────────────────────

st.title("PRTG Bandwidth Dashboard")
st.caption(f"Period: **{period}** ({sdate} to {edate}) | Graph ID: {graphid}")

total_in_min = total_in_max = total_out_min = total_out_max = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]

    for col, (name, sid) in zip(cols, pair):
        with col:
            in_min, in_max, out_min, out_max = get_traffic_stats(sid, use_historic, sdate, edate, avg_interval)

            total_in_min += in_min
            total_in_max += in_max
            total_out_min += out_min
            total_out_max += out_max

            st.subheader(name)

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Download Min", f"{in_min:,.2f} Mbps")
                st.metric("Download Max", f"{in_max:,.2f} Mbps")
            with c2:
                st.metric("Upload Min", f"{out_min:,.2f} Mbps")
                st.metric("Upload Max", f"{out_max:,.2f} Mbps")

            img = get_graph_image(sid, graphid)
            if img:
                st.image(img, use_container_width=True)
            else:
                st.caption("Graph unavailable")

st.markdown("## Combined Across All Circuits")

col_left, col_right = st.columns([3, 1])

with col_left:
    fig, ax = plt.subplots(figsize=(12, 7))
    groups = ["Download", "Upload"]
    mins = [total_in_min, total_out_min]
    maxs = [total_in_max, total_out_max]

    x = range(len(groups))
    width = 0.35

    ax.bar([i - width/2 for i in x], mins, width, label="Minimum", color="#00d4ff", edgecolor="white")
    ax.bar([i + width/2 for i in x], maxs, width, label="Maximum", color="#ff3366", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=16, fontweight="bold", color="white")
    ax.set_ylabel("Mbps", fontsize=16, fontweight="bold", color="white")
    ax.set_title(f"Total Min / Max – {period}", fontsize=24, fontweight="bold", color="white", pad=30)

    ax.set_facecolor("#0e1117")
    fig.patch.set_facecolor("#0e1117")
    ax.tick_params(colors="white", labelsize=14)
    ax.grid(axis="y", alpha=0.2, color="white", linestyle="--")
    ax.legend(fontsize=14)

    current_max = max(maxs) if max(maxs) > 0 else 100
    ax.set_ylim(0, current_max * 1.15)

    for i, v in enumerate(mins + maxs):
        if v > 0:
            offset = -width/2 if i < 2 else width/2
            ax.text(i % 2 + offset, v + current_max * 0.02, f"{v:,.0f}",
                    ha="center", va="bottom", fontsize=16, fontweight="bold", color="white")

    st.pyplot(fig, use_container_width=True)

with col_right:
    st.metric("**Combined Download Min**", f"{total_in_min:,.0f} Mbps")
    st.metric("**Combined Download Max**", f"{total_in_max:,.0f} Mbps")
    st.metric("**Combined Upload Min**", f"{total_out_min:,.0f} Mbps")
    st.metric("**Combined Upload Max**", f"{total_out_max:,.0f} Mbps")

    st.divider()
    st.markdown("### Utilization (based on Max)")
    cap = TOTAL_CAPACITY if TOTAL_CAPACITY > 0 else 1

    pct_in = (total_in_max / cap) * 100
    pct_out = (total_out_max / cap) * 100

    st.caption(f"Download ({pct_in:.1f}%)")
    st.progress(min(pct_in / 100, 1.0))

    st.caption(f"Upload ({pct_out:.1f}%)")
    st.progress(min(pct_out / 100, 1.0))

    st.caption(f"Total Capacity: {TOTAL_CAPACITY:,.0f} Mbps")
