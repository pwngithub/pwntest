import streamlit as st

# Pioneer color palette
PIONEER_BLUE = "#003865"
PIONEER_GREEN = "#8BC53F"
LIGHT_BG = "#FFFFFF"
DARK_BG = "#000000"
LIGHT_TEXT = "#003865"
DARK_TEXT = "#FFFFFF"

def init_theme_state():
    """Initialize dark/light mode state; default is dark."""
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = True  # Default to dark mode

def toggle_theme():
    """Toggle between dark and light mode."""
    st.session_state["dark_mode"] = not st.session_state["dark_mode"]
    st.rerun()

def get_colors():
    """Return color palette based on mode."""
    if st.session_state["dark_mode"]:
        return {"bg": DARK_BG, "text": DARK_TEXT, "accent": PIONEER_GREEN}
    else:
        return {"bg": LIGHT_BG, "text": LIGHT_TEXT, "accent": PIONEER_GREEN}

def apply_theme():
    """Apply global dark/light theme across all Streamlit elements, including sidebar and dropdowns."""
    colors = get_colors()

    st.markdown(
        f"""
        <style>
            html, body, [class*="css"] {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
            }}
            .stApp {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
            }}
            div[data-testid="stVerticalBlock"], div.block-container {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
            }}
            /* Sidebar */
            section[data-testid="stSidebar"] {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
                border-right: 2px solid {colors['accent']} !important;
            }}
            /* Top bar */
            header[data-testid="stHeader"] {{
                background-color: {colors['bg']} !important;
                border-bottom: 2px solid {colors['accent']} !important;
                color: {colors['text']} !important;
            }}
            /* Text and DataFrames */
            .stMarkdown, .stDataFrame, .stTable, .stTextInput > div > div > input {{
                color: {colors['text']} !important;
            }}
            /* Metrics */
            [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{
                color: {colors['text']} !important;
            }}
            /* Buttons */
            .stButton > button {{
                background-color: {colors['accent']} !important;
                color: white !important;
                border-radius: 8px;
                border: none;
                padding: 0.4em 1.2em;
            }}
            .stButton > button:hover {{
                background-color: {PIONEER_BLUE} !important;
                color: white !important;
            }}
            /* Inputs and selectboxes */
            div[data-baseweb="select"], div[data-baseweb="input"] {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
                border: 1px solid {colors['accent']} !important;
            }}
            label, span, p, h1, h2, h3, h4, h5 {{
                color: {colors['text']} !important;
            }}
            /* Sidebar selectbox dropdown specifically */
            div[data-baseweb="select"] > div {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
                border: 1px solid {colors['accent']} !important;
            }}
            div[data-baseweb="select"] span {{
                color: {colors['text']} !important;
            }}
            div[data-baseweb="select"] svg {{
                fill: {colors['text']} !important;
            }}
            /* Dropdown popup itself */
            ul[role="listbox"], div[role="listbox"] {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
                border: 1px solid {colors['accent']} !important;
            }}
            ul[role="listbox"] li, div[role="option"] {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
            }}
            ul[role="listbox"] li:hover, div[role="option"]:hover {{
                background-color: {colors['accent']} !important;
                color: white !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_footer():
    """Render a global footer."""
    colors = get_colors()
    st.markdown(
        f"""
        <div style="background-color:{colors['bg']}; padding:10px; text-align:center; border-top:3px solid {PIONEER_GREEN}; margin-top:40px;">
            <p style="color:{colors['text']}; font-size:0.9em;">© 2025 Pioneer Broadband — All Rights Reserved</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
