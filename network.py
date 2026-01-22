import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth – True Peaks", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps

period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key="period_selector_final"
)

graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}[period]

delta_map = {
    "Live (2 hours)": timedelta(hours=2),
    "Last 48 hours":  timedelta(hours=48),
    "Last 7 days":    timedelta(days=7),
    "Last 30 days":   timedelta(days=30),
    "Last 365 days":  timedelta(days=365)
}
delta = delta_map[period]

now = datetime.now()
edate = now.strftime("%Y-%m-%d-%H-%M-%S")
sdate = (now - delta).strftime("%Y-%m-%d-%H-%M-%S")

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

def parse_speed_to_mbps(s):
    if not s or not isinstance(s, str):
        return 0.0
    s = s.strip()
    try:
        match = re.match(r'([\d\.]+)\s*([kMG]?bit/s)', s, re.IGNORECASE)
        if not match:
            return 0.0
        val = float(match.group(1))
        unit = match.group(2).lower()
        if 'gbit' in unit:
            return val * 1000
        if 'mbit' in unit:
            return val
        if 'kbit' in unit:
            return val / 1000
        return 0.0
    except:
        return 0.0

@st.cache_data(ttl=180)
def get_min_max_speeds(sensor_id, sdate, edate):
    url = f"{BASE}/api/historicdata.json"
    params = {
        "id": sensor_id,
        "sdate": sdate,
        "edate": edate,
        "avg": 300,  # 5 min – good compromise
        "usecaption": 1,
        "username": USER,
        "passhash": PH
    }
    try:
        resp = requests.get(url, params=params, verify=False, timeout=30).json()
        histdata = resp.get("histdata", [])
        if not histdata:
            st.caption(f"No historic data for {sensor_id}")
            return 0.0, 0.0, 0.0, 0.0

        in_key = "Traffic In (Speed)"
        out_key = "Traffic Out (Speed)"

        if in_key not in histdata[0] or out_key not in histdata[0]:
            st.caption(f"Speed channels missing for {sensor_id}. Keys: {list(histdata[0].keys())}")
            return 0.0, 0.0, 0.0, 0.0

        in_values = []
        out_values = []

        for item in histdata:
            in_str = item.get(in_key, "")
            out_str = item.get(out_key, "")
            if in_str:
                in_values.append(parse_speed_to_mbps(in_str))
            if out_str:
                out_values.append(parse_speed_to_mbps(out_str))

        if not in_values or not out_values:
            st.caption(f"No valid speed values parsed for {sensor_id}")
            return 0.0, 0.0, 0.0, 0.0

        max_in  = max(in_values)
        min_in  = min(v for v in in_values if v > 0) if any(v > 0 for v in in_values) else 0.0
        max_out = max(out_values)
        min_out = min(v for v in out_values if v > 0) if any(v > 0 for v in out_values) else 0.0

        st.caption(f"{sensor_id} → {len(histdata)} points | "
                   f"Download: {min_in:,.0f} – {max_in:,.0f} Mbit/s | "
                   f"Upload: {min_out:,.0f} – {max_out:,.0f} Mbit/s")

        return round(min_in, 0), round(max_in, 0), round(min_out, 0), round(max_out, 0)

    except Exception as e:
        st.caption(f"Error for {sensor_id}: {str(e)[:120]}...")
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
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content))
    except:
        return None

# ────────────────────────────────────────────────

st.title("PRTG Bandwidth Dashboard – True Period Min/Max")
st.caption(f"**{period}** • {sdate} → {edate} • Graph ID: {graphid}")

total_min_in = total_max_in = total_min_out = total_max_out = 0.0

for name, sid in SENSORS.items():
    with st.container(border=True):
        st.subheader(name)

        min_in, max_in, min_out, max_out = get_min_max_speeds(sid, sdate, edate)

        total_min_in += min_in
        total_max_in += max_in
        total_min_out += min_out
        total_max_out += max_out

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Min Download", f"{min_in:,.0f} Mbit/s")
            st.metric("Max Download", f"{max_in:,.0f} Mbit/s")
        with col2:
            st.metric("Min Upload", f"{min_out:,.0f} Mbit/s")
            st.metric("Max Upload", f"{max_out:,.0f} Mbit/s")

        img = get_graph_image(sid, graphid)
        if img:
            st.image(img, use_container_width=True)
        else:
            st.caption("Graph unavailable")

# Combined
st.markdown("## Combined Min/Max Across All Circuits")

colL, colR = st.columns([3, 1])

with colL:
    fig, ax = plt.subplots(figsize=(12, 7))

    groups = ["Download", "Upload"]
    mins = [total_min_in, total_min_out]
    maxs = [total_max_in, total_max_out]

    x = range(len(groups))
    width = 0.35

    ax.bar([i - width/2 for i in x], mins, width, label="Min", color="#00d4ff", edgecolor="white")
    ax.bar([i + width/2 for i in x], maxs, width, label="Max", color="#ff3366", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=16, fontweight="bold", color="white")
    ax.set_ylabel("Mbit/s", fontsize=16, fontweight="bold", color="white")
    ax.set_title(f"Total Min / Max – {period}", fontsize=24, fontweight="bold", color="white", pad=30)

    ax.set_facecolor("#0e1117")
    fig.patch.set_facecolor("#0e1117")
    ax.tick_params(colors="white", labelsize=14)
    ax.grid(axis="y", alpha=0.2, color="white", linestyle="--")
    ax.legend(fontsize=14)

    ymax = max(max(maxs), 100)
    ax.set_ylim(0, ymax * 1.15)

    for i, (mn, mx) in enumerate(zip(mins, maxs)):
        if mn > 0:
            ax.text(i - width/2, mn + ymax*0.01, f"{mn:,.0f}", ha="center", color="white", fontsize=14)
        if mx > 0:
            ax.text(i + width/2, mx + ymax*0.01, f"{mx:,.0f}", ha="center", color="white", fontsize=14)

    st.pyplot(fig, use_container_width=True)

with colR:
    st.metric("**Combined Min Download**", f"{total_min_in:,.0f} Mbit/s")
    st.metric("**Combined Max Download**", f"{total_max_in:,.0f} Mbit/s")
    st.metric("**Combined Min Upload**",   f"{total_min_out:,.0f} Mbit/s")
    st.metric("**Combined Max Upload**",   f"{total_max_out:,.0f} Mbit/s")

    st.divider()
    st.markdown("### Utilization (based on Max)")
    cap = TOTAL_CAPACITY if TOTAL_CAPACITY > 0 else 1

    pct_in = (total_max_in / cap) * 100
    pct_out = (total_max_out / cap) * 100

    st.caption(f"Download ({pct_in:.1f}%)")
    st.progress(min(pct_in / 100, 1.0))

    st.caption(f"Upload ({pct_out:.1f}%)")
    st.progress(min(pct_out / 100, 1.0))

    st.caption(f"Capacity: {TOTAL_CAPACITY:,.0f} Mbit/s")
