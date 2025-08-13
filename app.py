
import streamlit as st
import pandas as pd
import requests

report = st.sidebar.selectbox(
    "📊 Select Report",
    ["Home", "Tally", "Construction", "Work Orders"]
)

if report == "Home":
    st.title("🏠 Welcome to Pioneer Dashboard")
    st.markdown("Use the sidebar to select a specific report.")

elif report == "Tally":
    import tally_dashboard

    api_key = "22179825a79dba61013e4fc3b9d30fa4"
    form_id = "240073839937062"
    url = f"https://api.jotform.com/form/{form_id}/submissions?apiKey={api_key}&limit=1000"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    submissions = []
    for item in data.get("content", []):
        answers = item.get("answers", {})
        record = {}
        for ans in answers.values():
            name = ans.get("name")
            answer = ans.get("answer")
            if name == "date" and isinstance(answer, dict) and "datetime" in answer:
                record["date"] = answer["datetime"]
            elif name == "customerName" and isinstance(answer, dict):
                record[name] = f"{answer.get('first','')} {answer.get('last','')}".strip()
            elif isinstance(answer, dict):
                record[name] = str(answer)
            elif name and answer is not None:
                record[name] = answer
        submissions.append(record)

    df = pd.DataFrame(submissions)
    tally_dashboard.run(df)

elif report == "Construction":
    import construction
    construction.run_construction_dashboard()

elif report == "Work Orders":
    import workorders
    workorders.run_workorders_dashboard()
