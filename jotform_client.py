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




import pandas as pd

def fetch_preps_data(form_id, limit=1000):
    """
    Specialized fetch for Preps form.
    Extracts key fields (date, technician, customer, FAT, card, fiber_connected).
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
                "date": answers.get("1", {}).get("answer"),
                "technician": answers.get("2", {}).get("answer"),
                "customer_name": answers.get("14", {}).get("answer"),
                "fat": answers.get("32", {}).get("answer"),
                "card": answers.get("34", {}).get("answer"),
                "fiber_connected": answers.get("49", {}).get("answer"),
            }
            rows.append(row)

        return pd.DataFrame(rows)

    except Exception as e:
        raise RuntimeError(f"Failed to fetch Preps data: {e}")
