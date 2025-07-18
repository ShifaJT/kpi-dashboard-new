import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# === CONFIG ===
SHEET_NAME = "KPI Month"
SHEET_ID = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"

# === Google Auth from Secrets ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)
worksheet = sheet.worksheet(SHEET_NAME)

@st.cache_data
def load_data():
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

df = load_data()
df.columns = df.columns.str.strip()  # Strip spaces from column names

# === Styling ===
st.markdown("""
    <style>
    .styled-table {
        font-size: 16px;
        color: #111;
        width: 100%;
        border-collapse: collapse;
    }
    .styled-table th, .styled-table td {
        border: 1px solid #ddd;
        padding: 10px 14px;
        text-align: left;
    }
    .styled-table tr:nth-child(even) {
        background-color: #f8f8f8;
    }
    .styled-table th {
        background-color: #eaeaea;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# === UI Title ===
st.title(" KPI Dashboard for Champs")

# === Timeframe Filter ===
time_frame = st.selectbox("Select Timeframe", ["Day", "Week", "Month"])

# === Input Section ===
emp_id = st.text_input("Enter EMP ID (e.g., 1070)")
month = st.selectbox("Select Month", sorted(df['Month'].unique(), key=lambda m: [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
].index(m)))

# === Filtered Data ===
if emp_id and month:
    emp_data = df[(df["EMP ID"].astype(str) == emp_id) & (df["Month"] == month)]

    if emp_data.empty:
        st.warning("No data found for that EMP ID and month.")
    else:
        emp_name = emp_data["NAME"].values[0]
        st.markdown(f"### KPI Data for **{emp_name}** (EMP ID: {emp_id}) | Month: **{month}**")

        # === Performance Table ===
        st.subheader(" Performance Metrics")
        perf_map = [
            ("Avg hold time used", "Hold", "HH:MM:SS"),
            ("Avg time taken to wrap the call", "Wrap", "HH:MM:SS"),
            ("Avg duration of champ using auto on", "Auto-On", "HH:MM:SS"),
            ("Shift adherence for the month", "Schedule Adherence", "Percentage"),
            ("Customer feedback on resolution given", "Resolution CSAT", "Percentage"),
            ("Customer feedback on champ behaviour", "Agent Behaviour", "Percentage"),
            ("Avg Quality Score achieved for the month", "Quality", "Percentage"),
            ("Process Knowledge Test", "PKT", "Percentage"),
            ("Number of sick and unplanned leaves", "SL + UPL", "Days"),
            ("Number of days logged in", "LOGINS", "Days"),
        ]

        perf_table = []
        for desc, metric, unit in perf_map:
            value = emp_data[metric].values[0] if metric in emp_data else "-"
            perf_table.append({
                "Description": desc,
                "Metric Name": metric,
                "Value": value,
                "Unit": unit
            })

        st.markdown(pd.DataFrame(perf_table).to_html(index=False, classes="styled-table"), unsafe_allow_html=True)

        # === KPI Scores Table ===
        st.subheader(" KPI Scores")
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
            kpi_table.append({
                "Weightage": weight,
                "KPI Metrics": kpi_metric,
                "Score": score
            })

        st.markdown(pd.DataFrame(kpi_table).to_html(index=False, classes="styled-table"), unsafe_allow_html=True)

        # === Grand Total ===
        st.subheader(" Grand Total")
        current_score = emp_data['Grand Total'].values[0]
        st.metric("Grand Total KPI", f"{current_score}")

        # === Previous Month Comparison ===
        month_order = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        all_months = [m for m in month_order if m in df['Month'].unique()]
        current_index = all_months.index(month)

        if current_index > 0:
            previous_month = all_months[current_index - 1]
            prev_data = df[(df["EMP ID"].astype(str) == emp_id) & (df["Month"] == previous_month)]

            if not prev_data.empty:
                prev_score = prev_data["Grand Total"].values[0]
                diff = round(current_score - prev_score, 2)

                if diff > 0:
                    st.success(f" You improved by +{diff} points since last month ({previous_month})!")
                elif diff < 0:
                    st.warning(f" You dropped by {abs(diff)} points since last month ({previous_month}). Let’s bounce back!")
                else:
                    st.info(f"No change from last month ({previous_month}). Keep the momentum going.")
            else:
                st.info("No data found for previous month.")
        else:
            st.info("First month in record — no comparison available.")

        # === Motivational Message ===
        if current_score >= 4.5:
            st.success(" Outstanding! You're setting the benchmark.")
        elif current_score >= 4.0:
            st.info(" Great job! Keep pushing to reach the top.")
        elif current_score >= 3.0:
            st.warning("You're doing good! Let’s strive for more consistency.")
        else:
            st.error("Don't give up — big growth starts with small steps. We're with you!")

        # === Target Committed ===
        st.subheader(" Target Committed for Next Month")
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
            st.info("No target data available.")
