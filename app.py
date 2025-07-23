# === COMPLETE KPI DASHBOARD SOLUTION ===
import streamlit as st
import pandas as pd
import gspread
import numpy as np
from google.oauth2.service_account import Credentials
from streamlit_lottie import st_lottie
import requests
import random
from datetime import datetime, timedelta

# === CONFIGURATION ===
SHEET_ID = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"
SHEET_MONTH = "KPI Month"
SHEET_DAY = "KPI Day"
SHEET_CSAT = "CSAT Score"

# === GOOGLE SHEETS AUTHENTICATION ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)

# === LOAD LOTTIE ANIMATION ===
def load_lottie_url(url):
    r = requests.get(url)
    return r.json() if r.status_code == 200 else None

lottie_cheer = load_lottie_url("https://assets2.lottiefiles.com/packages/lf20_snmohqxj.json")
lottie_trophy = load_lottie_url("https://assets1.lottiefiles.com/packages/lf20_0clcyar4.json")

# === LOAD SHEET DATA ===
@st.cache_data(ttl=3600)
def load_sheet(name):
    return pd.DataFrame(sheet.worksheet(name).get_all_records())

month_df = load_sheet(SHEET_MONTH)
day_df = load_sheet(SHEET_DAY)
csat_df = load_sheet(SHEET_CSAT)

# === BULLETPROOF TIME CONVERSION ===
def strict_time_to_seconds(time_val):
    try:
        if pd.isna(time_val) or str(time_val).strip() in ['', '0', '00:00', '00:00:00']:
            return 0.0
        if isinstance(time_val, (int, float)):
            return float(time_val)
        time_str = str(time_val).strip()
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 3:
                return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0])*60 + float(parts[1])
        if time_str.replace('.','',1).isdigit():
            return float(time_str)
        return 0.0
    except:
        return 0.0

time_columns = ['AHT', 'Wrap', 'Hold', 'Auto On']
for col in time_columns:
    if col in day_df.columns:
        day_df[f"{col}_sec"] = day_df[col].apply(strict_time_to_seconds)
        day_df[f"{col}_sec"] = pd.to_numeric(day_df[f"{col}_sec"], errors='coerce').fillna(0)

# === CLEAN CSAT COLUMNS TO PREVENT ERROR ===
csat_df['CSAT Resolution'] = pd.to_numeric(csat_df['CSAT Resolution'], errors='coerce').fillna(0)
csat_df['CSAT Behaviour'] = pd.to_numeric(csat_df['CSAT Behaviour'], errors='coerce').fillna(0)

# === DASHBOARD UI ===
st.markdown("""
<div style="background: linear-gradient(to right, #0072ff, #00c6ff); padding: 20px 30px; border-radius: 12px; color: white; font-size: 26px; font-weight: bold; margin-bottom: 20px;">
    🏆 KPI Dashboard for Champions 🏆
</div>
""", unsafe_allow_html=True)

# === TOP PERFORMERS SECTION ===
st.markdown("### 🏅 Top Performers of the Week")

if not day_df.empty:
    current_week = datetime.now().isocalendar()[1]
    day_df['Date'] = pd.to_datetime(day_df['Date'], errors='coerce')
    day_df['Week'] = day_df['Date'].dt.isocalendar().week
    current_data = day_df[day_df['Week'] == current_week]
    current_week_str = str(current_week)

    avg_metrics = current_data.groupby(['EMP ID', 'NAME']).agg({
        'Call Count': 'sum',
        'AHT_sec': 'mean',
        'Wrap_sec': 'mean',
        'Hold_sec': 'mean',
        'Auto On_sec': 'mean'
    }).reset_index()

    csat_data = csat_df[csat_df['Week'].astype(str) == current_week_str].groupby(['EMP ID', 'NAME']).agg({
        'CSAT Resolution': 'mean',
        'CSAT Behaviour': 'mean'
    }).reset_index()

    performance = pd.merge(avg_metrics, csat_data, on=['EMP ID', 'NAME'], how='left').fillna(0)

    # Scoring logic: higher is better for Call Count, Auto On, CSATs; lower is better for AHT, Wrap, Hold
    performance['Score'] = (
        performance['Call Count'] +
        (1 / performance['AHT_sec'].clip(lower=1)) * 100 +
        (1 / performance['Wrap_sec'].clip(lower=1)) * 50 +
        (1 / performance['Hold_sec'].clip(lower=1)) * 25 +
        performance['Auto On_sec'] +
        performance['CSAT Resolution'] * 10 +
        performance['CSAT Behaviour'] * 10
    )

    top5 = performance.nlargest(5, 'Score').reset_index(drop=True)

    rank_icons = ['🥇', '🥈', '🥉', '🎖️', '🎖️']

    for idx, row in top5.iterrows():
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"<div style='font-size:42px'>{rank_icons[idx]}</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div style='
                background-color:#f0f2f6;
                padding:20px;
                border-radius:12px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.05);
                margin-bottom:15px;
            '>
                <div style='font-size:20px; font-weight:bold; color:#333;'>{row["NAME"]}</div>
                <div style='margin-top:5px; font-size:16px;'>
                    📞 Calls: <b>{int(row['Call Count'])}</b> &nbsp; | &nbsp;
                    ⏱️ AHT: <b>{str(timedelta(seconds=int(row['AHT_sec'])))}</b> &nbsp; | &nbsp;
                    🕒 Hold: <b>{str(timedelta(seconds=int(row['Hold_sec'])))}</b><br>
                    📝 Wrap: <b>{str(timedelta(seconds=int(row['Wrap_sec'])))}</b> &nbsp; | &nbsp;
                    🤖 Auto On: <b>{str(timedelta(seconds=int(row['Auto On_sec'])))}</b><br>
                    😊 CSAT Res: <b>{row['CSAT Resolution']:.1f}%</b> &nbsp; | &nbsp;
                    👍 CSAT Beh: <b>{row['CSAT Behaviour']:.1f}%</b> &nbsp; | &nbsp;
                    🔢 Score: <b>{row['Score']:.2f}</b>
                </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("📭 No performance data available for the current week.")

