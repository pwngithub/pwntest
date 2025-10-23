    # --- Parse Re-Work File ---
    if df_rework is not None and not df_rework.empty:
        try:
            parsed_rows = []

            for _, row in df_rework.iterrows():
                values = row.tolist()

                # Detect Install rows
                if str(row[1]).startswith("Install"):
                    base_subset = [values[i] for i in [0, 2, 3, 4] if i < len(values)]
                else:
                    base_subset = [values[i] for i in [0, 1, 2, 3] if i < len(values)]

                while len(base_subset) < 4:
                    base_subset.append(None)
                parsed_rows.append(base_subset)

            # Convert to DataFrame
            df_combined = pd.DataFrame(parsed_rows, columns=["Technician", "Total_Jobs", "Rework", "Rework_Percentage"])

            # Clean & Convert
            df_combined["Technician"] = df_combined["Technician"].astype(str).str.replace('"', '').str.strip()
            df_combined["Total_Jobs"] = pd.to_numeric(df_combined["Total_Jobs"], errors="coerce")
            df_combined["Rework"] = pd.to_numeric(df_combined["Rework"], errors="coerce")
            df_combined["Rework_Percentage"] = (
                df_combined["Rework_Percentage"].astype(str)
                .str.replace("%", "")
                .str.replace('"', "")
                .str.strip()
            ).astype(float)

            # =============================
            # 📊 Main Rework KPIs
            # =============================
            st.markdown("### 📌 Re-Work KPIs")
            total_jobs_rw = df_combined["Total_Jobs"].sum()
            total_repeats = df_combined["Rework"].sum()
            avg_repeat_pct = df_combined["Rework_Percentage"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("🔧 Total Jobs", int(total_jobs_rw))
            c2.metric("🔁 Total Reworks", int(total_repeats))
            c3.metric("📈 Avg Rework %", f"{avg_repeat_pct:.1f}%")

            # =============================
            # 🧾 Re-Work Summary Table
            # =============================
            st.markdown("### 🧾 Re-Work Summary Table")
            st.dataframe(df_combined, use_container_width=True)

            # =============================
            # 📊 Rework % Chart
            # =============================
            st.markdown("### 📊 Rework % by Technician")
            fig_re = px.bar(
                df_combined.sort_values("Rework_Percentage", ascending=False),
                x="Technician",
                y="Rework_Percentage",
                title="Technician Rework % (Sorted Highest to Lowest)",
                text="Rework_Percentage",
                color="Rework_Percentage",
                template="plotly_dark",
                color_continuous_scale="Viridis"
            )
            fig_re.update_traces(textposition="outside")
            st.plotly_chart(fig_re, use_container_width=True)

            # --- Download option ---
            csv_rework = df_combined.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Re-Work Summary CSV",
                data=csv_rework,
                file_name="rework_summary.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"Error parsing re-work file: {e}")
