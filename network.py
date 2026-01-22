import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import urllib3
import matplotlib.pyplot as plt
import uuid
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="PRTG Bandwidth", layout="wide", page_icon="Signal")

USER = st.secrets["prtg_username"]
PH   = st.secrets["prtg_passhash"]
BASE = "https://prtg.pioneerbroadband.net"

# ────────────────────────────────────────────────
#   IMPORTANT: Tune this value based on debug output
#   Common values: 1000000 (1e6), 100000 (1e5), 10000 (1e4)
#   Start with 1000000 and look at "Raw max ..." captions
# ────────────────────────────────────────────────
DIVISOR = 1000000

TOTAL_CAPACITY = 40000  # Mbps

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

# Averaging only used in historic mode
avg_sec = 300 if use_historic else 0   # 5 minutes for longer periods

SENSORS = {
    "Firstlight":          "12435",
    "NNINIX":              "12506",
    "Hurricane Electric": "12363",
    "Cogent":              "12340",
}

@st.cache_data(ttl=300)
def get_traffic_stats(sensor_id, use_hist, sdate, edate, avg):
    divisor = DIVISOR

    if not use_hist:
        # Short periods: use channel maximum_raw (PRTG's computed max over recent data)
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
                st.caption(f"No channels for {sensor_id}")
                return 0.0, 0.0, 0.0, 0.0

            channel_names = [ch["name"].strip() for ch in channels]
            st.caption(f"Channels {sensor_id}: {', '.join(channel_names)}")

            in_min = in_max = out_min = out_max = 0.0
            raw_max_in = raw_max_out = 0

            for ch in channels:
                name = ch.get("name", "").strip().lower()
                min_raw = float(ch.get("minimum_raw", "0"))
                max_raw = float(ch.get("maximum_raw", "0"))

                if max_raw > 0:
                    if "in" in name or "down" in name or "rx" in name or "receive" in name or "traffic in" in name:
                        in_min = min(in_min, min_raw / divisor) if in_min else min_raw / divisor
                        in_max = max(in_max, max_raw / divisor)
                        raw_max_in = max(raw_max_in, max_raw)
                    elif "out" in name or "up" in name or "tx" in name or "transmit" in name or "traffic out" in name:
                        out_min = min(out_min, min_raw / divisor) if out_min else min_raw / divisor
                        out_max = max(out_max, max_raw / divisor)
                        raw_max_out = max(raw_max_out, max_raw)

            if raw_max_in > 0 or raw_max_out > 0:
                st.caption(f"Raw max in/out {sensor_id}: {raw_max_in:,.0f} / {raw_max_out:,.0f}")

            if in_max < 0.1 and out_max < 0.1 and (raw_max_in > 1000 or raw_max_out > 1000):
                st.warning(f"Values very low for {sensor_id} – try smaller DIVISOR (current: {divisor})")

            return round(in_min, 2), round(in_max, 2), round(out_min, 2), round(out_max, 2)

        except Exception as e:
            st.caption(f"Channel API error {sensor_id}: {str(e)}")
            return 0.0, 0.0, 0.0, 0.0

    else:
        # Historic mode for longer periods
        url = f"{BASE}/api/historicdata.json"
        params = {
            "id": sensor_id,
            "sdate": sdate,
            "edate": edate,
            "avg": avg,
            "usecaption": 1,
            "username": USER,
            "passhash": PH
        }
        try:
            resp = requests.get(url, params=params, verify=False, timeout=30).json()
            histdata = resp.get("histdata", [])
            if not histdata:
                st.caption(f"No historic data {sensor_id} ({period})")
                return 0.0, 0.0, 0.0, 0.0

            raw_keys = [k for k in histdata[0] if k.lower().endswith("_raw")]
            if raw_keys:
                st.caption(f"Raw keys {sensor_id}: {', '.join(raw_keys[:5])}...")

            in_raw_keys = [k for k in raw_keys if any(w in k.lower() for w in ["in", "down", "rx", "receive", "traffic in"])]
            out_raw_keys = [k for k in raw_keys if any(w in k.lower() for w in ["out", "up", "tx", "transmit", "traffic out"])]

            if not in_raw_keys or not out_raw_keys:
                st.caption(f"No matching in/out keys for {sensor_id}")
                return 0.0, 0.0, 0.0, 0.0

            in_values = []
            out_values = []
            for item in histdata:
                for k in in_raw_keys:
                    v = item.get(k)
                    if v and v.strip():
                        try: in_values.append(float(v))
                        except: pass
                for k in out_raw_keys:
                    v = item.get(k)
                    if v and v.strip():
                        try: out_values.append(float(v))
                        except: pass

            if not in_values or not out_values:
                return 0.0, 0.0, 0.0, 0.0

            in_min = min(in_values) / divisor
            in_max = max(in_values) / divisor
            out_min = min(out_values) / divisor
            out_max = max(out_values) / divisor

            # Debug raw extremes
            st.caption(f"Raw max in/out hist {sensor_id}: {max(in_values):,.0f} / {max(out_values):,.0f}")

            return round(in_min, 2), round(in_max, 2), round(out_min, 2), round(out_max, 2)

        except Exception as e:
            st.caption(f"Historic error {sensor_id}: {str(e)}")
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
        r = requests.get(url, params=params, verify=False, timeout=15)
        return Image.open(BytesIO(r.content)) if r.ok else None
    except:
        return None


