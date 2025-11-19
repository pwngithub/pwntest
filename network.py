import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import numpy as np

# Disable SSL warnings (internal use)
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

# --- Custom CSS for Better Visuals ---
st.markdown("""
<style>
    .big-font { font-size: 18px !important; font-weight: bold; }
    .metric-in { color: #00ff88; background-color: rgba(0, 255, 136, 0.1); padding: 10px; border-radius: 10px; }
    .metric-out { color: #ff0066; background-color: rgba(255, 0, 102, 0.1); padding: 10px; border-radius: 10px; }
    .card {
        background-color: var(--background-color);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border: 1px solid #333;
        margin-bottom: 20px;
    }
    .stPlotlyChart, .stImage { border-radius: 12px; overflow: hidden; }
    hr { border: 1px solid #444; margin: 30px 0; }
</style>
""", unsafe_allow_html=True)

st.title("📊 PRTG Bandwidth Dashboard")
st.markdown("Real-time and historical bandwidth monitoring across all circuits")

# --- Graph Period ---
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
    "Firstlight (ID 12435)": "12435",
    "NNINIX (ID 12506)": "12506",
    "HE (ID 12363)": "12363",
    "Cogent (ID 12340)": "12340",
}

# --- Fetch Stats ---
def fetch_bandwidth_stats(sensor_id):
    try:
        url = (
            f"{PRTG_URL}/api/table.json?"
            f"content=channels&columns=name,maximum_raw,average_raw"
            f"&id={sensor_id}"
            f"&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
        )
        response = requests.get(url, verify=False, timeout=15)
        if response.status_code != 200:
            return {}
        data = response.json()
        stats = {}
        for ch in data.get("channels", []):
            name = ch.get("name", "").strip()
            if "Traffic In" in name:
                key_max, key_avg = "in_max", "in_avg"
            elif "Traffic Out" in name:
                key_max, key_avg = "out_max", "out_avg"
            else:
                continue
            try:
                if ch.get("maximum_raw"):
                    stats[key_max] = round(float(ch["maximum_raw"]) / 1_000_000, 2)
                if ch.get("average_raw"):
                    stats[key_avg] = round(float(ch["average_raw"]) / 1_000_000, 2)
            except (ValueError, TypeError):
                pass
        return stats
    except Exception as e:
        st.error(f"Failed to fetch stats for sensor {sensor_id}: {e}")
        return {}

# --- Display Graph + Stats Card ---
def display_sensor_card(name, sensor_id):
    stats = fetch_bandwidth_stats(sensor_id)

    in_max = stats.get("in_max", 0)
    out_max = stats.get("out_max", 0)
    in_avg = stats.get("in_avg", 0)
    out_avg = stats.get("out_avg", 0)

    # Card container
    with st.container():
        st.markdown(f"<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"🔗 {name}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div class='metric-in big-font'>⬇ In Peak: <b>{in_max:,} Mbps</b></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='big-font'>⬇ Avg In: {in_avg:,} Mbps</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='metric-out big-font'>⬆ Out Peak: <b>{out_max:,} Mbps</b></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='big-font'>⬆ Avg Out: {out_avg:,} Mbps</div>", unsafe_allow_html=True)

        # High-res graph
        graph_url = (
            f"{PRTG_URL}/chart.png?"
            f"type=graph&id={sensor_id}&graphid={graphid}"
            f"&width=1800&height=800"
            f"&graphstyling=base&bgcolor=1e1e1e&fontcolor=ffffff"
            f"&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
        )
        try:
            response = requests.get(graph_url, verify=False, timeout=20)
            if response.status_code == 200 and response.content:
                img = Image.open(BytesIO(response.content))
                st.image(img, use_container_width=True)
            else:
                st.warning("⚠️ Graph image not available")
        except Exception as e:
            st.error(f"Failed to load graph: {e}")

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)

    return in_max, out_max, in_avg, out_avg

# --- Main Display ---
total_in_peak = total_out_peak = total_in_avg = total_out_avg = 0

st.markdown(f"### Viewing: **{graph_period}**")
st.markdown("---")

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    for col, (name, sid) in zip(cols, pair):
        with col:
            in_p, out_p, in_a, out_a = display_sensor_card(name, sid)
            total_in_peak += in_p
            total_out_peak += out_p
            total_in_avg += in_a
            total_out_avg += out_a

# --- Grand Total Summary ---
st.markdown("## 🌐 Aggregate Bandwidth Summary")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Peak In", f"{total_in_peak:,.0f} Mbps", delta=None)
with col2:
    st.metric("Total Peak Out", f"{total_out_peak:,.0f} Mbps", delta=None)
with col3:
    st.metric("Total Avg In", f"{total_in_avg:,.0f} Mbps")
with col4:
    st.metric("Total Avg Out", f"{total_out_avg:,.0f} Mbps")

# --- Beautiful Bar Chart ---
fig, ax = plt.subplots(figsize=(10, 6), facecolor="#0e1117")
bars1 = ax.bar(["Peak In", "Peak Out"], [total_in_peak, total_out_peak],
               color=["#00ff88", "#ff0066"], edgecolor="white", linewidth=1.5, width=0.6)

ax.set_ylabel("Bandwidth (Mbps)", fontsize=14, color="white")
ax.set_title("Total Combined Peak Bandwidth", fontsize=18, fontweight="bold", color="white", pad=20)
ax.tick_params(colors="white", labelsize=12)
ax.grid(axis="y", color="gray", linestyle="--", alpha=0.3)
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")

for bar in bars1:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + max(total_in_peak, total_out_peak)*0.01,
            f'{height:,.0f}', ha='center', va='bottom', fontweight='bold', fontsize=14, color='white')

st.pyplot(fig)
