# === COMPLETE KPI DASHBOARD SOLUTION ===
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import numpy as np

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

# === DATA LOADING WITH ERROR HANDLING ===
@st.cache_data(ttl=3600)
def load_sheet(name):
    try:
        sheet = client.open_by_key(SHEET_ID)
        worksheet = sheet.worksheet(name)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip()
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
    """Convert various time formats to seconds"""
    if pd.isna(time_val) or str(time_val).strip() in ['', '0', '00:00', '00:00:00']:
        return 0.0
    try:
        if isinstance(time_val, (int, float)):
            return float(time_val)
        
        time_str = str(time_val).strip()
        if ':' in time_str:
            parts = list(map(float, time_str.split(':')))
            if len(parts) == 3:  # HH:MM:SS
                return parts[0]*3600 + parts[1]*60 + parts[2]
            elif len(parts) == 2:  # MM:SS
                return parts[0]*60 + parts[1]
        return float(time_str)
    except:
        return 0.0

# Process day data
if not day_df.empty:
    day_df['Date'] = pd.to_datetime(day_df['Date'], errors='coerce').dt.date
    day_df['Week'] = day_df['Date'].apply(lambda x: x.isocalendar()[1]).astype(str)
    
    time_cols = ['AHT', 'Wrap', 'Hold', 'Auto On']
    for col in time_cols:
        if col in day_df.columns:
            day_df[f"{col}_sec"] = day_df[col].apply(safe_convert_time)

