
---

# 2️⃣ `reports/network.py` — **FULL FILE (NO TRIPLE QUOTES)**

```python
import streamlit as st
import pandas as pd


def handle_error(resp, label):
    st.error(f"{label} failed")
    if isinstance(resp, dict):
        st.write("Status:", resp.get("status"))
        if resp.get("url"):
            st.code(resp.get("url"))
        if resp.get("text"):
            st.write(resp.get("text")[:1000])


def show_network_report(auvik_get):
    st.header("🌐 Network Report")

    col1, col2 = st.columns(2)

    # ────────────────
    # Tenants
    # ────────────────
    with col1:
        st.subheader("Tenants")
        if st.button("Load Tenants"):
            tenants = auvik_get("tenants")
            if tenants.get("_error"):
                handle_error(tenants, "Load Tenants")
            else:
                data = tenants.get("data", [])
                st.success(f"Returned {len(data)} tenants")
                st.json(tenants)

    # ────────────────
    # Devices
    # ────────────────
    with col2:
        st.subheader("Devices")
        if st.button("Load Devices"):
            devices = auvik_get("inventory/device/info", {"page[limit]": 200})

            if devices.get("_error"):
                handle_error(devices, "Load Devices")
                return

            data = devices.get("data", [])
            if not data:
                st.warning("No devices returned")
                return

            rows = []
            for d in data:
                attr = d.get("attributes", {})
                rows.append({
                    "ID": d.get("id"),
                    "Name": attr.get("deviceName", "N/A"),
                    "Type": attr.get("deviceType", "N/A"),
                    "IP": attr.get("ipAddress", "N/A"),
                    "Status": attr.get("status", "N/A"),
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.divider()

    # ────────────────
    # Interfaces
    # ────────────────
    st.subheader("Interfaces")

    device_id = st.text_input("Filter by Device ID (optional)").strip()

    if st.button("Load Interfaces"):
        params = {"page[limit]": 200}
        if device_id:
            params["filter[deviceId]"] = device_id

        interfaces = auvik_get("inventory/interface/info", params)

        if interfaces.get("_error"):
            handle_error(interfaces, "Load Interfaces")
            return

        data = interfaces.get("data", [])
        if not data:
            st.warning("No interfaces returned")
            return

        rows = []
        for i in data:
            attr = i.get("attributes", {})
            rows.append({
                "Interface ID": i.get("id"),
                "Name": attr.get("interfaceName", "N/A"),
                "Device": attr.get("deviceName", "N/A"),
                "Speed": attr.get("speed", "N/A"),
                "Status": attr.get("status", "N/A"),
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True)
