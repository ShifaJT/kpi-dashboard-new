# === COMPLETE KPI DASHBOARD SOLUTION ===
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import numpy as np

# Add custom CSS for top performers section with dark mode compatibility
st.markdown("""
<style>
    .top-performer-card {
        background-color: var(--background-color);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border: 1px solid var(--border-color);
    }
    .top-performer-rank {
        font-weight: bold;
        color: var(--text-color);
        font-size: 1.2em;
    }
    .top-performer-name {
        font-weight: bold;
        color: var(--primary-color);
    }
    .top-performer-metric {
        font-size: 0.9em;
        margin-top: 5px;
        color: var(--text-color);
    }
    .metric-label {
        display: inline-block;
        width: 100px;
        color: var(--text-color);
    }
    
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-background) !important;
    }
    
    :root {
        --background-color: #f8f9fa;
        --border-color: #ddd;
        --text-color: #2c3e50;
        --primary-color: #3498db;
        --sidebar-background: #f8f9fa;
    }
    
    @media (prefers-color-scheme: dark) {
        :root {
            --background-color: #262730;
            --border-color: #555;
            --text-color: #f0f2f6;
            --primary-color: #5dade2;
            --sidebar-background: #262730;
        }
    }
    
    /* Additional styling for metrics */
    .metric-container {
        background-color: var(--background-color);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        border: 1px solid var(--border-color);
    }
</style>
""", unsafe_allow_html=True)

# Helper functions to clean values
def clean_value(val):
    if pd.isna(val) or str(val).strip() in ['', 'nan', 'None']:
        return 'N/A'
    return str(val).strip()

def clean_percentage_value(val):
    """Safely convert percentage strings to floats"""
    if pd.isna(val) or str(val).strip() in ['', 'nan', 'None', 'N/A']:
        return 0.0
    try:
        return float(str(val).replace('%', '').strip())
    except:
        return 0.0

def format_percentage(val):
    """Format a numeric value as percentage string"""
    if pd.isna(val) or val == 0:
        return 'N/A'
    return f"{float(val):.1f}%"

# === NEW FUNCTION FOR TOP PERFORMERS ===
def calculate_weighted_score(row):
    """Calculate weighted score with specified weightages"""
    try:
        # Convert time metrics to seconds
        wrap = safe_convert_time(row.get('Wrap', 0))
        auto_on = safe_convert_time(row.get('Auto On', 0))
        
        # Convert percentages
        csat_res = clean_percentage_value(row.get('CSAT Resolution', 0))
        csat_beh = clean_percentage_value(row.get('CSAT Behaviour', 0))
        quality = clean_percentage_value(row.get('Quality Score', 0))
        
        # Normalize time metrics (lower is better)
        wrap_score = max(0, 100 - (wrap / 120 * 100)) if wrap > 0 else 100
        auto_on_score = min(100, (auto_on / (8*3600) * 100)) if auto_on > 0 else 0
        
        # Calculate weighted score with specified weightages
        weighted_score = (
            (wrap_score * 0.05) +      # Wrap Up 5%
            (auto_on_score * 0.40) +   # Auto-On 40%
            (csat_res * 0.10) +        # Resolution CSAT 10%
            (csat_beh * 0.15) +        # CSAT Behaviour 15%
            (quality * 0.30)           # Quality 30%
        )
        
        return round(weighted_score, 2)
    except Exception as e:
        st.error(f"Error calculating score: {str(e)}")
        return 0

