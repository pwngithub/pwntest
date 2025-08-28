
import streamlit as st
import pandas as pd
import re
import altair as alt
import requests

st.set_page_config(page_title="Fiber Prep Dashboard", layout="wide")
st.title("📊 Fiber Prep Dashboard (via JotForm API)")

@st.cache_data
def fetch_prep_data():
    url = "https://api.jotform.com/form/210823797836164/submissions?apiKey=22179825a79dba61013e4fc3b9d30fa4&limit=1000"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    records = []

    for item in data.get("content", []):
        answers = item.get("answers", {})
        record = {
            "Date": item.get("created_at")
        }
        for ans in answers.values():
            name = ans.get("name")
            answer = ans.get("answer")
            if name and answer is not None:
                record[name.strip()] = answer
        records.append(record)

    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    return df

def extract_drop_size(text):
    match = re.search(r"(\d{2,4})['’]\s?Drop", str(text))
    return match.group(1) + "'" if match else "Unknown"

df = fetch_prep_data()

st.subheader("🧪 Available Columns")
st.write(df.columns.tolist())

required_columns = ['Date', 'Tech', 'INVENTORY ITEMS']
if not all(col in df.columns for col in required_columns):
    st.error("❌ Missing one or more required columns: 'Date', 'Tech', 'INVENTORY ITEMS'")
    st.warning("Check the column list above and update the field names accordingly.")
else:
    df['Drop Size'] = df['INVENTORY ITEMS'].apply(extract_drop_size)
    df['Tech'] = df['Tech'].astype(str).str.strip()

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

    preps_over_time = filtered_df.groupby('Date').size().reset_index(name='Prep Count')
    chart1 = alt.Chart(preps_over_time).mark_bar().encode(
        x='Date:T',
        y='Prep Count:Q',
        tooltip=['Date', 'Prep Count']
    ).properties(title='Preps Over Time')
    st.altair_chart(chart1, use_container_width=True)

    preps_per_tech = filtered_df.groupby('Tech').size().reset_index(name='Prep Count')
    chart2 = alt.Chart(preps_per_tech).mark_bar().encode(
        x='Tech:N',
        y='Prep Count:Q',
        tooltip=['Tech', 'Prep Count']
    ).properties(title='Preps per Technician')
    st.altair_chart(chart2, use_container_width=True)

    drop_dist = filtered_df['Drop Size'].value_counts().reset_index()
    drop_dist.columns = ['Drop Size', 'Count']
    chart3 = alt.Chart(drop_dist).mark_bar().encode(
        x='Drop Size:N',
        y='Count:Q',
        tooltip=['Drop Size', 'Count']
    ).properties(title='Drop Size Distribution')
    st.altair_chart(chart3, use_container_width=True)

    stacked_df = filtered_df.groupby(['Tech', 'Drop Size']).size().reset_index(name='Count')
    chart4 = alt.Chart(stacked_df).mark_bar().encode(
        x='Tech:N',
        y='Count:Q',
        color='Drop Size:N',
        tooltip=['Tech', 'Drop Size', 'Count']
    ).properties(title='Drop Size by Technician')
    st.altair_chart(chart4, use_container_width=True)

    line_chart = alt.Chart(preps_over_time).mark_line(point=True).encode(
        x='Date:T',
        y='Prep Count:Q',
        tooltip=['Date', 'Prep Count']
    ).properties(title='Prep Trend Over Time')
    st.altair_chart(line_chart, use_container_width=True)
