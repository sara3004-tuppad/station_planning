import streamlit as st
import json
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")
AUTH_TOKENS = st.secrets.get("AUTH_TOKENS")['tokens']
SHEET_URL = st.secrets.get("SHEET_URL")

CREDENTIALS_DATA = json.loads(st.secrets["CREDENTIALS_DATA"]["service_account_json"])