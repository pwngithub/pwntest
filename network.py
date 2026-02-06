import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import uuid
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Bandwidth", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps – update to match Pioneer's actual total uplink

# ── Period selection ─────────────────────────────────────────────────────────
if "period_key" not in st.session_state:
    st.session_state.period_key = f"period_{uuid.uuid4()}"

period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 2 days", "Last 30 days", "Last 365 days"],
    index=1,
    key=st.session_state.period_key
)

graphid = {
    "Live (2 hours)": "0",
    "Last 2 days":    "1",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}[period]

# Force refresh when period changes
if "last_period" not in st.session_state:
    st.session_state.last_period = None
    st.session_state.refresh_counter = 0

if st.session_state.last_period != period:
    st.session_state.refresh_counter += 1
    st.session_state.last_period = period

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

# ── Peak calculation with debug output ───────────────────────────────────────
@st.cache_data(ttl=60)
def get_real_peaks(sensor_id, period_str, refresh_counter):
    url = f"{BASE}/api/table.json"
    params = {
        "content": "channels",
        "id": sensor_id,
        "columns": "name,maximum_raw",
        "username": USER,
        "passhash": PH
    }
    try:
        resp = requests.get(url, params=params, verify=False, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        # Debug: store raw response for troubleshooting
        raw_channels = data.get("channels", [])
        
        in_peak = out_peak = 0.0
        debug_lines = []
        
        for ch in raw_channels:
            name = ch.get("name", "").strip()
            raw_str = ch.get("maximum_raw", "0")
            try:
                raw_val = float(raw_str)
            except (ValueError, TypeError):
                raw_val = 0.0
            
            if raw_val <= 0:
                continue
            
            # The divisor you're currently using
            mbps = raw_val / 9_000_000.0
            
            direction = "unknown"
            if any(x in name.lower() for x in ["traffic in", "down", "inbound", "rx", "receive", "in"]):
                in_peak = max(in_peak, round(mbps, 2))
                direction = "IN"
            elif any(x in name.lower() for x in ["traffic out", "up", "outbound", "tx", "transmit", "out"]):
                out_peak = max(out_peak, round(mbps, 2))
                direction = "OUT"
            
            debug_lines.append({
                "name": name,
                "raw": raw_str,
                "mbps": round(mbps, 2),
                "matched_as": direction
            })
        
        debug_info = {
            "sensor_id": sensor_id,
            "period": period_str,
            "raw_channel_count": len(raw_channels),
            "matched_in_peak": in_peak,
            "matched_out_peak": out_peak,
            "channels": debug_lines
        }
        
        return in_peak, out_peak, debug_info
    
    except Exception as e:
        return 0.0, 0.0, {"error": str(e)}

# ── Graph image (unchanged) ─────────────────────────────────────────────────
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
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))
    except:
        return None

# ── Main dashboard ───────────────────────────────────────────────────────────
st.title("PRTG Bandwidth Dashboard")
st.caption(f"Period: **{period}**")

total_in = total_out = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    
    for col, (name, sid) in zip(cols, pair):
        with col:
            in_peak, out_peak, debug_info = get_real_peaks(
                sid, period, st.session_state.refresh_counter
            )
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
            
            # Troubleshooting expander
            with st.expander(f"API Debug: {name} (click to see raw data)", expanded=False):
                if "error" in debug_info:
                    st.error(f"API Error: {debug_info['error']}")
                else:
                    st.markdown("**Summary**")
                    st.write(f"- Raw channels returned: {debug_info['raw_channel_count']}")
                    st.write(f"- Matched Peak In: {debug_info['matched_in_peak']:.2f} Mbps")
                    st.write(f"- Matched Peak Out: {debug_info['matched_out_peak']:.2f} Mbps")
                    
                    st.markdown("**Raw channel values & matching**")
                    if debug_info["channels"]:
                        st.json(debug_info["channels"])
                    else:
                        st.info("No channels with non-zero maximum_raw found")

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