def get_weekly_top_performers(day_df, csat_df, week, year=None):
    """Identify top performers for a given week"""
    try:
        # If year is provided, filter by both week and year
        if year:
            week_filter = (day_df['Week'] == str(week)) & (day_df['Year'] == str(year))
            week_day_data = day_df[week_filter].copy()
            
            csat_week_filter = (csat_df['Week'] == str(week)) & (csat_df['Year'] == str(year))
            week_csat_data = csat_df[csat_week_filter].copy()
        else:
            # Fallback to week-only filtering
            week_day_data = day_df[day_df['Week'] == str(week)].copy()
            week_csat_data = csat_df[csat_df['Week'] == str(week)].copy()
        
        if week_day_data.empty or week_csat_data.empty:
            return pd.DataFrame()
        
        # Group by employee and calculate averages
        weekly_metrics = week_day_data.groupby(['EMP ID', 'NAME']).agg({
            'Wrap_sec': 'mean',
            'Auto On_sec': 'mean',
            'Call Count': 'sum'
        }).reset_index()
        
        # Ensure we're using the correct column name for Quality score
        csat_columns = ['EMP ID', 'CSAT Resolution', 'CSAT Behaviour', 'Quality Score']
        
        # Merge with CSAT data
        weekly_metrics = pd.merge(
            weekly_metrics,
            week_csat_data[csat_columns],
            on='EMP ID',
            how='left'
        )
        
        # Calculate scores for ranking (without displaying the score)
        weekly_metrics['_weighted_score'] = weekly_metrics.apply(calculate_weighted_score, axis=1)
        
        # Get top 5 and format
        top_performers = weekly_metrics.sort_values('_weighted_score', ascending=False).head(5)
        
        # Convert times to readable format
        def format_time(seconds):
            if pd.isna(seconds) or seconds == 0:
                return "00:00"
            return str(timedelta(seconds=int(seconds))).split('.')[0]
        
        top_performers['Wrap'] = top_performers['Wrap_sec'].apply(format_time)
        top_performers['Auto On'] = top_performers['Auto On_sec'].apply(format_time)
        
        # Format scores as percentages
        for col in ['CSAT Resolution', 'CSAT Behaviour', 'Quality Score']:
            if col in top_performers.columns:
                top_performers[col] = top_performers[col].apply(
                    lambda x: format_percentage(x) if pd.notna(x) else 'N/A'
                )
            elif col == 'Quality Score':
                top_performers[col] = 'N/A'
        
        return top_performers[['EMP ID', 'NAME', 'Wrap', 'Auto On', 
                              'CSAT Resolution', 'CSAT Behaviour', 'Quality Score']]
    except Exception as e:
        st.error(f"Error identifying top performers: {str(e)}")
        return pd.DataFrame()

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
        st.error(f"🔐 Authentication failed: {str(e)}")
        st.info("Please make sure you have configured the Google Service Account credentials correctly.")
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
            
        # Clean percentage columns
        percentage_cols = ['CSAT Resolution', 'CSAT Behaviour', 'Quality Score']
        for col in percentage_cols:
            if col in df.columns:
                df[col] = df[col].apply(clean_percentage_value)
                
        return df
    except Exception as e:
        st.error(f"❌ Error loading {name}: {str(e)}")
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
    # Convert Date column to datetime, handling errors
    day_df['Date'] = pd.to_datetime(day_df['Date'], errors='coerce')
    
    # Extract week and year, handling NaT values
    day_df['Week'] = day_df['Date'].apply(
        lambda x: str(x.isocalendar()[1]) if pd.notna(x) else 'Unknown'
    )
    day_df['Year'] = day_df['Date'].apply(
        lambda x: str(x.year) if pd.notna(x) else 'Unknown'
    )
    
    # Convert back to date for display
    day_df['Date'] = day_df['Date'].dt.date
    
    for col in ['AHT', 'Wrap', 'Hold', 'Auto On']:
        if col in day_df.columns:
            day_df[f"{col}_sec"] = day_df[col].apply(safe_convert_time)

if not csat_df.empty:
    csat_df['Week'] = csat_df['Week'].astype(str)
    # Try to extract year from CSAT data if available
    if 'Date' in csat_df.columns:
        csat_df['Date'] = pd.to_datetime(csat_df['Date'], errors='coerce')
        csat_df['Year'] = csat_df['Date'].dt.year.astype(str)
    else:
        # Default to current year if no date column
        csat_df['Year'] = str(datetime.now().year)

