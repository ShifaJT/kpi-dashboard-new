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

# Get data based on view
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

# Display Performance Data
st.subheader("📌 Performance Data")
perf_cols = ['Call Count', 'AHT', 'Hold', 'Wrap', 'CSAT Resolution', 'CSAT Behaviour']
perf_data = data[[col for col in perf_cols if col in data.columns]]
st.dataframe(perf_data, use_container_width=True)

# Display KPI Data (Score based)
st.subheader("📈 KPI Scores")
kpi_cols = ['PKT', 'CSAT (Agent Behaviour)', 'Quality', 'Grand Total']
kpi_data = data[[col for col in kpi_cols if col in data.columns]]
st.dataframe(kpi_data, use_container_width=True)

# Show comparison (only for monthly view)
if view_option == "Month" and not data.empty:
    month_list = sorted(df_month['Month'].dropna().unique())
    if selected_month in month_list:
        current_index = month_list.index(selected_month)
        if current_index > 0:
            prev_month = month_list[current_index - 1]
            prev_data = df_month[(df_month['EMP ID'].astype(str) == emp_id) & (df_month['Month'] == prev_month)]
            st.subheader("📉 Comparison with Previous Month")
            if not prev_data.empty:
                compare_df = pd.DataFrame({
                    'Metric': ['PKT', 'CSAT (Agent Behaviour)', 'Quality', 'Grand Total'],
                    'Previous Month': [prev_data.get(col, ["N/A"])[0] for col in ['PKT', 'CSAT (Agent Behaviour)', 'Quality', 'Grand Total']],
                    'Current Month': [data.get(col, ["N/A"])[0] for col in ['PKT', 'CSAT (Agent Behaviour)', 'Quality', 'Grand Total']]
                })
                st.dataframe(compare_df, use_container_width=True)

    # Motivational message
    st.subheader("💡 Motivation")
    grand_total = data['Grand Total'].values[0] if 'Grand Total' in data.columns else None
    if grand_total is not None:
        try:
            grand_total = float(grand_total)
            if grand_total >= 90:
                st.success("Excellent performance! Keep it up! 🌟")
            elif grand_total >= 75:
                st.info("Good job! Aim for even higher! 🚀")
            else:
                st.warning("Let’s improve next month! You got this! 💪")
        except:
            st.info("Keep tracking your progress for motivation!")

    # Display Targets
    st.subheader("🎯 Target Committed")
    targets = get_target_committed(emp_id, selected_month)
    st.write(targets)
