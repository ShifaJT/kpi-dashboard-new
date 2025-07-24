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

# === IMPROVED DATA LOADING WITH DUPLICATE HEADER HANDLING ===
@st.cache_data(ttl=3600)
def safe_load_sheet(name):
    try:
        worksheet = sheet.worksheet(name)
        # First try standard method
        try:
            records = worksheet.get_all_records()
        except gspread.exceptions.APIError:
            # Fallback to manual header handling
            all_values = worksheet.get_all_values()
            headers = all_values[0]
            data = all_values[1:]
            
            # Handle duplicate headers
            seen = {}
            for i, h in enumerate(headers):
                if h in seen:
                    headers[i] = f"{h}_{seen[h]}"
                    seen[h] += 1
                else:
                    seen[h] = 1
            
            records = [dict(zip(headers, row)) for row in data]
        
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip()
        
        # Convert all string columns to stripped strings
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.strip()
                
        return df
    except Exception as e:
        st.error(f"Error loading {name} sheet: {str(e)}")
        return pd.DataFrame()

# Load all data
month_df = safe_load_sheet(SHEET_MONTH)
day_df = safe_load_sheet(SHEET_DAY)
csat_df = safe_load_sheet(SHEET_CSAT)

# === VALIDATE REQUIRED COLUMNS ===
REQUIRED_COLUMNS = {
    'day': ['EMP ID', 'Call Count'],
    'csat': ['EMP ID'],
    'month': ['EMP ID', 'Month', 'Grand Total']
}

def validate_dataframes():
    errors = []
    for df_name, df in [('Day', day_df), ('CSAT', csat_df), ('Month', month_df)]:
        required = REQUIRED_COLUMNS[df_name.lower()]
        missing = [col for col in required if col not in df.columns]
        if missing:
            errors.append(f"Missing in {df_name}: {', '.join(missing)}")
    return errors

validation_errors = validate_dataframes()
if validation_errors:
    st.error("Data validation failed:")
    for error in validation_errors:
        st.error(error)
    st.stop()

# === FIXED PERCENTAGE CONVERSION ===
def convert_percentage(value):
    try:
        if isinstance(value, str):
            return float(value.replace('%', '').strip())
        return float(value)
    except:
        return 0.0

# Clean CSAT columns if they exist
if 'CSAT Resolution' in csat_df.columns:
    csat_df['CSAT Resolution'] = csat_df['CSAT Resolution'].apply(convert_percentage)
if 'CSAT Behaviour' in csat_df.columns:
    csat_df['CSAT Behaviour'] = csat_df['CSAT Behaviour'].apply(convert_percentage)

# === ROBUST TIME CONVERSION ===
def convert_time_to_seconds(time_val):
    try:
        if pd.isna(time_val) or str(time_val).strip() in ['', '0', '00:00', '00:00:00']:
            return 0.0
            
        time_str = str(time_val).strip()
        
        if time_str.count(':') > 2:
            parts = time_str.split(':')
            time_str = f"{parts[-3]}:{parts[-2]}:{parts[-1]}"
            
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 3:  # HH:MM:SS
                return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
            elif len(parts) == 2:  # MM:SS
                return float(parts[0])*60 + float(parts[1])
                
        if time_str.replace('.','',1).isdigit():
            return float(time_str)
            
        return 0.0
    except:
        return 0.0

# Apply time conversion to relevant columns
time_columns = ['AHT', 'Wrap', 'Hold', 'Auto On']
for col in time_columns:
    if col in day_df.columns:
        day_df[f"{col}_sec"] = day_df[col].apply(convert_time_to_seconds)
        day_df[f"{col}_sec"] = pd.to_numeric(day_df[f"{col}_sec"], errors='coerce').fillna(0)

# === DATA NORMALIZATION ===
def normalize_data(df):
    if 'EMP ID' in df.columns:
        df['EMP ID'] = df['EMP ID'].astype(str).str.strip()
    if 'NAME' in df.columns:
        df['NAME'] = df['NAME'].str.strip()
    if 'Call Count' in df.columns:
        df['Call Count'] = pd.to_numeric(df['Call Count'], errors='coerce').fillna(0)
    return df

