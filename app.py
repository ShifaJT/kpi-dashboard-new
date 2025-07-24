# === COMPLETE KPI DASHBOARD SOLUTION ===
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import numpy as np

# Helper functions to clean values
def clean_value(val):
    if pd.isna(val) or str(val).strip() in ['', 'nan', 'None']:
        return 'N/A'
    return str(val).replace('%', '').strip()

def clean_percentage(val):
    cleaned = clean_value(val)
    return f"{cleaned}%" if cleaned != 'N/A' else 'N/A'

# === CONFIGURATION ===
SHEET_ID = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"
SHEET_MONTH = "KPI Month"
SHEET_DAY = "KPI Day"
SHEET_CSAT = "CSAT Score"

# === GOOGLE SHEETS AUTHENTICATION ===
@st.cache_resource
def get_gspread_client():
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return None

client = get_gspread_client()

# === IMPROVED DATA LOADING WITH DUPLICATE HEADER HANDLING ===
@st.cache_data(ttl=3600)
def load_sheet(name):
    try:
        sheet = client.open_by_key(SHEET_ID)
        worksheet = sheet.worksheet(name)
        
        all_data = worksheet.get_all_values()
        original_headers = all_data[0]
        cleaned_headers = []
        header_counts = {}
        
        for header in original_headers:
            header = header.strip()
            if not header:
                header = "Unnamed"
            if header in header_counts:
                header_counts[header] += 1
                header = f"{header}_{header_counts[header]}"
            else:
                header_counts[header] = 1
            cleaned_headers.append(header)
        
        if len(all_data) > 1:
            df = pd.DataFrame(all_data[1:], columns=cleaned_headers)
        else:
            df = pd.DataFrame(columns=cleaned_headers)
        return df
    except Exception as e:
        st.error(f"Error loading {name}: {str(e)}")
        return pd.DataFrame()

# Load all sheets
month_df = load_sheet(SHEET_MONTH)
day_df = load_sheet(SHEET_DAY)
csat_df = load_sheet(SHEET_CSAT)

# === DATA PROCESSING ===
def safe_convert_time(time_val):
    if pd.isna(time_val) or str(time_val).strip() in ['', '0', '00:00', '00:00:00']:
        return 0.0
    try:
        if isinstance(time_val, (int, float)):
            return float(time_val)
        time_str = str(time_val).strip()
        if ':' in time_str:
            parts = list(map(float, time_str.split(':')))
            if len(parts) == 3:
                return parts[0]*3600 + parts[1]*60 + parts[2]
            elif len(parts) == 2:
                return parts[0]*60 + parts[1]
        return float(time_str)
    except:
        return 0.0

if not day_df.empty:
    day_df['Date'] = pd.to_datetime(day_df['Date'], errors='coerce').dt.date
    day_df['Week'] = day_df['Date'].apply(lambda x: x.isocalendar()[1]).astype(str)
    time_cols = ['AHT', 'Wrap', 'Hold', 'Auto On']
    for col in time_cols:
        if col in day_df.columns:
            day_df[f"{col}_sec"] = day_df[col].apply(safe_convert_time)

if not csat_df.empty:
    csat_df['Week'] = csat_df['Week'].astype(str)
    for col in ['CSAT Resolution', 'CSAT Behaviour']:
        if col in csat_df.columns:
            csat_df[col] = pd.to_numeric(csat_df[col].astype(str).str.replace('%', ''), errors='coerce')

# === DASHBOARD UI ===
st.title("🏆 KPI Performance Dashboard")
time_frame = st.radio("Select Timeframe:", ["Day", "Week", "Month"], horizontal=True)

