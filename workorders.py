    # =================================================
    # ORIGINAL: OVERALL AVG DURATION BY WORK TYPE
    # =================================================
    st.markdown("### 📊 Overall Average Duration by Work Type")

    df_avg = df_filtered.dropna(subset=['Duration'])

    if not df_avg.empty:
        df_avg["Duration_Mins"] = pd.to_numeric(
            df_avg["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0],
            errors="coerce"
        )

        tech_group = (
            df_avg.groupby(['Work Type', 'Technician'])['Duration_Mins']
            .mean()
            .reset_index()
        )

        final_avg = tech_group.groupby('Work Type')['Duration_Mins'].mean().reset_index()

        fig = px.bar(
            final_avg,
            x="Work Type",
            y="Duration_Mins",
            title="Overall Average Job Duration by Work Type",
            template="plotly_dark",
            color="Duration_Mins"
        )
        fig.update_traces(marker_color="#8BC53F")
        st.plotly_chart(fig, use_container_width=True)

    # =================================================
    # ORIGINAL: TECHNICIAN JOB + DURATION CHARTS
    # =================================================
    st.markdown("### 📊 Work Orders Charts by Technician")

    if not df_avg.empty:
        grouped = (
            df_avg.groupby(["Technician", "Work Type"])
            .agg(
                Total_Jobs=("WO#", "nunique"),
                Avg_Duration=("Duration_Mins", "mean")
            )
            .reset_index()
        )

        fig1 = px.bar(
            grouped,
            x="Work Type",
            y="Total_Jobs",
            color="Technician",
            title="Jobs by Work Type & Technician",
            template="plotly_dark"
        )
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.bar(
            grouped,
            x="Work Type",
            y="Avg_Duration",
            color="Technician",
            title="Avg Duration by Work Type & Technician (mins)",
            template="plotly_dark"
        )
        st.plotly_chart(fig2, use_container_width=True)

    # =================================================
    # NEW — TRAVEL TIME CHART
    # =================================================
    if not df_travel.empty:
        st.markdown("### 📊 Average Travel Time per Technician")

        df_tt = df_travel.groupby("Technician")["Travel_Minutes"].mean().reset_index()

        fig_tt = px.bar(
            df_tt,
            x="Technician",
            y="Travel_Minutes",
            title="Avg Travel Time per Technician (mins)",
            template="plotly_dark",
            color="Travel_Minutes"
        )
        st.plotly_chart(fig_tt, use_container_width=True)

    # =================================================
    # NEW — JOBS PER MILE CHART
    # =================================================
    st.markdown("### 📊 Jobs Per Mile by Technician")

    fig_jpm = px.bar(
        df_jobs_per_mile,
        x="Technician",
        y="Jobs_Per_Mile",
        title="Jobs Per Mile by Technician",
        template="plotly_dark",
        color="Jobs_Per_Mile"
    )
    st.plotly_chart(fig_jpm, use_container_width=True)

    st.markdown("---")

    # =================================================
    # INSTALLATION REWORK MODULE (UNCHANGED)
    # =================================================

    st.markdown("<h2 style='color:#8BC53F;'>🔁 Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_mode = st.sidebar.radio(
        "Installation Rework File",
        ["Upload New File", "Load Existing File"],
        key="re_mode_file"
    )

    df_rework = None

    if re_mode == "Upload New File":
        re_up = st.sidebar.file_uploader(
            "Upload Installation Assessment File",
            type=["csv", "txt"],
            key="re_upload_file"
        )
        re_name = st.sidebar.text_input(
            "Enter name (no extension)",
            key="re_filename_input"
        )

        if re_up and re_name:
            fname = re_name + ".csv"
            fbytes = re_up.getvalue()

            local = f"saved_uploads/{fname}"
            with open(local, "wb") as f:
                f.write(fbytes)

            upload_workorders_file_to_github(fname, fbytes)

            df_rework = pd.read_csv(local, header=None)

    else:
        files = list_github_workorders()
        if files:
            rsel = st.sidebar.selectbox(
                "Select Installation Rework File",
                files,
                key="re_select_file"
            )
            local = download_github_workorder_file(rsel)
            df_rework = pd.read_csv(local, header=None)

    if df_rework is not None and not df_rework.empty:
        try:
            parsed = []
            for _, row in df_rework.iterrows():
                vals = row.tolist()
                if len(vals) > 1 and str(vals[1]).startswith("Install"):
                    sub = [vals[i] for i in [0, 2, 3, 4] if i < len(vals)]
                else:
                    sub = [vals[i] for i in [0, 1, 2, 3] if i < len(vals)]

                while len(sub) < 4:
                    sub.append(None)

                parsed.append(sub)

            df_rw = pd.DataFrame(
                parsed,
                columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"]
            )

            df_rw["Technician"] = df_rw["Technician"].astype(str).str.replace('"', '').str.strip()
            df_rw["Total_Installations"] = pd.to_numeric(df_rw["Total_Installations"], errors="coerce")
            df_rw["Rework"] = pd.to_numeric(df_rw["Rework"], errors="coerce")
            df_rw["Rework_Percentage"] = (
                df_rw["Rework_Percentage"].astype(str)
                .str.replace("%", "")
                .str.replace('"', "")
                .str.strip()
            )
            df_rw["Rework_Percentage"] = pd.to_numeric(df_rw["Rework_Percentage"], errors="coerce")

            df_rw.dropna(subset=["Technician", "Total_Installations"], inplace=True)
            df_rw = df_rw.sort_values("Total_Installations", ascending=False)

            st.markdown("### 📌 Installation Rework KPIs")

            r1, r2, r3 = st.columns(3)
            r1.metric("🏗 Total Installs", int(df_rw["Total_Installations"].sum()))
            r2.metric("🔁 Total Reworks", int(df_rw["Rework"].sum()))
            r3.metric("📈 Avg Rework %", f"{df_rw['Rework_Percentage'].mean():.1f}%")

            def color_rw(v):
                if pd.isna(v): return ""
                if v < 5: return "background-color:#3CB371;color:white;"
                if v < 10: return "background-color:#FFD700;color:black;"
                return "background-color:#FF6347;color:white;"

            table = (
                df_rw.style
                .map(color_rw, subset=["Rework_Percentage"])
                .format({
                    "Total_Installations": "{:.0f}",
                    "Rework": "{:.0f}",
                    "Rework_Percentage": "{:.1f}%"
                })
            )
            st.dataframe(table)

            st.markdown("### 📊 Installs vs Rework %")

            fig_rw = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rw.add_trace(go.Bar(
                x=df_rw["Technician"],
                y=df_rw["Total_Installations"],
                name="Total Installs",
                marker_color="#00BFFF"
            ), secondary_y=False)

            fig_rw.add_trace(go.Scatter(
                x=df_rw["Technician"],
                y=df_rw["Rework_Percentage"],
                name="Rework %",
                mode="lines+markers",
                line=dict(color="#FF6347", width=3)
            ), secondary_y=True)

            fig_rw.update_layout(
                title="Technician Installations vs Rework %",
                template="plotly_dark"
            )
            st.plotly_chart(fig_rw, use_container_width=True)

        except Exception as e:
            st.error(f"Error parsing rework file: {e}")


# RUN APP
if __name__ == "__main__":
    run_workorders_dashboard()
