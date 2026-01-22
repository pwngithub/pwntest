if st.button("Load Devices"):
    # Common Auvik inventory endpoint
    devices = auvik_get("inventory/device/info", params={"page[limit]": 200})
    if devices.get("_error"):
        st.error(f"Error ({devices.get('status')}): {devices.get('text')[:500]}")
        st.code(devices.get("url"))
    elif "data" in devices:
        rows = []
        for d in devices["data"]:
            attr = d.get("attributes", {})
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
    else:
        st.warning("Unexpected response format")
        st.json(devices)

st.markdown("---")
st.header("3. Interfaces")
device_id_filter = st.text_input("Filter by Device ID (optional)", "")

if st.button("Load Interfaces"):
    params = {"page[limit]": 200}
    if device_id_filter.strip():
        # Some endpoints support filter; if this doesn't work, we can adjust once we see your response.
        params["filter[deviceId]"] = device_id_filter.strip()

    interfaces = auvik_get("inventory/interface/info", params=params)
    if interfaces.get("_error"):
        st.error(f"Error ({interfaces.get('status')}): {interfaces.get('text')[:500]}")
        st.code(interfaces.get("url"))
    elif "data" in interfaces:
        rows = []
        for i in interfaces["data"]:
            attr = i.get("attributes", {})
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
    else:
        st.warning("Unexpected response format")
        st.json(interfaces)

st.markdown("---")
st.header("4. Traffic Stats (Interface)")

interface_id = st.text_input("Enter Interface ID for 24h stats", "")
if interface_id and st.button("Get 24h Bandwidth Stats"):
    end = datetime.utcnow()
    start = end - timedelta(hours=24)

    params = {
        "from": start.isoformat() + "Z",
        "to": end.isoformat() + "Z",
        "interval": "5m"
    }

    stats = auvik_get(f"interface/statistics/{interface_id.strip()}", params=params)
    if stats.get("_error"):
        st.error(f"Error ({stats.get('status')}): {stats.get('text')[:500]}")
        st.code(stats.get("url"))
    elif "data" in stats:
        st.success(f"Retrieved {len(stats['data'])} data points")
        st.json(stats["data"][:5])

        # Example: show max octets (counters)
        max_in = max((p.get("inOctets", 0) or 0) for p in stats["data"])
        max_out = max((p.get("outOctets", 0) or 0) for p in stats["data"])
        st.metric("Max In Octets (counter)", f"{int(max_in):,}")
        st.metric("Max Out Octets (counter)", f"{int(max_out):,}")
        st.info("To compute Mbps: delta_octets * 8 / delta_seconds / 1e6 between points.")
    else:
        st.warning("Unexpected response format / no data")
        st.json(stats)