day_df = normalize_data(day_df)
csat_df = normalize_data(csat_df)
month_df = normalize_data(month_df)

# Add week numbers if date column exists
if 'Week' not in day_df.columns and 'Date' in day_df.columns:
    try:
        day_df['Date'] = pd.to_datetime(day_df['Date'], errors='coerce')
        day_df['Week'] = day_df['Date'].dt.isocalendar().week.astype(str)
    except:
        day_df['Week'] = "1"

# === UPDATED TOP PERFORMERS CALCULATION WITH WEIGHTAGE ===
def get_weekly_top_performers(target_week=None):
    if target_week is None:
        target_week = datetime.now().isocalendar()[1]
    week_str = str(target_week)
    
    try:
        # Check if week column exists
        if 'Week' not in day_df.columns:
            st.error("Week column missing - cannot calculate top performers")
            return pd.DataFrame()
            
        week_day_data = day_df[day_df['Week'] == week_str]
        week_csat_data = csat_df[csat_df['Week'] == week_str] if 'Week' in csat_df.columns else pd.DataFrame()
        
        if week_day_data.empty:
            return pd.DataFrame()
        
        # Aggregate metrics
        agg_dict = {
            'Call Count': 'sum',
            'Hold_sec': 'mean',
            'Wrap_sec': 'mean',
            'Auto On_sec': 'mean'
        }
        metrics = week_day_data.groupby(['EMP ID', 'NAME'], as_index=False).agg(agg_dict)
        
        # Add CSAT scores if available
        if not week_csat_data.empty and {'CSAT Resolution', 'CSAT Behaviour'}.issubset(week_csat_data.columns):
            csat_scores = week_csat_data.groupby(['EMP ID', 'NAME'], as_index=False).agg({
                'CSAT Resolution': 'mean',
                'CSAT Behaviour': 'mean'
            })
            metrics = pd.merge(metrics, csat_scores, on=['EMP ID', 'NAME'], how='left')
        
        metrics.fillna(0, inplace=True)
        
        # === NEW WEIGHTED SCORING LOGIC ===
        def normalize(series, reverse=False):
            if series.max() == series.min():
                return 50
            if reverse:
                return 100 * (series.max() - series) / (series.max() - series.min())
            return 100 * (series - series.min()) / (series.max() - series.min())
        
        # Apply weights: Call Count 0%, Hold 5%, Wrap 5%, CSAT Beh 25%, CSAT Res 25%, Auto On 40%
        metrics['Score'] = (
            normalize(metrics['Hold_sec'], reverse=True) * 0.05 +
            normalize(metrics['Wrap_sec'], reverse=True) * 0.05 +
            normalize(metrics['CSAT Behaviour']) * 0.25 +
            normalize(metrics['CSAT Resolution']) * 0.25 +
            normalize(metrics['Auto On_sec']) * 0.40
        )
        
        # Format metrics for display
        metrics['Hold'] = metrics['Hold_sec'].apply(lambda x: str(timedelta(seconds=int(x))).split('.')[0])
        metrics['Wrap'] = metrics['Wrap_sec'].apply(lambda x: str(timedelta(seconds=int(x))).split('.')[0])
        metrics['Auto On'] = metrics['Auto On_sec'].apply(lambda x: str(timedelta(seconds=int(x))).split('.')[0])
        metrics['CSAT Beh'] = metrics['CSAT Behaviour'].apply(lambda x: f"{x:.1f}%")
        metrics['CSAT Res'] = metrics['CSAT Resolution'].apply(lambda x: f"{x:.1f}%")
        
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

# === CURRENT WEEK TOP PERFORMERS ===
current_week = datetime.now().isocalendar()[1]
top_performers = get_weekly_top_performers(current_week)

