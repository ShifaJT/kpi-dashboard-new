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

# === IMPROVED DATA LOADING ===
@st.cache_data(ttl=3600)
def load_sheet(name):
    worksheet = sheet.worksheet(name)
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip()
    return df

month_df = load_sheet(SHEET_MONTH)
day_df = load_sheet(SHEET_DAY)
csat_df = load_sheet(SHEET_CSAT)

# === TIME CONVERSION ===
def convert_time_to_seconds(time_val):
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

# Convert time columns
time_columns = ['AHT', 'Wrap', 'Hold', 'Auto On']
for col in time_columns:
    if col in day_df.columns:
        day_df[f"{col}_sec"] = day_df[col].apply(convert_time_to_seconds)
        day_df[f"{col}_sec"] = pd.to_numeric(day_df[f"{col}_sec"], errors='coerce').fillna(0)

# Clean CSAT columns
csat_df['CSAT Resolution'] = pd.to_numeric(csat_df['CSAT Resolution'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
csat_df['CSAT Behaviour'] = pd.to_numeric(csat_df['CSAT Behaviour'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)

# Format dates
day_df['Date'] = pd.to_datetime(day_df['Date'], errors='coerce').dt.date
day_df['Week'] = day_df['Date'].apply(lambda x: x.isocalendar()[1]).astype(str)

# === TOP PERFORMERS CALCULATION ===
def get_weekly_top_performers(target_week=None):
    if target_week is None:
        target_week = datetime.now().isocalendar()[1]
    week_str = str(target_week)
    
    try:
        week_day_data = day_df[day_df['Week'] == week_str]
        week_csat_data = csat_df[csat_df['Week'] == week_str]
        
        if week_day_data.empty:
            return pd.DataFrame()
        
        # Aggregate metrics
        metrics = week_day_data.groupby(['EMP ID', 'NAME']).agg({
            'Call Count': 'sum',
            'AHT_sec': 'mean',
            'Wrap_sec': 'mean',
            'Hold_sec': 'mean',
            'Auto On_sec': 'mean'
        }).reset_index()
        
        # Add CSAT scores
        if not week_csat_data.empty:
            csat_scores = week_csat_data.groupby(['EMP ID', 'NAME']).agg({
                'CSAT Resolution': 'mean',
                'CSAT Behaviour': 'mean'
            }).reset_index()
            metrics = pd.merge(metrics, csat_scores, on=['EMP ID', 'NAME'], how='left')
        
        metrics.fillna(0, inplace=True)
        
        # UPDATED SCORING - Focus on AHT, Wrap, Hold, Auto On, CSAT
        metrics['Score'] = (
            (1 / metrics['AHT_sec'].clip(lower=1)) * 50 +  # Lower AHT → Higher score
            (1 / metrics['Wrap_sec'].clip(lower=1)) * 30 +  # Lower Wrap → Higher score
            (1 / metrics['Hold_sec'].clip(lower=1)) * 20 +  # Lower Hold → Higher score
            metrics['Auto On_sec'] * 0.2 +  # Higher AutoOn → Higher score
            metrics['CSAT Resolution'] * 2 +  # Higher CSAT → Higher score
            metrics['CSAT Behaviour'] * 2
        )
        
        return metrics.nlargest(5, 'Score').reset_index(drop=True)
    
    except Exception as e:
        st.error(f"Error calculating top performers: {str(e)}")
        return pd.DataFrame()

# === DASHBOARD UI ===
st.markdown("""
<div style="background: linear-gradient(to right, #0072ff, #00c6ff); padding: 20px 30px; border-radius: 12px; color: white; font-size: 26px; font-weight: bold; margin-bottom: 10px;">
    🏆 KPI Dashboard for Champions 🏆
</div>
""", unsafe_allow_html=True)

# Metric legend in one line
st.markdown("""
<b>📊 Metrics:</b> 📞Calls | ⏱️AHT | 🤖AutoOn | 🕒Hold | 😊Res | 👍Beh | 🥇Gold | 🥈Silver | 🥉Bronze | 🎖️Top5
""", unsafe_allow_html=True)

# === CURRENT WEEK TOP PERFORMERS ===
current_week = datetime.now().isocalendar()[1]
top_performers = get_weekly_top_performers(current_week)

if not top_performers.empty:
    st.markdown("### 🏅 Current Week's Top Performers")
    
    # Single row layout
    cols = st.columns(5)
    
    for idx, row in top_performers.iterrows():
        with cols[idx]:
            medal = ['🥇', '🥈', '🥉', '🎖️', '🎖️'][idx]
            has_autoon = row['Auto On_sec'] > 0
            has_csat = (row['CSAT Resolution'] > 0) or (row['CSAT Behaviour'] > 0)
            
            st.markdown(f"""
            <div style='
                background:#f0f2f6;
                padding:10px;
                border-radius:8px;
                margin-bottom:10px;
                font-size:13px;
            '>
                <b>{medal} {row['NAME']}</b><br>
                📞{int(row['Call Count'])} ⏱️{timedelta(seconds=int(row['AHT_sec']))}
                {f"<br>🤖{timedelta(seconds=int(row['Auto On_sec']))}" if has_autoon else ""}
                {f"<br>😊{row['CSAT Resolution']:.1f}% 👍{row['CSAT Behaviour']:.1f}%" if has_csat else ""}
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("📭 No performance data available for the current week.")

# === TIMEFRAME SELECTOR ===
time_frame = st.selectbox("⏳ Select Timeframe", ["Day", "Week", "Month"])

# [Rest of your Week, Day, and Month view code remains exactly the same...]

# === WEEK VIEW ===
if time_frame == "Week":
    emp_id = st.text_input("🔢 Enter EMP ID")

    # Get available weeks safely
    try:
        day_weeks = set(day_df['Week'].dropna().unique()) if 'Week' in day_df.columns else set()
        csat_weeks = set(csat_df['Week'].dropna().unique()) if 'Week' in csat_df.columns else set()
        available_weeks = sorted(day_weeks.union(csat_weeks), key=lambda x: int(x) if x.isdigit() else 0)
    except Exception as e:
        st.error(f"Error loading week data: {str(e)}")
        available_weeks = []

    if available_weeks:
        selected_week = st.selectbox("📅 Select Week Number", available_weeks)

        if emp_id and selected_week:
            try:
                # Get week data
                week_data = day_df[
                    (day_df["EMP ID"] == emp_id.strip()) & 
                    (day_df["Week"] == selected_week.strip())
                ]

                # Get CSAT data
                csat_data = csat_df[
                    (csat_df["EMP ID"] == emp_id.strip()) &
                    (csat_df["Week"] == selected_week.strip())
                ]

                if not week_data.empty:
                    emp_name = week_data.iloc[0]['NAME']
                    st.markdown(f"### 📊 Weekly KPI Data for {emp_name} | Week {selected_week}")

                    # Convert all metrics to numeric
                    numeric_cols = ['Call Count', 'AHT_sec', 'Wrap_sec', 'Hold_sec', 'Auto On_sec']
                    for col in numeric_cols:
                        if col in week_data.columns:
                            week_data[col] = pd.to_numeric(week_data[col], errors='coerce').fillna(0)

                    # Calculate metrics
                    metrics = {
                        "📞 Total Calls": int(week_data["Call Count"].sum()),
                        "⏱️ Avg AHT": timedelta(seconds=int(week_data["AHT_sec"].mean())),
                        "🕒 Avg Hold": timedelta(seconds=int(week_data["Hold_sec"].mean())),
                        "📝 Avg Wrap": timedelta(seconds=int(week_data["Wrap_sec"].mean())),
                        "🤖 Avg Auto On": timedelta(seconds=int(week_data["Auto On_sec"].mean()))
                    }

                    # Display metrics
                    metric_df = pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"])
                    st.dataframe(metric_df, use_container_width=True, hide_index=True)

                    # Display CSAT if available
                    if not csat_data.empty:
                        st.subheader("😊 CSAT Scores")
                        # Ensure CSAT values are numeric
                        csat_data['CSAT Resolution'] = pd.to_numeric(csat_data['CSAT Resolution'], errors='coerce').fillna(0)
                        csat_data['CSAT Behaviour'] = pd.to_numeric(csat_data['CSAT Behaviour'], errors='coerce').fillna(0)

                        csat_metrics = {
                            "✅ CSAT Resolution": f"{csat_data['CSAT Resolution'].mean():.1f}%",
                            "👍 CSAT Behaviour": f"{csat_data['CSAT Behaviour'].mean():.1f}%"
                        }
                        csat_df = pd.DataFrame(list(csat_metrics.items()), columns=["Metric", "Value"])
                        st.dataframe(csat_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("📭 No CSAT data found for this week.")

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
                    st.warning("⚠️ No daily KPI data found for that EMP ID and week.")

            except Exception as e:
                st.error(f"Error displaying week data: {str(e)}")
    else:
        st.warning("No week data available")

# === DAY VIEW ===
elif time_frame == "Day":
    emp_id = st.text_input("🔢 Enter EMP ID")

    available_dates = sorted(day_df['Date'].unique())
    date_display = [date.strftime('%Y-%m-%d') for date in available_dates]
    selected_date_str = st.selectbox("📅 Select Date", date_display)

    if emp_id and selected_date_str:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        daily_data = day_df[
            (day_df["EMP ID"].str.strip() == emp_id.strip()) & 
            (day_df["Date"] == selected_date)
        ]

        if not daily_data.empty:
            row = daily_data.iloc[0]
            emp_name = row['NAME']
            st.markdown(f"### 📊 Daily KPI Data for **{emp_name}** | Date: {selected_date_str}")

            def format_time(time_val):
                if pd.isna(time_val):
                    return "00:00:00"
                if isinstance(time_val, str) and ':' in time_val:
                    return time_val.split('.')[0]
                return str(timedelta(seconds=convert_time_to_seconds(time_val))).split('.')[0]

            metrics = [
                ("📞 Call Count", f"{int(row['Call Count'])}"),
                ("⏱️ AHT", format_time(row["AHT"])),
                ("🕒 Hold", format_time(row["Hold"])),
                ("📝 Wrap", format_time(row["Wrap"])),
                ("🤖 Auto On", format_time(row["Auto On"])),
                ("✅ CSAT Resolution", f"{row['CSAT Resolution']}%"),
                ("👍 CSAT Behaviour", f"{row['CSAT Behaviour']}%"),
            ]

            daily_df = pd.DataFrame(metrics, columns=["Metric", "Value"])
            st.dataframe(daily_df, use_container_width=True, hide_index=True)

            if row["Call Count"] > 50:
                st.success("🎯 Excellent call volume today!")
            elif row["Call Count"] > 30:
                st.info("👍 Solid performance today!")
            else:
                st.warning("💪 Keep pushing - tomorrow is another opportunity!")
        else:
            st.info("📭 No data found for that EMP ID and date.")

# === MONTH VIEW ===
elif time_frame == "Month":
    df = month_df
    emp_id = st.text_input("🔢 Enter EMP ID (e.g., 1070)")

    month_order = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
    available_months = [m for m in month_order if m in df['Month'].unique()]
    month = st.selectbox("📅 Select Month", available_months)

    if emp_id and month:
        emp_data = df[(df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & (df["Month"] == month)]

        if not emp_data.empty:
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
                value = emp_data[metric].values[0] if metric in emp_data.columns else "-"
                perf_table.append({"Description": desc, "Metric Name": metric, "Value": value, "Unit": unit})

            st.dataframe(pd.DataFrame(perf_table), use_container_width=True, hide_index=True)

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
                score = emp_data[kpi_metric].values[0] if kpi_metric in emp_data.columns else "-"
                kpi_table.append({"Weightage": weight, "KPI Metrics": kpi_metric, "Score": score})

            st.dataframe(pd.DataFrame(kpi_table), use_container_width=True, hide_index=True)

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

            current_index = available_months.index(month)
            if current_index > 0:
                previous_month = available_months[current_index - 1]
                prev_data = df[(df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & (df["Month"] == previous_month)]

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

            target_data = []
            for col in target_cols:
                if col in emp_data.columns:
                    target_data.append({"Target Metric": col, "Target": emp_data[col].values[0]})
                else:
                    target_data.append({"Target Metric": col, "Target": "N/A"})

            if target_data:
                st.dataframe(pd.DataFrame(target_data), use_container_width=True, hide_index=True)
            else:
                st.info("📭 No target data available.")
        else:
            st.warning("⚠️ No data found for that EMP ID and month.")
