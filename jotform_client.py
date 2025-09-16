import requests

API_KEY = "22179825a79dba61013e4fc3b9d30fa4"  # Real JotForm API key

def fetch_jotform_data(form_id, limit=1000):
    """
    Fetch submissions from JotForm for the given form_id.
    Returns a list of submissions (JSON objects).
    """
    try:
        url = f"https://api.jotform.com/form/{form_id}/submissions"
        params = {"apiKey": API_KEY, "limit": limit}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()["content"]
    except Exception as e:
        raise RuntimeError(f"Failed to fetch JotForm data: {e}")


import pandas as pd

def fetch_preps_data(form_id, limit=1000):
    """
    Specialized fetch for Preps form.
    Extracts Technician, Prep Type, Location into a clean DataFrame.
    """
    try:
        url = f"https://api.jotform.com/form/{form_id}/submissions"
        params = {"apiKey": API_KEY, "limit": limit}
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()["content"]

        rows = []
        for sub in data:
            answers = sub.get("answers", {})
            row = {
                "id": sub.get("id"),
                "created_at": sub.get("created_at"),
                "status": sub.get("status"),
                "technician": answers.get("3", {}).get("answer"),
                "prep_type": answers.get("4", {}).get("answer"),
                "location": answers.get("5", {}).get("answer"),
            }
            rows.append(row)

        return pd.DataFrame(rows)

    except Exception as e:
        raise RuntimeError(f"Failed to fetch Preps data: {e}")
