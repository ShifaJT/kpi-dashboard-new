# ===== COMPLETE KPI DASHBOARD SOLUTION =====
import streamlit as st
import pandas as pd
import gspread
import numpy as np
from google.oauth2.service_account import Credentials
from streamlit_lottie import st_lottie
import requests
import random
from datetime import datetime, timedelta

# ===== CONFIGURATION =====
SHEET_ID = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"
SHEET_MONTH = "KPI Month"
SHEET_DAY = "KPI Day"
SHEET_CSAT = "CSAT Score"

# ===== GOOGLE SHEETS AUTHENTICATION =====
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)

# ===== DATA LOADING =====
@st.cache_data(ttl=3600)
def load_sheet_with_headers(name, expected_headers):
    try:
        worksheet = sheet.worksheet(name)
        records = worksheet.get_all_records(expected_headers=expected_headers)
        df = pd.DataFrame(records)
        
        # Clean data
        df = df.dropna(how='all')  # Remove empty rows
        df = df.loc[:, ~df.columns.duplicated()]  # Remove duplicate columns
        
        # Clean string columns
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace('', pd.NA)
                
        return df
    except Exception as e:
        st.error(f"Error loading {name} sheet: {str(e)}")
        return pd.DataFrame()

# Define expected headers matching your Google Sheets
MONTH_HEADERS = [
    "EMP ID", "NAME", "Month", "Hold", "Wrap", "Auto-On", "Schedule Adherence",
    "Resolution CSAT", "Agent Behaviour", "Quality", "PKT", "Hold KPI Score",
    "Wrap KPI Score", "Auto-On KPI Score", "Schedule Adherence KPI Score",
    "Resolution CSAT KPI Score", "Agent Behaviour KPI Score", "Quality KPI Score",
    "PKT KPI Score", "Grand Total", "SL + UPL", "LOGINS",
    "Target Committed for PKT", "Target Committed for CSAT (Agent Behaviour)",
    "Target Committed for Quality"
]

DAY_HEADERS = [
    "EMP ID", "Date", "NAME", "Call Count", "AHT", "Wrap", "Hold",
    "CSAT Resolution", "CSAT Behaviour", "Auto On", "Week"
]

CSAT_HEADERS = [
    "EMP ID", "NAME", "Week", "CSAT Resolution", "CSAT Behaviour"
]

# Load all data
month_df = load_sheet_with_headers(SHEET_MONTH, MONTH_HEADERS)
day_df = load_sheet_with_headers(SHEET_DAY, DAY_HEADERS)
csat_df = load_sheet_with_headers(SHEET_CSAT, CSAT_HEADERS)

# ===== DATA VALIDATION =====
def validate_data(df, df_name, required_cols):
    errors = []
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing column '{col}' in {df_name}")
        elif df[col].isna().all():
            errors.append(f"Column '{col}' in {df_name} has no data")
    return errors

validation_errors = []
validation_errors.extend(validate_data(month_df, 'Month', ["EMP ID", "Month", "Grand Total"]))
validation_errors.extend(validate_data(day_df, 'Day', ["EMP ID", "Call Count", "Date"]))
validation_errors.extend(validate_data(csat_df, 'CSAT', ["EMP ID", "CSAT Resolution"]))

if validation_errors:
    st.error("Data validation failed:")
    for error in validation_errors:
        st.error(error)
    st.stop()

