import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Disable SSL warnings for internal PRTG connection
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Bandwidth", layout="wide", page_icon="Signal")

# --- CONFIGURATION ---
USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"
TOTAL_CAPACITY = 40000 

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

# --- MANUAL OVERRIDE (Optional) ---
# If the auto-detector fails, enter the IDs found in the Troubleshooter here.
# Format: "SENSOR_ID": {"in": CHANNEL_ID, "out": CHANNEL_ID}
# Example: "12435": {"in": 0, "out": 1}
MANUAL_IDS = {
    # "12435": {"in": 0, "out": 1}, 
}

# --- DATE HELPER ---
def get_date_params(period_name):
    now = datetime.now()
    edate = now.strftime("%Y-%m-%d-%H-%M-%S")
    
    if period_name == "Live (2 hours)":
        sdate = (now - timedelta(hours=2)).strftime("%Y-%m-%d-%H-%M-%S")
        avg = 0 
    elif period_name == "Last 48 hours":
        sdate = (now - timedelta(hours=48)).strftime("%Y-%m-%d-%H-%M-%S")
        avg = 300 
    elif period_name == "Last 7 days":
        sdate = (now - timedelta(days=7)).strftime("%Y-%m-%d-%H-%M-%S")
        avg = 3600 
    elif period_name == "Last 30 days":
        sdate = (now - timedelta(days=30)).strftime("%Y-%m-%d-%H-%M-%S")
        avg = 3600 
    elif period_name == "Last 365 days":
        sdate = (now - timedelta(days=365)).strftime("%Y-%m-%d-%H-%M-%S")
        avg = 86400 
    else:
        sdate = (now - timedelta(hours=24)).strftime("%Y-%m-%d-%H-%M-%S")
        avg = 900

    return sdate, edate, avg

# --- DATA FETCHING (SHOWHIDE=1) ---
@st.cache_data(ttl=300)
def get_period_peaks_debug(sensor_id, period_name):
    """
    Returns (in_peak, out_peak, debug_info_dict)
    Uses showhide=1 to find channels from Tab 2.
    """
    debug_log = {"sensor_id": sensor_id}
    
    in_id = None
    out_id = None
    
    # 1. Check Manual Override First
    if str(sensor_id) in MANUAL_IDS:
        mapping = MANUAL_IDS[str(sensor_id)]
        in_id = mapping.get("in")
        out_id = mapping.get("out")
        debug_log["method"] = "Manual Override"
    else:
        # 2. Auto-Detect with SHOWHIDE=1
        meta_url = f"{BASE}/api/table.json"
        meta_params = {
            "content": "channels",
            "id": sensor_id,
            "columns": "name,objid,unit,lastvalue",
            "showhide": 1,  # <--- CRITICAL FIX: Shows hidden/Tab 2 channels
            "username": USER,
            "passhash": PH
        }
        
        try:
            meta_data = requests.get(meta_url, params=meta_params, verify=False, timeout=10).json()
            channels = meta_data.get("channels", [])
            debug_log["channels_found"] = channels # Save for troubleshooter
            
            for ch in channels:
                name = ch.get("name", "").lower()
                unit = ch.get("unit", "").lower()
                cid = ch.get("objid")
                
                # Skip pure Volume channels
                if "byte" in unit: 
                    continue

                # Look for Speed indicators
                is_speed = "bit" in unit or "speed" in name
                
                if is_speed:
                    if "traffic in" in name or "down" in name:
                        in_id = cid
                    elif "traffic out" in name or "up" in name:
                        out_id = cid
                    
                    # Fallback: simple "In" / "Out" if matched with Speed unit
                    if in_id is None and (" in" in name or name == "in"):
                        in_id = cid
                    if out_id is None and (" out" in name or name == "out"):
                        out_id = cid

            debug_log["method"] = "Auto-Detect"
            
        except Exception as e:
            debug_log["meta_error"] = str(e)
            return 0.0, 0.0, debug_log

    debug_log["matched_ids"] = {"in": in_id, "out": out_id}

    if in_id is None and out_id is None:
        return 0.0, 0.0, debug_log

    # 3. Get Historic Data
    sdate, edate, avg = get_date_params(period_name)
    hist_url = f"{BASE}/api/historicdata.json"
    
    cols_to_fetch = []
    if in_id is not None: cols_to_fetch.append(f"value_{in_id}")
    if out_id is not None: cols_to_fetch.append(f"value_{out_id}")
    
    hist_params = {
        "id": sensor_id,
        "sdate": sdate,
        "edate": edate,
        "avg": avg,
        "columns": ",".join(cols_to_fetch),
        "username": USER,
        "passhash": PH
    }
    
    try:
        hist_data = requests.get(hist_url, params=hist_params, verify=False, timeout=20).json()
        
        if "histdata" not in hist_data or len(hist_data["histdata"]) == 0:
            debug_log["data_empty"] = True
            return 0.0, 0.0, debug_log

        max_in = 0.0
        max_out = 0.0
        
        for row in hist_data["histdata"]:
            # Inbound
            if in_id is not None:
                val = row.get(f"value_{in_id}")
                if val:
                    # Conversion: (Bytes * 8) / 1,000,000 = Mbps
                    mbps = (float(val) * 8) / 1_000_000
                    if mbps > max_in: max_in = mbps
            
            # Outbound
            if out_id is not None:
                val = row.get(f"value_{out_id}")
                if val:
                    mbps = (float(val) * 8) / 1_000_000
                    if mbps > max_out: max_out = mbps

        return round(max_in, 2), round(max_out, 2), debug_log

    except Exception as e:
        debug_log["hist_error"] = str(e)
        return 0.0, 0.0, debug_log

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

# --- MAIN APP ---
st.title("PRTG Bandwidth Dashboard")

period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key="period_selector_main"
)
st.caption(f"Showing peak usage for: **{period}**")

graphid_map = {
    "Live (2 hours)": "0",
    "Last 48 hours": "1",
    "Last 7 days": "-7",
    "Last 30 days": "2",
    "Last 365 days": "3"
}
current_graph_id = graphid_map.get(period, "1")

total_in = 0.0
total_out = 0.0

all_debug_info = {}

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    for col, (name, sid) in zip(cols, pair):
        with col:
            in_peak, out_peak, dbg = get_period_peaks_debug(sid, period)
            all_debug_info[name] = dbg
            
            total_in  += in_peak
            total_out += out_peak
            
            st.subheader(name)
            st.metric("Peak In",  f"{in_peak:,.2f} Mbps")
            st.metric("Peak Out", f"{out_peak:,.2f} Mbps")
            
            img = get_graph_image(sid, current_graph_id)
            if img:
                st.image(img, use_container_width=True)
            else:
                st.caption("Graph unavailable")

# --- SUMMARY SECTION ---
st.markdown("---")
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

# --- DEBUGGER ---
with st.sidebar:
    st.divider()
    with st.expander("🛠 Troubleshooter (Check Channels Here)"):
        st.write("Using 'showhide=1' to see all channels (including Tab 2).")
        st.json(all_debug_info)
