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

TOTAL_CAPACITY = 40000

# Period to graphid mapping (for PNG graphs)
graphid_map = {
    "Live (2 hours)": "0",
    "Last 48 hours": "1",
    "Last 7 days": "-7",
    "Last 30 days": "2",
    "Last 365 days": "3"
}

if "period_key" not in st.session_state:
    st.session_state.period_key = f"period_{uuid.uuid4()}"

period = st.selectbox(
    "Time Period",
    list(graphid_map.keys()),
    index=1,
    key=st.session_state.period_key
)

graphid = graphid_map[period]

# Time range for historic data API
now = datetime.utcnow()
if period == "Live (2 hours)":
    start = now - timedelta(hours=2)
    avg_interval = 0   # raw
elif period == "Last 48 hours":
    start = now - timedelta(hours=48)
    avg_interval = 60
elif period == "Last 7 days":
    start = now - timedelta(days=7)
    avg_interval = 900
elif period == "Last 30 days":
    start = now - timedelta(days=30)
    avg_interval = 3600
else:  # 365 days
    start = now - timedelta(days=365)
    avg_interval = 86400

sdate = start.strftime("%Y-%m-%d-%H-%M-%S")
edate = now.strftime("%Y-%m-%d-%H-%M-%S")

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

@st.cache_data(ttl=180)
def get_period_peaks(sensor_id, sdate, edate, avg_interval):
    url = f"{BASE}/api/historicdata.json"
    params = {
        "id": sensor_id,
        "sdate": sdate,
        "edate": edate,
        "avg": avg_interval,
        "username": USER,
        "passhash": PH
    }
    try:
        resp = requests.get(url, params=params, verify=False, timeout=20).json()
        if "histdata" not in resp or not resp["histdata"]:
            return 0.0, 0.0

        in_max = out_max = 0.0
        for row in resp["histdata"]:
            for key, val in row.items():
                if key.startswith("value") and val and float(val) > 0:
                    # Convert assuming bits/sec (adjust if needed)
                    mbps = float(val) / 1_000_000.0
                    # Try to guess direction from channel name or fallback to order
                    ch_idx = key.replace("value", "")
                    ch_name = resp.get(f"item{ch_idx}", {}).get("name", "").lower()
                    if any(x in ch_name for x in ["in", "down", "rx", "receive", "ingress"]):
                        in_max = max(in_max, mbps)
                    elif any(x in ch_name for x in ["out", "up", "tx", "transmit", "egress"]):
                        out_max = max(out_max, mbps)
                    else:
                        # Fallback: odd columns in, even out (common pattern)
                        if int(ch_idx) % 2 == 0:
                            in_max = max(in_max, mbps)
                        else:
                            out_max = max(out_max, mbps)

        return round(in_max, 2), round(out_max, 2)
    except Exception:
        return 0.0, 0.0

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
        return Image.open(BytesIO(resp.content))
    except:
        return None

st.title("PRTG Bandwidth Dashboard")
st.caption(f"Period: **{period}**")

total_in = total_out = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    for col, (name, sid) in zip(cols, pair):
        with col:
            in_peak, out_peak = get_period_peaks(sid, sdate, edate, avg_interval)
            total_in  += in_peak
            total_out += out_peak
            st.subheader(name)
            st.metric("Peak In",  f"{in_peak:,.2f} Mbps")
            st.metric("Peak Out", f"{out_peak:,.2f} Mbps")
            img = get_graph_image(sid, graphid)
            if img:
                st.image(img, use_container_width=True)
            else:
                st.caption("Graph unavailable")

st.markdown("## Combined Peak Bandwidth Across All Circuits")

col1, col2 = st.columns([3, 1])
with col1:
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(
        ["Peak In", "Peak Out"],
        [total_in, total_out],
        color=["#00ff9d", "#ff3366"],
        width=0.5,
        edgecolor="white",
        linewidth=2.5
    )
    
    current_max = max(total_in, total_out)
    if current_max > 0:
        ax.set_ylim(0, current_max * 1.15)
    else:
        ax.set_ylim(0, 100)

    ax.set_ylabel("Mbps", fontsize=16, fontweight="bold", color="white")
    ax.set_title(f"Total Combined Peak – {period}", fontsize=24, fontweight="bold", color="white", pad=30)
    ax.set_facecolor("#0e1117")
    fig.patch.set_facecolor("#0e1117")
    
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
        
    ax.tick_params(colors="white", labelsize=14, length=0)
    ax.grid(axis="y", alpha=0.2, color="white", linestyle="--")

    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + (current_max * 0.02),
                f"{height:,.0f}",
                ha="center",
                va="bottom",
                fontsize=28,
                fontweight="bold",
                color="white"
            )
    st.pyplot(fig, use_container_width=True)

with col2:
    cap = TOTAL_CAPACITY if TOTAL_CAPACITY > 0 else 1 
    
    pct_in = (total_in / cap) * 100
    pct_out = (total_out / cap) * 100
    
    st.metric("**Total In**",  f"{total_in:,.0f} Mbps")
    st.metric("**Total Out**", f"{total_out:,.0f} Mbps")
    
    st.divider()
    
    st.markdown("### Utilization")
    
    st.caption(f"Inbound ({pct_in:.1f}%)")
    st.progress(min(pct_in / 100, 1.0))
    
    st.caption(f"Outbound ({pct_out:.1f}%)")
    st.progress(min(pct_out / 100, 1.0))
    
    st.caption(f"Capacity Goal: {TOTAL_CAPACITY:,.0f} Mbps")