if not top_performers.empty:
    st.markdown("### 🏅 Current Week's Top Performers")
    
    cols = st.columns(5)
    for idx, row in top_performers.iterrows():
        with cols[idx]:
            medal = ['🥇', '🥈', '🥉', '🎖️', '🎖️'][idx] if idx < 5 else '🎖️'
            
            display_text = f"""
            <div style='
                background:#f0f2f6;
                padding:12px;
                border-radius:8px;
                margin-bottom:12px;
                font-size:13px;
                box-shadow:0 2px 4px rgba(0,0,0,0.1);
            '>
                <div style='text-align:center; font-weight:bold; font-size:14px; margin-bottom:8px;'>
                    {medal} {row['NAME']}
                </div>
                <table style='width:100%; border-collapse:collapse; font-size:12px;'>
                    <tr><td>📞 Calls:</td><td style='text-align:right;'>{int(row['Call Count'])}</td></tr>
                    <tr><td>🕒 Hold:</td><td style='text-align:right;'>{row['Hold']}</td></tr>
                    <tr><td>📝 Wrap:</td><td style='text-align:right;'>{row['Wrap']}</td></tr>
                    <tr><td>😊 CSAT Res:</td><td style='text-align:right;'>{row['CSAT Res']}</td></tr>
                    <tr><td>👍 CSAT Beh:</td><td style='text-align:right;'>{row['CSAT Beh']}</td></tr>
                    <tr><td>🤖 Auto On:</td><td style='text-align:right;'>{row['Auto On']}</td></tr>
                </table>
                <div style='margin-top:8px; text-align:center; font-size:11px; color:#666;'>
                    Score: {row['Score']:.1f}
                </div>
            </div>
            """
            st.markdown(display_text, unsafe_allow_html=True)
else:
    st.info("📭 No performance data available for the current week.")

# === TIMEFRAME SELECTOR ===
time_frame = st.selectbox("⏳ Select Timeframe", ["Day", "Week", "Month"])

# === WEEK VIEW ===
if time_frame == "Week":
    emp_id = st.text_input("🔢 Enter EMP ID")
    
    if 'Week' not in day_df.columns:
        st.error("Week data not available - missing week column")
    else:
        try:
            available_weeks = sorted(day_df['Week'].unique())
            selected_week = st.selectbox("📅 Select Week Number", available_weeks)
            
            if emp_id:
                week_data = day_df[
                    (day_df["EMP ID"].str.strip() == emp_id.strip()) & 
                    (day_df["Week"] == selected_week)
                ]
                
                if not week_data.empty:
                    emp_name = week_data.iloc[0]['NAME'] if 'NAME' in week_data.columns else "Unknown"
                    st.markdown(f"### 📊 Weekly KPI Data for {emp_name} | Week {selected_week}")
                    
                    # Display metrics
                    metrics = []
                    if 'Call Count' in week_data.columns:
                        metrics.append(("📞 Total Calls", int(week_data["Call Count"].sum())))
                    if 'Hold_sec' in week_data.columns:
                        metrics.append(("🕒 Avg Hold", str(timedelta(seconds=int(week_data["Hold_sec"].mean()))).split('.')[0]))
                    if 'Wrap_sec' in week_data.columns:
                        metrics.append(("📝 Avg Wrap", str(timedelta(seconds=int(week_data["Wrap_sec"].mean()))).split('.')[0]))
                    if 'Auto On_sec' in week_data.columns:
                        metrics.append(("🤖 Avg Auto On", str(timedelta(seconds=int(week_data["Auto On_sec"].mean()))).split('.')[0]))
                    
                    if metrics:
                        metric_df = pd.DataFrame(metrics, columns=["Metric", "Value"])
                        st.dataframe(metric_df, use_container_width=True, hide_index=True)
                    
                    # Display CSAT if available
                    if not csat_df.empty and 'EMP ID' in csat_df.columns:
                        csat_data = csat_df[
                            (csat_df["EMP ID"].str.strip() == emp_id.strip()) &
                            (csat_df["Week"] == selected_week) if 'Week' in csat_df.columns else True
                        ]
                        
                        if not csat_data.empty:
                            st.subheader("😊 CSAT Scores")
                            csat_metrics = []
                            if 'CSAT Resolution' in csat_data.columns:
                                csat_metrics.append(("✅ CSAT Resolution", f"{csat_data['CSAT Resolution'].mean():.1f}%"))
                            if 'CSAT Behaviour' in csat_data.columns:
                                csat_metrics.append(("👍 CSAT Behaviour", f"{csat_data['CSAT Behaviour'].mean():.1f}%"))
                            
                            if csat_metrics:
                                csat_df_display = pd.DataFrame(csat_metrics, columns=["Metric", "Value"])
                                st.dataframe(csat_df_display, use_container_width=True, hide_index=True)
                    
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

