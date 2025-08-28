
import streamlit as st
import pandas as pd
import re
import altair as alt
import requests
import datetime as _dt

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
    # Normalize to date
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    return df

def extract_drop_size(text):
    match = re.search(r"(\d{2,4})['’]\s?Drop", str(text))
    return match.group(1) + "'" if match else "Unknown"

df = fetch_prep_data()
df.rename(columns={"tech": "Tech", "inventoryItems": "INVENTORY ITEMS"}, inplace=True)

# Guard: if required columns not present, show info and stop
required_columns = ['Date', 'Tech', 'INVENTORY ITEMS']
if not all(col in df.columns for col in required_columns):
    st.error("❌ Missing required columns: 'Date', 'Tech', 'INVENTORY ITEMS'")
    st.write("Available columns:", df.columns.tolist())
    st.stop()

# Derive fields
df['Drop Size'] = df['INVENTORY ITEMS'].apply(extract_drop_size)
df['Tech'] = df['Tech'].astype(str).str.strip()

# Sidebar: Date range (robust handling)
min_date = df["Date"].min()
max_date = df["Date"].max()
if min_date is None or max_date is None:
    st.info("No date data available yet.")
    st.dataframe(df.head(20))
    st.stop()

st.sidebar.write(f"📅 Data range: {min_date} → {max_date}")
default_start = max(min_date, max_date - _dt.timedelta(days=6)) if isinstance(max_date, _dt.date) else min_date
date_input = st.sidebar.date_input(
    "Select Date Range",
    value=(default_start, max_date),
    min_value=min_date,
    max_value=max_date,
    key="prep_date_range",
)

# Normalize the widget output to (start, end)
if isinstance(date_input, (_dt.date, pd.Timestamp)):
    start_date = end_date = date_input if isinstance(date_input, _dt.date) else date_input.date()
elif isinstance(date_input, (list, tuple)) and len(date_input) == 2:
    a, b = date_input
    # Convert pandas Timestamp to date if needed
    a = a if isinstance(a, _dt.date) else a.to_pydatetime().date()
    b = b if isinstance(b, _dt.date) else b.to_pydatetime().date()
    start_date, end_date = (a, b) if a <= b else (b, a)
else:
    start_date, end_date = default_start, max_date

# Reset button
if st.sidebar.button("🔄 Reset Dates"):
    st.session_state["prep_date_range"] = (default_start, max_date)

# Apply date filter
filtered_df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)].copy()

# Secondary filters
st.sidebar.header("🔍 More Filters")
tech_options = sorted(filtered_df['Tech'].dropna().unique().tolist())
drop_options = sorted(filtered_df['Drop Size'].dropna().unique().tolist())
selected_techs = st.sidebar.multiselect("Tech", tech_options)
selected_drops = st.sidebar.multiselect("Drop Size", drop_options)

if selected_techs:
    filtered_df = filtered_df[filtered_df['Tech'].isin(selected_techs)]
if selected_drops:
    filtered_df = filtered_df[filtered_df['Drop Size'].isin(selected_drops)]

# Diagnostics (collapsible)
with st.expander("🛠 Diagnostics"):
    st.write(f"Selected range: {start_date} → {end_date}")
    st.write("Rows after date filter:", len(df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]))
    st.write("Rows after all filters:", len(filtered_df))
    st.dataframe(filtered_df.head(10))

# Output
st.subheader("📋 Filtered Results")
if filtered_df.empty:
    st.info("No data for the selected filters. Try widening the date range.")
else:
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