# === TIMEFRAME SELECTOR ===
time_frame = st.selectbox("⏳ Select Timeframe", ["Day", "Week", "Month"])

# === MONTH VIEW ===
if time_frame == "Month":
    df = month_df
    df.columns = df.columns.str.strip()
    emp_id = st.text_input("🔢 Enter EMP ID (e.g., 1070)")
    month = st.selectbox("📅 Select Month", sorted(df['Month'].unique(), key=lambda m: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].index(m)))

    if emp_id and month:
        emp_data = df[(df["EMP ID"].astype(str) == emp_id) & (df["Month"] == month)]

        if emp_data.empty:
            st.warning("⚠️ No data found for that EMP ID and month.")
        else:
            emp_name = emp_data["NAME"].values[0]
            st.markdown(f"### 📊 KPI Data for **{emp_name}** (EMP ID: {emp_id}) | Month: **{month}**")

            st.subheader("📈 Performance Metrics")
            perf_map = [
                ("⏳ Avg hold time used", "Hold", "HH:MM:SS"),
                ("📝 Avg time taken to wrap the call", "Wrap", "HH:MM:SS"),
                ("🤖 Avg duration of champ using auto on", "Auto-On", "HH:MM:SS"),
                ("✅ Shift adherence for the month", "Schedule Adherence", "Percentage"),
                ("😊 Customer feedback on resolution given", "Resolution CSAT", "Percentage"),
                ("👍 Customer feedback on champ behaviour", "Agent Behaviour", "Percentage"),
                ("⭐ Avg Quality Score achieved for the month", "Quality", "Percentage"),
                ("🧠 Process Knowledge Test", "PKT", "Percentage"),
                ("🤒 Number of sick and unplanned leaves", "SL + UPL", "Days"),
                ("💻 Number of days logged in", "LOGINS", "Days"),
            ]

            perf_table = []
            for desc, metric, unit in perf_map:
                value = emp_data[metric].values[0] if metric in emp_data else "-"
                perf_table.append({"Description": desc, "Metric Name": metric, "Value": value, "Unit": unit})

            st.dataframe(pd.DataFrame(perf_table), use_container_width=True)

            st.subheader("🏆 KPI Scores")
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

            st.subheader("🏅 Grand Total")
            current_score = emp_data['Grand Total'].values[0]
            st.metric("Grand Total KPI", f"{current_score}")

            if lottie_cheer:
                st_lottie(lottie_cheer, speed=1, height=200, key="cheer")

            if current_score >= 4.5:
                st.success("🎉 Incredible! You're setting new standards!")
            elif current_score >= 4.0:
                st.info("🌟 Great work! Let's aim for the top.")
            elif current_score >= 3.0:
                st.warning("💪 You're doing good! Let's level up next month.")
            elif current_score >= 2.0:
                st.warning("📈 Progress in motion. Consistency is key!")
            else:
                st.error("🔥 Don't give up. Big wins come from small efforts.")

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
                        st.success(f"📈 You improved by +{diff} points since last month ({previous_month})!")
                    elif diff < 0:
                        st.warning(f"📉 You dropped by {abs(diff)} points since last month ({previous_month}). Let's bounce back!")
                    else:
                        st.info(f"➖ No change from last month ({previous_month}). Keep the momentum going.")
                else:
                    st.info("📭 No data found for previous month.")

            st.subheader("🎯 Target Committed for Next Month")
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
                st.info("📭 No target data available.")

