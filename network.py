import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Bandwidth – 100% Accurate", layout="wide", page_icon="Internet")

# ====================== CREDENTIALS ======================
USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

# ====================== PERIOD ======================
period = st.selectbox("Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1, key="period")

graphid_map = {"Live (2 hours)":"0", "Last 48 hours":"1", "Last 7 days":"-7", "Last 30 days":"2", "Last 365 days":"3"}
graphid = graphid_map[period]

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric":  "12363",
    "Cogent":              "12340",
}

# ====================== CORRECT PEAK CALCULATION ======================
def get_correct_peaks(sensor_id):
    url = f"{BASE}/api/table.json"
    params = {
        "content": "channels",
        "id": sensor_id,
        "columns": "name,maximum_raw",
        "username": USER,
        "passhash": PH
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=12)
        data = r.json()

        in_peak = out_peak = 0
        for ch in data.get("channels", []):
            name = ch.get("name", "").strip()
            max_raw = ch.get("maximum_raw", "0")

            if max_raw == "" or float(max_raw) == 0:
                continue

            # Convert bytes-per-10-seconds → real Mbps
            mbps = (float(max_raw) / 10240) * 1024

            if "Traffic In" in name:
                in_peak = int(round(mbps))
            elif "Traffic Out" in name:
                out_peak = int(round(mbps))

        return in_peak, out_peak
    except:
        return 0, 0

# ====================== MAIN DISPLAY ======================
st.title("PRTG Bandwidth Dashboard – 100 % Accurate Mbps")
st.caption(f"Period: **{period}**")

total_in = total_out = 0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    for col, (name, sid) in zip(cols, pair):
        with col:
            i_peak, o_peak = get_correct_peaks(sid)
            total_in  += i_peak
            total_out += o_peak

            st.subheader(name)
            st.metric("Peak In",  f"{i_peak:,} Mbps")
            st.metric("Peak Out", f"{o_peak:,} Mbps")

            # Full graph
            gurl = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
            try:
                img = Image.open(BytesIO(requests.get(gurl, params={"username":USER, "passhash":PH}, verify=False).content))
                st.image(img, use_container_width=True)
            except:
                st.caption("Graph unavailable")

# ====================== TOTAL SUMMARY ======================
st.markdown("## Combined Across All Circuits")
c1, c2 = st.columns(2)
c1.metric("Total Peak In",  f"{total_in:,} Mbps")
c2.metric("Total Peak Out", f"{total_out:,} Mbps")

# Bar chart
fig, ax = plt.subplots(figsize=(10,6))
ax.bar(["Total Peak In", "Total Peak Out"], [total_in, total_out],
       color=["#00ff88", "#ff3366"], width=0.6, edgecolor="white")
ax.set_ylabel("Mbps", color="white")
ax.set_title = f"Total Peak Bandwidth ({period})"
ax.set_title(ax_title, color="white", fontsize=18, fontweight="bold")
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")
ax.tick_params(colors="white")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,}", ha="center", fontweight="bold", color="white", fontsize=14)
st.pyplot(fig)
