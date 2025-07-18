import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Set page config
st.set_page_config(page_title="KPI Dashboard", layout="wide")

# Google Sheets Setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(creds)

# Spreadsheet ID and tab names
SHEET_ID = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"
sheet_month = client.open_by_key(SHEET_ID).worksheet("KPI Month")
df_month = pd.DataFrame(sheet_month.get_all_records())

sheet_day = client.open_by_key(SHEET_ID).worksheet("KPI Day")
df_day = pd.DataFrame(sheet_day.get_all_records())
df_day['Date'] = pd.to_datetime(df_day['Date'], format='%m/%d/%Y', errors='coerce')
df_day['Week'] = df_day['Week'].astype(str).str.extract(r'(\d+)').astype(float)

sheet_csat = client.open_by_key(SHEET_ID).worksheet("CSAT Score")
df_csat = pd.DataFrame(sheet_csat.get_all_records())
df_csat['Week'] = df_csat['Week'].astype(str).str.extract(r'(\d+)').astype(float)

# UI
st.title("📊 KPI Dashboard")
emp_id = st.text_input("Enter your EMP ID")
view_option = st.selectbox("Select View Mode", ["Month", "Week", "Day"])

if not emp_id:
    st.warning("Please enter your EMP ID.")
    st.stop()

# Function to get target committed
@st.cache_data
def get_target_committed(emp_id, month):
    data = df_month[(df_month['EMP ID'] == emp_id) & (df_month['Month'] == month)]
    if not data.empty:
        return {
            "Target Committed for PKT": data['Target Committed for PKT'].values[0],
            "Target Committed for CSAT (Agent Behaviour)": data['Target Committed for CSAT (Agent Behaviour)'].values[0],
            "Target Committed for Quality": data['Target Committed for Quality'].values[0]
        }
    return {
        "Target Committed for PKT": "N/A",
        "Target Committed for CSAT (Agent Behaviour)": "N/A",
        "Target Committed for Quality": "N/A"
    }

if view_option == "Month":
    selected_month = st.selectbox("Select Month", sorted(df_month['Month'].dropna().unique()))
    data = df_month[(df_month['EMP ID'].astype(str) == emp_id) & (df_month['Month'] == selected_month)]

elif view_option == "Week":
    selected_week = st.selectbox("Select Week", sorted(df_day['Week'].dropna().unique()))
    week_data = df_day[(df_day['EMP ID'].astype(str) == emp_id) & (df_day['Week'] == selected_week)]
    csat_data = df_csat[(df_csat['EMP ID'].astype(str) == emp_id) & (df_csat['Week'] == selected_week)]

    if not week_data.empty:
        call_count = week_data['Call Count'].astype(float).sum()
        aht = week_data['AHT'].astype(float).mean()
        hold = week_data['Hold'].astype(float).mean()
        wrap = week_data['Wrap'].astype(float).mean()
    else:
        call_count = aht = hold = wrap = 'N/A'

    if not csat_data.empty:
        csat_resolution = csat_data['CSAT Resolution'].values[0]
        csat_behaviour = csat_data['CSAT Behaviour'].values[0]
    else:
        csat_resolution = csat_behaviour = 'N/A'

    data = pd.DataFrame([{
        'Call Count': call_count,
        'AHT': aht,
        'Hold': hold,
        'Wrap': wrap,
        'CSAT Resolution': csat_resolution,
        'CSAT Behaviour': csat_behaviour
    }])

elif view_option == "Day":
    selected_date = st.date_input("Select Date")
    filtered_day = df_day[(df_day['EMP ID'].astype(str) == emp_id) & (df_day['Date'] == pd.to_datetime(selected_date))]
    if filtered_day.empty:
        st.warning("No data found for selected date.")
        st.stop()
    data = filtered_day

# Display data
st.subheader("📌 Performance Data")
st.dataframe(data, use_container_width=True)

# Display Targets (only for Monthly view)
if view_option == "Month" and not data.empty:
    st.subheader("🎯 Target Committed")
    targets = get_target_committed(emp_id, selected_month)
    st.write(targets)