# === DAY VIEW ===
elif time_frame == "Day":
    emp_id = st.text_input("🔢 Enter EMP ID")
    
    if 'Date' not in day_df.columns:
        st.error("Date column missing - cannot show daily view")
    else:
        try:
            day_df['Date'] = pd.to_datetime(day_df['Date'], errors='coerce')
            available_dates = sorted(day_df['Date'].dropna().unique())
            date_display = [date.strftime('%Y-%m-%d') for date in available_dates]
            selected_date_str = st.selectbox("📅 Select Date", date_display)
            
            if emp_id and selected_date_str:
                selected_date = pd.to_datetime(selected_date_str).date()
                daily_data = day_df[
                    (day_df["EMP ID"].str.strip() == emp_id.strip()) & 
                    (day_df["Date"].dt.date == selected_date)
                ]
                
                if not daily_data.empty:
                    row = daily_data.iloc[0]
                    emp_name = row['NAME'] if 'NAME' in row else "Unknown"
                    st.markdown(f"### 📊 Daily KPI Data for **{emp_name}** | Date: {selected_date_str}")

                    def format_time(time_val):
                        if pd.isna(time_val):
                            return "00:00:00"
                        if isinstance(time_val, str) and ':' in time_val:
                            return time_val.split('.')[0]
                        return str(timedelta(seconds=convert_time_to_seconds(time_val))).split('.')[0]

                    metrics = []
                    if 'Call Count' in row:
                        metrics.append(("📞 Call Count", f"{int(row['Call Count'])}"))
                    if 'AHT' in row:
                        metrics.append(("⏱️ AHT", format_time(row["AHT"])))
                    if 'Hold' in row:
                        metrics.append(("🕒 Hold", format_time(row["Hold"])))
                    if 'Wrap' in row:
                        metrics.append(("📝 Wrap", format_time(row["Wrap"])))
                    if 'Auto On' in row:
                        metrics.append(("🤖 Auto On", format_time(row["Auto On"])))
                    if 'CSAT Resolution' in row:
                        metrics.append(("✅ CSAT Resolution", f"{row['CSAT Resolution']}%"))
                    if 'CSAT Behaviour' in row:
                        metrics.append(("👍 CSAT Behaviour", f"{row['CSAT Behaviour']}%"))

                    if metrics:
                        daily_df = pd.DataFrame(metrics, columns=["Metric", "Value"])
                        st.dataframe(daily_df, use_container_width=True, hide_index=True)
                    
                    if 'Call Count' in row:
                        if row["Call Count"] > 50:
                            st.success("🎯 Excellent call volume today!")
                        elif row["Call Count"] > 30:
                            st.info("👍 Solid performance today!")
                        else:
                            st.warning("💪 Keep pushing - tomorrow is another opportunity!")
                else:
                    st.info("📭 No data found for that EMP ID and date.")
        except Exception as e:
            st.error(f"Error displaying day data: {str(e)}")

