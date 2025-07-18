import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# === CONFIG ===
SHEET_ID = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"

# === Google Auth from Secrets ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(creds)

@st.cache_data
def load_sheet(sheet_name):
    sheet = client.open_by_key(SHEET_ID).worksheet(sheet_name)
    return pd.DataFrame(sheet.get_all_records())

# Load all sheets
df_month = load_sheet("KPI Month")
df_day = load_sheet("KPI Day")
df_csat = load_sheet("CSAT Score")

# === Preprocess ===
df_month.columns = df_month.columns.str.strip()
df_day.columns = df_day.columns.str.strip()
df_csat.columns = df_csat.columns.str.strip()

# Convert date column
df_day['Date'] = pd.to_datetime(df_day['Date'], dayfirst=True, errors='coerce')
df_day['Week'] = df_day['Week'].astype(str)
df_csat['Week'] = df_csat['Week'].astype(str)

# === Styling ===
st.markdown("""
    <style>
    .styled-table {
        font-size: 16px;
        color: #111;
        width: 100%;
        border-collapse: collapse;
    }
    .styled-table th, .styled-table td {
        border: 1px solid #ddd;
        padding: 10px 14px;
        text-align: left;
    }
    .styled-table tr:nth-child(even) {
        background-color: #f8f8f8;
    }
    .styled-table th {
        background-color: #eaeaea;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# === UI Title ===
st.title("KPI Dashboard for Champs")

# === Timeframe Filter ===
time_frame = st.selectbox("Select Timeframe", ["Day", "Week", "Month"])
emp_id = st.text_input("Enter EMP ID (e.g., 1070)")

# --- MONTH VIEW ---
if time_frame == "Month":
    month = st.selectbox("Select Month", sorted(df_month['Month'].unique(), key=lambda m: [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ].index(m)))
    
    if emp_id and month:
        emp_data = df_month[(df_month["EMP ID"].astype(str) == emp_id) & (df_month["Month"] == month)]
        # ... (keep your full working monthly block here unchanged)
        # Paste your existing logic from "KPI Month" for display, comparison, target committed etc.

# --- WEEK VIEW ---
elif time_frame == "Week":
    available_weeks = sorted(df_day['Week'].unique())
    selected_week = st.selectbox("Select Week", available_weeks)
    
    if emp_id and selected_week:
        filtered = df_day[(df_day["EMP ID"].astype(str) == emp_id) & (df_day["Week"] == selected_week)]
        csat_row = df_csat[(df_csat["EMP ID"].astype(str) == emp_id) & (df_csat["Week"] == selected_week)]

        if filtered.empty:
            st.warning("No data found for that EMP ID and week.")
        else:
            emp_name = filtered["NAME"].iloc[0]
            st.markdown(f"### KPI Data for **{emp_name}** (EMP ID: {emp_id}) | Week: **{selected_week}**")

            total_calls = filtered["Call Count"].sum()
            avg_aht = filtered["AHT"].mode().iloc[0] if not filtered["AHT"].isnull().all() else "-"
            avg_hold = filtered["Hold"].mode().iloc[0] if not filtered["Hold"].isnull().all() else "-"
            avg_wrap = filtered["Wrap"].mode().iloc[0] if not filtered["Wrap"].isnull().all() else "-"
            csat_res = csat_row["CSAT Resolution"].iloc[0] if not csat_row.empty else "-"
            csat_beh = csat_row["CSAT Behaviour"].iloc[0] if not csat_row.empty else "-"

            weekly_table = pd.DataFrame([
                ["Total Calls", total_calls],
                ["Average AHT", avg_aht],
                ["Average Hold", avg_hold],
                ["Average Wrap", avg_wrap],
                ["CSAT Resolution", csat_res],
                ["CSAT Behaviour", csat_beh]
            ], columns=["Metric", "Value"])

            st.markdown(weekly_table.to_html(index=False, classes="styled-table"), unsafe_allow_html=True)

# --- DAY VIEW ---
elif time_frame == "Day":
    available_dates = df_day["Date"].dt.date.unique()
    selected_date = st.date_input("Select Date", min_value=min(available_dates), max_value=max(available_dates))

    if emp_id:
        filtered = df_day[(df_day["EMP ID"].astype(str) == emp_id) & (df_day["Date"].dt.date == selected_date)]

        if filtered.empty:
            st.warning("No data found for that EMP ID and date.")
        else:
            emp_name = filtered["NAME"].iloc[0]
            row = filtered.iloc[0]

            st.markdown(f"### KPI Data for **{emp_name}** (EMP ID: {emp_id}) | Date: **{selected_date}**")

            day_table = pd.DataFrame([
                ["Call Count", row["Call Count"]],
                ["AHT", row["AHT"]],
                ["Hold", row["Hold"]],
                ["Wrap", row["Wrap"]],
                ["CSAT Resolution", row["CSAT Resolution"]],
                ["CSAT Behaviour", row["CSAT Behaviour"]]
            ], columns=["Metric", "Value"])

            st.markdown(day_table.to_html(index=False, classes="styled-table"), unsafe_allow_html=True)
