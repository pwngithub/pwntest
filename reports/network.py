import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Network Report", layout="wide")


def handle_error(resp, label="Request"):
    st.error(f"{label} failed")

    if resp is None:
        st.write("Response was None (auvik_get returned None).")
        return

    if not isinstance(resp, dict):
        st.write("Unexpected error type:", type(resp))
        st.write(resp)
        return

    st.write("Status:", resp.get("status"))
    if resp.get("url"):
        st.code(resp.get("url"))

    txt = resp.get("text")
    if txt:
        st.write(txt[:2500])
    else:
        st.write("No error text returned.")
        st.json(resp)


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _compute_mbps_from_counters(df: pd.DataFrame, ts_col: str, in_col: str, out_col: str) -> pd.DataFrame:
    """
    Given cumulative octet counters + timestamps, compute Mbps time series.
    """
    if df.empty:
        return df

    df = df.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    df = df.dropna(subset=[ts_col]).sort_values(ts_col)

    # Ensure numeric
    df[in_col] = pd.to_numeric(df[in_col], errors="coerce")
    df[out_col] = pd.to_numeric(df[out_col], errors="coerce")

    # Deltas
    df["dt_seconds"] = df[ts_col].diff().dt.total_seconds()
    df["din"] = df[in_col].diff()
    df["dout"] = df[out_col].diff()

    # Handle counter resets / negatives
    df.loc[df["din"] < 0, "din"] = None
    df.loc[df["dout"] < 0, "dout"] = None
    df.loc[df["dt_seconds"] <= 0, "dt_seconds"] = None

    df["in_mbps"] = (df["din"] * 8) / df["dt_seconds"] / 1_000_000
    df["out_mbps"] = (df["dout"] * 8) / df["dt_seconds"] / 1_000_000

    return df