# === MONTH VIEW ===
if time_frame == "Month":
    st.subheader("\U0001F4C5 Monthly Performance")

    if not month_df.empty:
        month_df['Month'] = month_df['Month'].astype(str).str.strip()
        month_names = sorted(month_df['Month'].unique())

        if len(month_names) == 0:
            st.error("No months found in the data. Please check your 'KPI Month' sheet.")
        else:
            selected_month = st.selectbox("Select Month", month_names)
            emp_id = st.text_input("Enter Employee ID", key="month_emp_id")

            if emp_id and selected_month:
                try:
                    monthly_data = month_df[
                        (month_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) &
                        (month_df['Month'].str.strip() == selected_month.strip())
                    ]

                    if not monthly_data.empty:
                        row = monthly_data.iloc[0]
                        st.subheader(f"Performance for {row['NAME']} - {selected_month}")

                        st.markdown("### \U0001F4CA Performance Metrics")
                        cols = st.columns(4)
                        metrics = [
                            ("⏱️ Hold Time", clean_value(row.get('Hold'))),
                            ("📝 Wrap Time", clean_value(row.get('Wrap'))),
                            ("🤖 Auto-On", clean_value(row.get('Auto-On'))),
                            ("⏰ Schedule Adherence", clean_percentage(row.get('Schedule Adherence'))),
                            ("😊 CSAT Resolution", clean_percentage(row.get('Resolution CSAT'))),
                            ("👍 CSAT Behaviour", clean_percentage(row.get('Agent Behaviour'))),
                            ("⭐ Quality", clean_percentage(row.get('Quality'))),
                            ("🧠 PKT", clean_percentage(row.get('PKT'))),
                            ("📅 SL + UPL", clean_value(row.get('SL + UPL'))),
                            ("📞 Logins", clean_value(row.get('LOGINS')))
                        ]
                        for i, (label, value) in enumerate(metrics):
                            cols[i % 4].metric(label, value)

                        st.markdown("### \U0001F3AF KPI Scores")
                        kpi_cols = st.columns(4)
                        kpi_metrics = [
                            ("Hold KPI Score", clean_value(row.get('Hold KPI Score'))),
                            ("Wrap KPI Score", clean_value(row.get('Wrap KPI Score'))),
                            ("Auto-On KPI Score", clean_value(row.get('Auto-On KPI Score'))),
                            ("Schedule KPI Score", clean_value(row.get('Schedule Adherence KPI Score'))),
                            ("CSAT Res KPI Score", clean_value(row.get('Resolution CSAT KPI Score'))),
                            ("CSAT Beh KPI Score", clean_value(row.get('Agent Behaviour KPI Score'))),
                            ("Quality KPI Score", clean_value(row.get('Quality KPI Score'))),
                            ("PKT KPI Score", clean_value(row.get('PKT KPI Score')))
                        ]
                        for i, (label, value) in enumerate(kpi_metrics):
                            kpi_cols[i % 4].metric(label, value)

                        if 'Grand Total' in row:
                            current_score = float(row['Grand Total'])
                            st.markdown("### \U0001F4C8 Overall KPI Score")
                            try:
                                month_index = month_names.index(selected_month)
                                if month_index > 0:
                                    prev_month = month_names[month_index - 1]
                                    prev_data = month_df[
                                        (month_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) &
                                        (month_df['Month'].str.strip() == prev_month.strip())
                                    ]
                                    if not prev_data.empty:
                                        prev_score = float(prev_data.iloc[0]['Grand Total'])
                                        delta = current_score - prev_score
                                        delta_label = f"{'↑' if delta >= 0 else '↓'} {abs(delta):.1f}"
                                    else:
                                        delta = None
                                else:
                                    delta = None
                            except:
                                delta = None

                            if delta is not None:
                                st.metric("Overall Score", f"{current_score:.1f}/5.0", delta_label, delta_color="normal")
                                if delta > 0:
                                    st.markdown(f"🔺 **{abs(delta):.1f} improved from last month.**")
                                    st.success("Keep up the great work and continue the momentum! 💪")
                                elif delta < 0:
                                    st.markdown(f"🔻 **{abs(delta):.1f} dropped from last month.**")
                                    st.warning("Let's focus on areas of improvement and bounce back stronger! 🚀")
                            else:
                                st.metric("Overall Score", f"{current_score:.1f}/5.0")
                                st.info("No data from the previous month to compare.")

                            st.progress(current_score / 5)

                        st.markdown("### \U0001F3AF Targets Committed")
                        target_cols = st.columns(3)
                        targets = [
                            ("PKT Target", clean_value(row.get('Target Committed for PKT'))),
                            ("CSAT Target", clean_value(row.get('Target Committed for CSAT (Agent Behaviour)'))),
                            ("Quality Target", clean_value(row.get('Target Committed for Quality')))
                        ]
                        for i, (label, value) in enumerate(targets):
                            target_cols[i].metric(label, value)

                    else:
                        st.warning("No data found for this employee/month")
                except Exception as e:
                    st.error(f"Error processing data: {str(e)}")
    else:
        st.warning("Monthly data not loaded properly")

