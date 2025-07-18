import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Load Google Sheets using gspread and pandas
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    sh = client.open_by_key(sheet_id)
    worksheet = sh.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

# Google Sheets API setup using secrets.toml
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=scope)
client = gspread.authorize(creds)

# Load all sheets
sheet_id = "1kgdq2UwXQ1fIox0_m8_t52Ha7_vOeFucXs5_xMb69Y0"
month_df = load_sheet(sheet_id, "KPI Month")
day_df = load_sheet(sheet_id, "KPI Day")
csat_df = load_sheet(sheet_id, "CSAT Score")

# Streamlit UI
st.title("📊 KPI Dashboard")

emp_id = st.text_input("Enter your EMP ID")

if emp_id:
    view_type = st.selectbox("Select View", ["Month", "Week", "Day"])

    if view_type == "Month":
        emp_data = month_df[month_df['EMP ID'] == emp_id]
        months = emp_data['Month'].dropna().unique()
        selected_month = st.selectbox("Select Month", months)

        month_data = emp_data[emp_data['Month'] == selected_month]

        if not month_data.empty:
            st.subheader("Performance Metrics")
            st.dataframe(month_data[['Metric Name', 'Value', 'Unit']])

            st.subheader("KPI Scores")
            st.dataframe(month_data[['KPI Metrics', 'Score', 'Weightage']])

            st.subheader("Month-over-Month Comparison")
            all_months = sorted(emp_data['Month'].dropna().unique())
            current_index = list(all_months).index(selected_month)
            if current_index > 0:
                previous_month = all_months[current_index - 1]
                current_score = month_data['Grand Total KPI'].values[0]
                prev_score = emp_data[emp_data['Month'] == previous_month]['Grand Total KPI'].values[0]
                change = current_score - prev_score
                st.metric(label="KPI Score Change", value=f"{current_score}", delta=f"{change:.2f}")

            st.subheader("Motivational Message")
            if current_score >= 90:
                st.success("🌟 Outstanding work! Keep exceeding expectations!")
            elif current_score >= 75:
                st.info("👍 Great job! You're doing well. Aim higher!")
            else:
                st.warning("🚀 Keep pushing! You've got potential to grow!")

            st.subheader("🎯 Target Committed")
            st.write("Target Committed for PKT:", month_data['Target Committed for PKT'].values[0])
            st.write("Target Committed for CSAT (Agent Behaviour):", month_data['Target Committed for CSAT (Agent Behaviour)'].values[0])
            st.write("Target Committed for Quality:", month_data['Target Committed for Quality'].values[0])

    elif view_type == "Week":
        emp_data = day_df[day_df['EMP ID'] == emp_id]
        csat_data = csat_df[csat_df['EMP ID'] == emp_id]
        available_weeks = emp_data['Week'].dropna().unique()
        selected_week = st.selectbox("Select Week", available_weeks)

        week_data = emp_data[emp_data['Week'] == selected_week]
        if not week_data.empty:
            st.subheader("Performance Metrics")
            performance = {
                'Call Count': week_data['Call Count'].astype(float).sum(),
                'AHT': week_data['AHT'].astype(float).mean(),
                'Hold': week_data['Hold'].astype(float).mean(),
                'Wrap': week_data['Wrap'].astype(float).mean()
            }
            st.dataframe(pd.DataFrame(performance.items(), columns=['Metric Name', 'Value']))

            st.subheader("KPI Scores")
            csat_week = csat_data[csat_data['Week'] == selected_week]
            if not csat_week.empty:
                st.dataframe(csat_week[['CSAT Resolution', 'CSAT Behaviour']])
            else:
                st.warning("No CSAT data found for this week.")

    elif view_type == "Day":
        emp_data = day_df[day_df['EMP ID'] == emp_id]
        emp_data['Date'] = pd.to_datetime(emp_data['Date'], format="%m/%d/%Y", errors='coerce')
        available_dates = emp_data['Date'].dropna().dt.date.unique()

        if len(available_dates) > 0:
            selected_date = st.date_input("Select Date", min_value=min(available_dates), max_value=max(available_dates))
            day_data = emp_data[emp_data['Date'].dt.date == selected_date]

            if not day_data.empty:
                st.subheader("Performance Metrics")
                st.dataframe(day_data[['Call Count', 'AHT', 'Hold', 'Wrap']])

                st.subheader("KPI Scores")
                st.write("CSAT Resolution:", day_data['CSAT Resolution'].values[0])
                st.write("CSAT Behaviour:", day_data['CSAT Behaviour'].values[0])
            else:
                st.warning("No data found for selected date.")
        else:
            st.warning("No valid dates available for the selected employee.")
