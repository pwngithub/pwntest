import streamlit as st

def run(df):
    st.title("✅ Preps Report Running")

    st.write("This is a basic debug test.")
    st.write("DataFrame shape:", df.shape)
    st.write("Column names:", list(df.columns))
