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

import pandas as pd
import re

def _extract_by_keywords(answers: dict, keywords_any=None, keywords_all=None, prefer_ids=None):
    """
    Find the first answer whose name/text matches the given keyword rules.
    - keywords_any: at least one of these substrings must appear
    - keywords_all: all of these substrings must appear
    - prefer_ids: list of string IDs to try first
    Returns the "answer" value or None.
    """
    if not answers:
        return None
    # Prefer explicit IDs first
    if prefer_ids:
        for qid in prefer_ids:
            if qid in answers and answers[qid].get("answer"):
                return answers[qid].get("answer")
    def matches(details):
        text = f"{details.get('name','')} {details.get('text','')}".lower()
        ok_any = True
        ok_all = True
        if keywords_any:
            ok_any = any(k.lower() in text for k in keywords_any)
        if keywords_all:
            ok_all = all(k.lower() in text for k in keywords_all)
        return ok_any and ok_all
    for qid, details in answers.items():
        if details and details.get("answer") is not None and matches(details):
            return details.get("answer")
    return None

def fetch_preps_data(form_id, limit=1000):
    """
    Specialized fetch for Preps form.
    Returns a tidy DataFrame with columns: date, tech, drop_size, count.
    Uses robust keyword matching for field extraction so IDs needn't be hardcoded.
    """
    try:
        url = f"https://api.jotform.com/form/{form_id}/submissions"
        params = {"apiKey": API_KEY, "limit": limit}
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json().get("content", [])
        rows = []
        for sub in data:
            answers = sub.get("answers", {})
            # Extract fields
            date_raw = _extract_by_keywords(answers, keywords_any=["date"], prefer_ids=["1"])
            tech_raw = _extract_by_keywords(answers, keywords_any=["tech", "technician"], prefer_ids=["2"])
            drop_raw = _extract_by_keywords(answers, keywords_any=["drop"], keywords_all=None)
            count_raw = _extract_by_keywords(answers, keywords_any=["count", "fiber"], keywords_all=None)

            # Normalize
            # Date
            date_val = None
            if date_raw:
                # JotForm may return dict for date parts or string; handle both
                if isinstance(date_raw, dict):
                    # Try common keys
                    y = str(date_raw.get("year", "")).zfill(4) if date_raw.get("year") else ""
                    m = str(date_raw.get("month", "")).zfill(2) if date_raw.get("month") else ""
                    d = str(date_raw.get("day", "")).zfill(2) if date_raw.get("day") else ""
                    date_val = "-".join([p for p in [y, m, d] if p])
                else:
                    date_val = str(date_raw)
            # Tech
            tech_val = str(tech_raw) if tech_raw is not None else None
            # Drop Size
            drop_val = str(drop_raw) if drop_raw is not None else None
            # Count (numeric)
            count_val = None
            if isinstance(count_raw, (int, float)):
                count_val = count_raw
            elif isinstance(count_raw, str):
                m = re.search(r'-?\d+(?:\.\d+)?', count_raw.replace(',', ''))
                count_val = float(m.group()) if m else None
            elif isinstance(count_raw, dict):
                # Sometimes JotForm number widget returns dict with 'value'
                val = count_raw.get("value")
                if isinstance(val, (int, float)):
                    count_val = val
                elif isinstance(val, str):
                    m = re.search(r'-?\d+(?:\.\d+)?', val.replace(',', ''))
                    count_val = float(m.group()) if m else None

            rows.append({
                "date": date_val,
                "tech": tech_val,
                "drop_size": drop_val,
                "count": count_val
            })
        df = pd.DataFrame(rows)
        # Final cleanups
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if "count" in df.columns:
            df["count"] = pd.to_numeric(df["count"], errors="coerce")
        return df
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Preps data: {e}")
