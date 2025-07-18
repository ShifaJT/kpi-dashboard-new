# === app.py ===
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_lottie import st_lottie
import requests

# === CONFIG ===
SHEET_ID = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"
SHEET_MONTH = "KPI Month"
SHEET_DAY = "KPI Day"
SHEET_CSAT = "CSAT Score"

# === Google Auth ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)

# === Load Lottie ===
def load_lottie_url(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

lottie_cheer = load_lottie_url("https://assets2.lottiefiles.com/packages/lf20_snmohqxj.json")

# === Load Data ===
@st.cache_data
def load_sheet(name):
    return pd.DataFrame(sheet.worksheet(name).get_all_records())

month_df = load_sheet(SHEET_MONTH)
day_df = load_sheet(SHEET_DAY)
csat_df = load_sheet(SHEET_CSAT)

# === UI Styling ===
st.markdown("""
    <div style="background: linear-gradient(to right, #0072ff, #00c6ff); padding: 20px 30px; border-radius: 12px; color: white; font-size: 26px; font-weight: bold; margin-bottom: 20px;">
        🚀 KPI Dashboard for Champs
    </div>
""", unsafe_allow_html=True)

# === Time Filter ===
time_frame = st.selectbox("Select Timeframe", ["Day", "Week", "Month"])

# === Month Logic ===
if time_frame == "Month":
    df = month_df
    df.columns = df.columns.str.strip()
    emp_id = st.text_input("Enter EMP ID (e.g., 1070)")
    month = st.selectbox("Select Month", sorted(df['Month'].unique(), key=lambda m: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].index(m)))

    if emp_id and month:
        emp_data = df[(df["EMP ID"].astype(str) == emp_id) & (df["Month"] == month)]

        if emp_data.empty:
            st.warning("No data found for that EMP ID and month.")
        else:
            emp_name = emp_data["NAME"].values[0]
            st.markdown(f"### KPI Data for **{emp_name}** (EMP ID: {emp_id}) | Month: **{month}**")

            # === Performance Metrics ===
            st.subheader("Performance Metrics")
            perf_map = [
                ("Avg hold time used", "Hold", "HH:MM:SS"),
                ("Avg time taken to wrap the call", "Wrap", "HH:MM:SS"),
                ("Avg duration of champ using auto on", "Auto-On", "HH:MM:SS"),
                ("Shift adherence for the month", "Schedule Adherence", "Percentage"),
                ("Customer feedback on resolution given", "Resolution CSAT", "Percentage"),
                ("Customer feedback on champ behaviour", "Agent Behaviour", "Percentage"),
                ("Avg Quality Score achieved for the month", "Quality", "Percentage"),
                ("Process Knowledge Test", "PKT", "Percentage"),
                ("Number of sick and unplanned leaves", "SL + UPL", "Days"),
                ("Number of days logged in", "LOGINS", "Days"),
            ]

            perf_table = []
            for desc, metric, unit in perf_map:
                value = emp_data[metric].values[0] if metric in emp_data else "-"
                perf_table.append({"Description": desc, "Metric Name": metric, "Value": value, "Unit": unit})

            st.dataframe(pd.DataFrame(perf_table), use_container_width=True)

            # === KPI Scores ===
            st.subheader("KPI Scores")
            kpi_map = [
                ("0%", "Hold KPI Score"),
                ("30%", "Auto-On KPI Score"),
                ("10%", "Schedule Adherence KPI Score"),
                ("10%", "Resolution CSAT KPI Score"),
                ("20%", "Agent Behaviour KPI Score"),
                ("20%", "Quality KPI Score"),
                ("10%", "PKT KPI Score")
            ]

            kpi_table = []
            for weight, kpi_metric in kpi_map:
                score = emp_data[kpi_metric].values[0] if kpi_metric in emp_data else "-"
                kpi_table.append({"Weightage": weight, "KPI Metrics": kpi_metric, "Score": score})

            st.dataframe(pd.DataFrame(kpi_table), use_container_width=True)

            # === Grand Total ===
            st.subheader("Grand Total")
            current_score = emp_data['Grand Total'].values[0]
            st.metric("Grand Total KPI", f"{current_score}")

            if lottie_cheer:
                st_lottie(lottie_cheer, speed=1, height=200, key="cheer")

            # === Medals ===
            if current_score >= 4.5:
                st.success("🏅 Gold Medalist! You're setting the benchmark.")
            elif current_score >= 4.0:
                st.info("🥈 Silver Medalist – Great work!")
            elif current_score >= 3.5:
                st.warning("🥉 Bronze Medalist – Keep improving!")
            else:
                st.error("💡 No medal yet — push forward and grow!")

# === Week Logic ===
elif time_frame == "Week":
    emp_id = st.text_input("Enter EMP ID")
    week_num = st.selectbox("Select Week Number", sorted(day_df['Week'].unique()))

    if emp_id and week_num:
        week_data = day_df[(day_df["EMP ID"].astype(str) == emp_id) & (day_df["Week"] == week_num)]
        if not week_data.empty:
            st.subheader(f"Weekly KPI Data (Week {week_num})")

            # Call count
            total_calls = week_data["Call Count"].sum()

            # Averages
            def avg_time(col):
                return pd.to_timedelta(week_data[col]).mean().components

            aht = pd.to_timedelta(week_data["AHT"]).mean()
            hold = pd.to_timedelta(week_data["Hold"]).mean()
            wrap = pd.to_timedelta(week_data["Wrap"]).mean()

            def fmt(t):
                return str(t).split(" ")[-1].split(".")[0]  # remove days + microsec

            week_metrics = pd.DataFrame({
                "Metric": ["Call Count", "AHT", "Hold", "Wrap"],
                "Value": [total_calls, fmt(aht), fmt(hold), fmt(wrap)]
            })
            st.dataframe(week_metrics, use_container_width=True)

            # CSAT Scores
            csat = csat_df[(csat_df["EMP ID"].astype(str) == emp_id) & (csat_df["Week"] == week_num)]
            if not csat.empty:
                csat_score = csat[["CSAT Resolution", "CSAT Behaviour"]].T.reset_index()
                csat_score.columns = ["Type", "Score"]
                st.subheader("CSAT Scores")
                st.dataframe(csat_score, use_container_width=True)
            else:
                st.info("No CSAT data available.")

# === Day Logic ===
elif time_frame == "Day":
    emp_id = st.text_input("Enter EMP ID")
    selected_date = st.selectbox("Select Date", sorted(day_df["Date"].unique()))

    if emp_id and selected_date:
        row = day_df[(day_df["EMP ID"].astype(str) == emp_id) & (day_df["Date"] == selected_date)]
        if not row.empty:
            row = row.iloc[0]
            st.subheader(f"Daily KPI Data - {selected_date}")
            metrics = [
                ("Call Count", row["Call Count"]),
                ("AHT", str(pd.to_timedelta(row["AHT"]).components).split(" ")[-1].split(".")[0]),
                ("Hold", str(pd.to_timedelta(row["Hold"]).components).split(" ")[-1].split(".")[0]),
                ("Wrap", str(pd.to_timedelta(row["Wrap"]).components).split(" ")[-1].split(".")[0]),
                ("CSAT Resolution", row["CSAT Resolution"]),
                ("CSAT Behaviour", row["CSAT Behaviour"]),
            ]
            daily_df = pd.DataFrame(metrics, columns=["Metric", "Value"])
            st.dataframe(daily_df, use_container_width=True)
        else:
            st.info("No data found for that EMP ID and date.")
