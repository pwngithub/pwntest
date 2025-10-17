import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

# Disable SSL warnings for self-signed certs (safe internally)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Page Setup ---
st.set_page_config(page_title="PRTG Graph Viewer", layout="wide")

PRTG_URL = "https://prtg.pioneerbroadband.net"

# --- Load Credentials ---
try:
    PRTG_USERNAME = st.secrets["prtg_username"]
    PRTG_PASSHASH = st.secrets["prtg_passhash"]
except KeyError:
    st.error("Missing PRTG credentials in Streamlit secrets.")
    st.stop()

st.title("📊 PRTG Bandwidth Overview")

# --- Graph Period ---
graph_period = st.selectbox(
    "Select Graph Period",
    ("Live (2 hours)", "Last 48 hours", "Last 30 days", "Last 365 days"),
)
period_to_graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours": "1",
    "Last 30 days": "2",
    "Last 365 days": "3",
}
graphid = period_to_graphid[graph_period]

# --- Sensors (Renamed) ---
SENSORS = {
    "Firstlight (ID 12435)": "12435",
    "NNINIX (ID 12506)": "12506",
    "HE (ID 12363)": "12363",
    "Cogent (ID 12340)": "12340",
}

# --- Fetch Peak/Average Stats ---
def fetch_bandwidth_stats(sensor_id):
    try:
        url = (
            f"{PRTG_URL}/api/table.json?"
            f"content=channels&columns=name,maximum_raw,average_raw"
            f"&id={sensor_id}"
            f"&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
        )
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            stats = {}
            for ch in data.get("channels", []):
                name = ch.get("name", "")
                max_val = ch.get("maximum_raw")
                avg_val = ch.get("average_raw")

                if max_val not in (None, "", " "):
                    try:
                        stats[f"{name}_max"] = round(float(max_val) / 1_000_000, 2)
                    except ValueError:
                        pass
                if avg_val not in (None, "", " "):
                    try:
                        stats[f"{name}_avg"] = round(float(avg_val) / 1_000_000, 2)
                    except ValueError:
                        pass
            return stats
    except Exception as e:
        st.warning(f"Error fetching bandwidth data for sensor {sensor_id}: {e}")
    return {}

# --- Fetch and Display Graph ---
def show_graph(sensor_name, sensor_id):
    stats = fetch_bandwidth_stats(sensor_id)
    in_peak = stats.get("Traffic In_max", 0)
    out_peak = stats.get("Traffic Out_max", 0)
    in_avg = stats.get("Traffic In_avg", 0)
    out_avg = stats.get("Traffic Out_avg", 0)

    st.markdown(
        f"**Peak In:** {in_peak} Mbps  **Peak Out:** {out_peak} Mbps  \n"
        f"**Avg In:** {in_avg} Mbps  **Avg Out:** {out_avg} Mbps"
    )

    graph_url = (
        f"{PRTG_URL}/chart.png"
        f"?id={sensor_id}&graphid={graphid}"
        f"&width=1600&height=700"  # ⬅️ Larger, higher-resolution graphs
        f"&avg=0&graphstyling=base"
        f"&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
    )

    try:
        response = requests.get(graph_url, verify=False, timeout=10)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            img = Image.open(BytesIO(response.content))
            st.image(img, caption=f"{sensor_name}", use_container_width=True)  # ⬅️ Fill width
            st.markdown("<hr style='border:1px solid #ccc; margin:20px 0;'>", unsafe_allow_html=True)
        else:
            st.warning(f"⚠️ Could not load graph for {sensor_name}.")
    except requests.exceptions.RequestException as e:
        st.error(f"Network error for {sensor_name}")
        st.code(str(e))
    return in_peak, out_peak


# --- Display Sensors (2×2 Grid) + Collect Totals ---
total_in = 0
total_out = 0
sensor_items = list(SENSORS.items())

for i in range(0, len(sensor_items), 2):
    cols = st.columns(2)
    for col, (sensor_name, sensor_id) in zip(cols, sensor_items[i:i+2]):
        with col:
            st.subheader(f"{sensor_name} — {graph_period}")
            in_peak, out_peak = show_graph(sensor_name, sensor_id)
            total_in += in_peak
            total_out += out_peak

# --- Summary Chart for Total Bandwidth ---
st.markdown("---")
st.header("📈 Total Bandwidth Summary (All Sensors Combined)")

st.markdown(
    f"**Total Peak In:** {total_in:.2f} Mbps  **Total Peak Out:** {total_out:.2f} Mbps"
)

fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(["Total Peak In", "Total Peak Out"], [total_in, total_out],
       color=["tab:blue", "tab:orange"])
ax.set_ylabel("Mbps")
ax.set_title("Aggregate Peak Bandwidth (Current)")
ax.grid(axis="y", linestyle="--", alpha=0.6)
st.pyplot(fig)