# ────────────────────────────────────────────────
st.title("PRTG Bandwidth Dashboard")
st.caption(f"**{period}**  •  {sdate_str} → {edate_str}  •  Graph ID: {graphid}")
st.caption(f"**DIVISOR = {DIVISOR}**  – change at top of code and reload if values are wrong")

total_in_min = total_in_max = total_out_min = total_out_max = 0.0

for i in range(0, len(SENSORS), 2):
    cols = st.columns(2)
    pair = list(SENSORS.items())[i:i+2]

    for col, (name, sid) in zip(cols, pair):
        with col:
            in_min, in_max, out_min, out_max = get_traffic_stats(sid, use_historic, sdate_str, edate_str, avg_sec)

            total_in_min += in_min
            total_in_max += in_max
            total_out_min += out_min
            total_out_max += out_max

            st.subheader(name)

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Download Min", f"{in_min:,.2f} Mbps")
                st.metric("Download Max", f"{in_max:,.2f} Mbps")
            with c2:
                st.metric("Upload Min",   f"{out_min:,.2f} Mbps")
                st.metric("Upload Max",   f"{out_max:,.2f} Mbps")

            img = get_graph_image(sid, graphid)
            if img:
                st.image(img, use_container_width=True)
            else:
                st.caption("Graph unavailable")

# Combined
st.markdown("## Combined Across All Circuits")

colL, colR = st.columns([3, 1])

with colL:
    fig, ax = plt.subplots(figsize=(12, 7))
    groups = ["Download", "Upload"]
    mins = [total_in_min, total_out_min]
    maxs = [total_in_max, total_out_max]

    x = range(len(groups))
    w = 0.35

    ax.bar([i - w/2 for i in x], mins, w, label="Min", color="#00d4ff", edgecolor="white")
    ax.bar([i + w/2 for i in x], maxs, w, label="Max", color="#ff3366",  edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(groups, fontsize=16, fontweight="bold", color="white")
    ax.set_ylabel("Mbps", fontsize=16, fontweight="bold", color="white")
    ax.set_title(f"Total Min/Max – {period}", fontsize=24, fontweight="bold", color="white", pad=30)

    ax.set_facecolor("#0e1117")
    fig.patch.set_facecolor("#0e1117")
    ax.tick_params(colors="white", labelsize=14)
    ax.grid(axis="y", alpha=0.2, color="white", linestyle="--")
    ax.legend(fontsize=14)

    ymax = max(maxs) if max(maxs) > 0 else 100
    ax.set_ylim(0, ymax * 1.15)

    for i, v in enumerate(mins + maxs):
        if v > 0:
            offset = -w/2 if i < 2 else w/2
            ax.text(i % 2 + offset, v + ymax * 0.015, f"{v:,.0f}",
                    ha="center", va="bottom", fontsize=16, fontweight="bold", color="white")

    st.pyplot(fig, use_container_width=True)

with colR:
    st.metric("**Combined Download Min**", f"{total_in_min:,.0f} Mbps")
    st.metric("**Combined Download Max**", f"{total_in_max:,.0f} Mbps")
    st.metric("**Combined Upload Min**",   f"{total_out_min:,.0f} Mbps")
    st.metric("**Combined Upload Max**",   f"{total_out_max:,.0f} Mbps")

    st.divider()
    st.markdown("### Utilization (based on Max)")
    cap = TOTAL_CAPACITY if TOTAL_CAPACITY > 0 else 1
    pct_in  = (total_in_max  / cap) * 100
    pct_out = (total_out_max / cap) * 100

    st.caption(f"Download ({pct_in:.1f}%)")
    st.progress(min(pct_in / 100, 1.0))
    st.caption(f"Upload ({pct_out:.1f}%)")
    st.progress(min(pct_out / 100, 1.0))
    st.caption(f"Total Capacity: {TOTAL_CAPACITY:,.0f} Mbps")