# === DISPLAY WEEKLY TOP PERFORMERS ===
if not day_df.empty and not csat_df.empty:
    current_date = datetime.now()
    current_week = current_date.isocalendar()[1]
    current_year = current_date.year
    
    # Handle year transition for previous week
    if current_week == 1:
        previous_week = 52
        previous_year = current_year - 1
    else:
        previous_week = current_week - 1
        previous_year = current_year
    
    with st.sidebar:
        st.header("🏆 Previous Week Top Performers")
        st.markdown(f"**📅 Week {previous_week}, {previous_year}**")
        
        top_performers = get_weekly_top_performers(day_df, csat_df, previous_week, previous_year)
        
        if not top_performers.empty:
            for i, (_, row) in enumerate(top_performers.iterrows(), 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎖️"
                st.markdown(
                    f"""
                    <div class="top-performer-card">
                        <div class="top-performer-rank">{emoji} Rank #{i}</div>
                        <div class="top-performer-name">{row['NAME']}</div>
                        <div class="top-performer-metric">
                            <span class="metric-label">⏱️ Wrap:</span> {row['Wrap']}<br>
                            <span class="metric-label">💻 Auto On:</span> {row['Auto On']}<br>
                            <span class="metric-label">✅ CSAT Res:</span> {row['CSAT Resolution']}<br>
                            <span class="metric-label">😊 CSAT Beh:</span> {row['CSAT Behaviour']}<br>
                            <span class="metric-label">⭐ Quality:</span> {row['Quality Score']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.warning("No top performers data available for this week")

# === DASHBOARD UI ===
st.title("📊 KPI Performance Dashboard")
time_frame = st.radio("⏳ Select Timeframe:", ["Day", "Week", "Month"], horizontal=True)

# === MONTH VIEW ===
if time_frame == "Month":
    st.subheader("📅 Monthly Performance")

    if not month_df.empty:
        month_df['Month'] = month_df['Month'].astype(str).str.strip()
        
        # Convert month names to datetime for proper sorting
        month_df['Month_datetime'] = pd.to_datetime(month_df['Month'], format='%B', errors='coerce')
        month_df = month_df.sort_values('Month_datetime')
        month_names = month_df['Month'].unique().tolist()

        if len(month_names) == 0:
            st.error("❌ No months found in the data. Please check your 'KPI Month' sheet.")
        else:
            # Sort months with most recent first
            month_names_sorted = sorted(month_names, 
                                      key=lambda x: pd.to_datetime(x, format='%B'), 
                                      reverse=True)
            
            selected_month = st.selectbox("📆 Select Month", month_names_sorted)
            emp_id = st.text_input("🆔 Enter Employee ID", key="month_emp_id")

            if emp_id and selected_month:
                try:
                    monthly_data = month_df[
                        (month_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) &
                        (month_df['Month'].str.strip() == selected_month.strip())
                    ]

                    if not monthly_data.empty:
                        row = monthly_data.iloc[0]
                        st.subheader(f"📈 Performance for {row['NAME']} - {selected_month}")

                        # Clean percentage values before display
                        def get_clean_value(col_name):
                            val = row.get(col_name, 'N/A')
                            if pd.isna(val) or str(val).strip() in ['', 'nan', 'None']:
                                return 'N/A'
                            try:
                                if '%' in str(val):
                                    return f"{float(str(val).replace('%', '')):.1f}%"
                                return str(val)
                            except:
                                return 'N/A'

                        st.markdown("### 📊 Performance Metrics")
                        cols = st.columns(4)
                        metrics = [
                            ("⏱️ Hold Time", get_clean_value('Hold')),
                            ("⏱️ Wrap Time", get_clean_value('Wrap')),
                            ("💻 Auto-On", get_clean_value('Auto-On')),
                            ("⏰ Schedule Adherence", get_clean_value('Schedule Adherence')),
                            ("✅ CSAT Resolution", get_clean_value('Resolution CSAT')),
                            ("😊 CSAT Behaviour", get_clean_value('Agent Behaviour')),
                            ("⭐ Quality", get_clean_value('Quality')),
                            ("📞 PKT", get_clean_value('PKT')),
                            ("📶 SL + UPL", get_clean_value('SL + UPL')),
                            ("🔑 Logins", get_clean_value('LOGINS'))
                        ]
                        for i, (label, value) in enumerate(metrics):
                            cols[i % 4].metric(label, value)

                        st.markdown("### 🎯 KPI Scores")
                        kpi_cols = st.columns(4)
                        kpi_metrics = [
                            ("⏱️ Hold KPI Score", get_clean_value('Hold KPI Score')),
                            ("⏱️ Wrap KPI Score", get_clean_value('Wrap KPI Score')),
                            ("💻 Auto-On KPI Score", get_clean_value('Auto-On KPI Score')),
                            ("⏰ Schedule KPI Score", get_clean_value('Schedule Adherence KPI Score')),
                            ("✅ CSAT Res KPI Score", get_clean_value('Resolution CSAT KPI Score')),
                            ("😊 CSAT Beh KPI Score", get_clean_value('Agent Behaviour KPI Score')),
                            ("⭐ Quality KPI Score", get_clean_value('Quality KPI Score')),
                            ("📞 PKT KPI Score", get_clean_value('PKT KPI Score'))
                        ]
                        for i, (label, value) in enumerate(kpi_metrics):
                            kpi_cols[i % 4].metric(label, value)

                        if 'Grand Total' in row:
                            try:
                                current_score = float(str(row['Grand Total']).replace('%', ''))
                                st.markdown("### 📈 Overall KPI Score")
                                
                                # Get the index of selected month in sorted list
                                month_index = month_names_sorted.index(selected_month)
                                
                                # Find the previous month with data for this employee
                                delta = None
                                delta_label = ""
                                
                                # Check previous months for data
                                for i in range(month_index + 1, len(month_names_sorted)):
                                    prev_month = month_names_sorted[i]
                                    prev_data = month_df[
                                        (month_df["EMP ID"].astype(str).str.strip() == emp_id.strip()) &
                                        (month_df['Month'].str.strip() == prev_month.strip())
                                    ]
                                    
                                    if not prev_data.empty and 'Grand Total' in prev_data.columns:
                                        prev_score = float(str(prev_data.iloc[0]['Grand Total']).replace('%', ''))
                                        delta = current_score - prev_score
                                        delta_label = f"{'↑' if delta >= 0 else '↓'} {abs(delta):.1f}"
                                        break
                                
                                if delta is not None:
                                    st.metric("Overall Score", f"{current_score:.1f}/5.0", delta_label, delta_color="normal")
                                    if delta > 0:
                                        st.markdown(f"📈 **{abs(delta):.1f} points improved from previous month!**")
                                        st.success("🎉 Keep up the great work and continue the momentum!")
                                    elif delta < 0:
                                        st.markdown(f"📉 **{abs(delta):.1f} points dropped from previous month.**")
                                        st.warning("💪 Let's focus on areas of improvement and bounce back stronger!")
                                    else:
                                        st.markdown("➡️ **No change from previous month.**")
                                        st.info("🔄 Consistent performance! Let's aim for improvement next month.")
                                else:
                                    st.metric("Overall Score", f"{current_score:.1f}/5.0")
                                    st.info("ℹ️ No previous month data available for comparison.")

                                st.progress(current_score / 5)
                            except ValueError:
                                st.error("Could not convert Grand Total to numeric value")

                        st.markdown("### 🎯 Targets Committed")
                        target_cols = st.columns(3)
                        targets = [
                            ("📞 PKT Target", get_clean_value('Target Committed for PKT')),
                            ("😊 CSAT Target", get_clean_value('Target Committed for CSAT (Agent Behaviour)')),
                            ("⭐ Quality Target", get_clean_value('Target Committed for Quality'))
                        ]
                        for i, (label, value) in enumerate(targets):
                            target_cols[i].metric(label, value)

                    else:
                        st.warning("⚠️ No data found for this employee/month")
                except Exception as e:
                    st.error(f"❌ Error processing data: {str(e)}")
    else:
        st.warning("⚠️ Monthly data not loaded properly")
        
# === WEEK VIEW ===
elif time_frame == "Week":
    st.subheader("📅 Weekly Performance")
    
    if not day_df.empty and not csat_df.empty:
        # Filter out rows with unknown week/year and non-numeric weeks
        valid_day_data = day_df[
            (day_df['Week'] != 'Unknown') & 
            (day_df['Year'] != 'Unknown') &
            (day_df['Week'].apply(lambda x: str(x).isdigit()))
        ]
        valid_csat_data = csat_df[
            (csat_df['Week'] != 'Unknown') & 
            (csat_df['Year'] != 'Unknown') &
            (csat_df['Week'].apply(lambda x: str(x).isdigit()))
        ]
        
        if valid_day_data.empty or valid_csat_data.empty:
            st.warning("⚠️ No valid weekly data available")
        else:
            # Get unique weeks and convert to integers for proper sorting
            day_weeks = valid_day_data['Week'].drop_duplicates().dropna()
            csat_weeks = valid_csat_data['Week'].drop_duplicates().dropna()
            
            # Convert to integers, sort, then convert back to strings for display
            try:
                all_weeks_int = sorted(
                    set(int(week) for week in day_weeks) | set(int(week) for week in csat_weeks),
                    reverse=True
                )
                all_weeks = [str(week) for week in all_weeks_int]
                
            except Exception as e:
                st.error(f"Error processing weeks: {str(e)}")
                # Fallback: use string sorting
                all_weeks = sorted(set(day_weeks) | set(csat_weeks), reverse=True)
            
            selected_week = st.selectbox("📆 Select Week", all_weeks)
            emp_id = st.text_input("🆔 Enter Employee ID", key="week_emp_id")
            
            if emp_id and selected_week:
                try:
                    week_filter = (valid_day_data["Week"].astype(str).str.strip() == str(selected_week))
                    
                    week_calls = valid_day_data[
                        (valid_day_data["EMP ID"].astype(str).str.strip() == str(emp_id).strip()) & 
                        week_filter
                    ].copy()
                    
                    week_calls['Call Count'] = pd.to_numeric(week_calls['Call Count'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    if not week_calls.empty:
                        total_calls = int(week_calls["Call Count"].sum())
                        
                        def format_avg_time(col):
                            avg_sec = week_calls[f"{col}_sec"].mean()
                            return str(timedelta(seconds=int(avg_sec))).split('.')[0]
                        
                        st.subheader(f"📊 Week {selected_week} Performance")
                        st.markdown("### 📞 Call Metrics")
                        cols = st.columns(5)
                        call_metrics = [
                            ("📊 Total Calls", f"{total_calls:,}"),
                            ("⏱️ Avg AHT", format_avg_time('AHT')),
                            ("⏸️ Avg Hold", format_avg_time('Hold')),
                            ("⏱️ Avg Wrap", format_avg_time('Wrap')),
                            ("💻 Avg Auto On", format_avg_time('Auto On'))
                        ]
                        for i, (label, value) in enumerate(call_metrics):
                            cols[i].metric(label, value)
                        
                        # Filter CSAT data
                        csat_filter = (valid_csat_data["Week"].astype(str).str.strip() == str(selected_week))
                        
                        week_csat = valid_csat_data[
                            (valid_csat_data["EMP ID"].astype(str).str.strip() == str(emp_id).strip()) & 
                            csat_filter
                        ]
                        
                        if not week_csat.empty:
                            st.markdown("### 😊 CSAT Metrics")
                            csat_cols = st.columns(3)
                            csat_metrics = [
                                ("✅ CSAT Resolution", format_percentage(week_csat['CSAT Resolution'].mean())),
                                ("😊 CSAT Behaviour", format_percentage(week_csat['CSAT Behaviour'].mean())),
                                ("⭐ Quality Score", format_percentage(week_csat['Quality Score'].mean()))
                            ]
                            for i, (label, value) in enumerate(csat_metrics):
                                csat_cols[i].metric(label, value)
                        
                        with st.expander("🔍 View Daily Breakdown"):
                            daily_data = week_calls[['Date', 'Call Count', 'AHT', 'Hold', 'Wrap', 'Auto On']].copy()
                            st.dataframe(daily_data)
                    else:
                        st.warning("⚠️ No call data found for this employee/week")
                except Exception as e:
                    st.error(f"❌ Error processing weekly data: {str(e)}")
    else:
        st.warning("⚠️ Weekly data not loaded properly")
        
# === DAY VIEW ===
else:
    st.subheader("📅 Daily Performance")
    
    if not day_df.empty:
        # Filter out rows with invalid dates
        valid_day_data = day_df[day_df['Date'].notna()]
        available_dates = sorted(valid_day_data['Date'].dropna().unique(), reverse=True)
        
        if not available_dates:
            st.warning("⚠️ No valid daily data available")
        else:
            selected_date = st.selectbox("📆 Select Date", available_dates, key="day_date_select")
            emp_id = st.text_input("🆔 Enter Employee ID", key="day_emp_id")
            
            if emp_id and selected_date:
                daily_data = valid_day_data[
                    (valid_day_data["EMP ID"].astype(str).str.strip() == str(emp_id).strip()) & 
                    (valid_day_data["Date"] == selected_date)
                ]
                
                if not daily_data.empty:
                    row = daily_data.iloc[0]
                    st.subheader(f"📊 Performance for {row['NAME']} on {selected_date}")
                    
                    def format_time(time_val):
                        if pd.isna(time_val) or time_val == 0:
                            return "00:00:00"
                        return str(timedelta(seconds=int(time_val))).split('.')[0]
                    
                    # First row of metrics
                    cols1 = st.columns(4)
                    metrics1 = [
                        ("📞 Calls", f"{int(row.get('Call Count', 0)):,}"),
                        ("⏱️ AHT", format_time(safe_convert_time(row.get('AHT')))),
                        ("⏸️ Hold", format_time(safe_convert_time(row.get('Hold')))),
                        ("⏱️ Wrap", format_time(safe_convert_time(row.get('Wrap'))))
                    ]
                    for i, (label, value) in enumerate(metrics1):
                        cols1[i].metric(label, value)
                    
                    # Second row of metrics
                    cols2 = st.columns(4)
                    metrics2 = [
                        ("💻 Auto On", format_time(safe_convert_time(row.get('Auto On')))),
                        ("✅ CSAT Resolution", format_percentage(row.get('CSAT Resolution'))),
                        ("😊 CSAT Behaviour", format_percentage(row.get('CSAT Behaviour'))),
                        ("", "")  # Empty metric for layout
                    ]
                    for i, (label, value) in enumerate(metrics2):
                        if label:  # Only show if label is not empty
                            cols2[i].metric(label, value)
                    
                    call_count = int(row.get('Call Count', 0))
                    if call_count > 50:
                        st.success("🎉 Excellent call volume today!")
                    elif call_count > 30:
                        st.info("👍 Good performance today")
                    else:
                        st.warning("💪 Let's aim for more calls tomorrow")
                else:
                    st.warning("⚠️ No data found for this employee/date")
    else:
        st.warning("⚠️ Daily data not loaded properly")
