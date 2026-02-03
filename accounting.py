import streamlit as st
import pandas as pd
import requests
import re

# -------------------------------
# APP CONFIGURATION
# -------------------------------
st.set_page_config(page_title="Profit & Loss Dashboard", page_icon="💰", layout="wide")

# -------------------------------
# DARK MODE STYLING
# -------------------------------
bg_color = "#000000"
text_color = "#FFFFFF"
card_bg = "#1c1c1c"
border_color = "#1e90ff"
logo_url = (
    "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/"
    "369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo+white.png?format=1500w"
)

# -------------------------------
# GLOBAL BACKGROUND + FADE
# -------------------------------
st.markdown(
    f"""
    <style>
    * {{
        transition: background-color 0.3s ease, color 0.3s ease;
    }}
    body {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}
    [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}
    div[data-testid="stMarkdownContainer"] p, h1, h2, h3, h4, h5, h6 {{
        color: {text_color} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------
# HEADER SECTION
# -------------------------------
st.markdown(
    f"""
    <div style="display:flex;align-items:center;justify-content:flex-start;">
        <img src="{logo_url}" width="258" height="49" style="margin-right:15px;">
    </div>
    <hr style="height:4px;border:none;background-color:{border_color};margin-top:0;margin-bottom:20px;">
    """,
    unsafe_allow_html=True,
)

# -------------------------------
# GOOGLE SHEET CONFIG
# -------------------------------
SHEET_ID = "1iiBe4CLYPlr_kpIOuvzxLliwA0ferGtBRhtnMLfhOQg"

try:
    API_KEY = st.secrets["gcp"]["api_key"]
except Exception:
    st.error("❌ Google API key not found in Streamlit secrets under [gcp].")
    st.stop()

# -------------------------------
# FETCH SHEET NAMES
# -------------------------------
@st.cache_data(ttl=60)  # shorter cache during dev – can increase later
def get_sheet_tabs(sheet_id, api_key):
    meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?key={api_key}"
    r = requests.get(meta_url)
    if r.status_code != 200:
        raise Exception(f"Metadata error: {r.status_code} – {r.text}")
    sheets = r.json().get("sheets", [])
    return [s["properties"]["title"] for s in sheets]

# -------------------------------
# SIDEBAR – MONTH SELECTION + REFRESH
# -------------------------------
st.sidebar.markdown("### Controls")

if st.sidebar.button("🔄 Refresh sheet list"):
    get_sheet_tabs.clear()
    st.rerun()

try:
    sheet_names = get_sheet_tabs(SHEET_ID, API_KEY)
    
    # Select tabs that look like monthly sheets (e.g. 25.12, 26.01, 26.02...)
    month_tabs = [
        n for n in sheet_names
        if re.match(r'^\d{2}\.\d{2}$', n.strip())
    ]
    
    # Sort newest first (26.01 > 25.12 > 25.11 ...)
    month_tabs.sort(reverse=True)
    
    if not month_tabs:
        # Fallback: show all tabs if no month-like names found
        month_tabs = sorted(sheet_names, reverse=True)
    
    selected_tab = st.sidebar.selectbox(
        "📅 Select Month",
        month_tabs,
        index=0,  # newest tab selected by default
        key="accounting_month_selectbox_v5",
    )
except Exception as e:
    st.sidebar.error(f"❌ Could not fetch sheet tabs: {e}")
    st.stop()

# -------------------------------
# LOAD SHEET DATA
# -------------------------------
@st.cache_data(ttl=300)
def load_sheet(sheet_id, tab, api_key):
    # URL-encode single quotes if needed, but Google usually handles ' fine
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab}!A1:Z200?key={api_key}"
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Failed to load '{tab}': {r.status_code} – {r.text}")
    vals = r.json().get("values", [])
    if not vals:
        raise Exception("No data returned from sheet.")
    
    # Try to find header row with enough non-empty cells
    header_row = next((i for i, row in enumerate(vals) if sum(1 for c in row if str(c).strip()) >= 3), None)
    if header_row is None:
        raise Exception("Could not find a valid header row.")
    
    df = pd.DataFrame(vals[header_row + 1:], columns=vals[header_row])
    df.columns = [str(c).strip() if c else f"Column_{i}" for i, c in enumerate(df.columns)]
    
    # Handle duplicate columns
    if df.columns.duplicated().any():
        df.columns = [
            f"{c}_{i}" if df.columns.tolist().count(c) > 1 else c
            for i, c in enumerate(df.columns)
        ]
    return df

try:
    df = load_sheet(SHEET_ID, selected_tab, API_KEY)
except Exception as e:
    st.error(f"❌ Load error for tab **{selected_tab}**: {e}")
    st.stop()

# -------------------------------
# HELPERS
# -------------------------------
def find_row(df, keys):
    """Find first row where column A CONTAINS any of the keys (case-insensitive)."""
    col = df.iloc[:, 0].astype(str).str.lower()
    for k in keys:
        m = col[col.str.contains(k.lower(), na=False)]
        if not m.empty:
            return m.index[0]
    return None

def find_exact_row(df, key):
    """Find first row where column A EQUALS the key (case-insensitive, trimmed)."""
    col = df.iloc[:, 0].astype(str).str.strip().str.lower()
    m = col[col == key.lower()]
    if not m.empty:
        return m.index[0]
    return None

def find_col(df, key):
    for i, c in enumerate(df.columns):
        if re.search(key, str(c), re.IGNORECASE):
            return i
    return None

def num(df, r, c):
    try:
        v = str(df.iat[r, c]).strip()
        if "%" in v:
            return float(v.replace("%", "").replace(",", "").replace("$", ""))
        return pd.to_numeric(v.replace(",", "").replace("$", ""), errors="coerce")
    except:
        return 0

# -------------------------------
# KPI LOGIC
# -------------------------------
col_idx = find_col(df, "month") or 1
ebitda_r   = find_row(df, ["ebitda"])
subs_r     = find_row(df, ["users months", "user months"])
mrr_r      = find_row(df, ["broadhub rev", "broadhub"])

ebitda = num(df, ebitda_r, col_idx) if ebitda_r is not None else 0
subs   = num(df, subs_r, col_idx)   if subs_r is not None else 0
mrr    = num(df, mrr_r, col_idx)    if mrr_r is not None else 0
arpu   = (mrr / subs) if subs > 0 else 0

# ROI
roi_row = find_exact_row(df, "roi")
roi_monthly = 0
roi_ytd = 0

if roi_row is not None:
    roi_monthly_col = next((i for i, c in enumerate(df.columns) if re.search(r"month", str(c), re.IGNORECASE)), None)
    roi_ytd_col     = next((i for i, c in enumerate(df.columns) if re.search(r"ytd",   str(c), re.IGNORECASE)), None)

    if roi_monthly_col is not None:
        roi_monthly = num(df, roi_row, roi_monthly_col)
    if roi_ytd_col is not None:
        roi_ytd = num(df, roi_row, roi_ytd_col)

# -------------------------------
# KPI DISPLAY
# -------------------------------
st.markdown(
    f"<h2 style='color:{border_color};text-shadow:0px 0px 8px rgba(30,144,255,0.45);'>💼 Financial Performance – {selected_tab}</h2>",
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)

def kpi_box(label, value, is_percent=False, is_number=False):
    try:
        n = float(str(value).replace("%", "").replace("$", "").replace(",", ""))
    except:
        n = 0
    val_color = border_color if n >= 0 else "red"

    if is_percent:
        formatted = f"{n:,.2f}%"
    elif is_number:
        formatted = f"{n:,.0f}"
    else:
        formatted = f"${n:,.2f}"

    return f"""
    <div class="kpi-card" style="
        background-color:{card_bg};
        border:2px solid {border_color};
        border-radius:12px;
        padding:16px;
        box-shadow:0px 0px 12px rgba(30,144,255,0.25);
        text-align:center;
        transition: all 0.3s ease-in-out;">
        <div style="font-weight:600;color:{text_color};margin-bottom:4px;">{label}</div>
        <div style="font-size:1.6em;font-weight:700;color:{val_color};">{formatted}</div>
    </div>
    """

c1.markdown(kpi_box("Monthly Recurring Revenue", mrr), unsafe_allow_html=True)
c2.markdown(kpi_box("Subscriber Count", subs, is_number=True), unsafe_allow_html=True)
c3.markdown(kpi_box("Average Revenue Per User", arpu), unsafe_allow_html=True)
c4.markdown(kpi_box("EBITDA", ebitda), unsafe_allow_html=True)

r1, r2 = st.columns(2)
r1.markdown(kpi_box("ROI Monthly", roi_monthly, is_percent=True), unsafe_allow_html=True)
r2.markdown(kpi_box("ROI Year To Date", roi_ytd, is_percent=True), unsafe_allow_html=True)

# -------------------------------
# SIDEBAR OPTIONS + DOWNLOAD
# -------------------------------
st.sidebar.markdown("---")
show_df = st.sidebar.checkbox(
    "📋 Show Profit & Loss Sheet Preview",
    False,
    key="accounting_show_pl_preview_v5",
)
if show_df:
    st.subheader(f"📋 Profit & Loss Sheet Preview – {selected_tab}")
    st.dataframe(df, use_container_width=True)

st.subheader("⬇️ Download Data")
csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    f"Download {selected_tab} CSV",
    csv,
    f"{selected_tab}_profit_loss.csv",
    "text/csv"
)

# -------------------------------
# GLOBAL CSS FOR HOVER + BUTTONS
# -------------------------------
st.markdown(
    f"""
    <style>
    .kpi-card:hover {{
        box-shadow: 0px 0px 18px rgba(30,144,255,0.45);
        transform: scale(1.01);
        cursor: pointer;
    }}
    section[data-testid="stSidebar"] {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}
    div[data-testid="stDownloadButton"] button {{
        background-color: {border_color} !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: none !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")
st.caption("© 2025 Pioneer Broadband")
