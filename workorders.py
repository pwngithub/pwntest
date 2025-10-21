import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sqlite3
from datetime import datetime

def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders Dashboard", layout="wide")

    # --- Persistent save folder ---
    # Use Streamlit Cloud persistent storage if available, otherwise local home dir
    if os.path.exists("/mount/data"):
        saved_folder = "/mount/data/saved_uploads"
    else:
        saved_folder = os.path.join(os.path.expanduser("~"), "pbb_workorders_saved")

    os.makedirs(saved_folder, exist_ok=True)

    # --- SQLite setup (persistent) ---
    db_path = os.path.join(saved_folder, "uploads.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            path TEXT,
            uploaded_at TEXT
        )
    """)
    conn.commit()

    st.sidebar.header("📁 File Management")
    mode = st.sidebar.radio("Select Mode", ["Upload New File", "Load Existing File"], key="mode_select")
    df = None

    # --- UPLOAD MODE ---
    if mode == "Upload New File":
        uploaded_file = st.sidebar.file_uploader("Upload Technician Workflow CSV", type=["csv"])
        custom_filename = st.sidebar.text_input("Enter a name to save this file as (without extension):")

        if uploaded_file and custom_filename:
            save_path = os.path.join(saved_folder, custom_filename + ".csv")
            try:
                # ✅ Actually write to disk
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # ✅ Store file record in DB
                conn.execute(
                    "INSERT OR REPLACE INTO uploads (filename, path, uploaded_at) VALUES (?, ?, ?)",
                    (custom_filename + ".csv", save_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()

                st.sidebar.success(f"✅ File saved to: {save_path}")
                df = pd.read_csv(save_path)

            except Exception as e:
                st.sidebar.error(f"❌ Error saving or reading file: {e}")

        elif uploaded_file and not custom_filename:
            st.sidebar.warning("Please enter a file name to save.")

    # --- LOAD MODE ---
    else:
        saved_files = [row[0] for row in conn.execute("SELECT filename FROM uploads ORDER BY uploaded_at DESC").fetchall()]
        if not saved_files:
            st.warning("No saved files found. Please upload one first.")
            return

        selected_file = st.sidebar.selectbox("Select a saved file to load", saved_files)
        if selected_file:
            path_row = conn.execute("SELECT path FROM uploads WHERE filename=?", (selected_file,)).fetchone()
            if path_row and os.path.exists(path_row[0]):
                st.sidebar.info(f"📂 Loaded from: {path_row[0]}")
                df = pd.read_csv(path_row[0])
            else:
                st.sidebar.error("⚠️ File not found on disk. It may have been deleted.")
                return

        # --- DELETE SECTION ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("🗑 Delete a Saved File")
        file_to_delete = st.sidebar.selectbox("Select a file to delete", ["-"] + saved_files)
        if st.sidebar.button("Delete Selected File"):
            if file_to_delete and file_to_delete != "-":
                path_row = conn.execute("SELECT path FROM uploads WHERE filename=?", (file_to_delete,)).fetchone()
                if path_row and os.path.exists(path_row[0]):
                    os.remove(path_row[0])
                conn.execute("DELETE FROM uploads WHERE filename=?", (file_to_delete,))
                conn.commit()
                st.sidebar.success(f"'{file_to_delete}' deleted.")
                st.experimental_rerun()
