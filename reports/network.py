import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd

st.set_page_config(page_title="Network Report", layout="wide")


def handle_error(resp, label="Request"):
    st.error(f"{label} failed")
    if isinstance(resp, dict):
        st.write("Status:", resp.get("status"))
        if resp.get("url"):
            st.code(resp.get("url"))
        # ALWAYS show text so we can see the real exception
        if resp.get("text"):
            st.write(resp.get("text")[:2000])


def show_network_report(auvik_get):
    st.title("🌐 Network Report")

    st.subheader("1) Select Tenant (required for inventory calls)")

    tenants_resp = auvik_get("tenants")
    if isinstance(tenants_resp, dict) and tenants_resp.get("_error"):
        handle_error(tenants_resp, "Load Tenants")
        return

    tenants = tenants_resp.get("data", [])
    if not tenants:
        st.warning("No tenants returned for this API user.")
        st.json(tenants_resp)
        return

    tenant_options = []
    for t in tenants:
        tid = t.get("id")
        name = (t.get("attributes", {}) or {}).get("name", tid)
        tenant_options.append((name, tid))

    tenant_name = st.selectbox(
        "Tenant",
        options=[x[0] for x in tenant_options],
        index=0,
    )
    tenant_id = dict(tenant_options)[tenant_name]
    st.caption(f"Using tenantId: {tenant_id}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Devices")
        if st.button("Load Devices", key="net_load_devices"):
            # IMPORTANT: tenants param is required
            devices = auvik_get(
                "inventory/device/info",
                params={"tenants": tenant_id, "page[limit]": 200}
            )

            if isinstance(devices, dict) and devices.get("_error"):
                handle_error(devices, "Load Devices")
                return

            data = devices.get("data", [])
            if not data:
                st.warning("No devices returned.")
                st.json(devices)
                return

            rows = []
            for d in data:
                attr = d.get("attributes", {}) or {}
                rows.append({
                    "ID": d.get("id"),
                    "Name": attr.get("deviceName") or attr.get("name") or "N/A",
                    "Type": attr.get("deviceType", "N/A"),
                    "IP": attr.get("ipAddress", "N/A"),
                    "Status": attr.get("status", "N/A"),
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.success(f"Found {len(rows)} devices")

    with col2:
        st.subheader("Interfaces")
        device_id = st.text_input("Filter by Device ID (optional)", "").strip()

        if st.button("Load Interfaces", key="net_load_interfaces"):
            params = {"tenants": tenant_id, "page[limit]": 200}
            if device_id:
                params["filter[deviceId]"] = device_id

            interfaces = auvik_get("inventory/interface/info", params=params)

            if isinstance(interfaces, dict) and interfaces.get("_error"):
                handle_error(interfaces, "Load Interfaces")
                return

            data = interfaces.get("data", [])
            if not data:
                st.warning("No interfaces returned.")
                st.json(interfaces)
                return

            rows = []
            for i in data:
                attr = i.get("attributes", {}) or {}
                rows.append({
                    "Interface ID": i.get("id"),
                    "Name": attr.get("interfaceName") or attr.get("name") or "N/A",
                    "Device": attr.get("deviceName", "N/A"),
                    "Speed": attr.get("speed", "N/A"),
                    "Status": attr.get("status", "N/A"),
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.success(f"Found {len(rows)} interfaces")


# ────────────────────────────────────────────────
# Standalone mode (so reports/network.py can run independently)
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
    BASE_URL = "https://auvikapi.us6.my.auvik.com/v1"
    HEADERS = {
        # Auvik commonly uses JSON:API
        "Accept": "application/vnd.api+json"
    }

    API_USERNAME, API_KEY = _load_auvik_creds_from_secrets()

    with st.sidebar:
        st.header("🔧 Debug")
        st.write("Secrets keys:", list(st.secrets.keys()))
        st.write("Username loaded:", bool(API_USERNAME))
        st.write("API key loaded:", bool(API_KEY))

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


if __name__ == "__main__":
    main()
