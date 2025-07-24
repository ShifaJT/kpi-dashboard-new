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
        
        # First get all data as list of lists
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
if time_frame == "Month":
    st.subheader("📅 Monthly Performance")
    
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
                    ("📞 Call Volume", f"{row.get('LOGINS', 'N/A')} days"),
                    ("⏱️ Avg Hold", f"{row.get('Hold', 'N/A')}"),
                    ("📝 Avg Wrap", f"{row.get('Wrap', 'N/A')}"),
                    ("🤖 Auto-On", f"{row.get('Auto-On', 'N/A')}"),
                    ("😊 CSAT Res", f"{row.get('Resolution CSAT', 'N/A')}%"),
                    ("👍 CSAT Beh", f"{row.get('Agent Behaviour', 'N/A')}%"),
                    ("⭐ Quality", f"{row.get('Quality', 'N/A')}%"),
                    ("🧠 PKT", f"{row.get('PKT', 'N/A')}%")
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
    emp_id = st.text_input("Enter EMP ID")

    day_df["Week"] = pd.to_numeric(day_df["Week"], errors="coerce")
    day_df = day_df.dropna(subset=["Week"])
    day_df["Week"] = day_df["Week"].astype(int)

    selected_week = st.selectbox("Select Week Number", sorted(day_df["Week"].unique()))

  if emp_id and selected_week:
    week_data = day_df[(day_df["EMP ID"].astype(str) == emp_id) & (day_df["Week"] == selected_week)]

    csat_df['EMP ID'] = csat_df['EMP ID'].astype(str).str.strip()
    csat_df['Week'] = csat_df['Week'].astype(str).str.strip()

    csat_data = csat_df[
        (csat_df["EMP ID"] == emp_id.strip()) &
        (csat_df["Week"] == str(selected_week).strip())
    ]

    if not week_data.empty:
        emp_name = week_data["NAME"].iloc[0]
        st.markdown(f"### Weekly KPI Data for **{emp_name}** | Week {selected_week}")

        total_calls = week_data["Call Count"].sum()
        avg_aht = pd.to_timedelta(week_data["AHT"]).mean()
        avg_hold = pd.to_timedelta(week_data["Hold"]).mean()
        avg_wrap = pd.to_timedelta(week_data["Wrap"]).mean()
        avg_auto_on = pd.to_timedelta(week_data["Auto On"]).mean()

        def fmt(td):
            return str(td).split(" ")[-1].split(".")[0]

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
            " You’ve got the spark — now fire up more!",
            " Progress is progress, no matter how small."
        ]
        st.info(random.choice(quotes))
    else:
        st.warning("No data found for that EMP ID and week.")

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