# ===== DATA PROCESSING =====
def process_data(df):
    # Convert EMP IDs to strings
    if 'EMP ID' in df.columns:
        df['EMP ID'] = df['EMP ID'].astype(str).str.strip()
    
    # Convert percentages
    pct_cols = [col for col in df.columns if 'CSAT' in col or 'KPI Score' in col or 'Quality' in col]
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('%', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Convert dates
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    return df

month_df = process_data(month_df)
day_df = process_data(day_df)
csat_df = process_data(csat_df)

# Convert time columns to seconds
time_cols = ['AHT', 'Wrap', 'Hold', 'Auto On']
for col in time_cols:
    if col in day_df.columns:
        day_df[f"{col}_sec"] = day_df[col].apply(
            lambda x: sum(int(t) * 60**i for i, t in enumerate(reversed(x.split(':')))) 
            if isinstance(x, str) and ':' in x else 0
        )

# Add week numbers if not present
if 'Week' not in day_df.columns and 'Date' in day_df.columns:
    day_df['Week'] = day_df['Date'].dt.isocalendar().week.astype(str)

# ===== TOP PERFORMERS CALCULATION =====
def get_weekly_top_performers():
    try:
        current_week = str(datetime.now().isocalendar()[1])
        week_day = day_df[day_df['Week'] == current_week]
        week_csat = csat_df[csat_df['Week'] == current_week]
        
        if week_day.empty:
            return pd.DataFrame()
        
        # Aggregate metrics
        metrics = week_day.groupby(['EMP ID', 'NAME']).agg({
            'Call Count': 'sum',
            'Hold_sec': 'mean',
            'Wrap_sec': 'mean',
            'Auto On_sec': 'mean'
        }).reset_index()
        
        # Add CSAT scores
        if not week_csat.empty:
            csat_agg = week_csat.groupby(['EMP ID', 'NAME']).agg({
                'CSAT Resolution': 'mean',
                'CSAT Behaviour': 'mean'
            }).reset_index()
            metrics = pd.merge(metrics, csat_agg, on=['EMP ID', 'NAME'], how='left')
        
        metrics.fillna(0, inplace=True)
        
        # Apply weights (Call Count 0%, Hold 5%, Wrap 5%, CSAT Beh 25%, CSAT Res 25%, Auto On 40%)
        def normalize(col, reverse=False):
            if metrics[col].max() == metrics[col].min():
                return 50
            if reverse:
                return 100 * (metrics[col].max() - metrics[col]) / (metrics[col].max() - metrics[col].min())
            return 100 * (metrics[col] - metrics[col].min()) / (metrics[col].max() - metrics[col].min())
        
        metrics['Score'] = (
            normalize('Hold_sec', reverse=True) * 0.05 +
            normalize('Wrap_sec', reverse=True) * 0.05 +
            normalize('CSAT Behaviour') * 0.25 +
            normalize('CSAT Resolution') * 0.25 +
            normalize('Auto On_sec') * 0.40
        )
        
        # Format for display
        metrics['Hold'] = metrics['Hold_sec'].apply(lambda x: str(timedelta(seconds=int(x))).split('.')[0])
        metrics['Wrap'] = metrics['Wrap_sec'].apply(lambda x: str(timedelta(seconds=int(x))).split('.')[0])
        metrics['Auto On'] = metrics['Auto On_sec'].apply(lambda x: str(timedelta(seconds=int(x))).split('.')[0])
        metrics['CSAT Beh'] = metrics['CSAT Behaviour'].apply(lambda x: f"{x:.1f}%")
        metrics['CSAT Res'] = metrics['CSAT Resolution'].apply(lambda x: f"{x:.1f}%")
        
        return metrics.nlargest(5, 'Score')
    
    except Exception as e:
        st.error(f"Error calculating top performers: {str(e)}")
        return pd.DataFrame()

# ===== DASHBOARD UI =====
st.set_page_config(layout="wide")
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .metric-title {
        font-weight: bold;
        font-size: 16px;
        margin-bottom: 10px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div style="background: linear-gradient(to right, #0072ff, #00c6ff); padding: 20px; border-radius: 10px; color: white;">
    <h1 style="margin: 0; text-align: center;">🏆 KPI Dashboard for Champions</h1>
</div>
""", unsafe_allow_html=True)

# Top Performers Section
st.markdown("## 🏅 Current Week's Top Performers")
top_performers = get_weekly_top_performers()

if not top_performers.empty:
    cols = st.columns(5)
    for idx, (_, row) in enumerate(top_performers.iterrows()):
        with cols[idx]:
            medal = ['🥇', '🥈', '🥉', '🎖️', '🎖️'][idx]
            st.markdown(f"""
            <div class="metric-card">
                <div style="text-align: center; font-size: 18px; margin-bottom: 10px;">
                    {medal} <strong>{row['NAME']}</strong>
                </div>
                <table style="width: 100%; font-size: 14px;">
                    <tr><td>📞 Calls:</td><td style="text-align: right;">{int(row['Call Count'])}</td></tr>
                    <tr><td>🕒 Hold:</td><td style="text-align: right;">{row['Hold']}</td></tr>
                    <tr><td>📝 Wrap:</td><td style="text-align: right;">{row['Wrap']}</td></tr>
                    <tr><td>😊 CSAT Res:</td><td style="text-align: right;">{row['CSAT Res']}</td></tr>
                    <tr><td>👍 CSAT Beh:</td><td style="text-align: right;">{row['CSAT Beh']}</td></tr>
                    <tr><td>🤖 Auto On:</td><td style="text-align: right;">{row['Auto On']}</td></tr>
                </table>
                <div style="text-align: center; margin-top: 10px; font-size: 12px; color: #666;">
                    Score: {row['Score']:.1f}
                </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("📭 No performance data available for the current week.")

# Timeframe Selector
time_frame = st.selectbox("⏳ Select Timeframe", ["Day", "Week", "Month"], key="timeframe_select")

# ===== DAY VIEW =====
if time_frame == "Day":
    st.markdown("## 📅 Daily Performance")
    
    emp_id = st.text_input("🔢 Enter EMP ID", key="day_emp_id")
    available_dates = sorted(day_df['Date'].dt.date.unique())
    selected_date = st.selectbox("Select Date", available_dates, key="day_date_select")
    
    if emp_id:
        daily_data = day_df[
            (day_df['EMP ID'].str.strip() == emp_id.strip()) & 
            (day_df['Date'].dt.date == selected_date)
        ]
        
        if not daily_data.empty:
            row = daily_data.iloc[0]
            emp_name = row['NAME'] if 'NAME' in row else "Unknown"
            
            st.markdown(f"### {emp_name}'s Performance on {selected_date.strftime('%Y-%m-%d')}")
            
            # Create metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">📞 Call Count</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(int(row['Call Count'])), unsafe_allow_html=True)
                
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">⏱️ AHT</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(
                    str(timedelta(seconds=int(row['AHT_sec']))).split('.')[0] if 'AHT_sec' in row else "N/A"
                ), unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">🕒 Hold Time</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(
                    str(timedelta(seconds=int(row['Hold_sec']))).split('.')[0] if 'Hold_sec' in row else "N/A"
                ), unsafe_allow_html=True)
                
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">📝 Wrap Time</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(
                    str(timedelta(seconds=int(row['Wrap_sec']))).split('.')[0] if 'Wrap_sec' in row else "N/A"
                ), unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">🤖 Auto On</div>
                    <div class="metric-value">{}</div>
                </div>
                """.format(
                    str(timedelta(seconds=int(row['Auto On_sec']))).split('.')[0] if 'Auto On_sec' in row else "N/A"
                ), unsafe_allow_html=True)
                
                if 'CSAT Resolution' in row and 'CSAT Behaviour' in row:
                    st.markdown("""
                    <div class="metric-card">
                        <div class="metric-title">😊 CSAT Scores</div>
                        <div>Resolution: {:.1f}%</div>
                        <div>Behaviour: {:.1f}%</div>
                    </div>
                    """.format(
                        float(row['CSAT Resolution']), float(row['CSAT Behaviour'])
                    ), unsafe_allow_html=True)
            
            # Performance comment
            if 'Call Count' in row:
                calls = int(row['Call Count'])
                if calls > 50:
                    st.success("🎯 Excellent call volume today!")
                elif calls > 30:
                    st.info("👍 Solid performance today!")
                else:
                    st.warning("💪 Keep pushing - tomorrow is another opportunity!")
        else:
            st.warning("No data found for this EMP ID and date")

# ===== WEEK VIEW =====
elif time_frame == "Week":
    st.markdown("## 📅 Weekly Performance")
    
    emp_id = st.text_input("🔢 Enter EMP ID", key="week_emp_id")
    available_weeks = sorted(day_df['Week'].unique())
    selected_week = st.selectbox("Select Week", available_weeks, key="week_select")
    
    if emp_id:
        week_data = day_df[
            (day_df['EMP ID'].str.strip() == emp_id.strip()) & 
            (day_df['Week'] == selected_week)
        ]
        
        if not week_data.empty:
            emp_name = week_data.iloc[0]['NAME'] if 'NAME' in week_data.columns else "Unknown"
            
            st.markdown(f"### {emp_name}'s Performance for Week {selected_week}")
            
            # Calculate weekly aggregates
            agg_data = {
                "📞 Total Calls": int(week_data['Call Count'].sum()),
                "⏱️ Avg AHT": str(timedelta(seconds=int(week_data['AHT_sec'].mean()))).split('.')[0],
                "🕒 Avg Hold": str(timedelta(seconds=int(week_data['Hold_sec'].mean()))).split('.')[0],
                "📝 Avg Wrap": str(timedelta(seconds=int(week_data['Wrap_sec'].mean()))).split('.')[0],
                "🤖 Avg Auto On": str(timedelta(seconds=int(week_data['Auto On_sec'].mean()))).split('.')[0]
            }
            
            # Display metrics
            col1, col2 = st.columns(2)
            
            with col1:
                for metric, value in list(agg_data.items())[:3]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">{metric}</div>
                        <div class="metric-value">{value}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col2:
                for metric, value in list(agg_data.items())[3:]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">{metric}</div>
                        <div class="metric-value">{value}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Add CSAT if available
            week_csat = csat_df[
                (csat_df['EMP ID'].str.strip() == emp_id.strip()) &
                (csat_df['Week'] == selected_week)
            ]
            
            if not week_csat.empty:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">😊 Weekly CSAT Averages</div>
                    <div>Resolution: {:.1f}%</div>
                    <div>Behaviour: {:.1f}%</div>
                </div>
                """.format(
                    week_csat['CSAT Resolution'].mean(),
                    week_csat['CSAT Behaviour'].mean()
                ), unsafe_allow_html=True)
            
            # Daily breakdown
            st.markdown("#### Daily Breakdown")
            daily_breakdown = week_data.groupby('Date').agg({
                'Call Count': 'sum',
                'AHT_sec': 'mean',
                'Hold_sec': 'mean',
                'Wrap_sec': 'mean',
                'Auto On_sec': 'mean'
            }).reset_index()
            
            # Format time columns
            for col in ['AHT_sec', 'Hold_sec', 'Wrap_sec', 'Auto On_sec']:
                daily_breakdown[col] = daily_breakdown[col].apply(
                    lambda x: str(timedelta(seconds=int(x))).split('.')[0]
                )
            
            st.dataframe(daily_breakdown, hide_index=True, use_container_width=True)
            
        else:
            st.warning("No data found for this EMP ID and week")