def show_network_report(auvik_get):
    st.title("🌐 Network Report")

    # ────────────────────────────────────────────────
    # Tenants
    # ────────────────────────────────────────────────
    tenants_resp = auvik_get("tenants")
    if isinstance(tenants_resp, dict) and tenants_resp.get("_error"):
        handle_error(tenants_resp, "Load Tenants")
        return

    tenants = (tenants_resp or {}).get("data", [])
    if not tenants:
        st.warning("No tenants returned. Check API user permissions.")
        st.json(tenants_resp)
        return

    tenant_options = []
    for t in tenants:
        tid = t.get("id")
        name = (t.get("attributes", {}) or {}).get("name", tid)
        tenant_options.append((name, tid))

    st.subheader("Tenant")
    tenant_name = st.selectbox(
        "Select Tenant (required for device/interface calls)",
        options=[x[0] for x in tenant_options],
        index=0,
        key="tenant_select",
    )
    tenant_id = dict(tenant_options)[tenant_name]
    st.caption(f"Using tenantId: {tenant_id}")

    st.divider()

    # ────────────────────────────────────────────────
    # Devices + Interfaces
    # ────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    devices_df = None
    interfaces_df = None

    with col1:
        st.subheader("Devices")
        page_size = st.number_input("Page size (page[first])", min_value=1, max_value=100, value=100, step=10, key="dev_page")
        if st.button("Load Devices", key="btn_load_devices"):
            devices = auvik_get(
                "inventory/device/info",
                params={"tenants": tenant_id, "page[first]": page_size},
            )

            if isinstance(devices, dict) and devices.get("_error"):
                handle_error(devices, "Load Devices")
                return

            data = (devices or {}).get("data", [])
            if not data:
                st.warning("No devices returned.")
                st.json(devices)
                return

            rows = []
            for d in data:
                attr = d.get("attributes", {}) or {}
                rows.append({
                    "device_id": d.get("id"),
                    "name": attr.get("deviceName") or attr.get("name") or "N/A",
                    "type": attr.get("deviceType", "N/A"),
                    "ip": attr.get("ipAddress", "N/A"),
                    "status": attr.get("onlineStatus") or attr.get("status") or "N/A",
                })

            devices_df = pd.DataFrame(rows)
            st.session_state["devices_df"] = devices_df
            st.dataframe(devices_df, use_container_width=True)
            st.success(f"Found {len(devices_df)} devices")

    with col2:
        st.subheader("Interfaces")
        device_id_filter = st.text_input("Filter by Device ID (optional)", "", key="iface_dev_filter").strip()
        page_size_i = st.number_input("Page size (page[first])", min_value=1, max_value=100, value=100, step=10, key="iface_page")

        if st.button("Load Interfaces", key="btn_load_interfaces"):
            params = {"tenants": tenant_id, "page[first]": page_size_i}
            if device_id_filter:
                params["filter[deviceId]"] = device_id_filter

            interfaces = auvik_get("inventory/interface/info", params=params)

            if isinstance(interfaces, dict) and interfaces.get("_error"):
                handle_error(interfaces, "Load Interfaces")
                return

            data = (interfaces or {}).get("data", [])
            if not data:
                st.warning("No interfaces returned.")
                st.json(interfaces)
                return

            rows = []
            for i in data:
                attr = i.get("attributes", {}) or {}
                rows.append({
                    "interface_id": i.get("id"),
                    "name": attr.get("interfaceName") or attr.get("name") or "N/A",
                    "device_name": attr.get("deviceName", "N/A"),
                    "device_id": attr.get("deviceId", "N/A"),
                    "speed": attr.get("speed", "N/A"),
                    "status": attr.get("status", "N/A"),
                })

            interfaces_df = pd.DataFrame(rows)
            st.session_state["interfaces_df"] = interfaces_df
            st.dataframe(interfaces_df, use_container_width=True)
            st.success(f"Found {len(interfaces_df)} interfaces")

    st.divider()

    # ────────────────────────────────────────────────
    # Bandwidth (Mbps) from interface statistics
    # ────────────────────────────────────────────────
    st.subheader("📈 Bandwidth (Mbps) – Interface Statistics")

    devices_df = st.session_state.get("devices_df")
    interfaces_df = st.session_state.get("interfaces_df")

    if devices_df is None or interfaces_df is None or devices_df.empty or interfaces_df.empty:
        st.info("Load Devices and Interfaces above first, then come back here.")
        return

    # Device picker
    device_map = dict(zip(devices_df["name"], devices_df["device_id"]))
    selected_device_name = st.selectbox("Device", options=list(device_map.keys()), key="bw_device")
    selected_device_id = device_map[selected_device_name]

    # Filter interfaces by device (if device_id exists in interface data)
    iface_filtered = interfaces_df.copy()
    if "device_id" in iface_filtered.columns:
        iface_filtered = iface_filtered[iface_filtered["device_id"].astype(str) == str(selected_device_id)]

    if iface_filtered.empty:
        st.warning("No interfaces matched that device from the loaded interface list. Try reloading interfaces with device filter.")
        return

    iface_map = dict(zip(iface_filtered["name"], iface_filtered["interface_id"]))
    selected_iface_name = st.selectbox("Interface", options=list(iface_map.keys()), key="bw_iface")
    selected_iface_id = iface_map[selected_iface_name]

    # Time range
    hours = st.slider("Lookback window (hours)", min_value=1, max_value=72, value=24, step=1)
    interval = st.selectbox("Interval", options=["5m", "15m", "30m", "1h"], index=0)

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    if st.button("Get Mbps Stats", key="bw_go"):
        params = {
            "tenants": tenant_id,
            "from": _iso_z(start),
            "to": _iso_z(end),
            "interval": interval,
        }

        # Your API already worked with interface/statistics earlier; keeping this path.
        stats = auvik_get(f"interface/statistics/{selected_iface_id}", params=params)

        if isinstance(stats, dict) and stats.get("_error"):
            handle_error(stats, "Interface Statistics")
            return

        points = (stats or {}).get("data", [])
        if not points:
            st.warning("No statistics returned for that interface/time range.")
            st.json(stats)
            return

        # Try common field names
        # Many APIs use timestamp + inOctets/outOctets.
        df = pd.DataFrame(points)
        ts_col = "timestamp" if "timestamp" in df.columns else ("time" if "time" in df.columns else None)

        if ts_col is None:
            st.warning("Could not find timestamp column in returned data. Showing raw sample:")
            st.json(points[:5])
            return

        # Counters might be named inOctets/outOctets (common in your earlier code)
        in_col = "inOctets" if "inOctets" in df.columns else None
        out_col = "outOctets" if "outOctets" in df.columns else None

        if in_col is None or out_col is None:
            st.warning("Could not find inOctets/outOctets in returned data. Showing columns:")
            st.write(list(df.columns))
            st.json(points[:5])
            return

        df2 = _compute_mbps_from_counters(df, ts_col=ts_col, in_col=in_col, out_col=out_col)
        df2 = df2.dropna(subset=["in_mbps", "out_mbps"])

        if df2.empty:
            st.warning("Not enough valid datapoints to compute Mbps (possible counter resets or missing values).")
            st.json(points[:10])
            return

        st.metric("Peak In (Mbps)", f"{df2['in_mbps'].max():.2f}")
        st.metric("Peak Out (Mbps)", f"{df2['out_mbps'].max():.2f}")

        st.dataframe(df2[[ts_col, "in_mbps", "out_mbps"]].tail(50), use_container_width=True)

        # Plot (no fixed colors per your environment rules)
        fig = plt.figure()
        plt.plot(df2[ts_col], df2["in_mbps"], label="In Mbps")
        plt.plot(df2[ts_col], df2["out_mbps"], label="Out Mbps")
        plt.legend()
        plt.xlabel("Time (UTC)")
        plt.ylabel("Mbps")
        plt.title(f"Interface Mbps: {selected_device_name} / {selected_iface_name}")
        st.pyplot(fig)


