# === app.py ===
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_lottie import st_lottie
import requests
import random
from datetime import datetime

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

# === Load Lottie Animation ===
def load_lottie_url(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

lottie_cheer = load_lottie_url("https://assets2.lottiefiles.com/packages/lf20_snmohqxj.json")

# === Load Sheets ===
@st.cache_data
def load_sheet(name):
    return pd.DataFrame(sheet.worksheet(name).get_all_records())

month_df = load_sheet(SHEET_MONTH)
day_df = load_sheet(SHEET_DAY)
csat_df = load_sheet(SHEET_CSAT)

# === Convert time strings to timedelta for KPI Day ===
def convert_time_columns(df):
    time_cols = ['AHT', 'Wrap', 'Hold', 'Auto On']
    for col in time_cols:
        if col in df.columns:
            # Convert to string first in case some values are already timedeltas
            df[col] = pd.to_timedelta(df[col].astype(str))
    return df

day_df = convert_time_columns(day_df)

# === UI Banner ===
st.markdown("""
    <div style="background: linear-gradient(to right, #0072ff, #00c6ff); padding: 20px 30px; border-radius: 12px; color: white; font-size: 26px; font-weight: bold; margin-bottom: 20px;">
        KPI Dashboard for Champs
    </div>
""", unsafe_allow_html=True)

# === Top Performers Section ===
current_week = datetime.now().isocalendar()[1]

try:
    # Filter for current week and convert Week to string for comparison
    current_week_data = day_df[day_df['Week'].astype(str) == str(current_week)].copy()
    
    if not current_week_data.empty:
        # Calculate mean of timedelta columns
        weekly_metrics = current_week_data.groupby(['EMP ID', 'NAME']).agg({
            'AHT': 'mean',
            'Wrap': 'mean',
            'Hold': 'mean',
            'Auto On': 'mean'
        }).reset_index()
        
        # Get CSAT data for current week
        weekly_csat = csat_df[csat_df['Week'].astype(str) == str(current_week)].groupby(['EMP ID', 'NAME']).agg({
            'CSAT Resolution': 'mean',
            'CSAT Behaviour': 'mean'
        }).reset_index()
        
        # Merge metrics and CSAT
        if not weekly_csat.empty:
            top_data = pd.merge(weekly_metrics, weekly_csat, on=['EMP ID', 'NAME'], how='left')
        else:
            top_data = weekly_metrics.copy()
            top_data['CSAT Resolution'] = 0
            top_data['CSAT Behaviour'] = 0
        
        # Calculate composite score
        top_data['Score'] = (
            (1/top_data['AHT'].dt.total_seconds().clip(lower=1)) +  # Convert to seconds
            (1/top_data['Wrap'].dt.total_seconds().clip(lower=1)) +
            (1/top_data['Hold'].dt.total_seconds().clip(lower=1)) +
            top_data['Auto On'].dt.total_seconds() +
            top_data['CSAT Resolution'].fillna(0) +
            top_data['CSAT Behaviour'].fillna(0)
        )
        
        # Get top 5 performers
        top_5 = top_data.nlargest(5, 'Score')
        
        # Format display
        def format_timedelta(x):
            if pd.isna(x):
                return "00:00:00"
            total_seconds = x.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        top_5_display = top_5[['NAME', 'AHT', 'Wrap', 'Hold', 'Auto On', 'CSAT Resolution', 'CSAT Behaviour']].copy()
        top_5_display.columns = ['Agent', '⏱️ AHT', '📝 Wrap', '🎧 Hold', '🔄 Auto-On', '💬 CSAT Res', '😊 CSAT Beh']
        
        # Apply formatting
        for col in ['⏱️ AHT', '📝 Wrap', '🎧 Hold', '🔄 Auto-On']:
            top_5_display[col] = top_5_display[col].apply(format_timedelta)
        
        for col in ['💬 CSAT Res', '😊 CSAT Beh']:
            top_5_display[col] = top_5_display[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "0.0%")
        
        st.markdown("### 🏆 Current Week Top Performers")
        st.dataframe(
            top_5_display,
            height=182,
            use_container_width=True
        )
    else:
        st.info("No data available for current week yet")
except Exception as e:
    st.warning(f"Couldn't load top performers: {str(e)}")

# === Timeframe Selector ===
time_frame = st.selectbox("Select Timeframe", ["Day", "Week", "Month"])

# === MONTH VIEW ===
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

            st.subheader("Grand Total")
            current_score = emp_data['Grand Total'].values[0]
            st.metric("Grand Total KPI", f"{current_score}")

            if lottie_cheer:
                st_lottie(lottie_cheer, speed=1, height=200, key="cheer")

            if current_score >= 4.5:
                st.success(" Incredible! You're setting new standards!")
            elif current_score >= 4.0:
                st.info(" Great work! Let's aim for the top.")
            elif current_score >= 3.0:
                st.warning(" You're doing good! Let's level up next month.")
            elif current_score >= 2.0:
                st.warning(" Progress in motion. Consistency is key!")
            else:
                st.error(" Don't give up. Big wins come from small efforts.")

            month_order = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
            all_months = [m for m in month_order if m in df['Month'].unique()]
            current_index = all_months.index(month)

            if current_index > 0:
                previous_month = all_months[current_index - 1]
                prev_data = df[(df["EMP ID"].astype(str) == emp_id) & (df["Month"] == previous_month)]

                if not prev_data.empty:
                    prev_score = prev_data["Grand Total"].values[0]
                    diff = round(current_score - prev_score, 2)

                    if diff > 0:
                        st.success(f" You improved by +{diff} points since last month ({previous_month})!")
                    elif diff < 0:
                        st.warning(f" You dropped by {abs(diff)} points since last month ({previous_month}). Let's bounce back!")
                    else:
                        st.info(f"No change from last month ({previous_month}). Keep the momentum going.")
                else:
                    st.info("No data found for previous month.")

            st.subheader("Target Committed for Next Month")
            target_cols = [
                "Target Committed for PKT",
                "Target Committed for CSAT (Agent Behaviour)",
                "Target Committed for Quality"
            ]

            emp_data.columns = emp_data.columns.str.strip()
            if all(col in emp_data.columns for col in target_cols):
                target_table = emp_data[target_cols].T.reset_index()
                target_table.columns = ["Target Metric", "Target"]
                st.markdown(target_table.to_html(index=False, classes="styled-table"), unsafe_allow_html=True)
            else:
                st.info("No target data available.")

# === WEEK VIEW ===
elif time_frame == "Week":
    emp_id = st.text_input("Enter EMP ID")

    day_df["Week"] = pd.to_numeric(day_df["Week"], errors="coerce")
    day_df = day_df.dropna(subset=["Week"])
    day_df["Week"] = day_df["Week"].astype(int)

    selected_week = st.selectbox("Select Week Number", sorted(day_df["Week"].unique()))

    if emp_id and selected_week:
        week_data = day_df[(day_df["EMP ID"].astype(str) == emp_id) & (day_df["Week"] == selected_week)]
        csat_data = csat_df[(csat_df["EMP ID"].astype(str) == emp_id) & (csat_df["Week"] == selected_week)]

        if not week_data.empty:
            emp_name = week_data["NAME"].iloc[0]
            st.markdown(f"### Weekly KPI Data for **{emp_name}** | Week {selected_week}")

            total_calls = week_data["Call Count"].sum()
            avg_aht = pd.to_timedelta(week_data["AHT"]).mean()
            avg_hold = pd.to_timedelta(week_data["Hold"]).mean()
            avg_wrap = pd.to_timedelta(week_data["Wrap"]).mean()
            avg_auto_on = pd.to_timedelta(week_data["Auto On"]).mean()

            def fmt(td): return str(td).split(" ")[-1].split(".")[0]

            kpi_df = pd.DataFrame([
                ("📞 Total Calls", total_calls),
                ("⏱️ AHT", fmt(avg_aht)),
                ("🎧 Hold", fmt(avg_hold)),
                ("📝 Wrap", fmt(avg_wrap)),
                ("🔄 Avg Auto On", fmt(avg_auto_on)),
            ], columns=["Metric", "Value"])

            st.dataframe(kpi_df, use_container_width=True)

            if not csat_data.empty:
                st.subheader("CSAT Scores")
                csat_df_show = pd.DataFrame([
                    ("💬 CSAT Resolution", csat_data["CSAT Resolution"].values[0]),
                    ("😊 CSAT Behaviour", csat_data["CSAT Behaviour"].values[0])
                ], columns=["Type", "Score"])
                st.dataframe(csat_df_show, use_container_width=True)
            else:
                st.info("CSAT data not found for this week.")

            quotes = [
                " Keep up the momentum and aim higher!",
                " Greatness is built on good habits.",
                " Stay consistent — growth follows.",
                " You've got the spark — now fire up more!",
                " Progress is progress, no matter how small."
            ]
            st.info(random.choice(quotes))
        else:
            st.warning("No data found for that EMP ID and week.")

# === DAY VIEW ===
elif time_frame == "Day":
    emp_id = st.text_input("Enter EMP ID")
    selected_date = st.selectbox("Select Date", sorted(day_df["Date"].unique()))

    if emp_id and selected_date:
        row = day_df[(day_df["EMP ID"].astype(str) == emp_id) & (day_df["Date"] == selected_date)]
        if not row.empty:
            row = row.iloc[0]
            emp_name = row['NAME']
            st.markdown(f"### Daily KPI Data for **{emp_name}** | Date: {selected_date}")

            def fmt(t):
                return str(pd.to_timedelta(t)).split(" ")[-1].split(".")[0]

            metrics = [
                ("📞 Call Count", row["Call Count"]),
                ("⏱️ AHT", fmt(row["AHT"])),
                ("🎧 Hold", fmt(row["Hold"])),
                ("📝 Wrap", fmt(row["Wrap"])),
                ("🔄 Auto On", fmt(row["Auto On"])),
                ("💬 CSAT Resolution", row["CSAT Resolution"]),
                ("😊 CSAT Behaviour", row["CSAT Behaviour"]),
            ]

            daily_df = pd.DataFrame(metrics, columns=["Metric", "Value"])
            st.dataframe(daily_df, use_container_width=True)
        else:
            st.info("No data found for that EMP ID and date.")
