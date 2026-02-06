import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import uuid

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Bandwidth", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps – update this to match your actual total uplink capacity

# Session state for period selectbox
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
    "Last 48 hours": "1",
    "Last 7 days": "-7",
    "Last 30 days": "2",
    "Last 365 days": "3"
}[period]

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

@st.cache_data(ttl=300)
def get_real_peaks(sensor_id):
    url = f"{BASE}/api/table.json"
    params = {
        "content": "channels",
        "id": sensor_id,
        "columns": "name,maximum_raw",
        "username": USER,
        "passhash": PH
    }
    try:
        data = requests.get(url, params=params, verify=False, timeout=15).json()
        in_peak = out_peak = 0.0
        for ch in data.get("channels", []):
            name = ch.get("name", "").strip()
            raw = ch.get("maximum_raw", "0")
            if not raw or float(raw) == 0:
                continue
            mbps = float(raw) / 10_000_000
            if any(x in name for x in ["Traffic In", "Down", "Inbound", "Rx", "Receive"]):
                in_peak = max(in_peak, round(mbps, 2))
            elif any(x in name for x in ["Traffic Out", "Up", "Outbound", "Tx", "Transmit"]):
                out_peak = max(out_peak, round(mbps, 2))
        return in_peak, out_peak
    except Exception:
        return 0.0, 0.0

@st.cache_data(ttl=300)
def get_graph_image(sensor_id, graphid):
    url = f"{BASE}/chart.png"
    params = {
        "id": sensor_id,
        "graphid": graphid,
        "width": 2200,           # wider for better label readability
        "height": 1050,          # taller for legend & spacing
        "bgcolor": "0d1117",     # dark github-like background
        "fontcolor": "c9d1d9",   # light gray text
        "gridcolor": "444444",   # subtle visible grid
        "gridlinewidth": "1",
        "legend": "1",           # attempt to force legend
        "username": USER,
        "passhash": PH
    }
    try:
        resp = requests.get(url, params=params, verify=False, timeout=20)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))
    except Exception as e:
        st.warning(f"Graph fetch failed for {sensor_id}: {str(e)}")
        return None

# ────────────────────────────────────────────────────────────────
st.title("PRTG Bandwidth Dashboard")
st.caption(f"Period: **{period}**   |   Total capacity: **{TOTAL_CAPACITY:,.0f} Mbps**")

total_in = total_out = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    
    for col, (name, sid) in zip(cols, pair):
        with col:
            in_peak, out_peak = get_real_peaks(sid)
            total_in  += in_peak
            total_out += out_peak
            
            st.subheader(name)
            st.metric("Peak In",  f"{in_peak:,.1f} Mbps")
            st.metric("Peak Out", f"{out_peak:,.1f} Mbps")
            
            img = get_graph_image(sid, graphid)
            if img:
                st.image(img, use_container_width=True)
                st.caption(f"**Peak** — In: {in_peak:,.1f} Mbps   |   Out: {out_peak:,.1f} Mbps")
            else:
                st.error("Graph unavailable")
            
            st.markdown("")  # small vertical spacing

# ────────────────────────────────────────────────────────────────
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
    ax.set_title(f"Total Combined Peak – {period}", fontsize=22, fontweight="bold", pad=25)
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
    pct_in  = (total_in  / cap) * 100
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
