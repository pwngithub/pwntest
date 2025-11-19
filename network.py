import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================== CONFIG
st.set_page_config(page_title="PRTG Bandwidth Dashboard", layout="wide", page_icon="Chart")

try:
    PRTG_USERNAME = st.secrets["prtg_username"]
    PRTG_PASSHASH = st.secrets["prtg_passhash"]
except KeyError:
    st.error("Missing PRTG credentials in Streamlit secrets.")
    st.stop()

PRTG_URL = "https://prtg.pioneerbroadband.net"

# ==================================== CSS
st.markdown("""
<style>
    .big-font {font-size:19px !important; font-weight:bold;}
    .metric-in  {color:#00ee88; background:rgba(0,238,136,0.12); padding:14px; border-radius:12px; border-left:6px solid #00ee88;}
    .metric-out {color:#ff3366; background:rgba(255,51,102,0.12); padding:14px; border-radius:12px; border-left:6px solid #ff3366;}
    .card {background-color:var(--background-color); padding:22px; border-radius:16px; box-shadow:0 6px 20px rgba(0,0,0,0.25); border:1px solid #333; margin-bottom:30px;}
    hr {border:1px solid #444; margin:50px 0;}
</style>
""", unsafe_allow_html=True)

st.title("PRTG Bandwidth Dashboard")
st.markdown("Live & historical bandwidth across all circuits")

# ==================================== TIME PERIOD
graph_period = st.selectbox(
    "Select Time Period",
    ("Live (2 hours)", "Last 48 hours", "Last 30 days", "Last 365 days"),
    index=1
)

period_to_graphid = {"Live (2 hours)": "0", "Last 48 hours": "1", "Last 30 days": "2", "Last 365 days": "3"}
graphid = period_to_graphid[graph_period]

# ==================================== SENSORS
SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric":  "12363",
    "Cogent":              "12340",
}

# ==================================== FETCH STATS (ROBUST VERSION)
def fetch_speed_stats(sensor_id):
    url = f"{PRTG_URL}/api/table.json?content=channels&columns=name,maximum_raw,average_raw&id={sensor_id}&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
    
    try:
        r = requests.get(url, verify=False, timeout=15)
        r.raise_for_status()
        data = r.json()

        stats = {"in_max": 0.0, "in_avg": 0.0, "out_max": 0.0, "out_avg": 0.0}

        for channel in data.get("channels", []):
            name = channel.get("name", "").strip()

            # This matches EXACTLY what your sensors return:
            if "Traffic In (Speed)" in name:
                if channel.get("maximum_raw"):  stats["in_max"]  = round(float(channel["maximum_raw"]) / 1_000_000, 2)
                if channel.get("average_raw"):  stats["in_avg"]  = round(float(channel["average_raw"]) / 1_000_000, 2)

            if "Traffic Out (Speed)" in name:
                if channel.get("maximum_raw"):  stats["out_max"] = round(float(channel["maximum_raw"]) / 1_000_000, 2)
                if channel.get("average_raw"):  stats["out_avg"] = round(float(channel["average_raw"]) / 1_000_000, 2)

        return stats

    except Exception as e:
        st.error(f"Failed to fetch data for sensor {sensor_id}: {e}")
        return {"in_max": 0, "in_avg": 0, "out_max": 0, "out_avg": 0}

# ==================================== DISPLAY CARD
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
            st.markdown(f"<div class='metric-in big-font'>In Peak  <b>{in_max:,} Mbps</b></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='big-font'>Avg In   {in_avg:,} Mbps</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-out big-font'>Out Peak  <b>{out_max:,} Mbps</b></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='big-font'>Avg Out   {out_avg:,} Mbps</div>", unsafe_allow_html=True)

        # High-resolution dark graph
        graph_url = (
            f"{PRTG_URL}/chart.png?"
            f"type=graph&id={sensor_id}&graphid={graphid}"
            f"&width=2000&height=900"
            f"&bgcolor=1e1e1e&fontcolor=ffffff"
            f"&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
        )
        try:
            r = requests.get(graph_url, verify=False, timeout=20)
            if r.status_code == 200 and len(r.content) > 8000:
                img = Image.open(BytesIO(r.content))
                st.image(img, use_container_width=True)
            else:
                st.warning("Graph not available right now")
        except:
            st.error("Could not load graph")

        st.markdown("</div>", unsafe_allow_html=True)

    return in_max, out_max, in_avg, out_avg

# ==================================== MAIN LOOP
total_in_peak = total_out_peak = total_in_avg = total_out_avg = 0.0

st.markdown(f"### {graph_period}")
st.markdown("---")

sensor_list = list(SENSORS.items())
for i in range(0, len(sensor_list), 2):
    cols = st.columns(2)
    for col, (name, sid) in zip(cols, sensor_list[i:i+2]):
        with col:
            ip, op, ia, oa = display_sensor_card(name, sid)
            total_in_peak  += ip
            total_out_peak += op
            total_in_avg   += ia
            total_out_avg  += oa

# ==================================== SUMMARY
st.markdown("## Aggregate Bandwidth Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Peak In",  f"{total_in_peak:,.0f} Mbps")
col2.metric("Total Peak Out", f"{total_out_peak:,.0f} Mbps")
col3.metric("Total Avg In",   f"{total_in_avg:,.0f} Mbps")
col4.metric("Total Avg Out",  f"{total_out_avg:,.0f} Mbps")

# ==================================== BAR CHART
fig, ax = plt.subplots(figsize=(10, 6), facecolor="#0e1117")
bars = ax.bar(["Peak In", "Peak Out"], [total_in_peak, total_out_peak],
              color=["#00ee88", "#ff3366"], edgecolor="white", linewidth=2, width=0.6)

ax.set_ylabel("Mbps", fontsize=14, color="white")
ax.set_title("Total Combined Peak Bandwidth", fontsize=20, fontweight="bold", color="white", pad=30)
ax.tick_params(colors="white", labelsize=12)
ax.grid(axis="y", color="#333", linestyle="--", alpha=0.4)
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")

for bar in bars:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., h + max(total_in_peak, total_out_peak)*0.02,
            f'{h:,.0f}', ha='center', va='bottom', fontsize=16, fontweight='bold', color='white')

st.pyplot(fig)