# === WEEK VIEW ===
elif time_frame == "Week":
    emp_id = st.text_input("🔢 Enter EMP ID")

    # Ensure Week is properly formatted as string for comparison
    day_df["Week"] = day_df["Week"].astype(str).str.strip()
    selected_week = st.selectbox("📅 Select Week Number", sorted(day_df["Week"].unique(), key=lambda x: int(x)))

    if emp_id and selected_week:
        try:
            week_data = day_df[
                (day_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & 
                (day_df["Week"] == selected_week.strip())
            ]

            # Process CSAT data with consistent type handling
            csat_df['EMP ID'] = csat_df['EMP ID'].astype(str).str.strip()
            csat_df['Week'] = csat_df['Week'].astype(str).str.strip()
            
            csat_data = csat_df[
                (csat_df["EMP ID"] == emp_id.strip()) &
                (csat_df["Week"] == selected_week.strip())
            ]

            if not week_data.empty:
                emp_name = week_data["NAME"].iloc[0]
                st.markdown(f"### 📊 Weekly KPI Data for **{emp_name}** | Week {selected_week}")

                # Calculate metrics with error handling
                try:
                    total_calls = week_data["Call Count"].sum()
                    avg_aht = pd.to_timedelta(week_data["AHT"].mean())
                    avg_hold = pd.to_timedelta(week_data["Hold"].mean())
                    avg_wrap = pd.to_timedelta(week_data["Wrap"].mean())
                    avg_auto_on = pd.to_timedelta(week_data["Auto On"].mean())

                    def fmt(td):
                        return str(td).split(" ")[-1].split(".")[0]

                    kpi_df = pd.DataFrame([
                        ("📞 Total Calls", total_calls),
                        ("⏱️ AHT", fmt(avg_aht)),
                        ("🕒 Hold", fmt(avg_hold)),
                        ("📝 Wrap", fmt(avg_wrap)),
                        ("🤖 Avg Auto On", fmt(avg_auto_on)),
                    ], columns=["Metric", "Value"])

                    st.dataframe(kpi_df, use_container_width=True)

                except Exception as e:
                    st.error(f"⚠️ Error calculating metrics: {str(e)}")

                # Display CSAT data if available
                if not csat_data.empty:
                    st.subheader("😊 CSAT Scores")
                    try:
                        csat_df_show = pd.DataFrame([
                            ("✅ CSAT Resolution", csat_data["CSAT Resolution"].values[0]),
                            ("👍 CSAT Behaviour", csat_data["CSAT Behaviour"].values[0])
                        ], columns=["Type", "Score"])
                        st.dataframe(csat_df_show, use_container_width=True)
                    except Exception as e:
                        st.error(f"⚠️ Error displaying CSAT data: {str(e)}")
                else:
                    st.info("📭 CSAT data not found for this week.")

                # Motivational quote
                quotes = [
                    "🚀 Keep up the momentum and aim higher!",
                    "🌟 Greatness is built on good habits.",
                    "📈 Stay consistent — growth follows.",
                    "🔥 You've got the spark — now fire up more!",
                    "💪 Progress is progress, no matter how small."
                ]
                st.info(random.choice(quotes))
            else:
                st.warning("⚠️ No data found for that EMP ID and week.")
                
        except Exception as e:
            st.error(f"⚠️ An error occurred: {str(e)}")

# === DAY VIEW ===
elif time_frame == "Day":
    emp_id = st.text_input("🔢 Enter EMP ID")
    selected_date = st.selectbox("📅 Select Date", sorted(day_df["Date"].unique()))

    if emp_id and selected_date:
        row = day_df[(day_df["EMP ID"].astype(str) == emp_id) & (day_df["Date"] == selected_date)]
        if not row.empty:
            row = row.iloc[0]
            emp_name = row['NAME']
            st.markdown(f"### 📊 Daily KPI Data for **{emp_name}** | Date: {selected_date}")

            def fmt(t):
                return str(pd.to_timedelta(t)).split(" ")[-1].split(".")[0]

            metrics = [
                ("📞 Call Count", row["Call Count"]),
                ("⏱️ AHT", fmt(row["AHT"])),
                ("🕒 Hold", fmt(row["Hold"])),
                ("📝 Wrap", fmt(row["Wrap"])),
                ("🤖 Auto On", fmt(row["Auto On"])),
                ("✅ CSAT Resolution", row["CSAT Resolution"]),
                ("👍 CSAT Behaviour", row["CSAT Behaviour"]),
            ]

            daily_df = pd.DataFrame(metrics, columns=["Metric", "Value"])
            st.dataframe(daily_df, use_container_width=True)
            
            # Daily performance comment
            if row["Call Count"] > 50:
                st.success("🎯 Excellent call volume today!")
            elif row["Call Count"] > 30:
                st.info("👍 Solid performance today!")
            else:
                st.warning("💪 Keep pushing - tomorrow is another opportunity!")
        else:
            st.info("📭 No data found for that EMP ID and date.")
