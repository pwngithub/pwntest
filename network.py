import streamlit as st
import requests
import json

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

sensor_id = 12435
sdate = "2026-01-20-14-00-00"   # adjust to match your graph start
edate = "2026-01-22-14-00-00"   # adjust to match your graph end

params = {
    "id": sensor_id,
    "sdate": sdate,
    "edate": edate,
    "avg": 300,
    "usecaption": 1,
    "username": USER,
    "passhash": PH
}

try:
    r = requests.get(f"{BASE}/api/historicdata.json", params=params, verify=False)
    data = r.json()

    st.write("**Status code:**", r.status_code)
    st.write("**Number of data points:**", len(data.get("histdata", [])))

    if "histdata" in data and data["histdata"]:
        first = data["histdata"][0]
        st.write("**First row keys:**")
        st.code(list(first.keys()))

        st.write("**First row values (first 10):**")
        for k, v in list(first.items())[:10]:
            st.write(f"{k}: {v}")

        st.write("**Last row (most recent):**")
        last = data["histdata"][-1]
        for k, v in last.items():
            if "Speed" in k:
                st.write(f"**{k}:** {v}")

        # Try to find max in the data
        max_in = 0
        max_out = 0
        for row in data["histdata"]:
            if "Traffic In (Speed)" in row:
                try:
                    val = float(re.search(r'\d+\.?\d*', row["Traffic In (Speed)"]).group())
                    if "Gbit" in row["Traffic In (Speed)"]:
                        val *= 1000
                    max_in = max(max_in, val)
                except:
                    pass
            if "Traffic Out (Speed)" in row:
                try:
                    val = float(re.search(r'\d+\.?\d*', row["Traffic Out (Speed)"]).group())
                    if "Gbit" in row["Traffic Out (Speed)"]:
                        val *= 1000
                    max_out = max(max_out, val)
                except:
                    pass

        st.write(f"**Calculated max from data → In:** {max_in:,.1f} Mbit/s")
        st.write(f"**Calculated max from data → Out:** {max_out:,.1f} Mbit/s")

    else:
        st.error("No histdata returned")

except Exception as e:
    st.error(f"Error: {str(e)}")
