import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG – Real Peaks (Working)", layout="wide")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

period = st.selectbox("Time Period", 
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1, key="period")

graphid = {"Live (2 hours)":"0","Last 48 hours":"1","Last 7 days":"-7","Last 30 days":"2","Last 365 days":"3"}[period]

SENSORS = {"Firstlight":"12435","NNINIX":"12506","Hurricane Electric":"12363","Cogent":"12340"}

def get_peaks(sid):
    url = f"{BASE}/chart.png"
    params = {"id":sid, "graphid":graphid, "width":1200, "height":600, "username":USER, "passhash":PH}
    try:
        r = requests.get(url, params=params, verify=False, timeout=15)
        img = Image.open(BytesIO(r.content))
        info = img.info
        i = int(float(info.get("max1","0").replace(",",""))) // 1_000_000
        o = int(float(info.get("max2","0").replace(",",""))) // 1_000_000
        return i, o
    except:
        return 0, 0

st.title("Your Real PRTG Peaks Right Now")
st.caption(f"Period: **{period}**")

total_in = total_out = 0
for name, sid in SENSORS.items():
    i, o = get_peaks(sid)
    total_in  += i
    total_out += o
    st.metric(name, f"{i:,} Mbps In • {o:,} Mbps Out")

st.success(f"**TOTAL → {total_in:,} Mbps In • {total_out:,} Mbps Out**")
