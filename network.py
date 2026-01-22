import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth Peaks + Troubleshooter", layout="wide")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

TOTAL_CAPACITY = 40000  # Mbps

# ────────────────────────────────────────────────
# Period selector with unique key (fixes duplicate ID error)
period = st.selectbox(
    "Time Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1,
    key="period_selector_unique_key"
)

graphid = {
    "Live (2 hours)": "0",
    "Last 48 hours":  "1",
    "Last 7 days":    "-7",
    "Last 30 days":   "2",
    "Last 365 days":  "3"
}[period]

delta_map = {
    "Live (2 hours)": timedelta(hours=2),
    "Last 48 hours":  timedelta(hours=48),
    "Last 7 days":    timedelta(days=7),
    "Last 30 days":   timedelta(days=30),
    "Last 365 days":  timedelta(days=365)
}
delta = delta_map[period]

now = datetime.now()
edate = now.strftime("%Y-%m-%d-%H-%M-%S")
sdate = (now - delta).strftime("%Y-%m-%d-%H-%M-%S")

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

# ────────────────────────────────────────────────
# API TROUBLESHOOTER / DEBUG SECTION
# ────────────────────────────────────────────────

with st.expander("🔍 API Troubleshooter & Raw Data Viewer", expanded=True):

    st.subheader("Current period settings")
    st.write(f"sdate: {sdate}")
    st.write(f"edate: {edate}")
    st.write(f"avg used: 300 seconds (5 min buckets)")

    debug_sensor_id = st.selectbox(
        "Select sensor to debug",
        list(SENSORS.values()),
        index=0,
        format_func=lambda x: next(k for k,v in SENSORS.items() if v==x),
        key="debug_sensor_selector"
    )

    if st.button("Run API Troubleshooter → Fetch both endpoints", type="primary"):

        # 1. Channels endpoint
        st.markdown("### 1. /api/table.json – channels")
        try:
            url = f"{BASE}/api/table.json"
            params = {
                "content": "channels",
                "id": debug_sensor_id,
                "columns": "name,minimum_raw,maximum_raw,lastvalue_raw",
                "username": USER,
                "passhash": PH
            }
            r = requests.get(url, params=params, verify=False, timeout=15)
            data = r.json()
            st.success(f"Status: {r.status_code}")
            st.json(data)
        except Exception as e:
            st.error(f"Channels endpoint failed: {str(e)}")

        st.divider()

        # 2. Historic data endpoint
        st.markdown("### 2. /api/historicdata.json – time series")
        try:
            params = {
                "id": debug_sensor_id,
                "sdate": sdate,
                "edate": edate,
                "avg": 300,
                "usecaption": 1,
                "username": USER,
                "passhash": PH
            }
            r = requests.get(f"{BASE}/api/historicdata.json", params=params, verify=False, timeout=30)
            data = r.json()

            st.success(f"Status: {r.status_code} – {len(data.get('histdata', []))} data points")

            if "histdata" in data and data["histdata"]:
                first = data["histdata"][0]
                st.write("**First data point keys:**")
                st.code(list(first.keys()))

                st.write("**First data point values (sample):**")
                for k, v in list(first.items())[:10]:
                    st.write(f"{k}: {v}")

                # Look for speed channels
                in_key = "Traffic In (Speed)"
                out_key = "Traffic Out (Speed)"

                if in_key in first:
                    st.success(f"Found: {in_key} = {first[in_key]}")
                else:
                    st.warning(f"{in_key} NOT found in keys")

                if out_key in first:
                    st.success(f"Found: {out_key} = {first[out_key]}")
                else:
                    st.warning(f"{out_key} NOT found in keys")

            else:
                st.warning("No 'histdata' array or empty response")

        except Exception as e:
            st.error(f"Historic endpoint failed: {str(e)}")

# ────────────────────────────────────────────────
# MAIN DASHBOARD
# ────────────────────────────────────────────────

st.title("PRTG Bandwidth Dashboard – Period Peak")
st.caption(f"{period} • {sdate} → {edate} • Graph ID: {graphid}")

total_peak_in = total_peak_out = 0.0

for name, sid in SENSORS.items():
    with st.container():
        st.subheader(name)

        # Fetch peaks
        peak_in, peak_out = get_peak_speeds(sid, sdate, edate)

        total_peak_in += peak_in
        total_peak_out += peak_out

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Peak Download", f"{peak_in:,.2f} Mbps")
        with c2:
            st.metric("Peak Upload", f"{peak_out:,.2f} Mbps")

        # Graph
        img = get_graph_image(sid, graphid)
        if img:
            st.image(img, use_container_width=True)
        else:
            st.caption("Graph unavailable")

# Combined summary
st.markdown("## Combined Peak")
st.metric("Total Peak Download", f"{total_peak_in:,.0f} Mbps")
st.metric("Total Peak Upload",   f"{total_peak_out:,.0f} Mbps")

pct_in = (total_peak_in / TOTAL_CAPACITY) * 100 if TOTAL_CAPACITY > 0 else 0
pct_out = (total_peak_out / TOTAL_CAPACITY) * 100 if TOTAL_CAPACITY > 0 else 0

st.progress(min(pct_in / 100, 1.0))
st.caption(f"Download utilization: {pct_in:.1f}%")
st.progress(min(pct_out / 100, 1.0))
st.caption(f"Upload utilization: {pct_out:.1f}%")
