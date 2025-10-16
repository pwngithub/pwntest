import streamlit as st

# Pioneer color palette
PIONEER_BLUE = "#003865"
PIONEER_GREEN = "#8BC53F"
LIGHT_BG = "#FFFFFF"
DARK_BG = "#000000"
LIGHT_TEXT = "#003865"
DARK_TEXT = "#FFFFFF"

LOGO_URL = "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w"


def init_theme_state():
    """Initialize dark/light mode state if not set."""
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False


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
    """Apply global dark/light theme across all Streamlit elements."""
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
            div[data-testid="stVerticalBlock"] {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
            }}
            div.block-container {{
                background-color: {colors['bg']} !important;
                color: {colors['text']} !important;
            }}
            .stDataFrame, .stTable {{
                color: {colors['text']} !important;
            }}
            [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{
                color: {colors['text']} !important;
            }}
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header():
    """Render the global Pioneer header with logo, title, and dark mode toggle."""
    init_theme_state()
    colors = get_colors()
    toggle_label = "☀️ Light Mode" if st.session_state["dark_mode"] else "🌙 Dark Mode"

    st.markdown(
        f"""
        <div style="background-color:{colors['bg']}; padding:20px; text-align:center; border-bottom:3px solid {PIONEER_GREEN};">
            <img src="{LOGO_URL}" width="300"><br>
            <h1 style="color:{colors['text']}; margin-top:10px;">Pioneer Broadband Dashboard</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar toggle
    if st.sidebar.button(toggle_label):
        toggle_theme()


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