# ────────────────────────────────────────────────
# Standalone mode (so this file can run independently)
# ────────────────────────────────────────────────
def _load_auvik_creds_from_secrets():
    username = ""
    api_key = ""

    if "auvik_api_username" in st.secrets:
        username = str(st.secrets.get("auvik_api_username", "")).strip()
    if "auvik_api_key" in st.secrets:
        api_key = str(st.secrets.get("auvik_api_key", "")).strip()

    if (not username or not api_key) and "auvik" in st.secrets:
        block = st.secrets.get("auvik", {})
        if isinstance(block, dict):
            username = username or str(block.get("api_username", "")).strip()
            api_key = api_key or str(block.get("api_key", "")).strip()

    return username, api_key


def main():
    st.sidebar.header("🔧 Standalone Debug")

    API_USERNAME, API_KEY = _load_auvik_creds_from_secrets()

    st.sidebar.write("Secrets keys:", list(st.secrets.keys()))
    st.sidebar.write("Username loaded:", bool(API_USERNAME))
    st.sidebar.write("API key loaded:", bool(API_KEY))

    if not API_USERNAME or not API_KEY:
        st.error("Missing Auvik credentials in Streamlit Secrets.")
        st.code(
            'auvik_api_username = "api-user@yourdomain.com"\n'
            'auvik_api_key = "YOUR_AUVIK_API_KEY_HERE"'
        )
        st.stop()

    BASE_URL = "https://auvikapi.us6.my.auvik.com/v1"
    HEADERS = {"Accept": "application/vnd.api+json"}
    auth = HTTPBasicAuth(API_USERNAME, API_KEY)

    def auvik_get(endpoint, params=None):
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        try:
            r = requests.get(
                url,
                headers=HEADERS,
                auth=auth,
                params=params,
                timeout=60,
                allow_redirects=True,
            )
            if r.status_code >= 400:
                return {"_error": True, "status": r.status_code, "text": r.text, "url": url}
            return r.json()
        except Exception as e:
            return {"_error": True, "status": None, "text": repr(e), "url": url}

    show_network_report(auvik_get)


if __name__ == "__main__":
    main()
