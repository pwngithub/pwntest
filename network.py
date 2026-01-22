import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import uuid

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

# Update to your actual total uplink capacity in Mbps
TOTAL_CAPACITY = 40000  # e.g. 40 Gbps

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

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

@st.cache_data(ttl=300)
def get_traffic_stats(sensor_id):
    """
    Fetch min/max from channel overview (table.json) for the sensor.
    This gives the min/max over the current graph period in PRTG.
    """
    url = f"{BASE}/api/table.json"
    params = {
        "content": "channels",
        "id": sensor_id,
        "columns": "name,minimum_raw,maximum_raw,lastvalue_raw",
        "username": USER,
        "passhash": PH
    }
    try:
        data = requests.get(url, params=params, verify=False, timeout=20).json()
        channels = data.get("channels", [])

        if not channels:
            st.info(f"No channels found for sensor {sensor_id}")
            return 0.0, 0.0, 0.0, 0.0

        # Debug: show actual channel names
        channel_names = [ch.get("name", "Unknown") for ch in channels]
        st.caption(f"Channels for {sensor_id}: {', '.join(channel_names)}")

        in_min = in_max = out_min = out_max = 0.0

        for ch in channels:
            name = ch.get("name", "").strip().lower()
            min_raw = ch.get("minimum_raw", "0")
            max_raw = ch.get("maximum_raw", "0")

            # Skip if no valid raw value
            if not min_raw or not max_raw:
                continue

            try:
                min_val = float(min_raw) / 10_000_000
                max_val = float(max_raw) / 10_000_000
            except:
                continue

            # Match common traffic channel names
            if any(word in name for word in ["traffic in", "in", "down", "download", "rx", "receive", "input", "ingress"]):
                in_min = min(in_min, min_val) if in_min else min_val
                in_max = max(in_max, max_val)
            elif any(word in name for word in ["traffic out", "out", "up", "upload", "tx", "send", "transmit", "output", "egress"]):
                out_min = min(out_min, min_val) if out_min else min_val
                out_max = max(out_max, max_val)

        if in_max == 0 and out_max == 0:
            st.warning(f"No matching in/out traffic channels found for {sensor_id}")

        return (
            round(in_min, 2),
            round(in_max, 2),
            round(out_min, 2),
            round(out_max, 2)
        )

    except Exception as e:
        st.error(f"Error fetching stats for sensor {sensor_id}: {str(e)}")
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
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content))
        return None
    except:
        return None


st.title("PRTG Bandwidth Dashboard – Min & Max per Period")
st.caption(f"Period: **{period}**   |   Graph ID: {graphid}")
st.info("Showing min/max from PRTG channel data (matches graph period). Check captions below each provider for actual channel names.")

total_in_min = total_in_max = 0.0
total_out_min = total_out_max = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]

    for col, (name, sid) in zip(cols, pair):
        with col:
            in_min, in_max, out_min, out_max = get_traffic_stats(sid)

            total_in_min += in_min
            total_in_max += in_max
            total_out_min += out_min
            total_out_max += out_max

            st.subheader(name)

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Download Min", f"{in_min:,.2f} Mbps" if in_min > 0 else "N/A")
                st.metric("Download Max", f"{in_max:,.2f} Mbps" if in_max > 0 else "N/A")
            with c2:
                st.metric("Upload Min",   f"{out_min:,.2f} Mbps" if out_min > 0 else "N/A")
                st.metric("Upload Max",   f"{out_max:,.2f} Mbps" if out_max > 0 else "N/A")

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
            offset = -width/2 if i < len(groups) else width/2
            ax.text((i % len(groups)) + offset, v + current_max * 0.015,
                    f"{v:,.0f}", ha="center", va="bottom",
                    fontsize=16, fontweight="bold", color="white")

    st.pyplot(fig, use_container_width=True)

with col_right:
    st.metric("**Combined Download Min**", f"{total_in_min:,.0f} Mbps")
    st.metric("**Combined Download Max**", f"{total_in_max:,.0f} Mbps")
    st.metric("**Combined Upload Min**",   f"{total_out_min:,.0f} Mbps")
    st.metric("**Combined Upload Max**",   f"{total_out_max:,.0f} Mbps")

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
