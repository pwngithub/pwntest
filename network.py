import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import json  # Added for pretty-printing debug data

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Page Config ---
st.set_page_config(page_title="PRTG Bandwidth Dashboard", layout="wide", page_icon="📊")

# --- Credentials ---
try:
    PRTG_USERNAME = st.secrets["prtg_username"]
    PRTG_PASSHASH = st.secrets["prtg_passhash"]
except KeyError:
    st.error("⚠️ Missing PRTG credentials in Streamlit secrets.")
    st.stop()

PRTG_URL = "https://prtg.pioneerbroadband.net"

# --- Custom CSS ---
st.markdown("""
<style>
    .big-font { font-size: 19px !important; font-weight: bold; }
    .metric-in { color: #00ff88; background-color: rgba(0,255,136,0.15); padding: 12px; border-radius: 12px; border-left: 6px solid #00ff88; }
    .metric-out { color: #ff3366; background-color: rgba(255,51,102,0.15); padding: 12px; border-radius: 12px; border-left: 6px solid #ff3366; }
    .card { background-color: var(--background-color); padding: 20px; border-radius: 16px; box-shadow: 0 6px 16px rgba(0,0,0,0.2); border: 1px solid #333; margin-bottom: 25px; }
    hr { border: 1px solid #444; margin: 40px 0; }
    .debug-box { background-color: #f0f2f6; padding: 10px; border-radius: 8px; border-left: 4px solid #007acc; }
</style>
""", unsafe_allow_html=True)

st.title("📊 PRTG Bandwidth Dashboard")
st.markdown("Real-time & historical bandwidth across all circuits")

# --- Debug Toggle (NEW) ---
debug_mode = st.checkbox("🔧 Enable Debug Mode (Shows Raw Channel Data)")

# --- Time Period ---
graph_period = st.selectbox(
    "Select Time Period",
    ("Live (2 hours)", "Last 48 hours", "Last 30 days", "Last 365 days"),
    index=1
)

period_to_graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours": "1",
    "Last 30 days": "2",
    "Last 365 days": "3",
}
graphid = period_to_graphid[graph_period]

# --- Sensors ---
SENSORS = {
    "Firstlight": "12435",
    "NNINIX": "12506",
    "Hurricane Electric": "12363",
    "Cogent": "12340",
}

# --- Fetch Stats (Enhanced with Debug Logging) ---
def fetch_speed_stats(sensor_id, debug=False):
    url = (
        f"{PRTG_URL}/api/table.json?"
        f"content=channels&columns=name,maximum_raw,average_raw"
        f"&id={sensor_id}&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
    )
    stats = {"in_max": 0.0, "in_avg": 0.0, "out_max": 0.0, "out_avg": 0.0}
    raw_channels = []  # For debug

    try:
        r = requests.get(url, verify=False, timeout=15)
        if r.status_code != 200:
            if debug:
                st.error(f"HTTP {r.status_code} for sensor {sensor_id}")
            return stats, raw_channels

        data = r.json()
        channels = data.get("channels", [])

        if debug:
            raw_channels = [{"name": ch.get("name", ""), "max_raw": ch.get("maximum_raw"), "avg_raw": ch.get("average_raw")} for ch in channels]

        for ch in channels:
            name = ch.get("name", "").strip().lower()  # Case-insensitive partial match for robustness

            # Flexible matching for "Traffic In (Speed)" variations
            if "traffic in" in name and "speed" in name:
                if ch.get("maximum_raw") and ch["maximum_raw"] != "":
                    stats["in_max"] = round(float(ch["maximum_raw"]) / 1_000_000, 2)
                if ch.get("average_raw") and ch["average_raw"] != "":
                    stats["in_avg"] = round(float(ch["average_raw"]) / 1_000_000, 2)

            # Same for Out
            if "traffic out" in name and "speed" in name:
                if ch.get("maximum_raw") and ch["maximum_raw"] != "":
                    stats["out_max"] = round(float(ch["maximum_raw"]) / 1_000_000, 2)
                if ch.get("average_raw") and ch["average_raw"] != "":
                    stats["out_avg"] = round(float(ch["average_raw"]) / 1_000_000, 2)

        return stats, raw_channels

    except Exception as e:
        if debug:
            st.error(f"Exception for sensor {sensor_id}: {str(e)}")
        return stats, raw_channels

