import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets access
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["google_service_account"], scopes=SCOPES
)
client = gspread.authorize(creds)
sheet = client.open("YTD KPI sheet")

# Load data
kpi_month_df = pd.DataFrame(sheet.worksheet("KPI Month").get_all_records())
kpi_day_df = pd.DataFrame(sheet.worksheet("KPI Day").get_all_records())
csat_df = pd.DataFrame(sheet.worksheet("CSAT Score").get_all_records())

# Convert and clean data
def parse_time_to_seconds(t):
    try:
        t = t.strip()
        h, m, s = map(int, t.split(":"))
        return h * 3600 + m * 60 + s
    except:
        return np.nan

def seconds_to_hhmmss(seconds):
    if pd.isna(seconds):
        return "N/A"
    return str(pd.to_timedelta(seconds, unit='s'))

def safe_percent(val):
    try:
        return float(str(val).replace('%', ''))
    except:
        return np.nan

kpi_day_df['Date'] = pd.to_datetime(kpi_day_df['Date'], format='%m/%d/%Y')
kpi_day_df['AHT_sec'] = kpi_day_df['AHT'].apply(parse_time_to_seconds)
kpi_day_df['Hold_sec'] = kpi_day_df['Hold'].apply(parse_time_to_seconds)
kpi_day_df['Wrap_sec'] = kpi_day_df['Wrap'].apply(parse_time_to_seconds)
csat_df['CSAT Resolution'] = csat_df['CSAT Resolution'].apply(safe_percent)
csat_df['CSAT Behaviour'] = csat_df['CSAT Behaviour'].apply(safe_percent)

# UI Elements
st.title("📊 KPI Dashboard")
emp_id = st.text_input("Enter EMP ID")
view_type = st.selectbox("Select View Type", ["Month", "Week", "Day"])

if emp_id:
    emp_id = emp_id.strip()

    if view_type == "Month":
        month = st.selectbox("Select Month", sorted(kpi_month_df['Month'].unique()))
        emp_data = kpi_month_df[(kpi_month_df['EMP ID'] == emp_id) & (kpi_month_df['Month'] == month)]

        if not emp_data.empty:
            emp_row = emp_data.iloc[0]
            st.subheader("Performance")
            perf_data = pd.DataFrame({
                "Description": ["Call Count", "AHT", "Hold", "Wrap", "CSAT Resolution", "CSAT Behaviour"],
                "Metric Name": ["Call Count", "AHT", "Hold", "Wrap", "CSAT Resolution", "CSAT Behaviour"],
                "Value": [emp_row['Call Count'], emp_row['AHT'], emp_row['Hold'], emp_row['Wrap'], emp_row['CSAT Resolution'], emp_row['CSAT Behaviour']],
                "Unit": ["Calls", "HH:MM:SS", "HH:MM:SS", "HH:MM:SS", "%", "%"]
            })
            st.table(perf_data)

            st.subheader("KPI Scores")
            kpi_data = pd.DataFrame({
                "Weightage": [30, 30, 40],
                "KPI Metrics": ["PKT", "CSAT (Agent Behaviour)", "Quality"],
                "Score": [emp_row['PKT'], emp_row['CSAT (Agent Behaviour)'], emp_row['Quality']]
            })
            st.table(kpi_data)

            # Month Comparison
            prev_month = sorted(kpi_month_df['Month'].unique())
            current_index = prev_month.index(month)
            if current_index > 0:
                previous = prev_month[current_index - 1]
                prev_data = kpi_month_df[(kpi_month_df['EMP ID'] == emp_id) & (kpi_month_df['Month'] == previous)]
                if not prev_data.empty:
                    st.subheader("📈 Month-over-Month Comparison")
                    st.write(f"Previous Month ({previous}) Grand Total: {prev_data.iloc[0]['Grand Total']}")
                    st.write(f"Current Month ({month}) Grand Total: {emp_row['Grand Total']}")

            # Motivational Message
            st.subheader("💡 Motivation")
            score = emp_row['Grand Total']
            if score >= 85:
                st.success("Excellent work! Keep the momentum strong.")
            elif score >= 70:
                st.info("You're doing well, strive for more!")
            else:
                st.warning("Focus on improvement — you've got this!")

            # Target Committed
            st.subheader("🎯 Target Committed")
            st.markdown(f"- **PKT**: {emp_row.get('Target Committed for PKT', 'N/A')}")
            st.markdown(f"- **CSAT (Agent Behaviour)**: {emp_row.get('Target Committed for CSAT (Agent Behaviour)', 'N/A')}")
            st.markdown(f"- **Quality**: {emp_row.get('Target Committed for Quality', 'N/A')}")

    elif view_type == "Week":
        week = st.selectbox("Select Week", sorted(kpi_day_df['Week'].unique()))
        week_df = kpi_day_df[(kpi_day_df['EMP ID'] == emp_id) & (kpi_day_df['Week'] == str(week))]

        if not week_df.empty:
            call_count = week_df['Call Count'].astype(int).sum()
            avg_aht = seconds_to_hhmmss(week_df['AHT_sec'].mean())
            avg_hold = seconds_to_hhmmss(week_df['Hold_sec'].mean())
            avg_wrap = seconds_to_hhmmss(week_df['Wrap_sec'].mean())

            csat_week = csat_df[(csat_df['EMP ID'] == emp_id) & (csat_df['Week'] == str(week))]
            csat_res = csat_week['CSAT Resolution'].values[0] if not csat_week.empty else "N/A"
            csat_beh = csat_week['CSAT Behaviour'].values[0] if not csat_week.empty else "N/A"

            st.subheader("Performance")
            week_perf = pd.DataFrame({
                "Description": ["Call Count", "AHT", "Hold", "Wrap", "CSAT Resolution", "CSAT Behaviour"],
                "Metric Name": ["Call Count", "AHT", "Hold", "Wrap", "CSAT Resolution", "CSAT Behaviour"],
                "Value": [call_count, avg_aht, avg_hold, avg_wrap, f"{csat_res}%", f"{csat_beh}%"],
                "Unit": ["Calls", "HH:MM:SS", "HH:MM:SS", "HH:MM:SS", "%", "%"]
            })
            st.table(week_perf)

    elif view_type == "Day":
        day = st.date_input("Select Date")
        day_df = kpi_day_df[(kpi_day_df['EMP ID'] == emp_id) & (kpi_day_df['Date'] == pd.to_datetime(day))]

        if not day_df.empty:
            row = day_df.iloc[0]
            st.subheader("Performance")
            st.table(pd.DataFrame({
                "Description": ["Call Count", "AHT", "Hold", "Wrap", "CSAT Resolution", "CSAT Behaviour"],
                "Metric Name": ["Call Count", "AHT", "Hold", "Wrap", "CSAT Resolution", "CSAT Behaviour"],
                "Value": [row['Call Count'], row['AHT'], row['Hold'], row['Wrap'], row['CSAT Resolution'], row['CSAT Behaviour']],
                "Unit": ["Calls", "HH:MM:SS", "HH:MM:SS", "HH:MM:SS", "%", "%"]
            }))
