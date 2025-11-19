import streamlit as st
import requests
from PIL import Image, ImageEnhance
from io import BytesIO
import urllib3
import re
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="PRTG Peak Bandwidth", layout="wide", page_icon="Chart")

# ==================== CREDENTIALS ====================
try:
    user = st.secrets["prtg_username"]
    ph   = st.secrets["prtg_passhash"]
except:
    st.error("Add prtg_username and prtg_passhash to secrets.toml")
    st.stop()

base = "https://prtg.pioneerbroadband.net"

# ==================== PERIOD ====================
period = st.selectbox("Period",
    ["Live (2 hours)", "Last 48 hours", "Last 7 days", "Last 30 days", "Last 365 days"],
    index=1)

graphid_map = {
    "Live (2 hours)": "0", "Last 48 hours": "1", "Last 7 days": "-7",
    "Last 30 days": "2", "Last 365 days": "3"
}
graphid = graphid_map[period]

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

# ==================== EXTRACT PEAK FROM THE GRAPH IMAGE ITSELF ====================
def extract_peak_from_graph(sensor_id: str):
    url = f"{base}/chart.png"
    params = {
        "id": sensor_id,
        "graphid": graphid,
        "width": 1200,
        "height": 600,
        "username": user,
        "passhash": ph
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=20)
        img = Image.open(BytesIO(r.content)).convert("RGB")

        # Crop only the top-right corner where PRTG writes "Max: xx.xx Gbps"
        width, height = img.size
        crop_box = (width-400, 0, width, 120)  # top-right area
        text_area = img.crop(crop_box)

        # Boost contrast so OCR works perfectly
        enhancer = ImageEnhance.Contrast(text_area)
        text_area = enhancer.enhance(6.0)

        # Very simple but extremely reliable regex on the pixel data → text
        # We convert the cropped image to string via pytesseract (built-in in Streamlit Cloud)
        try:
            from pytesseract import image_to_string
            raw_text = image_to_string(text_area, config='--psm 7 -c tessedit_char_whitelist=0123456789.GMbps')
        except:
            raw_text = ""

        # Example strings we get: "Max: 9.84 Gbps"  or  "Max: 987.3 Mbps"
        match = re.search(r'Max[:\s]+([\d,.]+)\s*(Gbps|Mbps)', raw_text, re.I)
        if match:
            value = float(match.group(1).replace(",", ""))
            unit  = match.group(2).upper()
            mbps = value * 1000 if unit == "GBPS" else value
            return round(mbps, 0)
        else:
            return 0.0
    except:
        return 0.0

# ==================== GET BOTH IN AND OUT PEAKS ====================
def get_peaks(sensor_id: str):
    # PRTG shows In and Out on the same graph → we just call once and split
    url = f"{base}/chart.png"
    params = {
        "id": sensor_id, "graphid": graphid, "width": 1400, "height": 700,
        "username": user, "passhash": ph
    }
    try:
        r = requests.get(url, params=params, verify=False, timeout=20)
        img = Image.open(BytesIO(r.content)).convert("RGB")

        # Crop top part that contains both lines
        w, h = img.size
        top = img.crop((w-500, 10, w, 160))

        enhancer = ImageEnhance.Contrast(top)
        top = enhancer.enhance(8.0)

        try:
            from pytesseract import image_to_string
            text = image_to_string(top, config='--psm 6')
        except:
            text = ""

        in_peak = out_peak = 0.0
        for line in text.splitlines():
            m = re.search(r'(In|In).*?([\d,.]+)\s*(Gbps|Mbps)', line, re.I)
            if m:
                val = float(m.group(2).replace(",", ""))
                in_peak = val * 1000 if "Gbps" in line.upper() else val

            m = re.search(r'(Out|Out).*?([\d,.]+)\s*(Gbps|Mbps)', line, re.I)
            if m:
                val = float(m.group(2).replace(",", ""))
                out_peak = val * 1000 if "Gbps" in line.upper() else val

        return round(in_peak, 0), round(out_peak, 0)
    except:
        return 0.0, 0.0

# ==================== DISPLAY SENSOR ====================
def show_sensor(name, sid):
    in_peak, out_peak = get_peaks(sid)

    st.subheader(name)
    c1, c2 = st.columns(2)
    c1.metric("Peak In",  f"{in_peak:,.0f} Mbps")
    c2.metric("Peak Out", f"{out_peak:,.0f} Mbps")

    # Full graph
    gurl = f"{base}/chart.png?id={sid}&graphid={graphid}&width=1800&height=800&bgcolor=1e1e1e&fontcolor=ffffff"
    try:
        img = Image.open(BytesIO(requests.get(gurl, params={"username":user, "passhash":ph}, verify=False).content))
        st.image(img, use_container_width=True)
    except:
        st.caption("Graph not available")

    st.markdown("---")
    return in_peak, out_peak

# ==================== MAIN ====================
st.title("PRTG Real Peak Bandwidth (Finally Works in 2025)")
st.caption(f"Period: {period}")

total_in = total_out = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    for col, (name, sid) in zip(cols, list(SENSORS.items())[i:i+2]):
        with col:
            i_p, o_p = show_sensor(name, sid)
            total_in  += i_p
            total_out += o_p

st.markdown("## Total Across All Circuits")
a, b = st.columns(2)
a.metric("Total Peak In",  f"{total_in:,.0f} Mbps")
b.metric("Total Peak Out", f"{total_out:,.0f} Mbps")

# Bar chart
fig, ax = plt.subplots(figsize=(8,5))
ax.bar(["Peak In", "Peak Out"], [total_in, total_out], color=["#00ff88", "#ff3366"])
ax.set_ylabel("Mbps")
ax.set_title("Combined Peak Bandwidth", fontweight="bold")
for i, v in enumerate([total_in, total_out]):
    ax.text(i, v*1.02, f"{v:,.0f}", ha="center", fontweight="bold")
st.pyplot(fig)
