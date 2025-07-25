# === COMPLETE KPI DASHBOARD SOLUTION ===
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import numpy as np

# ======================
# STYLING IMPROVEMENTS
# ======================
st.markdown("""
<style>
    /* Main styling */
    .header {
        color: #2c3e50;
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .subheader {
        color: #1a73e8;
        font-size: 1.4rem;
        font-weight: 600;
        margin: 1.5rem 0 1rem 0;
    }
    
    /* Top Performers Section */
    .top-performer-container {
        margin-bottom: 1.5rem;
    }
    .top-performer-header {
        color: #2c3e50;
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .week-header {
        color: #1a73e8;
        font-size: 1.3rem;
        margin-bottom: 1rem;
    }
    .performer-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        border-left: 4px solid #1a73e8;
    }
    .performer-rank {
        font-weight: 700;
        color: #1a73e8;
        font-size: 1.2rem;
        margin-bottom: 0.5rem;
    }
    .performer-name {
        font-weight: 600;
        color: #2c3e50;
        font-size: 1.1rem;
        margin-bottom: 0.8rem;
    }
    .metric-row {
        display: flex;
        margin-bottom: 0.5rem;
    }
    .metric-label {
        font-weight: 500;
        color: #5f6368;
        width: 100px;
    }
    .metric-value {
        font-weight: 400;
        color: #202124;
    }

    /* Table styling */
    .metric-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
    }
    .metric-table th {
        background-color: #f1f3f4;
        text-align: left;
        padding: 0.5rem;
        font-weight: 500;
    }
    .metric-table td {
        padding: 0.5rem;
        border-bottom: 1px solid #f1f3f4;
    }
    
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .header, .top-performer-header, .performer-name {
            color: #e8eaed;
        }
        .subheader, .week-header, .performer-rank {
            color: #8ab4f8;
        }
        .performer-card {
            background-color: #202124;
            border-left-color: #8ab4f8;
        }
        .metric-label {
            color: #9aa0a6;
        }
        .metric-value {
            color: #f1f3f4;
        }
        .metric-table th {
            background-color: #303134;
        }
        .metric-table td {
            border-bottom-color: #3c4043;
        }
    }
</style>
""", unsafe_allow_html=True)

# ======================
# HELPER FUNCTIONS
# ======================
def clean_value(val):
    """Clean and format values for display"""
    if pd.isna(val) or str(val).strip() in ['', 'nan', 'None']:
        return 'N/A'
    return str(val).replace('%', '').strip()

def clean_percentage(val):
    """Format percentage values"""
    cleaned = clean_value(val)
    return f"{cleaned}%" if cleaned != 'N/A' else 'N/A'

def safe_convert_time(time_val):
    """Convert time values to seconds"""
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

def format_time_display(seconds):
    """Format seconds into HH:MM:SS"""
    if pd.isna(seconds) or seconds == 0:
        return "00:00:00"
    return str(timedelta(seconds=int(seconds))).split('.')[0]

# ======================
# TOP PERFORMERS LOGIC
# ======================
def calculate_weighted_score(row):
    """Calculate weighted score for ranking"""
    try:
        # Convert time metrics to seconds
        hold = safe_convert_time(row.get('Hold', 0))
        wrap = safe_convert_time(row.get('Wrap', 0))
        auto_on = safe_convert_time(row.get('Auto On', 0))
        
        # Convert CSAT percentages
        csat_beh = float(str(row.get('CSAT Behaviour', '0')).replace('%', '')) if str(row.get('CSAT Behaviour', '0')).replace('%', '').replace('.', '').isdigit() else 0
        csat_res = float(str(row.get('CSAT Resolution', '0')).replace('%', '')) if str(row.get('CSAT Resolution', '0')).replace('%', '').replace('.', '').isdigit() else 0
        
        # Normalize time metrics (lower is better)
        hold_score = max(0, 100 - (hold / 60 * 100)) if hold > 0 else 100
        wrap_score = max(0, 100 - (wrap / 120 * 100)) if wrap > 0 else 100
        auto_on_score = min(100, (auto_on / (8*3600) * 100)) if auto_on > 0 else 0
        
        # Calculate weighted score
        weighted_score = (
            (hold_score * 0.05) + 
            (wrap_score * 0.05) + 
            (csat_beh * 0.25) + 
            (csat_res * 0.25) + 
            (auto_on_score * 0.40)
        )
        return round(weighted_score, 2)
    except Exception as e:
        st.error(f"Error calculating score: {str(e)}")
        return 0

