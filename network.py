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

TOTAL_CAPACITY = 40000  # Mbps (40 Gbps example)

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

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

@st.cache_data(ttl=300)
def get_max_speeds(sensor_id):
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
        channels = data.get("channels", [])
        in_max = out_max = 0.0
        for ch in channels:
            name = ch.get("name", "").strip()
            max_raw = ch.get("maximum_raw", "0")
            if not max_raw or float(max_raw) == 0:
                continue
            mbps = float(max_raw) / 10_000_000
            if "Traffic In" in name:
                in_max = max(in_max, round(mbps, 2))
            elif "Traffic Out" in name:
                out_max = max(out_max, round(mbps, 2))
        return in_max, out_max
    except:
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
            in_max, out_max = get_max_speeds(sid)
            total_in  += in_max
            total_out += out_max
            st.subheader(name)
            st.metric("Max Download", f"{in_max:,.2f} Mbps")
            st.metric("Max Upload", f"{out_max:,.2f} Mbps")
            img = get_graph_image(sid, graphid)
            if img:
                st.image(img, use_container_width=True)
            else:
                st.caption("Graph unavailable")

st.markdown("## Combined Max Bandwidth Across All Circuits")

col1, col2 = st.columns([3, 1])
with col1:
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(
        ["Max Download", "Max Upload"],
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
    ax.set_title(f"Total Combined Max – {period}", fontsize=24, fontweight="bold", color="white", pad=30)
    ax.set_facecolor("#0e1e17")
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
    st.metric("**Total Download Max**", f"{total_in:,.0f} Mbps")
    st.metric("**Total Upload Max**", f"{total_out:,.0f} Mbps")

    st.divider()

    # Utilization based on max
    st.markdown("### Utilization")

    pct_in = (total_in / TOTAL_CAPACITY) * 100 if TOTAL_CAPACITY > 0 else 0
    pct_out = (total_out / TOTAL_CAPACITY) * 100 if TOTAL_CAPACITY > 0 else 0

    st.caption(f"Download ({pct_in:.1f}%)")
    st.progress(min(pct_in / 100, 1.0))

    st.caption(f"Upload ({pct_out:.1f}%)")
    st.progress(min(pct_out / 100, 1.0))

    st.caption(f"Capacity Goal: {TOTAL_CAPACITY:,.0f} Mbps")
