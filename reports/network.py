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

    # 1) Tenants
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
        "Select Tenant",
        options=[x[0] for x in tenant_options],
        index=0,
        key="tenant_select",
    )
    tenant_id = dict(tenant_options)[tenant_name]
    st.caption(f"Using tenantId: {tenant_id}")

    st.divider()

    # 2) Devices (load + select by name)
    st.subheader("Devices")

    page_size = st.number_input(
        "Device page size (page[first])",
        min_value=1, max_value=100, value=100, step=10,
        key="dev_page_size"
    )

    load_devices = st.button("Load Devices", key="btn_load_devices")

    # Load devices when button pressed OR reuse cached list for this tenant
    if load_devices or ("devices_df" in st.session_state and st.session_state.get("devices_tenant") == tenant_id):
        if load_devices or st.session_state.get("devices_tenant") != tenant_id:
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
                    "device_name": attr.get("deviceName") or attr.get("name") or "N/A",
                    "device_type": attr.get("deviceType", "N/A"),
                    "ip": attr.get("ipAddress", "N/A"),
                    "status": attr.get("onlineStatus") or attr.get("status") or "N/A",
                })

            devices_df = pd.DataFrame(rows)

            st.session_state["devices_df"] = devices_df
            st.session_state["devices_tenant"] = tenant_id

            # Reset interface cache when tenant/device list refreshes
            st.session_state.pop("interfaces_df", None)
            st.session_state.pop("interfaces_device_id", None)
        else:
            devices_df = st.session_state["devices_df"]

        st.success(f"Loaded {len(devices_df)} devices")
        st.dataframe(devices_df[["device_name", "device_type", "ip", "status"]], use_container_width=True)

        # Device selector by name
        device_names = devices_df["device_name"].fillna("N/A").tolist()
        selected_device_name = st.selectbox("Select Device (by name)", options=device_names, key="selected_device_name")

        matches = devices_df[devices_df["device_name"] == selected_device_name]
        if matches.empty:
            st.warning("Could not resolve selected device to an ID.")
            return

        # If duplicate names exist, let user pick the correct ID
        if len(matches) > 1:
            st.warning("Multiple devices share this name. Select the correct device ID:")
            selected_device_id = st.selectbox(
                "Device ID",
                options=matches["device_id"].tolist(),
                key="selected_device_id_dupe"
            )
        else:
            selected_device_id = matches.iloc[0]["device_id"]

        st.caption(f"Selected deviceId: {selected_device_id}")

        st.divider()

        # 3) Interfaces (ONLY for selected device)
        st.subheader("Interfaces (only for selected device)")

        iface_page_size = st.number_input(
            "Interface page size (page[first])",
            min_value=1, max_value=100, value=100, step=10,
            key="iface_page_size"
        )

        device_changed = st.session_state.get("interfaces_device_id") != selected_device_id
        load_ifaces = st.button("Load Interfaces for Selected Device", key="btn_load_ifaces")

        if load_ifaces or device_changed or "interfaces_df" not in st.session_state:
            # ✅ IMPORTANT: Auvik uses filter[parentDevice] for interface->device filtering
            interfaces = auvik_get(
                "inventory/interface/info",
                params={
                    "tenants": tenant_id,
                    "filter[parentDevice]": selected_device_id,  # ✅ fixed
                    "page[first]": iface_page_size,
                }
            )

            if isinstance(interfaces, dict) and interfaces.get("_error"):
                handle_error(interfaces, "Load Interfaces")
                return

            data_i = (interfaces or {}).get("data", [])
            if not data_i:
                st.warning("No interfaces returned for that device.")
                st.json(interfaces)
                return

            rows_i = []
            for i in data_i:
                attr = i.get("attributes", {}) or {}
                rows_i.append({
                    "interface_id": i.get("id"),
                    "interface_name": attr.get("interfaceName") or attr.get("name") or "N/A",
                    "interface_type": attr.get("interfaceType", "N/A"),
                    "admin_status": attr.get("adminStatus", "N/A"),
                    "oper_status": attr.get("operationalStatus", attr.get("status", "N/A")),
                    "speed": attr.get("speed", "N/A"),
                    "mac": attr.get("macAddress", "N/A"),
                    "device_name": attr.get("parentDeviceName", selected_device_name),
                })

            interfaces_df = pd.DataFrame(rows_i)
            st.session_state["interfaces_df"] = interfaces_df
            st.session_state["interfaces_device_id"] = selected_device_id
        else:
            interfaces_df = st.session_state["interfaces_df"]

        st.success(f"Loaded {len(interfaces_df)} interfaces for {selected_device_name}")
        st.dataframe(interfaces_df, use_container_width=True)

    else:
        st.info("Click **Load Devices** to begin.")


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