def get_weekly_top_performers(day_df, csat_df, week):
    """Identify top 5 performers for a given week with actual metrics"""
    try:
        week_day_data = day_df[day_df['Week'] == str(week)].copy()
        week_csat_data = csat_df[csat_df['Week'] == str(week)].copy()
        
        if week_day_data.empty or week_csat_data.empty:
            return pd.DataFrame()
        
        weekly_metrics = week_day_data.groupby(['EMP ID', 'NAME']).agg({
            'Hold_sec': 'mean',
            'Wrap_sec': 'mean',
            'Auto On_sec': 'mean',
            'Call Count': 'sum'
        }).reset_index()
        
        weekly_metrics = pd.merge(
            weekly_metrics,
            week_csat_data[['EMP ID', 'CSAT Behaviour', 'CSAT Resolution']],
            on='EMP ID',
            how='left'
        )
        
        weekly_metrics['_weighted_score'] = weekly_metrics.apply(calculate_weighted_score, axis=1)
        top_performers = weekly_metrics.sort_values('_weighted_score', ascending=False).head(5)
        
        top_performers['Hold'] = top_performers['Hold_sec'].apply(format_time_display)
        top_performers['Wrap'] = top_performers['Wrap_sec'].apply(format_time_display)
        top_performers['Auto On'] = top_performers['Auto On_sec'].apply(format_time_display)
        
        for col in ['CSAT Behaviour', 'CSAT Resolution']:
            if col in top_performers.columns:
                top_performers[col] = top_performers[col].apply(lambda x: f"{x}%" if pd.notna(x) else 'N/A')
        
        return top_performers[['EMP ID', 'NAME', 'Hold', 'Wrap', 'Auto On', 'CSAT Behaviour', 'CSAT Resolution']]
    except Exception as e:
        st.error(f"Error identifying top performers: {str(e)}")
        return pd.DataFrame()

# ======================
# CONFIGURATION
# ======================
SHEET_ID = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"
SHEET_MONTH = "KPI Month"
SHEET_DAY = "KPI Day"
SHEET_CSAT = "CSAT Score"

# ======================
# DATA LOADING
# ======================
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

# ======================
# DATA PROCESSING
# ======================
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

# ======================
# DASHBOARD UI
# ======================
st.markdown('<div class="header">KPI Performance Dashboard</div>', unsafe_allow_html=True)

# Timeframe selection
time_frame = st.radio("Select Timeframe:", ["Day", "Week", "Month"], horizontal=True)

