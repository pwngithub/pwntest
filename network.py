import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth Peaks", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps

# Unique key for the period selector
period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key="main_period_selector"   # ← this fixes the duplicate ID error
)

graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}[period]

# Time range
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

@st.cache_data(ttl=300)
def get_peak_speeds(sensor_id, sdate, edate):
    url = f"{BASE}/api/historicdata.json"
    params = {
        "id": sensor_id,
        "sdate": sdate,
        "edate": edate,
        "avg": 300,                 # 5 minutes – good balance
        "usecaption": 1,
        "username": USER,
        "passhash": PH
    }
    try:
        resp = requests.get(url, params=params, verify=False, timeout=30).json()
        histdata = resp.get("histdata", [])
        
        if not histdata:
            st.caption(f"No data returned for sensor {sensor_id}")
            return 0.0, 0.0

        # Debug: show what keys we actually got
        if histdata:
            st.caption(f"Keys in data for {sensor_id}: {list(histdata[0].keys())}")

        # Look for Traffic In_raw and Traffic Out_raw (or similar)
        in_values = []
        out_values = []

        for item in histdata:
            for k, v in item.items():
                if "_raw" in k:
                    try:
                        val = float(v)
                        if val > 0:
                            if "in" in k.lower() or "down" in k.lower() or "rx" in k.lower():
                                in_values.append(val)
                            elif "out" in k.lower() or "up" in k.lower() or "tx" in k.lower():
                                out_values.append(val)
                    except:
                        pass

        peak_in  = max(in_values) / 1000000 if in_values else 0.0   # ← changed to 1e6
        peak_out = max(out_values) / 1000000 if out_values else 0.0

        return round(peak_in, 2), round(peak_out, 2)

    except Exception as e:
        st.caption(f"Error fetching {sensor_id}: {str(e)}")
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
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content))
    except:
        return None

# ────────────────────────────────────────────────

st.title("PRTG Bandwidth Dashboard – Period Peak")
st.caption(f"{period} • {sdate} → {edate} • Graph ID: {graphid}")

total_peak_in = total_peak_out = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]

    for col, (name, sid) in zip(cols, pair):
        with col:
            peak_in, peak_out = get_peak_speeds(sid, sdate, edate)

            total_peak_in  += peak_in
            total_peak_out += peak_out

            st.subheader(name)
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Peak Download", f"{peak_in:,.2f} Mbps")
            with c2:
                st.metric("Peak Upload",   f"{peak_out:,.2f} Mbps")

            img = get_graph_image(sid, graphid)
            if img:
                st.image(img, use_container_width=True)
            else:
                st.caption("Graph unavailable")

# Combined
st.markdown("## Combined Peak Across All Circuits")

col_left, col_right = st.columns([3, 1])

with col_left:
    fig, ax = plt.subplots(figsize=(12, 7))
    groups = ["Peak Download", "Peak Upload"]
    peaks = [total_peak_in, total_peak_out]

    x = range(len(groups))
    ax.bar(x, peaks, 0.5, color=["#00ff9d", "#ff3366"], edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=16, fontweight="bold", color="white")
    ax.set_ylabel("Mbps", fontsize=16, fontweight="bold", color="white")
    ax.set_title(f"Total Peak – {period}", fontsize=24, fontweight="bold", color="white", pad=30)

    ax.set_facecolor("#0e1117")
    fig.patch.set_facecolor("#0e1117")
    ax.tick_params(colors="white", labelsize=14)
    ax.grid(axis="y", alpha=0.2, color="white", linestyle="--")

    current_max = max(peaks) if max(peaks) > 0 else 100
    ax.set_ylim(0, current_max * 1.15)

    for i, v in enumerate(peaks):
        if v > 0:
            ax.text(i, v + current_max * 0.02, f"{v:,.0f}",
                    ha="center", va="bottom", fontsize=20, fontweight="bold", color="white")

    st.pyplot(fig, use_container_width=True)

with col_right:
    st.metric("**Total Peak Download**", f"{total_peak_in:,.0f} Mbps")
    st.metric("**Total Peak Upload**",   f"{total_peak_out:,.0f} Mbps")

    st.divider()
    st.markdown("### Utilization (based on peak)")
    cap = TOTAL_CAPACITY if TOTAL_CAPACITY > 0 else 1

    pct_in = (total_peak_in / cap) * 100
    pct_out = (total_peak_out / cap) * 100

    st.caption(f"Download ({pct_in:.1f}%)")
    st.progress(min(pct_in / 100, 1.0))

    st.caption(f"Upload ({pct_out:.1f}%)")
    st.progress(min(pct_out / 100, 1.0))

    st.caption(f"Capacity: {TOTAL_CAPACITY:,.0f} Mbps")