# === MONTH VIEW ===
elif time_frame == "Month":
    emp_id = st.text_input("🔢 Enter EMP ID (e.g., 1070)")
    
    if 'Month' not in month_df.columns:
        st.error("Month column missing - cannot show monthly view")
    else:
        month_order = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
        available_months = [m for m in month_order if m in month_df['Month'].unique()]
        month = st.selectbox("📅 Select Month", available_months)

        if emp_id and month:
            emp_data = month_df[(month_df["EMP ID"].str.strip() == emp_id.strip()) & 
                              (month_df["Month"] == month)]

            if not emp_data.empty:
                emp_name = emp_data["NAME"].values[0] if 'NAME' in emp_data.columns else "Unknown"
                st.markdown(f"### 📊 KPI Data for **{emp_name}** (EMP ID: {emp_id}) | Month: **{month}**")

                # Performance Metrics
                perf_table = []
                metric_map = [
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

                for desc, metric, unit in metric_map:
                    if metric in emp_data.columns:
                        value = emp_data[metric].values[0]
                        perf_table.append({"Description": desc, "Metric Name": metric, "Value": value, "Unit": unit})

                if perf_table:
                    st.subheader("📈 Performance Metrics")
                    st.dataframe(pd.DataFrame(perf_table), use_container_width=True, hide_index=True)

                # KPI Scores
                kpi_table = []
                kpi_map = [
                    ("0%", "Hold KPI Score"),
                    ("30%", "Auto-On KPI Score"),
                    ("10%", "Schedule Adherence KPI Score"),
                    ("10%", "Resolution CSAT KPI Score"),
                    ("20%", "Agent Behaviour KPI Score"),
                    ("20%", "Quality KPI Score"),
                    ("10%", "PKT KPI Score")
                ]

                for weight, kpi_metric in kpi_map:
                    if kpi_metric in emp_data.columns:
                        score = emp_data[kpi_metric].values[0]
                        kpi_table.append({"Weightage": weight, "KPI Metrics": kpi_metric, "Score": score})

                if kpi_table:
                    st.subheader("🏆 KPI Scores")
                    st.dataframe(pd.DataFrame(kpi_table), use_container_width=True, hide_index=True)

                # Grand Total
                if 'Grand Total' in emp_data.columns:
                    st.subheader("🏅 Grand Total")
                    try:
                        current_score = float(emp_data['Grand Total'].values[0])
                        st.metric("Grand Total KPI", f"{current_score:.1f}")

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

                        # Month comparison
                        current_index = available_months.index(month)
                        if current_index > 0:
                            previous_month = available_months[current_index - 1]
                            prev_data = month_df[(month_df["EMP ID"].str.strip() == emp_id.strip()) & 
                                                (month_df["Month"] == previous_month)]

                            if not prev_data.empty and 'Grand Total' in prev_data.columns:
                                prev_score = float(prev_data["Grand Total"].values[0])
                                diff = round(current_score - prev_score, 2)

                                if diff > 0:
                                    st.success(f"📈 You improved by +{diff} points since last month ({previous_month})!")
                                elif diff < 0:
                                    st.warning(f"📉 You dropped by {abs(diff)} points since last month ({previous_month}). Let's bounce back!")
                                else:
                                    st.info(f"➖ No change from last month ({previous_month}). Keep the momentum going.")
                    except Exception as e:
                        st.error(f"Error processing Grand Total score: {str(e)}")

                # Target Committed
                target_cols = [
                    "Target Committed for PKT",
                    "Target Committed for CSAT (Agent Behaviour)",
                    "Target Committed for Quality"
                ]

                target_data = []
                for col in target_cols:
                    if col in emp_data.columns:
                        target_value = emp_data[col].values[0]
                        if isinstance(target_value, str) and '%' in target_value:
                            target_value = target_value.replace('%', '').strip()
                        target_data.append({"Target Metric": col, "Target": target_value})

                if target_data:
                    st.subheader("🎯 Target Committed for Next Month")
                    st.dataframe(pd.DataFrame(target_data), use_container_width=True, hide_index=True)
                else:
                    st.info("📭 No target data available.")
            else:
                st.warning("⚠️ No data found for that EMP ID and month.")