# ===== MONTH VIEW =====
elif time_frame == "Month":
    st.markdown("## 📅 Monthly Performance")
    
    emp_id = st.text_input("🔢 Enter EMP ID", key="month_emp_id")
    available_months = sorted(month_df['Month'].unique())
    selected_month = st.selectbox("Select Month", available_months, key="month_select")
    
    if emp_id:
        month_data = month_df[
            (month_df['EMP ID'].str.strip() == emp_id.strip()) & 
            (month_df['Month'] == selected_month)
        ]
        
        if not month_data.empty:
            row = month_data.iloc[0]
            emp_name = row['NAME'] if 'NAME' in row else "Unknown"
            
            st.markdown(f"### {emp_name}'s Performance for {selected_month}")
            
            # Main metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">🏅 Grand Total KPI</div>
                    <div class="metric-value">{:.1f}</div>
                </div>
                """.format(float(row['Grand Total'])), unsafe_allow_html=True)
                
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">⭐ Quality Score</div>
                    <div class="metric-value">{:.1f}%</div>
                </div>
                """.format(float(row['Quality'])), unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">😊 Resolution CSAT</div>
                    <div class="metric-value">{:.1f}%</div>
                </div>
                """.format(float(row['Resolution CSAT'])), unsafe_allow_html=True)
                
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">👍 Agent Behaviour</div>
                    <div class="metric-value">{:.1f}%</div>
                </div>
                """.format(float(row['Agent Behaviour'])), unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">🧠 PKT Score</div>
                    <div class="metric-value">{:.1f}%</div>
                </div>
                """.format(float(row['PKT'])), unsafe_allow_html=True)
                
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-title">✅ Adherence</div>
                    <div class="metric-value">{:.1f}%</div>
                </div>
                """.format(float(row['Schedule Adherence'])), unsafe_allow_html=True)
            
            # KPI Breakdown
            st.markdown("#### KPI Score Breakdown")
            kpi_scores = pd.DataFrame({
                "Metric": ["Hold", "Auto-On", "Adherence", "Resolution CSAT", "Agent Behaviour", "Quality", "PKT"],
                "Weightage": ["0%", "30%", "10%", "10%", "20%", "20%", "10%"],
                "Score": [
                    row['Hold KPI Score'],
                    row['Auto-On KPI Score'],
                    row['Schedule Adherence KPI Score'],
                    row['Resolution CSAT KPI Score'],
                    row['Agent Behaviour KPI Score'],
                    row['Quality KPI Score'],
                    row['PKT KPI Score']
                ]
            })
            st.dataframe(kpi_scores, hide_index=True, use_container_width=True)
            
            # Targets for next month
            st.markdown("#### Targets for Next Month")
            targets = pd.DataFrame({
                "Metric": ["PKT", "CSAT (Agent Behaviour)", "Quality"],
                "Target": [
                    row['Target Committed for PKT'],
                    row['Target Committed for CSAT (Agent Behaviour)'],
                    row['Target Committed for Quality']
                ]
            })
            st.dataframe(targets, hide_index=True, use_container_width=True)
            
            # Month comparison
            month_index = available_months.index(selected_month)
            if month_index > 0:
                prev_month = available_months[month_index - 1]
                prev_data = month_df[
                    (month_df['EMP ID'].str.strip() == emp_id.strip()) & 
                    (month_df['Month'] == prev_month)
                ]
                
                if not prev_data.empty:
                    prev_row = prev_data.iloc[0]
                    diff = float(row['Grand Total']) - float(prev_row['Grand Total'])
                    
                    if diff > 0:
                        st.success(f"📈 Improved by +{diff:.1f} points from {prev_month}")
                    elif diff < 0:
                        st.warning(f"📉 Decreased by {abs(diff):.1f} points from {prev_month}")
                    else:
                        st.info(f"➖ No change from {prev_month}")
            
            # Motivational message
            score = float(row['Grand Total'])
            if score >= 4.5:
                st.success("🎉 Outstanding performance! Keep up the excellent work!")
            elif score >= 4.0:
                st.info("🌟 Great job! You're performing above expectations")
            elif score >= 3.0:
                st.warning("💪 Good work! There's room for improvement")
            else:
                st.error("🔥 Let's work together to improve next month")
            
            if lottie_cheer:
                st_lottie(lottie_cheer, speed=1, height=200, key="cheer")
            
        else:
            st.warning("No data found for this EMP ID and month")
