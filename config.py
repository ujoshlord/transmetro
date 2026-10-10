import streamlit as st

# Acceso a la sección [database]
DATABASE_URL = st.secrets["database"]["url"]

# Acceso a la sección [security] y [app]
SECRET_KEY = st.secrets["security"]["secret_key"]
APP_NAME = st.secrets["app"]["name"]
DEFAULT_PAGE_TITLE = st.secrets["app"]["default_page_title"]
DEFAULT_PAGE_ICON = st.secrets["app"]["default_page_icon"]

DEFAULT_LATITUDE = 14.634915
DEFAULT_LONGITUDE = -90.506882
DEFAULT_ZOOM = 12
