import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd

st.set_page_config(page_title="Network Report", layout="wide")


# ────────────────────────────────────────────────
# Error display helpers
# ────────────────────────────────────────────────
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


# ────────────────────────────────────────────────
# Report function (importable by your main dashboard)
# ────────────────────────────────────────────────
def show_network_report(auvik_get):
    st.title("🌐 Network Report")

    # Load tenants so we can scope inventory calls
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

    col1, col2 = st.columns(2)

    # ────────────────
    # Devices
    # ────────────────
    with col1:
        st.subheader("Devices")
        page_size = st.number_input("Page size (page[first])", min_value=1, max_value=100, value=100, step=10)

        if st.button("Load Devices", key="btn_load_devices"):
            # Auvik uses page[first] (NOT page[limit]) :contentReference[oaicite:1]{index=1}
            devices = auvik_get(
                "inventory/device/info",
                params={
                    "tenants": tenant_id,
                    "page[first]": page_size,  # ✅ correct param
                },
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
                    "ID": d.get("id"),
                    "Name": attr.get("deviceName") or attr.get("name") or "N/A",
                    "Type": attr.get("deviceType", "N/A"),
                    "Model": attr.get("makeModel") or attr.get("model") or "N/A",
                    "IP": attr.get("ipAddress", "N/A"),
                    "Status": attr.get("onlineStatus") or attr.get("status") or "N/A",
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
            st.success(f"Found {len(df)} devices")

            # Helpful for paging
            links = (devices or {}).get("links", {})
            if links:
                st.caption("Pagination links returned by API:")
                st.json(links)

    # ────────────────
    # Interfaces
    # ────────────────
    with col2:
        st.subheader("Interfaces")
        device_id = st.text_input("Filter by Device ID (optional)", "", key="device_id_filter").strip()
        page_size_i = st.number_input("Page size (page[first])", min_value=1, max_value=100, value=100, step=10, key="iface_page_size")

        if st.button("Load Interfaces", key="btn_load_interfaces"):
            params = {
                "tenants": tenant_id,
                "page[first]": page_size_i,  # ✅ correct param (same paging model) :contentReference[oaicite:2]{index=2}
            }
            if device_id:
                params["filter[deviceId]"] = device_id

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
                    "Interface ID": i.get("id"),
                    "Name": attr.get("interfaceName") or attr.get("name") or "N/A",
                    "Device": attr.get("deviceName", "N/A"),
                    "Speed": attr.get("speed", "N/A"),
                    "Status": attr.get("status", "N/A"),
                    "MAC": attr.get("macAddress", "N/A"),
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
            st.success(f"Found {len(df)} interfaces")

            links = (interfaces or {}).get("links", {})
            if links:
                st.caption("Pagination links returned by API:")
                st.json(links)


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
    if API_KEY:
        st.sidebar.write("API key length:", len(API_KEY))

    if not API_USERNAME or not API_KEY:
        st.error("Missing Auvik credentials in Streamlit Secrets.")
        st.code(
            'auvik_api_username = "api-user@yourdomain.com"\n'
            'auvik_api_key = "YOUR_AUVIK_API_KEY_HERE"'
        )
        st.stop()

    BASE_URL = "https://auvikapi.us6.my.auvik.com/v1"
    HEADERS = {"Accept": "application/vnd.api+json"}  # Auvik uses JSON:API
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
