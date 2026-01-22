import streamlit as st

st.set_page_config(page_title="Auvik Dashboard", layout="wide")

# If you DON'T see this, Streamlit Cloud is not running this file.
st.title("Auvik Dashboard ✅ (App is running)")
st.caption("If this is blank, your Streamlit Cloud main file path is wrong or the app failed to start.")

st.write("Step 1 reached: app.py loaded")

import requests
from requests.auth import HTTPBasicAuth

# ---------- Secrets ----------
def load_auvik_creds():
    username = ""
    api_key = ""

    if "auvik_api_username" in st.secrets:
        username = str(st.secrets["auvik_api_username"]).strip()
    if "auvik_api_key" in st.secrets:
        api_key = str(st.secrets["auvik_api_key"]).strip()

    if (not username or not api_key) and "auvik" in st.secrets:
        block = st.secrets["auvik"]
        if isinstance(block, dict):
            username = username or str(block.get("api_username", "")).strip()
            api_key = api_key or str(block.get("api_key", "")).strip()

    return username, api_key

API_USERNAME, API_KEY = load_auvik_creds()

with st.sidebar:
    st.header("🔧 Debug")
    try:
        st.write("Secrets keys:", list(st.secrets.keys()))
    except Exception as e:
        st.write("Could not read secrets keys:", str(e))
    st.write("Username loaded:", bool(API_USERNAME))
    st.write("API key loaded:", bool(API_KEY))
    if API_KEY:
        st.write("API key length:", len(API_KEY))

st.write("Step 2 reached: secrets checked")

if not API_USERNAME or not API_KEY:
    st.error("Missing Auvik secrets. Add to Streamlit Cloud → Settings → Secrets:")
    st.code('auvik_api_username = "api-user@yourdomain.com"\nauvik_api_key = "YOUR_AUVIK_API_KEY"')
    st.stop()

# ---------- API helper ----------
BASE_URL = "https://auvikapi.us6.my.auvik.com/v1"
HEADERS = {"Accept": "application/json"}
AUTH = HTTPBasicAuth(API_USERNAME, API_KEY)

def auvik_get(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    try:
        r = requests.get(url, headers=HEADERS, auth=AUTH, params=params, timeout=30)
        if r.status_code in (401, 403):
            return {"_error": True, "status": r.status_code, "text": r.text, "url": url}
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": True, "status": None, "text": str(e), "url": url}

st.write("Step 3 reached: auvik_get defined")

# ---------- Report load (wrapped so it NEVER blanks) ----------
st.subheader("Network Report Loader")
try:
    from reports.network import show_network_report
    st.success("Imported reports.network ✅")
    show_network_report(auvik_get)
except Exception as e:
    st.error("Network report failed to load")
    st.exception(e)
    st.info("Confirm the path is: reports/network.py and it starts with: import streamlit as st")
