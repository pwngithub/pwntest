
import requests
import pandas as pd
import streamlit as st

API_KEY = "ba9013143bfda3a448297144c0527f7e"

def fetch_jotform_data(form_id):
    try:
        url = f"https://api.jotform.com/form/{form_id}/submissions?apiKey={API_KEY}"
        response = requests.get(url)
        st.sidebar.write("JotForm API Status:", response.status_code)

        if response.status_code != 200:
            return None

        content = response.json()
        submissions = content.get("content", [])
        if not submissions:
            return pd.DataFrame()

        fields = submissions[0]["answers"]
        columns = {key: val["text"] for key, val in fields.items()}

        data = []
        for submission in submissions:
            row = {}
            for key, val in submission["answers"].items():
                if "answer" in val:
                    row[columns.get(key, key)] = val["answer"]
            data.append(row)

        return pd.DataFrame(data)

    except Exception as e:
        st.sidebar.error(f"Error fetching data: {e}")
        return None
