
import requests
import pandas as pd

def fetch_jotform_data(form_id: str, api_key: str) -> pd.DataFrame:
    url = f"https://api.jotform.com/form/{form_id}/submissions?apiKey={api_key}&limit=1000"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if "content" not in data:
            return pd.DataFrame()
        records = []
        for submission in data["content"]:
            answers = submission.get("answers", {})
            record = {}
            for qid, answer in answers.items():
                name = answer.get("name")
                value = answer.get("answer")
                if isinstance(value, dict):
                    value = " ".join(str(v) for v in value.values() if v)
                record[name] = value
            records.append(record)
        return pd.DataFrame(records)
    except Exception as e:
        print(f"Error fetching JotForm data: {e}")
        return pd.DataFrame()

def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].fillna("").astype(str)
    return df
