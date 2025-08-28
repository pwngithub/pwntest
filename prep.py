
import streamlit as st
import pandas as pd
import re
import altair as alt
from pathlib import Path
import os

st.set_page_config(page_title="Fiber Prep Dashboard", layout="wide")
st.title("📊 Fiber Prep Dashboard")

# Ensure shared directory exists and log its path
shared_dir = Path("shared_files")
shared_dir.mkdir(parents=True, exist_ok=True)
st.sidebar.info(f"Shared file directory: {shared_dir.resolve()}")

def extract_drop_size(inventory):
    match = re.search(r"(\d{2,4})['’]\s?Drop", str(inventory))
    return match.group(1) + "'" if match else "Unknown"

# Upload and save
uploaded_file = st.file_uploader("Upload your Excel file to share (.xlsx, .xlsm)", type=["xlsx", "xlsm"])
if uploaded_file:
    save_path = shared_dir / uploaded_file.name
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"✅ File saved as: {uploaded_file.name}")
    st.write(f"Full path: {save_path.resolve()}")

# File selector
st.sidebar.header("📂 Select a Shared File")
excel_files = sorted([f.name for f in shared_dir.glob("*.xls*")])
selected_file = st.sidebar.selectbox("Choose a file to analyze", excel_files)

if selected_file:
    try:
        df = pd.read_excel(shared_dir / selected_file, sheet_name=0)
        df.columns = df.columns.str.strip()

        required_columns = ['Date', 'Tech', 'INVENTORY ITEMS']
        if not all(col in df.columns for col in required_columns):
            st.error("Missing required columns: 'Date', 'Tech', or 'INVENTORY ITEMS'")
        else:
            df['Drop Size'] = df['INVENTORY ITEMS'].apply(extract_drop_size)
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
            df['Tech'] = df['Tech'].astype(str).str.strip()

            # Sidebar filters
            st.sidebar.header("🔍 Filter Data")
            selected_dates = st.sidebar.multiselect("Select Date(s)", sorted(df['Date'].dropna().unique()))
            selected_techs = st.sidebar.multiselect("Select Tech(s)", sorted(df['Tech'].dropna().unique()))
            selected_drops = st.sidebar.multiselect("Select Drop Size(s)", sorted(df['Drop Size'].dropna().unique()))

            filtered_df = df.copy()
            if selected_dates:
                filtered_df = filtered_df[filtered_df['Date'].isin(selected_dates)]
            if selected_techs:
                filtered_df = filtered_df[filtered_df['Tech'].isin(selected_techs)]
            if selected_drops:
                filtered_df = filtered_df[filtered_df['Drop Size'].isin(selected_drops)]

            st.subheader("📋 Filtered Results")
            st.dataframe(filtered_df, use_container_width=True)

            st.subheader("📌 Summary by Date, Tech, and Drop Size")
            summary = filtered_df.groupby(['Date', 'Tech', 'Drop Size']).size().reset_index(name='Count')
            st.dataframe(summary)

            st.markdown("---")
            st.header("📊 Visualizations")

            # 1. Preps over time
            preps_over_time = filtered_df.groupby('Date').size().reset_index(name='Prep Count')
            chart1 = alt.Chart(preps_over_time).mark_bar().encode(
                x='Date:T',
                y='Prep Count:Q',
                tooltip=['Date', 'Prep Count']
            ).properties(title='Preps Over Time')
            st.altair_chart(chart1, use_container_width=True)

            # 2. Preps per Technician
            preps_per_tech = filtered_df.groupby('Tech').size().reset_index(name='Prep Count')
            chart2 = alt.Chart(preps_per_tech).mark_bar().encode(
                x='Tech:N',
                y='Prep Count:Q',
                tooltip=['Tech', 'Prep Count']
            ).properties(title='Preps per Technician')
            st.altair_chart(chart2, use_container_width=True)

            # 3. Drop Size Distribution
            drop_dist = filtered_df['Drop Size'].value_counts().reset_index()
            drop_dist.columns = ['Drop Size', 'Count']
            chart3 = alt.Chart(drop_dist).mark_bar().encode(
                x='Drop Size:N',
                y='Count:Q',
                tooltip=['Drop Size', 'Count']
            ).properties(title='Drop Size Distribution')
            st.altair_chart(chart3, use_container_width=True)

            # 4. Stacked bar: Drop Size per Tech
            stacked_df = filtered_df.groupby(['Tech', 'Drop Size']).size().reset_index(name='Count')
            chart4 = alt.Chart(stacked_df).mark_bar().encode(
                x='Tech:N',
                y='Count:Q',
                color='Drop Size:N',
                tooltip=['Tech', 'Drop Size', 'Count']
            ).properties(title='Drop Size by Technician')
            st.altair_chart(chart4, use_container_width=True)

            # 5. Line chart: Prep trend over time
            line_chart = alt.Chart(preps_over_time).mark_line(point=True).encode(
                x='Date:T',
                y='Prep Count:Q',
                tooltip=['Date', 'Prep Count']
            ).properties(title='Prep Trend Over Time')
            st.altair_chart(line_chart, use_container_width=True)

    except Exception as e:
        st.error(f"Error processing file: {e}")
