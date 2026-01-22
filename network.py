import streamlit as st
import pandas as pd


def handle_error(resp, label="Request"):
    st.error(f"{label} failed")
    if isinstance(resp, dict):
        st.write("Status:", resp.get("status"))
        url = resp.get("url")
        if url:
            st.code(url)
        text = resp.get("text")
        if text:
            st.write(text[:1000])


def show_network_report(auvik_get):
    st.header("🌐 Network Report")

    col1, col2 = st.columns(2)

    # ─────────────────────────
    # Tenants
    # ─────────────────────────
    with col1:
        st.subheader("Tenants")
        if st.button("Load Tenants"):
            tenants = auvik_get("tenants")
            if isinstance(tenants, dict) and tenants.get("_error"):
                handle_error(tenants, "Load Tenants")
            else:
                data = tenants.get("data", [])
                st.success(f"Returned {len(data)} tenants")
                st.json(tenants)

    # ─────────────────────────
    # Devices
    # ─────────────────────────
    with col2:
        st.subheader("Devices")
        if st.button("Load Devices"):
            devices = auvik_get(
                "inventory/device/info",
                params={"page[limit]": 200}
            )

            if isinstance(devices, dict) and devices.get("_error"):
                handle_error(devices, "Load Devices")
                return

            data = devices.get("data", [])
            if not data:
                st.warning("No devices returned")
                st.json(devices)
                return

            rows = []
            for d in data:
                attr = d.get("attributes", {}) or {}
                rows.append({
                    "ID": d.get("id"),
                    "Name": attr.get("deviceName") or attr.get("name") or "N/A",
                    "Type": attr.get("deviceType", "N/A"),
                    "Model": attr.get("model", "N/A"),
                    "IP": attr.get("ipAddress", "N/A"),
                    "Status": attr.get("status", "N/A"),
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
            st.success(f"Found {len(df)} devices")

    st.divider()

    # ─────────────────────────
    # Interfaces
    # ─────────────────────────
    st.subheader("Interfaces")

    device_id = st.text_input(
        "Filter by Device ID (optional)",
        key="network_device_filter"
    ).strip()

    if st.button("Load Interfaces"):
        params = {"page[limit]": 200}
        if device_id:
            params["filter[deviceId]"] = device_id

        interfaces = auvik_get(
            "inventory/interface/info",
            params=params
        )

        if isinstance(interfaces, dict) and interfaces.get("_error"):
            handle_error(interfaces, "Load Interfaces")
            return

        data = interfaces.get("data", [])
        if not data:
            st.warning("No interfaces returned")
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