# --- Display Sensor Card (With Debug Expander) ---
def display_sensor_card(name, sensor_id, debug=False):
    stats, raw_channels = fetch_speed_stats(sensor_id, debug)

    in_max = stats["in_max"]
    in_avg = stats["in_avg"]
    out_max = stats["out_max"]
    out_avg = stats["out_avg"]

    with st.container():
        st.markdown(f"<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"🔗 {name}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div class='metric-in big-font'>⬇️ Peak In: <b>{in_max:,.2f} Mbps</b></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='big-font'>⬇️ Avg In: {in_avg:,.2f} Mbps</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-out big-font'>⬆️ Peak Out: <b>{out_max:,.2f} Mbps</b></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='big-font'>⬆️ Avg Out: {out_avg:,.2f} Mbps</div>", unsafe_allow_html=True)

        # Debug Expander (Only Shows if Enabled)
        if debug and raw_channels:
            with st.expander(f"🔍 Raw Data for {name} (Click to View)", expanded=False):
                st.markdown("<div class='debug-box'>", unsafe_allow_html=True)
                st.json({"channels": raw_channels})  # Pretty-prints the full list
                st.markdown("</div>", unsafe_allow_html=True)

        # Graph
        graph_url = (
            f"{PRTG_URL}/chart.png?"
            f"type=graph&id={sensor_id}&graphid={graphid}"
            f"&width=1900&height=850"
            f"&bgcolor=1e1e1e&fontcolor=ffffff"
            f"&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
        )
        try:
            r = requests.get(graph_url, verify=False, timeout=20)
            if r.status_code == 200 and len(r.content) > 5000:
                img = Image.open(BytesIO(r.content))
                st.image(img, use_container_width=True, caption=f"Graph for {name} ({graph_period})")
            else:
                st.warning(f"⚠️ Graph unavailable for {name} (Status: {r.status_code})")
        except Exception as e:
            st.error(f"Failed to load graph for {name}: {e}")

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)

    return in_max, out_max, in_avg, out_avg

# --- Main Layout ---
total_in_peak = total_out_peak = total_in_avg = total_out_avg = 0.0

st.markdown(f"### 📅 Viewing: **{graph_period}**")
st.markdown("---")

sensor_items = list(SENSORS.items())
for i in range(0, len(sensor_items), 2):
    cols = st.columns(2)
    for col, (name, sid) in zip(cols, sensor_items[i:i+2]):
        with col:
            ip, op, ia, oa = display_sensor_card(name, sid, debug=debug_mode)
            total_in_peak += ip
            total_out_peak += op
            total_in_avg += ia
            total_out_avg += oa

# --- Summary ---
if total_in_peak > 0 or total_out_peak > 0:
    st.markdown("## 🌐 Aggregate Bandwidth Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Peak In", f"{total_in_peak:,.2f} Mbps")
    with col2: st.metric("Total Peak Out", f"{total_out_peak:,.2f} Mbps")
    with col3: st.metric("Total Avg In", f"{total_in_avg:,.2f} Mbps")
    with col4: st.metric("Total Avg Out", f"{total_out_avg:,.2f} Mbps")

    # Bar Chart
    fig, ax = plt.subplots(figsize=(10, 6), facecolor="#0e1117")
    bars = ax.bar(["Peak In", "Peak Out"], [total_in_peak, total_out_peak],
                  color=["#00ff88", "#ff3366"], edgecolor="white", linewidth=2, width=0.6)
    ax.set_ylabel("Mbps", fontsize=14, color="white")
    ax.set_title("Total Combined Peak Bandwidth", fontsize=20, fontweight="bold", color="white", pad=30)
    ax.tick_params(colors="white", labelsize=12)
    ax.grid(axis="y", color="#333", linestyle="--", alpha=0.4)
    ax.set_facecolor("#1e1e1e")
    fig.patch.set_facecolor("#0e1117")
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2., h + max(total_in_peak, total_out_peak)*0.01,
                    f'{h:,.0f}', ha='center', va='bottom', fontsize=16, fontweight='bold', color='white')
    st.pyplot(fig)
else:
    st.warning("⚠️ No data pulled—check debug mode above for raw channels, or verify credentials/network access.")

# --- Global Debug Info (If Enabled) ---
if debug_mode:
    st.markdown("---")
    st.info("💡 Debug Mode Active: Expand each sensor card to see raw channel data. Look for channels containing 'traffic in/out' and 'speed'.")
