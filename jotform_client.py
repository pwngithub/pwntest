import requests

API_KEY = "your-real-api-key-here"  # Replace with your actual JotForm API key

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
