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

TOTAL_CAPACITY = 40000  # Mbps

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

period_deltas = {
    "Live (2 hours)": (timedelta(hours=2), 0),       # raw
    "Last 48 hours":  (timedelta(hours=48), 60),     # 1 min
    "Last 7 days":    (timedelta(days=7), 300),      # 5 min
    "Last 30 days":   (timedelta(days=30), 900),     # 15 min
    "Last 365 days":  (timedelta(days=365), 86400)   # daily
}
delta, avg_interval = period_deltas[period]

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
def get_traffic_stats(sensor_id, sdate, edate, avg):
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
            st.warning(f"No historic data for sensor {sensor_id} in period {sdate} to {edate} with avg={avg}")
            return 0.0, 0.0, 0.0, 0.0
        
        # Debug: show first item keys
        first_keys = list(histdata[0].keys())
        st.caption(f"Data keys for {sensor_id}: {', '.join(first_keys)}")
        
        raw_keys = [k for k in first_keys if k.lower().endswith("_raw")]
        st.caption(f"Raw keys: {', '.join(raw_keys)}")
        
        in_raw_keys = []
        out_raw_keys = []
        
        for key in raw_keys:
            base_name = key[:-4].strip().lower()
            if any(w in base_name for w in ["traffic in", "in", "down", "download", "rx", "receive", "input", "ingress"]):
                in_raw_keys.append(key)
            elif any(w in base_name for w in ["traffic out", "out", "up", "upload", "tx", "send", "transmit", "output", "egress"]):
                out_raw_keys.append(key)
        
        if not in_raw_keys or not out_raw_keys:
            st.error(f"No matching in/out keys for {sensor_id}. Raw keys: {raw_keys}")
            return 0.0, 0.0, 0.0, 0.0
        
        in_values = []
        out_values = []
        
        for item in histdata:
            for k in in_raw_keys:
                val = item.get(k)
                if val is not None and val != '':
                    try:
                        in_values.append(float(val))
                    except ValueError:
                        pass
            for k in out_raw_keys:
                val = item.get(k)
                if val is not None and val != '':
                    try:
                        out_values.append(float(val))
                    except ValueError:
                        pass
        
        if not in_values or not out_values:
            st.warning(f"No valid values found for {sensor_id}")
            return 0.0, 0.0, 0.0, 0.0
        
        divisor = 10_000_000
        
        in_min = min(in_values) / divisor
        in_max = max(in_values) / divisor
        out_min = min(out_values) / divisor
        out_max = max(out_values) / divisor
        
        return round(in_min, 2), round(in_max, 2), round(out_min, 2), round(out_max, 2)
    
    except Exception as e:
        st.error(f"Error for {sensor_id}: {str(e)}")
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

st.title("PRTG Bandwidth Dashboard")
st.caption(f"Period: {period} ({sdate} to {edate}) | Graph ID: {graphid}")

total_in_min = total_in_max = total_out_min = total_out_max = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]

    for col, (name, sid) in zip(cols, pair):
        with col:
            in_min, in_max, out_min, out_max = get_traffic_stats(sid, sdate, edate, avg_interval)
            
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
