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

# === IMPROVED DATA LOADING WITH DUPLICATE HEADER HANDLING ===
@st.cache_data(ttl=3600)
def load_sheet(name):
    try:
        sheet = client.open_by_key(SHEET_ID)
        worksheet = sheet.worksheet(name)
        
        # Get all data as list of lists (bypasses get_all_records header issue)
        all_data = worksheet.get_all_values()
        
        # Process headers to handle duplicates
        original_headers = all_data[0]
        cleaned_headers = []
        header_counts = {}
        
        for header in original_headers:
            header = header.strip()
            if not header:
                header = "Unnamed"
                
            # Handle duplicate headers
            if header in header_counts:
                header_counts[header] += 1
                header = f"{header}_{header_counts[header]}"
            else:
                header_counts[header] = 1
                
            cleaned_headers.append(header)
        
        # Create DataFrame with cleaned headers
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
# === MONTH VIEW ===
if time_frame == "Month":
    st.subheader("📅 Monthly Performance")
    
    if not month_df.empty:
        # Convert month strings to datetime for proper sorting
        try:
            month_df['Month'] = pd.to_datetime(month_df['Month'], format='%b-%y', errors='coerce')
            available_months = month_df['Month'].dropna().unique()
            available_months = sorted(available_months)
            month_names = [month.strftime('%b-%y') for month in available_months]
        except:
            month_names = sorted(month_df['Month'].unique())
        
        selected_month = st.selectbox("Select Month", month_names)
        emp_id = st.text_input("Enter Employee ID", key="month_emp_id")
        
        if emp_id and selected_month:
            # Filter data for selected month and employee
            monthly_data = month_df[
                (month_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & 
                (month_df['Month'].astype(str).str.contains(selected_month))
            ]
            
            if not monthly_data.empty:
                row = monthly_data.iloc[0]
                st.subheader(f"Performance for {row['NAME']} - {selected_month}")
                
                # Performance Metrics Section
                st.markdown("### 📊 Performance Metrics")
                cols = st.columns(4)
                metrics = [
                    ("⏱️ Hold Time", row.get('Hold', 'N/A')),
                    ("📝 Wrap Time", row.get('Wrap', 'N/A')),
                    ("🤖 Auto-On", row.get('Auto-On', 'N/A')),
                    ("⏰ Schedule Adherence", f"{row.get('Schedule Adherence', 'N/A')}%"),
                    ("😊 CSAT Resolution", f"{row.get('Resolution CSAT', 'N/A')}%"),
                    ("👍 CSAT Behaviour", f"{row.get('Agent Behaviour', 'N/A')}%"),
                    ("⭐ Quality", f"{row.get('Quality', 'N/A')}%"),
                    ("🧠 PKT", f"{row.get('PKT', 'N/A')}%"),
                    ("📅 SL + UPL", row.get('SL + UPL', 'N/A')),
                    ("📞 Logins", row.get('LOGINS', 'N/A'))
                ]
                
                for i, (label, value) in enumerate(metrics):
                    cols[i%4].metric(label, value)
                
                # Rest of your month view code...
            else:
                st.warning("No data found for this employee/month")
    else:
        st.warning("Monthly data not loaded properly")

# === WEEK VIEW ===
elif time_frame == "Week":
    st.subheader("📅 Weekly Performance")
    
    if not day_df.empty and not csat_df.empty:
        # Get available weeks from both dataframes
        day_weeks = day_df['Week'].dropna().unique()
        csat_weeks = csat_df['Week'].dropna().unique()
        all_weeks = sorted(set(day_weeks) | set(csat_weeks))
        
        selected_week = st.selectbox("Select Week", all_weeks, key="week_select")
        emp_id = st.text_input("Enter Employee ID", key="week_emp_id")
        
        if emp_id and selected_week:
            try:
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
                    total_calls = int(week_calls["Call Count"].sum())
                    avg_aht = str(timedelta(seconds=int(week_calls["AHT_sec"].mean())))[:-3]
                    avg_hold = str(timedelta(seconds=int(week_calls["Hold_sec"].mean())))[:-3]
                    avg_wrap = str(timedelta(seconds=int(week_calls["Wrap_sec"].mean())))[:-3]
                    avg_auto = str(timedelta(seconds=int(week_calls["Auto On_sec"].mean())))[:-3]
                    
                    # Display metrics
                    st.subheader(f"Week {selected_week} Performance")
                    
                    # Call Metrics
                    st.markdown("### 📞 Call Metrics")
                    cols = st.columns(4)
                    call_metrics = [
                        ("Total Calls", total_calls),
                        ("Avg AHT", avg_aht),
                        ("Avg Hold", avg_hold),
                        ("Avg Wrap", avg_wrap),
                        ("Avg Auto On", avg_auto)
                    ]
                    
                    for i, (label, value) in enumerate(call_metrics):
                        cols[i%4].metric(label, value)
                    
                    # CSAT Metrics if available
                    if not week_csat.empty:
                        st.markdown("### 😊 CSAT Metrics")
                        csat_cols = st.columns(2)
                        csat_metrics = [
                            ("CSAT Resolution", f"{week_csat['CSAT Resolution'].mean():.1f}%"),
                            ("CSAT Behaviour", f"{week_csat['CSAT Behaviour'].mean():.1f}%")
                        ]
                        for i, (label, value) in enumerate(csat_metrics):
                            csat_cols[i].metric(label, value)
                    
                    # Daily Breakdown
                    with st.expander("📅 View Daily Breakdown"):
                        daily_data = week_calls.groupby('Date').agg({
                            'Call Count': 'sum',
                            'AHT_sec': 'mean',
                            'Hold_sec': 'mean',
                            'Wrap_sec': 'mean',
                            'Auto On_sec': 'mean'
                        }).reset_index()
                        
                        # Format time columns
                        for col in ['AHT_sec', 'Hold_sec', 'Wrap_sec', 'Auto On_sec']:
                            daily_data[col] = daily_data[col].apply(
                                lambda x: str(timedelta(seconds=int(x)))[:-3] if pd.notnull(x) else '00:00'
                            )
                        
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
        # Show date selector first
        available_dates = sorted(day_df['Date'].dropna().unique())
        selected_date = st.selectbox("Select Date", available_dates, key="day_date_select")
        
        # Then show EMP ID input
        emp_id = st.text_input("Enter Employee ID", key="day_emp_id")
        
        if emp_id and selected_date:
            # Filter the data
            daily_data = day_df[
                (day_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) & 
                (day_df["Date"] == selected_date)
            ]
            
            if not daily_data.empty:
                row = daily_data.iloc[0]
                st.subheader(f"Performance for {row['NAME']} on {selected_date}")
                
                # Format time
                def format_time(seconds):
                    return str(timedelta(seconds=int(seconds)))[:-3] if seconds > 0 else "00:00"
                
                # Prepare metrics
                cols = st.columns(4)
                metrics = [
                    ("📞 Calls", row.get('Call Count', 0)),
                    ("⏱️ AHT", format_time(row.get('AHT_sec', 0))),
                    ("🕒 Hold", format_time(row.get('Hold_sec', 0))),
                    ("📝 Wrap", format_time(row.get('Wrap_sec', 0))),
                    ("🤖 Auto On", format_time(row.get('Auto On_sec', 0))),
                    ("😊 CSAT Res", f"{row.get('CSAT Resolution', 0)}%"),
                    ("👍 CSAT Beh", f"{row.get('CSAT Behaviour', 0)}%")
                ]
                
                # Display metrics
                for i, (label, value) in enumerate(metrics):
                    cols[i%4].metric(label, value)
                
                # Performance comment
                call_count = row.get('Call Count', 0)
                if isinstance(call_count, str):
                    try:
                        call_count = float(call_count)
                    except:
                        call_count = 0
                
                if call_count > 50:
                    st.success("Excellent call volume today!")
                elif call_count > 30:
                    st.info("Good performance today")
                else:
                    st.warning("Let's aim for more calls tomorrow")
            else:
                st.warning("No data found for this employee/date")
    else:
        st.warning("Daily data not loaded properly")
