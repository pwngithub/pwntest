import streamlit as st
import pandas as pd
import requests
import io

# Enable Streamlit caching for persistent data
# Cache lasts for 1 hour (3600 seconds)
CACHE_TTL = 3600


@st.cache_data(ttl=CACHE_TTL)
def fetch_jotform_data(form_id, api_key):
    """Fetch submissions from JotForm API with caching."""
    url = f"https://api.jotform.com/form/{form_id}/submissions?apiKey={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        submissions = data.get("content", [])
        df = pd.json_normalize(submissions)
        return df
    else:
        st.error(f"Failed to fetch JotForm data. Status code: {response.status_code}")
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL)
def load_csv(uploaded_file):
    """Load a CSV file with caching enabled."""
    try:
        return pd.read_csv(uploaded_file)
    except Exception:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file)


@st.cache_data(ttl=CACHE_TTL)
def load_google_sheet(sheet_url):
    """Load Google Sheet data and cache it."""
    try:
        csv_url = sheet_url.replace("/edit#gid=", "/export?format=csv&gid=")
        df = pd.read_csv(csv_url)
        return df
    except Exception as e:
        st.error(f"Error loading Google Sheet: {e}")
        return pd.DataFrame()
