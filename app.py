import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil import parser
import calendar

# --- Google Sheet Connection ---
def load_sheet(sheet_id, sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.worksheet(sheet_name)
    data = pd.DataFrame(worksheet.get_all_records())
    return data

# --- Load Data ---
sheet_id = "1BR1G5_gTvwXZG5e3uegkOp2AUL6vBzv6cYzPbC-epic"
df_month = load_sheet(sheet_id, "KPI Month")
df_day = load_sheet(sheet_id, "KPI Day")
df_csat = load_sheet(sheet_id, "CSAT Score")

# --- Page Config ---
st.set_page_config(page_title="KPI Dashboard", layout="centered")

st.markdown("<h1 style='display: flex; align-items: center; gap: 10px;'>📊 KPI Dashboard</h1>", unsafe_allow_html=True)

# --- Sidebar Inputs ---
emp_id = st.text_input("Enter your EMP ID:", "")
view_type = st.selectbox("Select View Type:", ["Month", "Week", "Day"])

# --- View Type Filters ---
if view_type == "Month":
    month = st.selectbox("Select Month:", df_month["Month"].unique())
elif view_type == "Week":
    week = st.selectbox("Select Week:", sorted(df_day["Week"].unique()))
else:
    date_str = st.selectbox("Select Day:", sorted(df_day["Date"].unique()))
    try:
        selected_date = datetime.strptime(date_str, "%m/%d/%Y")
    except Exception:
        st.error("Date parsing failed. Please check the date format in the sheet.")

# --- Filter Functions ---
def get_month_data(emp_id, month):
    return df_month[(df_month["EMP ID"] == int(emp_id)) & (df_month["Month"] == month)]

def get_day_data(emp_id, selected_date):
    return df_day[(df_day["EMP ID"] == int(emp_id)) & (df_day["Date"] == selected_date.strftime("%m/%d/%Y"))]

def get_week_data(emp_id, week):
    day_part = df_day[(df_day["EMP ID"] == int(emp_id)) & (df_day["Week"] == week)]
    csat_part = df_csat[(df_csat["EMP ID"] == int(emp_id)) & (df_csat["Week"] == week)]
    return pd.merge(day_part, csat_part, on=["EMP ID", "Week", "NAME"], how="left")

# --- Display Logic ---
if emp_id:
    if view_type == "Month" and month:
        data = get_month_data(emp_id, month)

        if not data.empty:
            st.subheader("📌 Performance Metrics")
            perf = data[["Call Count", "AHT", "Hold", "Wrap"]].T.reset_index()
            perf.columns = ["Metric Name", "Value"]
            perf["Description"] = ["Total Calls", "Average Handle Time", "Hold Time", "Wrap Time"]
            perf["Unit"] = ["Calls", "min", "min", "min"]
            st.dataframe(perf[["Description", "Metric Name", "Value", "Unit"]], use_container_width=True)

            st.subheader("🏆 KPI Metrics")
            kpi = data[["PKT Score", "CSAT Behaviour Score", "Quality Score"]].T.reset_index()
            kpi.columns = ["KPI Metrics", "Score"]
            kpi["Weightage"] = [40, 30, 30]
            st.dataframe(kpi[["Weightage", "KPI Metrics", "Score"]], use_container_width=True)

            st.subheader("📈 Month-over-Month Comparison")
            months = list(df_month["Month"].unique())
            if month in months:
                idx = months.index(month)
                prev_month = months[idx - 1] if idx > 0 else None
                if prev_month:
                    prev_data = get_month_data(emp_id, prev_month)
                    if not prev_data.empty:
                        current_score = data["Grand Total KPI"].values[0]
                        prev_score = prev_data["Grand Total KPI"].values[0]
                        change = round(current_score - prev_score, 2)
                        st.success(f"Compared to {prev_month}, your KPI changed by {change} points.")

            st.subheader("💬 Motivational Quote")
            score = data["Grand Total KPI"].values[0]
            if score >= 90:
                msg = "🚀 Outstanding! Keep up the excellent work!"
            elif score >= 75:
                msg = "👏 Great job! Let’s push for even better!"
            elif score >= 60:
                msg = "😊 Good effort. A little more focus and you’ll be there!"
            else:
                msg = "💡 Don’t give up! Every expert was once a beginner."
            st.info(msg)

            st.subheader("🎯 Target Committed")
            target = data[[
                "Target Committed for PKT",
                "Target Committed for CSAT (Agent Behaviour)",
                "Target Committed for Quality"
            ]].T.reset_index()
            target.columns = ["Target Area", "Target"]
            st.dataframe(target, use_container_width=True)
        else:
            st.warning("No data found for selected EMP ID and Month.")

    elif view_type == "Day" and date_str:
        data = get_day_data(emp_id, selected_date)
        if not data.empty:
            st.dataframe(data)
        else:
            st.warning("No data found for this day.")

    elif view_type == "Week" and week:
        data = get_week_data(emp_id, week)
        if not data.empty:
            st.dataframe(data)
        else:
            st.warning("No data found for this week.")
