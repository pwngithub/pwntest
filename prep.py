
def run_preps_dashboard(df=None):
    import streamlit as st
    import pandas as pd
    import plotly.express as px
    from jotform_client import fetch_preps_data

    st.markdown("<h1 style='color:#405C88;'>🧰 Preps (Date · Tech · Drop Size · Count)</h1>", unsafe_allow_html=True)

    # Pull fresh from API if not provided
    if df is None or df.empty or not set(["date","tech","drop_size","count"]).issubset(set(df.columns)):
        df = fetch_preps_data(form_id="210823797836164")

    if df is None or df.empty:
        st.warning("No Preps data available.")
        return

    # Sidebar filters
    st.sidebar.header("Filters")
    # Date filter
    if "date" in df.columns and not df["date"].isna().all():
        min_d, max_d = pd.to_datetime(df["date"], errors="coerce").min(), pd.to_datetime(df["date"], errors="coerce").max()
        date_sel = st.sidebar.date_input("Date range", [min_d.date() if pd.notna(min_d) else None, max_d.date() if pd.notna(max_d) else None])
        if date_sel and len(date_sel) == 2 and all(date_sel):
            d0, d1 = pd.to_datetime(date_sel[0]), pd.to_datetime(date_sel[1])
            df = df[(pd.to_datetime(df["date"], errors="coerce") >= d0) & (pd.to_datetime(df["date"], errors="coerce") <= d1)]

    # Tech filter
    tech_vals = sorted([t for t in df["tech"].dropna().unique().tolist() if str(t).strip() != ""]) if "tech" in df.columns else []
    tech_sel = st.sidebar.multiselect("Tech", tech_vals, default=tech_vals)
    if tech_sel:
        df = df[df["tech"].isin(tech_sel)]

    # Drop Size filter
    drop_vals = sorted([t for t in df["drop_size"].dropna().unique().tolist() if str(t).strip() != ""]) if "drop_size" in df.columns else []
    drop_sel = st.sidebar.multiselect("Drop Size", drop_vals, default=drop_vals)
    if drop_sel:
        df = df[df["drop_size"].isin(drop_sel)]

    # KPIs
    total_rows = len(df)
    total_count = pd.to_numeric(df["count"], errors="coerce").sum() if "count" in df.columns else 0
    unique_techs = df["tech"].nunique() if "tech" in df.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", total_rows)
    c2.metric("Sum of Count", f"{total_count:,.0f}")
    c3.metric("Unique Techs", unique_techs)

    st.markdown("---")

    # Table of the four columns
    show_df = df[["date","tech","drop_size","count"]].copy()
    show_df = show_df.sort_values(by=["date","tech"], ascending=[True, True])
    st.dataframe(show_df, use_container_width=True)

    # Helpful visuals
    if not show_df.empty:
        if "drop_size" in show_df.columns:
            grp = show_df.groupby("drop_size")["count"].sum().reset_index()
            st.plotly_chart(px.bar(grp, x="drop_size", y="count", title="Total Count by Drop Size"), use_container_width=True)
        if "tech" in show_df.columns:
            grp2 = show_df.groupby("tech")["count"].sum().reset_index()
            st.plotly_chart(px.bar(grp2, x="tech", y="count", title="Total Count by Tech"), use_container_width=True)

    # Download
    st.download_button("Download (Date-Tech-DropSize-Count)", data=show_df.to_csv(index=False), file_name="preps_date_tech_drop_count.csv", mime="text/csv")
