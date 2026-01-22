import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth + Debug", layout="wide")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

# ────────────────────────────────────────────────
# CONFIG – change these
DIVISOR = 1000000          # ← Start here; try 100000 / 10000 if values too small
TOTAL_CAPACITY = 40000     # Mbps

SENSORS = {                # ← This was missing → defines your sensors
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}
# ────────────────────────────────────────────────

# Period selector
period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1
)

graphid_map = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}
graphid = graphid_map[period]

use_historic = period in ["Last 7 days", "Last 30 days", "Last 365 days"]

delta_map = {
    "Live (2 hours)": timedelta(hours=2),
    "Last 48 hours":  timedelta(hours=48),
    "Last 7 days":    timedelta(days=7),
    "Last 30 days":   timedelta(days=30),
    "Last 365 days":  timedelta(days=365)
}
delta = delta_map[period]

now = datetime.now()
edate_str = now.strftime("%Y-%m-%d-%H-%M-%S")
sdate_str = (now - delta).strftime("%Y-%m-%d-%H-%M-%S")

avg_sec = 300 if use_historic else 0

# ────────────────────────────────────────────────
# DEBUG SECTION – inspect raw API output
# ────────────────────────────────────────────────

with st.expander("🛠 DEBUG: Raw API Responses", expanded=False):
    st.subheader("Channels (table.json)")
    if st.button("Fetch Channels for All Sensors"):
        for name, sid in SENSORS.items():
            try:
                url = f"{BASE}/api/table.json"
                params = {
                    "content": "channels",
                    "id": sid,
                    "columns": "name,minimum_raw,maximum_raw,lastvalue_raw",
                    "username": USER,
                    "passhash": PH
                }
                r = requests.get(url, params=params, verify=False, timeout=15)
                data = r.json()
                st.write(f"**{name} (ID {sid})**")
                st.json(data)
            except Exception as e:
                st.error(f"{name}: {str(e)}")

    st.divider()
    st.subheader("Historic Data Sample")
    sensor_for_hist = st.selectbox("Sensor for historic sample", list(SENSORS.keys()))
    sid_hist = SENSORS[sensor_for_hist]
    if st.button("Fetch Historic Sample"):
        try:
            params = {
                "id": sid_hist,
                "sdate": sdate_str,
                "edate": edate_str,
                "avg": avg_sec,
                "usecaption": 1,
                "username": USER,
                "passhash": PH
            }
            r = requests.get(f"{BASE}/api/historicdata.json", params=params, verify=False, timeout=30)
            data = r.json()
            st.json(data)
            if "histdata" in data and data["histdata"]:
                st.write("First data point keys:", list(data["histdata"][0].keys()))
        except Exception as e:
            st.error(str(e))

# ────────────────────────────────────────────────
# Dashboard
# ────────────────────────────────────────────────

st.title("PRTG Bandwidth Dashboard")
st.caption(f"{period} • {sdate_str} → {edate_str} • Graph ID: {graphid}")
st.caption(f"DIVISOR = {DIVISOR:,} – change at top if Mbps scale wrong")

total_in_max = total_out_max = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]

    for col, (name, sid) in zip(cols, pair):
        with col:
            # Simple fallback fetch for max
            try:
                url = f"{BASE}/api/table.json"
                params = {
                    "content": "channels",
                    "id": sid,
                    "columns": "name,maximum_raw",
                    "username": USER,
                    "passhash": PH
                }
                data = requests.get(url, params=params, verify=False, timeout=15).json()
                channels = data.get("channels", [])

                in_max_raw = out_max_raw = 0
                for ch in channels:
                    name_ch = ch.get("name", "").strip()
                    max_str = ch.get("maximum_raw", "0")
                    if max_str and max_str.strip():
                        try:
                            val = float(max_str)
                            if "Traffic In" in name_ch:
                                in_max_raw = val
                            elif "Traffic Out" in name_ch:
                                out_max_raw = val
                        except:
                            pass

                in_max_mbps = in_max_raw / DIVISOR if in_max_raw else 0.0
                out_max_mbps = out_max_raw / DIVISOR if out_max_raw else 0.0

                st.subheader(name)
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Download Max", f"{in_max_mbps:,.2f} Mbps")
                with c2:
                    st.metric("Upload Max", f"{out_max_mbps:,.2f} Mbps")

                total_in_max += in_max_mbps
                total_out_max += out_max_mbps

                # Graph
                try:
                    img_url = f"{BASE}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff&username={USER}&passhash={PH}"
                    img_resp = requests.get(img_url, verify=False, timeout=15)
                    if img_resp.status_code == 200:
                        st.image(img_resp.content, use_container_width=True)
                    else:
                        st.caption("Graph unavailable")
                except:
                    st.caption("Graph fetch failed")

            except Exception as e:
                st.error(f"{name}: {str(e)}")

# Combined
st.markdown("## Combined Peak Max")
col1, col2 = st.columns([3,1])
with col1:
    fig, ax = plt.subplots(figsize=(10,6))
    ax.bar(["Download", "Upload"], [total_in_max, total_out_max], color=["#00ff9d", "#ff3366"])
    ax.set_ylabel("Mbps")
    ax.set_title(f"Total Peak – {period}")
    st.pyplot(fig)

with col2:
    st.metric("Download Max", f"{total_in_max:,.0f} Mbps")
    st.metric("Upload Max", f"{total_out_max:,.0f} Mbps")

    pct_in = (total_in_max / TOTAL_CAPACITY) * 100 if TOTAL_CAPACITY > 0 else 0
    pct_out = (total_out_max / TOTAL_CAPACITY) * 100 if TOTAL_CAPACITY > 0 else 0
    st.progress(min(pct_in / 100, 1.0))
    st.caption(f"Download {pct_in:.1f}%")
    st.progress(min(pct_out / 100, 1.0))
    st.caption(f"Upload {pct_out:.1f}%")
