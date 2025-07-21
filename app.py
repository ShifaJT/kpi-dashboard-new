import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

# Load Sheets
sheet = client.open_by_url("YOUR_GOOGLE_SHEET_URL")
day_data = pd.DataFrame(sheet.worksheet("KPI Day").get_all_records())
csat_data = pd.DataFrame(sheet.worksheet("CSAT Score").get_all_records())
month_data = pd.DataFrame(sheet.worksheet("KPI Data").get_all_records())

# Title
st.set_page_config(page_title="📊 KPI Dashboard", layout="wide")
st.title("📞 Call Performance Dashboard")

view_type = st.selectbox("Select View", ["Day", "Week", "Month"])

emp_ids = day_data["EMP ID"].unique()
selected_emp = st.selectbox("Select EMP ID", emp_ids)

# === Helper Functions ===
def fmt(val):
    if pd.isnull(val):
        return "-"
    if isinstance(val, pd.Timedelta):
        return str(val).split(".")[0]
    return str(val)

def convert_to_timedelta(series):
    return pd.to_timedelta(series.fillna("0:00:00"))

# === DAY VIEW ===
if view_type == "Day":
    st.subheader("📅 Day-wise Performance")
    selected_date = st.date_input("Select Date")

    day_data["Date"] = pd.to_datetime(day_data["Date"]).dt.date
    filtered = day_data[(day_data["EMP ID"] == selected_emp) & (day_data["Date"] == selected_date)]

    if filtered.empty:
        st.warning("No data found for this date.")
    else:
        row = filtered.iloc[0]
        st.metric("📞 Calls", row["Call Count"])
        st.metric("⏱️ AHT", fmt(pd.to_timedelta(row["AHT"])))
        st.metric("🎧 Hold", fmt(pd.to_timedelta(row["Hold"])))
        st.metric("🧹 Wrap", fmt(pd.to_timedelta(row["Wrap"])))
        st.metric("⚙️ Auto On", fmt(pd.to_timedelta(row["Auto On"])))
        st.metric("😊 CSAT Resolution", row["CSAT Resolution"])
        st.metric("🗣️ CSAT Behaviour", row["CSAT Behaviour"])

# === WEEK VIEW ===
elif view_type == "Week":
    st.subheader("📆 Week-wise Performance")
    week_number = st.number_input("Enter Week Number (e.g., 27)", min_value=1, max_value=53)

    # Convert and filter
    day_data["Date"] = pd.to_datetime(day_data["Date"])
    day_data["Week"] = day_data["Date"].dt.isocalendar().week
    week_filtered = day_data[(day_data["EMP ID"] == selected_emp) & (day_data["Week"] == week_number)]

    if week_filtered.empty:
        st.warning("No data found for this week.")
    else:
        total_calls = week_filtered["Call Count"].sum()
        avg_aht = convert_to_timedelta(week_filtered["AHT"]).mean()
        avg_hold = convert_to_timedelta(week_filtered["Hold"]).mean()
        avg_wrap = convert_to_timedelta(week_filtered["Wrap"]).mean()
        avg_auto_on = convert_to_timedelta(week_filtered["Auto On"]).mean()

        st.metric("📞 Total Calls", total_calls)
        st.metric("⏱️ Avg AHT", fmt(avg_aht))
        st.metric("🎧 Avg Hold", fmt(avg_hold))
        st.metric("🧹 Avg Wrap", fmt(avg_wrap))
        st.metric("⚙️ Avg Auto On", fmt(avg_auto_on))

        # CSAT Score lookup
        csat_data["Week"] = csat_data["Week"].astype(int)
        csat_filtered = csat_data[(csat_data["EMP ID"] == selected_emp) & (csat_data["Week"] == week_number)]

        if not csat_filtered.empty:
            csat_row = csat_filtered.iloc[0]
            st.metric("😊 CSAT Resolution", csat_row.get("CSAT Resolution", "-"))
            st.metric("🗣️ CSAT Behaviour", csat_row.get("CSAT Behaviour", "-"))

# === MONTH VIEW ===
elif view_type == "Month":
    st.subheader("📆 Monthly Performance")
    selected_month = st.selectbox("Select Month", month_data["Month"].unique())

    # Fetch row
    month_filtered = month_data[(month_data["EMP ID"] == selected_emp) & (month_data["Month"] == selected_month)]

    if month_filtered.empty:
        st.warning("No data found for this month.")
    else:
        row = month_filtered.iloc[0]
        st.markdown(f"**Name:** {row['NAME']}")

        kpis = {
            "Hold Score": "🎧 Hold",
            "Wrap Score": "🧹 Wrap",
            "Auto-On Score": "⚙️ Auto On",
            "Schedule Adherence Score": "📅 Adherence",
            "Resolution CSAT Score": "😊 CSAT Resolution",
            "Agent Behaviour Score": "🗣️ CSAT Behaviour",
            "Quality Score": "✅ Quality",
            "PKT Score": "📘 PKT",
            "Login Score": "🔐 Login",
        }

        total_score = 0
        for kpi, label in kpis.items():
            val = row.get(kpi, "-")
            total_score += float(val) if str(val).replace(".", "", 1).isdigit() else 0
            st.metric(label, val)

        avg_score = total_score / len(kpis)
        st.markdown("---")
        st.subheader("🏆 Grand Total KPI Score")
        st.metric("📈 Achieved", round(avg_score, 2))

        # Motivational message
        if avg_score >= 4.5:
            st.success("🌟 Outstanding performance! Keep leading the way!")
        elif avg_score >= 4:
            st.info("💪 Great job! A little push for excellence!")
        elif avg_score >= 3.2:
            st.warning("✨ Fair effort, you can rise higher!")
        else:
            st.error("🚀 Let's focus and bounce back stronger!")

