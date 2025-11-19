import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
urllib3.disable_warnings()

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

def get_peaks(sid):
    url = f"{BASE}/chart.png?id={sid}&graphid=1&width=1000&height=500"
    r = requests.get(url, params={"username": USER, "passhash": PH}, verify=False, timeout=15)
    img = Image.open(BytesIO(r.content))
    info = img.info
    i = int(float(info.get("max1","0").replace(",",""))) // 1_000_000
    o = int(float(info.get("max2","0").replace(",",""))) // 1_000_000
    return i, o

st.title("Your Real Peaks Right Now")
for name, sid in {"Firstlight": "12435", "NNINIX": "12506", "Hurricane Electric": "12363", "Cogent": "12340"}.items():
    i, o = get_peaks(sid)
    st.metric(name, f"{i:,} Mbps In  •  {o:,} Mbps Out")
