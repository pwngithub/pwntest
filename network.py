import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth Peaks - FINAL", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps

period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=0,
    key="period_sel_final"
)

graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}[period]

delta = {
    "Live (2 hours)": timedelta(hours=2),
    "Last 48 hours":  timedelta(hours=48),
    "Last 7 days":    timedelta(days=7),
    "Last 30 days":   timedelta(days=30),
    "Last 365 days":  timedelta(days=365)
}[period]

now = datetime.now()
edate = now.strftime("%Y-%m-%d-%H-%M-%S")
sdate = (now - delta).strftime("%Y-%m-%d-%H-%M-%S")

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

@st.cache_data(ttl=180)
def get_peak_speeds(sensor_id, sdate, edate, is_live):
    if is_live:
        # LIVE MODE: use channel maximum_raw (super reliable for Live 2 hours)
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
            in_raw = out_raw = 0
            for ch in channels:
                name = ch.get("name", "")
                raw_str = ch.get("maximum_raw", "")
                if not raw_str or raw_str == "":
                    continue
                try:
                    val = float(raw_str)
                    if "Traffic In" in name:
                        in_raw = val
                    elif "Traffic Out" in name:
                        out_raw = val
                except:
                    continue
            in_mbps = in_raw / 1_000_000
            out_mbps = out_raw / 1_000_000
            return round(in_mbps, 2), round(out_mbps, 2)
        except:
            return 0.0, 0.0

    else:
        # LONGER PERIODS: historicdata with exact parsing
        url = f"{BASE}/api/historicdata.json"
        params = {
            "id": sensor_id,
            "sdate": sdate,
            "edate": edate,
            "avg": 300,
            "usecaption": 1,
            "username": USER,
            "passhash": PH
        }
        try:
            resp = requests.get(url, params=params, verify=False, timeout=30).json()
            hist = resp.get("histdata", [])
            if not hist:
                return 0.0, 0.0

            in_vals = []
            out_vals = []

            for row in hist:
                in_str = row.get("Traffic In (Speed)", "")
                out_str = row.get("Traffic Out (Speed)", "")
                if in_str and "bit/s" in in_str:
                    num = float(re.search(r"([\d\.]+)", in_str).group(1))
                    if "Gbit" in in_str:
                        in_vals.append(num * 1000)
                    elif "Mbit" in in_str:
                        in_vals.append(num)
                    elif "kbit" in in_str:
                        in_vals.append(num / 1000)
                if out_str and "bit/s" in out_str:
                    num = float(re.search(r"([\d\.]+)", out_str).group(1))
                    if "Gbit" in out_str:
                        out_vals.append(num * 1000)
                    elif "Mbit" in out_str:
                        out_vals.append(num)
                    elif "kbit" in out_str:
                        out_vals.append(num / 1000)

            return (round(max(in_vals), 2) if in_vals else 0.0,
                    round(max(out_vals), 2) if out_vals else 0.0)

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
        r = requests.get(url, params=params, verify=False, timeout=15)
        return Image.open(BytesIO(r.content)) if r.status_code == 200 else None
    except:
        return None

# MAIN DASHBOARD
st.title("PRTG Bandwidth Dashboard – Period Peak")
st.caption(f"**{period}** • {sdate} → {edate} • Graph ID: {graphid}")

is_live = period == "Live (2 hours)"

total_in = total_out = 0.0

for name, sid in SENSORS.items():
    with st.container():
        st.subheader(name)
        peak_in, peak_out = get_peak_speeds(sid, sdate, edate, is_live)
        total_in += peak_in
        total_out += peak_out

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Peak Download", f"{peak_in:,.2f} Mbit/s")
        with col2:
            st.metric("Peak Upload", f"{peak_out:,.2f} Mbit/s")

        img = get_graph_image(sid, graphid)
        if img:
            st.image(img, use_container_width=True)

# COMBINED
st.markdown("## Combined Peak Across All Circuits")

left, right = st.columns([3, 1])
with left:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(["Download", "Upload"], [total_in, total_out],
           color=["#00ff9d", "#ff3366"], edgecolor="white", linewidth=2)
    ax.set_ylabel("Mbit/s", color="white", fontsize=14)
    ax.set_title(f"Total Peak – {period}", color="white", fontsize=18)
    ax.tick_params(colors="white")
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")
    for i, v in enumerate([total_in, total_out]):
        ax.text(i, v + max(total_in, total_out)*0.01, f"{v:,.0f}", ha="center", color="white", fontweight="bold")
    st.pyplot(fig)

with right:
    st.metric("Total Peak Download", f"{total_in:,.0f} Mbit/s")
    st.metric("Total Peak Upload",   f"{total_out:,.0f} Mbit/s")
    st.divider()
    pct_in = total_in / TOTAL_CAPACITY * 100
    pct_out = total_out / TOTAL_CAPACITY * 100
    st.progress(pct_in / 100)
    st.caption(f"Download {pct_in:.1f}% of capacity")
    st.progress(pct_out / 100)
    st.caption(f"Upload {pct_out:.1f}% of capacity")
