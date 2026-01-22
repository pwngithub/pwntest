import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd

st.set_page_config(page_title="Network Report", layout="wide")


# ────────────────────────────────────────────────
# Shared UI helpers
# ────────────────────────────────────────────────
def handle_error(resp, label="Request"):
    st.error(f"{label} failed")
    if isinstance(resp, dict):
        st.write("Status:", resp.get("status"))
        if resp.get("url"):
            st.code(resp.get("url"))
        if resp.get("text"):
            st.write(resp.get("text")[:1200])


# ────────────────────────────────────────────────
# Report entrypoint used by your main dashboard
# ────────────────────────────────────────────────
def show_network_report(auvik_get):
    st.title("🌐 Network Report")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Tenants")
        if st.button("Load Tenants", key="net_load_tenants"):
            tenants = auvik_get("tenants")
            if isinstance(tenants, dict) and tenants.get("_error"):
                handle_error(tenants, "Load Tenants")
            else:
                st.success(f"Returned {len(tenants.get('data', []))} tenants")
                st.json(tenants)

    with col2:
        st.subheader("Devices")
        if st.button("Load Devices", key="net_load_devices"):
            devices = auvik_get("inventory/device/info", {"page[limit]": 200})
            if isinstance(devices, dict) and devices.get("_error"):
                handle_error(devices, "Load Devices")
                return

            data = devices.get("data", [])
            if not data:
                st.warning("No devices returned")
                return

            rows = []
            for d in data:
                attr = d.get("attributes", {}) or {}
                rows.append({
                    "ID": d.get("id"),
                    "Name": attr.get("deviceName", "N/A"),
                    "Type": attr.get("deviceType", "N/A"),
                    "IP": attr.get("ipAddress", "N/A"),
                    "Status": attr.get("status", "N/A"),
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.divider()

    st.subheader("Interfaces")
    device_id = st.text_input("Filter by Device ID (optional)", key="net_device_filter").strip()

    if st.button("Load Interfaces", key="net_load_interfaces"):
        params = {"page[limit]": 200}
        if device_id:
            params["filter[deviceId]"] = device_id

        interfaces = auvik_get("inventory/interface/info", params)
        if isinstance(interfaces, dict) and interfaces.get("_error"):
            handle_error(interfaces, "Load Interfaces")
            return

        data = interfaces.get("data", [])
        if not data:
            st.warning("No interfaces returned")
            return

        rows = []
        for i in data:
            attr = i.get("attributes", {}) or {}
            rows.append({
                "Interface ID": i.get("id"),
                "Name": attr.get("interfaceName", "N/A"),
                "Device": attr.get("deviceName", "N/A"),
                "Speed": attr.get("speed", "N/A"),
                "Status": attr.get("status", "N/A"),
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ────────────────────────────────────────────────
# Standalone mode wiring (secrets + auvik_get)
# ────────────────────────────────────────────────
def _load_auvik_creds_from_secrets():
    # Supports both:
    # A) auvik_api_username / auvik_api_key
    # B) [auvik] api_username / api_key
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
    # If you want region selectable later, we can add a dropdown.
    BASE_URL = "https://auvikapi.us6.my.auvik.com/v1"
    HEADERS = {"Accept": "application/json"}

    API_USERNAME, API_KEY = _load_auvik_creds_from_secrets()

    with st.sidebar:
        st.header("🔧 Standalone Debug")
        st.write("Secrets keys:", list(st.secrets.keys()))
        st.write("Username loaded:", bool(API_USERNAME))
        st.write("API key loaded:", bool(API_KEY))
        if API_KEY:
            st.write("API key length:", len(API_KEY))

    if not API_USERNAME or not API_KEY:
        st.error("Missing Auvik credentials in Streamlit Secrets.")
        st.code(
            'auvik_api_username = "api-user@yourdomain.com"\n'
            'auvik_api_key = "YOUR_AUVIK_API_KEY_HERE"'
        )
        st.stop()

    auth = HTTPBasicAuth(API_USERNAME, API_KEY)

    def auvik_get(endpoint, params=None):
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        try:
            r = requests.get(url, headers=HEADERS, auth=auth, params=params, timeout=30)
            if r.status_code in (401, 403):
                return {"_error": True, "status": r.status_code, "text": r.text, "url": url}
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"_error": True, "status": None, "text": str(e), "url": url}

    show_network_report(auvik_get)


# When Streamlit runs a file as the entry script, __name__ is "__main__"
if __name__ == "__main__":
    main()
