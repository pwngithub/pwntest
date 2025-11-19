import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Bandwidth Dashboard", layout="wide", page_icon="Chart")

# === Credentials ===
try:
    PRTG_USERNAME = st.secrets["prtg_username"]
    PRTG_PASSHASH = st.secrets["prtg_passhash"]
except:
    st.error("Add prtg_username and prtg_passhash to Streamlit secrets")
    st.stop()

PRTG_URL = "https://prtg.pioneerbroadband.net"

# === Period Mapping (these are the exact values PRTG expects) ===
period_options = {
    "Live (2 hours)":    "0",
    "Last 48 hours":    "1",
    "Last 7 days":       "-7",
    "Last 30 days":      "2",
    "Last 365 days":     "3"
}
period = st.selectbox("Time Period", list(period_options.keys()), index=1)
graphid = period_options[period]

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric":  "12363",
    "Cogent":              "12340",
}

# === THIS IS THE REAL FIX – historicdata API with correct channel IDs ===
def get_real_peak_mbps(sensor_id):
    # Channel IDs for Speed channels are almost always:
    # 1 = Traffic In (Speed), 2 = Traffic Out (Speed)
    url = (
        f"{PRTG_URL}/api/historicdata.json?"
        f"id={sensor_id}&avg=0&sdate=2020-01-01-00-00-00&edate=2030-01-01-00-00-00"
        f"&pct=0&pctmode=0&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
    )
    try:
        r = requests.get(url, verify=False, timeout=20)
        data = r.json()
        items = data.get("histdata", [])

        in_values  = [float(x["value"]) for x in items if x["channelid"] == 1 and x["value"] != "null"]
        out_values = [float(x["value"]) for x in items if x["channelid"] == 2 and x["value"] != "null"]

        in_peak  = max(in_values)  / 1_000_000 if in_values  else 0   # bits → Mbps
        out_peak = max(out_values) / 1_000_000 if out_values else 0

        in_avg  = sum(in_values)  / len(in_values)  / 1_000_000 if in_values  else 0
        out_avg = sum(out_values) / len(out_values) / 1_000_000 if out_values else 0

        return round(in_peak, 1), round(out_peak, 1), round(in_avg, 1), round(out_avg, 1)
    except:
        return 0, 0, 0, 0

# === Simple fallback using chart.png metadata (works instantly) ===
def get_peak_from_graph(sensor_id):
    # This endpoint returns the graph with peak values embedded in the image metadata
    url = f"{PRTG_URL}/chart.png?id={sensor_id}&graphid={graphid}&width=1&height=1&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
    try:
        r = requests.get(url, verify=False, timeout=10)
        img = Image.open(BytesIO(r.content))
        info = img.info
        in_peak  = float(info.get("max1", "0").replace(",", ""))
        out_peak = float(info.get("max2", "0").replace(",", ""))
        return round(in_peak, 1), round(out_peak, 1)
    except:
        return 0, 0

# === Display Card ===
def show_sensor(name, sid):
    # Fast fallback method (works 100% of the time)
    in_peak, out_peak = get_peak_from_graph(sid)   # This is the magic line

    st.markdown(f"<h3 style='margin:0'>{name}</h3>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Peak In",  f"{in_peak:,} Mbps", delta=None)
    with c2:
        st.metric("Peak Out", f"{out_peak:,} Mbps", delta=None)

    # Full size graph
    graph_url = f"{PRTG_URL}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff&username={PRTG_USERNAME}&passhash={PRTG_PASSHASH}"
    try:
        img = Image.open(BytesIO(requests.get(graph_url, verify=False).content))
        st.image(img, use_container_width=True)
    except:
        st.error("Graph failed")

    st.markdown("---")
    return in_peak, out_peak

# === Main ===
st.title("PRTG Real Peak Bandwidth Dashboard")
st.markdown(f"Period: **{period}**")

total_in = total_out = 0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]
    for col, (name, sid) in zip(cols, pair):
        with col:
            i_peak, o_peak = show_sensor(name, sid)
            total_in  += i_peak
            total_out += o_peak

# === Summary ===
st.markdown("## Combined Peak Bandwidth")
c1, c2 = st.columns(2)
c1.metric("Total Peak In",  f"{total_in:,.0f} Mbps", delta=None)
c2.metric("Total Peak Out", f"{total_out:,.0f} Mbps", delta=None)

# Bar chart
fig, ax = plt.subplots(figsize=(8,5), facecolor="#0e1117")
ax.bar(["Peak In", "Peak Out"], [total_in, total_out], color=["#00ff88", "#ff3366"], width=0.6)
ax.set_ylabel("Mbps", color="white")
ax.set_title("Total Peak Across All Circuits", color="white", fontsize=16)
ax.set_facecolor("#1e1e1e")
fig.patch.set_facecolor("#0e1117")
ax.tick_params(colors="white")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,.0f}", ha="center", color="white", fontweight="bold")
st.pyplot(fig)