# TOP PERFORMERS SECTION
if not day_df.empty and not csat_df.empty:
    current_week = datetime.now().isocalendar()[1]
    top_performers = get_weekly_top_performers(day_df, csat_df, current_week)
    
    if not top_performers.empty:
        with st.sidebar:
            st.markdown("""
            <div class="top-performer-container">
                <div class="top-performer-header">Weekly Top Performers</div>
                <div class="week-header">Week {}</div>
            </div>
            """.format(current_week), unsafe_allow_html=True)
            
            for i, (_, row) in enumerate(top_performers.iterrows(), 1):
                st.markdown(f"""
                <div class="performer-card">
                    <div class="performer-rank">Rank #{i}</div>
                    <div class="performer-name">{row['NAME']}</div>
                    
                    <div class="metric-row">
                        <span class="metric-label">Hold:</span>
                        <span class="metric-value">{row['Hold']}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Wrap:</span>
                        <span class="metric-value">{row['Wrap']}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Auto On:</span>
                        <span class="metric-value">{row['Auto On']}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">CSAT Beh:</span>
                        <span class="metric-value">{row.get('CSAT Behaviour', 'N/A')}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">CSAT Res:</span>
                        <span class="metric-value">{row.get('CSAT Resolution', 'N/A')}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# MONTH VIEW
if time_frame == "Month":
    st.markdown('<div class="subheader">📅 Monthly Performance</div>', unsafe_allow_html=True)

    if not month_df.empty:
        month_df['Month'] = month_df['Month'].astype(str).str.strip()
        month_names = sorted(month_df['Month'].unique())

        if len(month_names) == 0:
            st.error("No months found in the data. Please check your 'KPI Month' sheet.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                selected_month = st.selectbox("Select Month", month_names)
            with col2:
                emp_id = st.text_input("Enter Employee ID", key="month_emp_id")

            if emp_id and selected_month:
                try:
                    monthly_data = month_df[
                        (month_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) &
                        (month_df['Month'].str.strip() == selected_month.strip())
                    ]

                    if not monthly_data.empty:
                        row = monthly_data.iloc[0]
                        st.markdown(f'<div class="subheader">Performance for {row["NAME"]} - {selected_month}</div>', unsafe_allow_html=True)

                        # Performance Metrics Table
                        st.markdown("""
                        <table class="metric-table">
                            <tr>
                                <th colspan="4">Performance Metrics</th>
                            </tr>
                            <tr>
                                <td>Hold Time</td>
                                <td>Wrap Time</td>
                                <td>Auto-On</td>
                                <td>Schedule Achieved</td>
                            </tr>
                            <tr>
                                <td>{}</td>
                                <td>{}</td>
                                <td>{}</td>
                                <td>{}</td>
                            </tr>
                            <tr>
                                <td>CSAT Resolution</td>
                                <td>CSAT Behaviour</td>
                                <td>Quality</td>
                                <td>PKT</td>
                            </tr>
                            <tr>
                                <td>{}</td>
                                <td>{}</td>
                                <td>{}</td>
                                <td>{}</td>
                            </tr>
                        </table>
                        """.format(
                            clean_value(row.get('Hold')),
                            clean_value(row.get('Wrap')),
                            clean_value(row.get('Auto-On')),
                            clean_percentage(row.get('Schedule Adherence')),
                            clean_percentage(row.get('Resolution CSAT')),
                            clean_percentage(row.get('Agent Behaviour')),
                            clean_percentage(row.get('Quality')),
                            clean_percentage(row.get('PKT'))
                        ), unsafe_allow_html=True)

                        # Additional Metrics
                        cols = st.columns(2)
                        cols[0].metric("SL + UPL", clean_value(row.get('SL + UPL')))
                        cols[1].metric("Logins", clean_value(row.get('LOGINS')))

                        st.markdown('<div class="subheader">🎯 KPI Scores</div>', unsafe_allow_html=True)
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
                            st.markdown('<div class="subheader">📈 Overall KPI Score</div>', unsafe_allow_html=True)
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
                                    st.success(f"**{abs(delta):.1f} improved from last month.** Keep up the great work!")
                                elif delta < 0:
                                    st.warning(f"**{abs(delta):.1f} dropped from last month.** Focus on areas for improvement!")
                            else:
                                st.metric("Overall Score", f"{current_score:.1f}/5.0")
                                st.info("No previous month data available for comparison")

                            st.progress(current_score / 5)

                        st.markdown('<div class="subheader">🎯 Targets Committed</div>', unsafe_allow_html=True)
                        target_cols = st.columns(3)
                        targets = [
                            ("PKT Target", clean_value(row.get('Target Committed for PKT'))),
                            ("CSAT Target", clean_value(row.get('Target Committed for CSAT (Agent Behaviour)'))),
                            ("Quality Target", clean_value(row.get('Target Committed for Quality')))
                        ]
                        for i, (label, value) in enumerate(targets):
                            target_cols[i].metric(label, value)

                    else:
                        st.warning("No data found for this employee/month combination")
                except Exception as e:
                    st.error(f"Error processing data: {str(e)}")
    else:
        st.warning("Monthly data not loaded properly")

# WEEK VIEW
elif time_frame == "Week":
    st.markdown('<div class="subheader">📅 Weekly Performance</div>', unsafe_allow_html=True)
    
    if not day_df.empty and not csat_df.empty:
        day_weeks = day_df['Week'].dropna().unique()
        csat_weeks = csat_df['Week'].dropna().unique()
        all_weeks = sorted(set(day_weeks) | set(csat_weeks))
        
        col1, col2 = st.columns(2)
        with col1:
            selected_week = st.selectbox("Select Week", all_weeks, key="week_select")
        with col2:
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
                        return format_time_display(avg_sec)
                    
                    st.markdown(f'<div class="subheader">Week {selected_week} Performance</div>', unsafe_allow_html=True)
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
                    st.warning("No call data found for this employee/week combination")
            except Exception as e:
                st.error(f"Error processing weekly data: {str(e)}")
    else:
        st.warning("Weekly data not loaded properly")

# DAY VIEW
else:
    st.markdown('<div class="subheader">📅 Daily Performance</div>', unsafe_allow_html=True)
    
    if not day_df.empty:
        available_dates = sorted(day_df['Date'].dropna().unique())
        col1, col2 = st.columns(2)
        with col1:
            selected_date = st.selectbox("Select Date", available_dates, key="day_date_select")
        with col2:
            emp_id = st.text_input("Enter Employee ID", key="day_emp_id")
        
        if emp_id and selected_date:
            daily_data = day_df[
                (day_df["EMP ID"].astype(str).str.strip() == str(emp_id).strip()) & 
                (day_df["Date"] == selected_date)
            ]
            
            if not daily_data.empty:
                row = daily_data.iloc[0]
                st.markdown(f'<div class="subheader">Performance for {row["NAME"]} on {selected_date}</div>', unsafe_allow_html=True)
                
                cols = st.columns(4)
                metrics = [
                    ("📞 Calls", f"{int(row.get('Call Count', 0)):,}"),
                    ("⏱️ AHT", format_time_display(row.get('AHT_sec', 0))),
                    ("⏸️ Hold", format_time_display(row.get('Hold_sec', 0))),
                    ("⏹️ Wrap", format_time_display(row.get('Wrap_sec', 0))),
                    ("🤖 Auto On", format_time_display(row.get('Auto On_sec', 0)))
                ]
                for i, (label, value) in enumerate(metrics):
                    cols[i%4].metric(label, value)
                
                call_count = int(row.get('Call Count', 0))
                if call_count > 50:
                    st.success("🎉 Excellent call volume today!")
                elif call_count > 30:
                    st.info("👍 Good performance today")
                else:
                    st.warning("💪 Let's aim for more calls tomorrow")
            else:
                st.warning("No data found for this employee/date combination")
