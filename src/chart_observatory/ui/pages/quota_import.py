import streamlit as st

from chart_observatory.ui.quota_import import render_quota_import

st.set_page_config(page_title="Importação por cotas", layout="wide")
render_quota_import()