# === WEEK VIEW ===
elif time_frame == "Week":
    st.subheader("📅 Weekly Performance")
    
    if not day_df.empty and not csat_df.empty:
        day_weeks = day_df['Week'].dropna().unique()
        csat_weeks = csat_df['Week'].dropna().unique()
        all_weeks = sorted(set(day_weeks) | set(csat_weeks))
        
        selected_week = st.selectbox("Select Week", all_weeks, key="week_select")
        emp_id = st.text_input("Enter Employee ID", key="week_emp_id")
        
        if emp_id and selected_week:
            try:
                week_calls = day_df[
                    (day_df["EMP ID"].astype(str).str.strip() == str(emp_id).strip()) & 
                    (day_df["Week"].astype(str).str.strip() == str(selected_week).strip())
                ].copy()
                week_calls['Call Count'] = pd.to_numeric(week_calls['Call Count'].astype(str).str.replace(',', ''), errors='coerce')
                
                if not week_calls.empty:
                    total_calls = int(week_calls["Call Count"].sum())
                    
                    def format_avg_time(col):
                        avg_sec = week_calls[f"{col}_sec"].mean()
                        return str(timedelta(seconds=int(avg_sec))).split('.')[0]
                    
                    st.subheader(f"Week {selected_week} Performance")
                    st.markdown("### 📞 Call Metrics")
                    cols = st.columns(5)
                    call_metrics = [
                        ("Total Calls", f"{total_calls:,}"),
                        ("Avg AHT", format_avg_time('AHT')),
                        ("Avg Hold", format_avg_time('Hold')),
                        ("Avg Wrap", format_avg_time('Wrap')),
                        ("Avg Auto On", format_avg_time('Auto On'))
                    ]
                    for i, (label, value) in enumerate(call_metrics):
                        cols[i].metric(label, value)
                    
                    week_csat = csat_df[
                        (csat_df["EMP ID"].astype(str).str.strip() == str(emp_id).strip()) & 
                        (csat_df["Week"].astype(str).str.strip() == str(selected_week).strip())
                    ]
                    if not week_csat.empty:
                        st.markdown("### 😊 CSAT Metrics")
                        csat_cols = st.columns(2)
                        csat_metrics = [
                            ("CSAT Resolution", f"{week_csat['CSAT Resolution'].mean():.1f}%"),
                            ("CSAT Behaviour", f"{week_csat['CSAT Behaviour'].mean():.1f}%")
                        ]
                        for i, (label, value) in enumerate(csat_metrics):
                            csat_cols[i].metric(label, value)
                    
                    with st.expander("📅 View Daily Breakdown"):
                        daily_data = week_calls[['Date', 'Call Count', 'AHT', 'Hold', 'Wrap', 'Auto On']].copy()
                        st.dataframe(daily_data)
                else:
                    st.warning("No call data found for this employee/week")
            except Exception as e:
                st.error(f"Error processing weekly data: {str(e)}")
    else:
        st.warning("Weekly data not loaded properly")

# === DAY VIEW ===
else:
    st.subheader("📅 Daily Performance")
    
    if not day_df.empty:
        available_dates = sorted(day_df['Date'].dropna().unique())
        selected_date = st.selectbox("Select Date", available_dates, key="day_date_select")
        emp_id = st.text_input("Enter Employee ID", key="day_emp_id")
        
        if emp_id and selected_date:
            daily_data = day_df[
                (day_df["EMP ID"].astype(str).str.strip() == str(emp_id).strip()) & 
                (day_df["Date"] == selected_date)
            ]
            
            if not daily_data.empty:
                row = daily_data.iloc[0]
                st.subheader(f"Performance for {row['NAME']} on {selected_date}")
                
                def format_time(time_val):
                    if pd.isna(time_val) or time_val == 0:
                        return "00:00:00"
                    return str(timedelta(seconds=int(time_val))).split('.')[0]
                
                cols = st.columns(4)
                metrics = [
                    ("📞 Calls", f"{int(row.get('Call Count', 0)):,}"),
                    ("⏱️ AHT", format_time(row.get('AHT_sec', 0))),
                    ("🕒 Hold", format_time(row.get('Hold_sec', 0))),
                    ("📝 Wrap", format_time(row.get('Wrap_sec', 0))),
                    ("🤖 Auto On", format_time(row.get('Auto On_sec', 0)))
                ]
                for i, (label, value) in enumerate(metrics):
                    cols[i%4].metric(label, value)
                
                call_count = int(row.get('Call Count', 0))
                if call_count > 50:
                    st.success("Excellent call volume today!")
                elif call_count > 30:
                    st.info("Good performance today")
                else:
                    st.warning("Let's aim for more calls tomorrow")
            else:
                st.warning("No data found for this employee/date")