# Process CSAT data
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
    st.subheader("📅 Monthly Performance")
    
    # Get available months
    if not month_df.empty:
        available_months = sorted(month_df['Month'].unique())
        selected_month = st.selectbox("Select Month", available_months)
        
        emp_id = st.text_input("Enter Employee ID", key="month_emp_id")
        
        if emp_id and selected_month:
            monthly_data = month_df[
                (month_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & 
                (month_df["Month"] == selected_month)
            ]
            
            if not monthly_data.empty:
                row = monthly_data.iloc[0]
                st.subheader(f"Performance for {row['NAME']} - {selected_month}")
                
                # Display KPIs
                cols = st.columns(4)
                metrics = [
                    ("📞 Call Volume", f"{row['LOGINS']} days"),
                    ("⏱️ Avg Hold", f"{row['Hold']}"),
                    ("📝 Avg Wrap", f"{row['Wrap']}"),
                    ("🤖 Auto-On", f"{row['Auto-On']}"),
                    ("😊 CSAT Res", f"{row['Resolution CSAT']}%"),
                    ("👍 CSAT Beh", f"{row['Agent Behaviour']}%"),
                    ("⭐ Quality", f"{row['Quality']}%"),
                    ("🧠 PKT", f"{row['PKT']}%")
                ]
                
                for i, (label, value) in enumerate(metrics):
                    cols[i%4].metric(label, value)
                
                # Show score
                st.progress(row['Grand Total']/5)
                st.metric("Overall Score", f"{row['Grand Total']}/5.0")
                
                # Show targets
                with st.expander("View Targets"):
                    targets = [
                        ("PKT Target", row.get('Target Committed for PKT', 'N/A')),
                        ("CSAT Target", row.get('Target Committed for CSAT (Agent Behaviour)', 'N/A')),
                        ("Quality Target", row.get('Target Committed for Quality', 'N/A'))
                    ]
                    for target in targets:
                        st.write(f"{target[0]}: {target[1]}")
            else:
                st.warning("No data found for this employee/month")

# === WEEK VIEW ===
elif time_frame == "Week":
    st.subheader("📅 Weekly Performance")
    
    if not day_df.empty and not csat_df.empty:
        # Get available weeks
        all_weeks = sorted(set(day_df['Week'].unique()) | set(csat_df['Week'].unique()))
        selected_week = st.selectbox("Select Week", all_weeks)
        
        emp_id = st.text_input("Enter Employee ID", key="week_emp_id")
        
        if emp_id and selected_week:
            # Get weekly call data
            week_calls = day_df[
                (day_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & 
                (day_df["Week"] == selected_week)
            ]
            
            # Get weekly CSAT
            week_csat = csat_df[
                (csat_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & 
                (csat_df["Week"] == selected_week)
            ]
            
            if not week_calls.empty:
                # Calculate metrics
                metrics = {
                    "📞 Total Calls": int(week_calls["Call Count"].sum()),
                    "⏱️ Avg AHT": str(timedelta(seconds=int(week_calls["AHT_sec"].mean()))[:-3],
                    "🕒 Avg Hold": str(timedelta(seconds=int(week_calls["Hold_sec"].mean()))[:-3],
                    "📝 Avg Wrap": str(timedelta(seconds=int(week_calls["Wrap_sec"].mean()))[:-3],
                    "🤖 Avg Auto On": str(timedelta(seconds=int(week_calls["Auto On_sec"].mean()))[:-3])
                }
                
                # Add CSAT if available
                if not week_csat.empty:
                    metrics.update({
                        "😊 CSAT Resolution": f"{week_csat['CSAT Resolution'].mean():.1f}%",
                        "👍 CSAT Behaviour": f"{week_csat['CSAT Behaviour'].mean():.1f}%"
                    })
                
                # Display
                st.subheader(f"Week {selected_week} Performance")
                for metric, value in metrics.items():
                    st.metric(metric, value)
                
                # Show daily breakdown
                with st.expander("Daily Breakdown"):
                    daily_data = week_calls.groupby('Date').agg({
                        'Call Count': 'sum',
                        'AHT_sec': 'mean',
                        'Hold_sec': 'mean',
                        'Wrap_sec': 'mean',
                        'Auto On_sec': 'mean'
                    }).reset_index()
                    
                    # Format time columns
                    for col in ['AHT_sec', 'Hold_sec', 'Wrap_sec', 'Auto On_sec']:
                        daily_data[col] = daily_data[col].apply(lambda x: str(timedelta(seconds=int(x)))[:-3])
                    
                    st.dataframe(daily_data)
            else:
                st.warning("No call data found for this employee/week")

# === DAY VIEW ===
else:
    st.subheader("📅 Daily Performance")
    
    if not day_df.empty:
        # Get available dates
        available_dates = sorted(day_df['Date'].unique())
        selected_date = st.selectbox("Select Date", available_dates)
        
        emp_id = st.text_input("Enter Employee ID", key="day_emp_id")
        
        if emp_id and selected_date:
            daily_data = day_df[
                (day_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & 
                (day_df["Date"] == selected_date)
            ]
            
            if not daily_data.empty:
                row = daily_data.iloc[0]
                st.subheader(f"Performance for {row['NAME']} - {selected_date}")
                
                # Format time columns
                def format_time(seconds):
                    return str(timedelta(seconds=int(seconds)))[:-3] if seconds > 0 else "00:00"
                
                metrics = [
                    ("📞 Calls", row['Call Count']),
                    ("⏱️ AHT", format_time(row.get('AHT_sec', 0))),
                    ("🕒 Hold", format_time(row.get('Hold_sec', 0))),
                    ("📝 Wrap", format_time(row.get('Wrap_sec', 0))),
                    ("🤖 Auto On", format_time(row.get('Auto On_sec', 0))),
                    ("😊 CSAT Res", f"{row.get('CSAT Resolution', 0)}%"),
                    ("👍 CSAT Beh", f"{row.get('CSAT Behaviour', 0)}%")
                ]
                
                # Display metrics
                cols = st.columns(4)
                for i, (label, value) in enumerate(metrics):
                    cols[i%4].metric(label, value)
                
                # Performance comment
                if row['Call Count'] > 50:
                    st.success("Excellent call volume today!")
                elif row['Call Count'] > 30:
                    st.info("Good performance today")
                else:
                    st.warning("Let's aim for more calls tomorrow")
            else:
                st.warning("No data found for this employee/date")
