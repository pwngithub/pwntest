import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth Peaks", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps

period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key="period_selector_unique_key"
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

DIVISOR = 1000000  # bit/s → Mbit/s (1e6) – most common for PRTG traffic speed channels

def parse_speed_to_mbps(speed_str):
    """Parse '1.23 Gbit/s' → 1230 Mbps, '456 Mbit/s' → 456 Mbps, '89.7 kbit/s' → 0.09 Mbps"""
    if not speed_str or speed_str == "N/A":
        return 0.0
    try:
        match = re.match(r'([\d\.]+)\s*([kMG]?bit/s)', speed_str.strip(), re.IGNORECASE)
        if not match:
            return 0.0
        value = float(match.group(1))
        unit = match.group(2).lower()
        if 'gbit' in unit:
            return value * 1000
        elif 'mbit' in unit:
            return value
        elif 'kbit' in unit:
            return value / 1000
        return 0.0
    except:
        return 0.0

@st.cache_data(ttl=300)
def get_peak_speeds(sensor_id, sdate, edate, is_live):
    if is_live:
        # Live/short: use channel maximum_raw (fast, current peak)
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

            peak_in_raw = peak_out_raw = 0
            for ch in channels:
                name = ch.get("name", "").strip()
                max_raw_str = ch.get("maximum_raw", "0")
                if max_raw_str and max_raw_str.strip():
                    try:
                        val = float(max_raw_str)
                        if "Traffic In" in name:
                            peak_in_raw = val
                        elif "Traffic Out" in name:
                            peak_out_raw = val
                    except:
                        pass

            peak_in  = peak_in_raw  / DIVISOR if peak_in_raw  else 0.0
            peak_out = peak_out_raw / DIVISOR if peak_out_raw else 0.0

            st.caption(f"Live mode – raw max: In {peak_in_raw:,.0f} → {peak_in:,.2f} Mbps | Out {peak_out_raw:,.0f} → {peak_out:,.2f} Mbps")
            return round(peak_in, 2), round(peak_out, 2)

        except Exception as e:
            st.caption(f"Live fetch error {sensor_id}: {str(e)}")
            return 0.0, 0.0

    else:
        # Longer periods: historic data + parse formatted speed strings
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
            histdata = resp.get("histdata", [])
            if not histdata:
                return 0.0, 0.0

            in_key = "Traffic In (Speed)"
            out_key = "Traffic Out (Speed)"

            if in_key not in histdata[0] or out_key not in histdata[0]:
                st.caption(f"Speed channels not found for {sensor_id}")
                return 0.0, 0.0

            in_peaks = []
            out_peaks = []

            for item in histdata:
                in_str = item.get(in_key, "")
                out_str = item.get(out_key, "")
                if in_str.strip():
                    in_peaks.append(parse_speed_to_mbps(in_str))
                if out_str.strip():
                    out_peaks.append(parse_speed_to_mbps(out_str))

            peak_in  = max(in_peaks) if in_peaks else 0.0
            peak_out = max(out_peaks) if out_peaks else 0.0

            st.caption(f"Historic mode – {len(histdata)} points | Peak In: {peak_in:,.2f} Mbps | Peak Out: {peak_out:,.2f} Mbps")

            return round(peak_in, 2), round(peak_out, 2)

        except Exception as e:
            st.caption(f"Historic error {sensor_id}: {str(e)}")
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
st.caption(f"Using divisor 1,000,000 (bit/s → Mbit/s) – change DIVISOR if scale is wrong")

total_peak_in = total_peak_out = 0.0

is_live = period == "Live (2 hours)"

for name, sid in SENSORS.items():
    with st.container():
        st.subheader(name)

        peak_in, peak_out = get_peak_speeds(sid, sdate, edate, is_live)

        total_peak_in  += peak_in
        total_peak_out += peak_out

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Peak Download", f"{peak_in:,.2f} Mbit/s")
        with c2:
            st.metric("Peak Upload",   f"{peak_out:,.2f} Mbit/s")

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
    ax.set_ylabel("Mbit/s", fontsize=16, fontweight="bold", color="white")
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
    st.metric("**Total Peak Download**", f"{total_peak_in:,.0f} Mbit/s")
    st.metric("**Total Peak Upload**",   f"{total_peak_out:,.0f} Mbit/s")

    st.divider()
    st.markdown("### Utilization (based on peak)")
    cap = TOTAL_CAPACITY if TOTAL_CAPACITY > 0 else 1

    pct_in = (total_peak_in / cap) * 100
    pct_out = (total_peak_out / cap) * 100

    st.caption(f"Download ({pct_in:.1f}%)")
    st.progress(min(pct_in / 100, 1.0))

    st.caption(f"Upload ({pct_out:.1f}%)")
    st.progress(min(pct_out / 100, 1.0))

    st.caption(f"Capacity: {TOTAL_CAPACITY:,.0f} Mbit/s")
