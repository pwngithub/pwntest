
import streamlit as st
import pandas as pd
import plotly.express as px
import os


def run_workorders_dashboard():
    import streamlit as st
    import pandas as pd
    import plotly.express as px

    st.markdown("<h1 style='color:#405C88;'>📋 Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("This dashboard provides insights into work order activity, including totals, status by type, and overall averages.")

    # --- Load Data ---
    # Expect df to be set from file uploader or context; if not, handle gracefully
    if "df" not in globals():
        st.warning("⚠️ No data loaded for Work Orders.")
        return
    df = globals()["df"]

    # --- Handle Date Column Robustly ---
    date_col = None
    for candidate in ["Date When", "Date", "Submission Date", "Created At"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df["Month"] = df[date_col].dt.to_period("M").astype(str)
    else:
        st.warning("⚠️ No recognizable date column found in Work Orders data.")

    # --- KPIs ---
    total_orders = len(df)
    completed = len(df[df['Status'].str.lower() == 'completed']) if 'Status' in df.columns else 0
    pending = len(df[df['Status'].str.lower() == 'pending']) if 'Status' in df.columns else 0
    cancelled = len(df[df['Status'].str.lower() == 'cancelled']) if 'Status' in df.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📑 Total", total_orders, delta_color="off")
    col2.metric("✅ Completed", completed, delta_color="normal")
    col3.metric("⏳ Pending", pending, delta_color="inverse")
    col4.metric("❌ Cancelled", cancelled, delta_color="inverse")

    if 'Type' in df.columns:
        avg_by_type = df.groupby('Type').size().mean()
        st.metric("📊 Avg per Type", f"{avg_by_type:.1f}")

    st.markdown("---")

    # --- Visualizations ---
    if 'Status' in df.columns:
        status_summary = df['Status'].value_counts().reset_index()
        status_summary.columns = ['Status', 'Count']
        fig_status = px.pie(status_summary, names='Status', values='Count',
                            title='Work Orders by Status', hole=0.4,
                            color_discrete_sequence=['#405C88','#7CB342','#FF7043'])
        st.plotly_chart(fig_status, use_container_width=True)

    if 'Type' in df.columns:
        type_summary = df['Type'].value_counts().reset_index()
        type_summary.columns = ['Type', 'Count']
        fig_type = px.bar(type_summary, x='Type', y='Count',
                          title='Work Orders by Type',
                          color='Count', color_continuous_scale=['#7CB342','#405C88'])
        st.plotly_chart(fig_type, use_container_width=True)

    if 'Month' in df.columns:
        trend = df.groupby('Month').size().reset_index(name='Count')
        fig_trend = px.line(trend, x='Month', y='Count', markers=True,
                            title='Work Orders Trend Over Time',
                            color_discrete_sequence=['#405C88'])
        st.plotly_chart(fig_trend, use_container_width=True)
