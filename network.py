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

# Force a permanent, stable key for the entire lifetime of the session
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
    "Last 48 hours": "1",
    "Last 7 days": "-7",
    "Last 30 days": "2",
    "Last 365 days": "3"
}[period]

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

@st.cache_data(ttl=300)
def get_real_peaks(sensor_id):
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
        in_peak = out_peak = 0.0
        for ch in data.get("channels", []):
            name = ch.get("name", "").strip()
            raw = ch.get("maximum_raw", "0")
            if not raw or float(raw) == 0:
                continue
            mbps = float(raw) / 1e7
            if "Traffic In" in name or "Down" in name:
                in_peak = max(in_peak, round(mbps, 2))
            elif "Traffic Out" in name or "Up" in name:
                out_peak = max(out_peak, round(mbps, 2))
        return in_peak, out_peak
    except:
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
        return Image.open(BytesIO(resp.content))
    except:
        return None

st.title("PRTG Bandwidth Dashboard")
st.caption(f"Period: **{period}**")

total_in = total_out = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    for col, (name, sid) in zip(cols, pair):
        with col:
            in_peak, out_peak = get_real_peaks(sid)
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

st.markdown("## Combined Peak Across All Circuits")
c1, c2 = st.columns(2)
c1.metric("Total Peak In",  f"{total_in:,.2f} Mbps")
c2.metric("Total Peak Out", f"{total_out:,.2f} Mbps")

fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(["Total Peak In", "Total Peak Out"], [total_in, total_out],
       color=["#00ff88", "#ff3366"], width=0.6, edgecolor="white", linewidth=2)
ax.set_ylabel("Mbps", color="white", fontsize=14)
ax.set_title(f"Combined Peak Bandwidth – {period}", color="white", fontsize=20, fontweight="bold")
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")
ax.tick_params(colors="white")
for bar in ax.patches:
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(total_in, total_out)*0.01,
            f"{bar.get_height():,.2f}", ha="center", va="bottom",
            color="white", fontsize=18, fontweight="bold")
st.pyplot(fig)
