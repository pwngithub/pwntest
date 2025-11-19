import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Page Config ---
st.set_page_config(page_title="PRTG Bandwidth Dashboard", layout="wide", page_icon="Chart")

# --- Credentials ---
try:
    PRTG_USERNAME = st.secrets["prtg_username"]
    PRTG_PASSHASH = st.secrets["prtg_passhash"]
except KeyError:
    st.error("Missing PRTG credentials in Streamlit secrets.")
    st.stop()

PRTG_URL = "https://prtg.pioneerbroadband.net"

# --- Custom CSS (keeps it gorgeous) ---
st.markdown("""
<style>
    .big-font { font-size: 19px !important; font-weight: bold; }
    .metric-in { color: #00ff88; background-color: rgba(0,255,136,0.15); padding: 12px; border-radius: 12px; border-left: 6px solid #00ff88; }
    .metric-out { color: #ff3366; background-color: rgba(255,51,102,0.15); padding: 12px; border-radius: 12px; border-left: 6px solid #ff3366; }
    .card {
        background-color: var(--background-color);
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 6px 16px rgba(0,0,0,0.2);
        border: 1px solid #333;
        margin-bottom: 25px;
    }
    hr { border: 1px solid #444; margin: 40px 0; }
</style>
""", unsafe_allow_html=True)

st.title("PRTG Bandwidth Dashboard")
st.markdown("Real-time & historical bandwidth across all circuits")

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

# --- Your Sensors ---
SENSORS = {
    "Firstlight": "12435",
    "NNINIX":    "12506",
    "Hurricane Electric": "12363",
    "Cogent":    "12340",
}

# --- Fetch Peak & Average from "Traffic In (Speed)" and "Traffic Out (Speed)" ---
def fetch_speed_stats(sensor_id):
    url = (
        f"{PRTG_URL}/api/table.json?"
        f"content=channels&columns=name,maximum_raw,average_raw,lastvalue_raw"
        f"&id={sensor_id}&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
    )
    try:
        r = requests.get(url, verify=False, timeout=15)
        r.raise_for_status()
        data = r.json()

        stats = {"in_max": 0, "in_avg": 0, "out_max": 0, "out_avg": 0}

        for channel in data.get("channels", []):
            name = channel.get("name", "").strip()

            if name == "Traffic In (Speed)":
                if channel.get("maximum_raw"):
                    stats["in_max"] = round(float(channel["maximum_raw"]) / 1_000_000, 2)
                if channel.get("average_raw"):
                    stats["in_avg"] = round(float(channel["average_raw"]) / 1_000_000, 2)

            elif name == "Traffic Out (Speed)":
                if channel.get("maximum_raw"):
                    stats["out_max"] = round(float(channel["maximum_raw"]) / 1_000_000, 2)
                if channel.get("average_raw"):
                    stats["out_avg"] = round(float(channel["average_raw"]) / 1_000_000, 2)

        return stats
    except Exception as e:
        st.error(f"Failed to fetch stats for sensor {sensor_id}: {e}")
        return {"in_max": 0, "in_avg": 0, "out_max": 0, "out_avg": 0}

# --- Display One Sensor Card ---
def display_sensor_card(name, sensor_id):
    stats = fetch_speed_stats(sensor_id)

    in_max  = stats["in_max"]
    in_avg  = stats["in_avg"]
    out_max = stats["out_max"]
    out_avg = stats["out_avg"]

    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"{name}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div class='metric-in big-font'>Down Arrow In Peak {big}{in_max:,} Mbps</big></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='big-font>Down Arrow Avg In  {in_avg:,} Mbps</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-out big-font'>Up Arrow Out Peak {big}{out_max:,} Mbps</big></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='big-font'>Up Arrow Avg Out  {out_avg:,} Mbps</div>", unsafe_allow_html=True)

        # High-quality dark PRTG graph
        graph_url = (
            f"{PRTG_URL}/chart.png?"
            f"type=graph&id={sensor_id}&graphid={sensor_id}&graphid={graphid}"
            f"&width=1900&height=850"
            f"&graphstyling=showLegend%3D0%26baseFontSize%3D14"
            f"&bgcolor=1e1e1e&fontcolor=ffffff"
            f"&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
        )
        try:
            r = requests.get(graph_url, verify=False, timeout=20)
            if r.status_code == 200 and len(r.content) > 1000:
                img = Image.open(BytesIO(r.content))
                st.image(img, use_container_width=True)
            else:
                st.warning("Graph not available")
        except:
            st.error("Failed to load graph")

        st.markdown("</div>", unsafe_allow_html=True)

    return in_max, out_max, in_avg, out_avg

# --- Main Layout ---
total_in_peak = total_out_peak = total_in_avg = total_out_avg = 0

st.markdown(f"### {graph_period}")
st.markdown("---")

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    for col, (name, sid) in zip(cols, list(SENSORS.items())[i:i+2]):
        with col:
            ip, op, ia, oa = display_sensor_card(name, sid)
            total_in_peak  += ip
            total_out_peak += op
            total_in_avg   += ia
            total_out_avg  += oa

# --- Grand Summary ---
st.markdown("## Global Aggregate Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Peak In",  f"{total_in_peak:,.0f} Mbps",  delta=None)
col2.metric("Total Peak Out", f"{total_out_peak:,.0f} Mbps", delta=None)
col3.metric("Total Avg In",   f"{total_in_avg:,.0f} Mbps")
col4.metric("Total Avg Out",  f"{total_out_avg:,.0f} Mbps")

# --- Fancy Bar Chart ---
fig, ax = plt.subplots(figsize=(10, 6), facecolor="#0e1117")
bars = ax.bar(["Peak In", "Peak Out"],
              [total_in_peak, total_out_peak],
              color=["#00ff88", "#ff3366"],
              edgecolor="white", linewidth=2, width=0.55)

ax.set_ylabel("Mbps", fontsize=14, color="white")
ax.set_title("Total Combined Peak Bandwidth", fontsize=20, fontweight="bold", color="white", pad=30)
ax.tick_params(colors="white", labelsize=12)
ax.grid(axis="y", color="#333", linestyle="--", alpha=0.4)
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")

for bar in bars:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., h + total_in_peak*0.015,
            f'{h:,.0f}', ha='center', va='bottom', fontsize=16, fontweight='bold', color='white')

st.pyplot(fig, use_container_width=True)
