import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import numpy as np

# Auth using st.secrets
credentials = Credentials.from_service_account_info(st.secrets["google_service_account"])
gc = gspread.authorize(credentials)

# Sheet setup
sheet_id = "19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA"
kpi_month = gc.open_by_key(sheet_id).worksheet("KPI Month")
kpi_day = gc.open_by_key(sheet_id).worksheet("KPI Day")
csat_score = gc.open_by_key(sheet_id).worksheet("CSAT Score")

# Load data
df_month = pd.DataFrame(kpi_month.get_all_records())
df_day = pd.DataFrame(kpi_day.get_all_records())
df_csat = pd.DataFrame(csat_score.get_all_records())

# Date parsing for 'KPI Day'
df_day["Date"] = pd.to_datetime(df_day["Date"], format="%m/%d/%Y", errors="coerce")
df_day = df_day.dropna(subset=["Date"])

st.title("📊 KPI Dashboard")

emp_id = st.text_input("Enter your EMP ID")

view_mode = st.selectbox("Select View", ["Month", "Week", "Day"])

def show_performance_section(performance_data):
    st.subheader("📌 Performance Overview")
    st.dataframe(performance_data, hide_index=True)

def show_kpi_section(kpi_data):
    st.subheader("📈 KPI Scores")
    st.dataframe(kpi_data, hide_index=True)

def show_comparison(current_score, previous_score):
    st.subheader("🔄 Month-over-Month Comparison")
    diff = round(current_score - previous_score, 2)
    if diff > 0:
        st.success(f"Improved by {diff} points! 🚀")
    elif diff < 0:
        st.error(f"Dropped by {abs(diff)} points. Let's aim higher!")
    else:
        st.info("No change from last month.")

def motivational_quote(score):
    st.subheader("💡 Motivational Boost")
    if score >= 90:
        st.success("Outstanding performance! Keep shining 🌟")
    elif score >= 75:
        st.info("Good job! Let’s push to the next level 💪")
    else:
        st.warning("Stay focused. You’ve got potential to grow 🚀")

def show_target_committed(data):
    st.subheader("🎯 Target Committed for Next Month")
    targets = {
        "Target Committed for PKT": data.get("Target Committed for PKT", "N/A"),
        "Target Committed for CSAT (Agent Behaviour)": data.get("Target Committed for CSAT (Agent Behaviour)", "N/A"),
        "Target Committed for Quality": data.get("Target Committed for Quality", "N/A")
    }
    st.write(targets)

# Metric explanations and weightage
metric_explainer = pd.DataFrame({
    "Description": ["Calls handled", "Average handling time", "Wrap time", "Hold time", "CSAT Resolution", "CSAT Behaviour"],
    "Metric Name": ["Call Count", "AHT", "Wrap", "Hold", "CSAT Resolution", "CSAT Behaviour"],
    "Value": ["Numeric", "Time (mins)", "Time (mins)", "Time (mins)", "Score (%)", "Score (%)"],
    "Unit": ["#", "mins", "mins", "mins", "%", "%"]
})

kpi_weightage = pd.DataFrame({
    "Weightage": ["30%", "30%", "40%"],
    "KPI Metrics": ["PKT", "CSAT (Agent Behaviour)", "Quality"],
    "Score": ["From your data", "From your data", "From your data"]
})

if emp_id:
    if view_mode == "Month":
        month_selected = st.selectbox("Select Month", df_month["Month"].unique())
        filtered = df_month[(df_month["EMP ID"] == emp_id) & (df_month["Month"] == month_selected)]
        if not filtered.empty:
            perf_data = filtered[["NAME", "Call Count", "AHT", "Hold", "Wrap", "CSAT Resolution", "CSAT Behaviour"]]
            show_performance_section(perf_data)

            kpi_data = filtered[["PKT", "CSAT (Agent Behaviour)", "Quality"]]
            kpi_df = pd.DataFrame({
                "Weightage": ["30%", "30%", "40%"],
                "KPI Metrics": ["PKT", "CSAT (Agent Behaviour)", "Quality"],
                "Score": [kpi_data["PKT"].values[0], kpi_data["CSAT (Agent Behaviour)"].values[0], kpi_data["Quality"].values[0]]
            })
            show_kpi_section(kpi_df)

            # Comparison
            all_months = sorted(df_month["Month"].unique().tolist())
            current_index = all_months.index(month_selected)
            if current_index > 0:
                prev_month = all_months[current_index - 1]
                prev_score = df_month[(df_month["EMP ID"] == emp_id) & (df_month["Month"] == prev_month)]
                if not prev_score.empty:
                    show_comparison(filtered["Grand Total"].values[0], prev_score["Grand Total"].values[0])
            motivational_quote(filtered["Grand Total"].values[0])
            show_target_committed(filtered.iloc[0])
            st.subheader("📌 Metric Explanation")
            st.dataframe(metric_explainer, hide_index=True)
        else:
            st.warning("No data found for this EMP ID and month.")

    elif view_mode == "Day":
        day = st.date_input("Select Date")
        filtered = df_day[(df_day["EMP ID"] == emp_id) & (df_day["Date"] == pd.to_datetime(day))]
        if not filtered.empty:
            st.subheader("📌 Performance (Day View)")
            st.write(filtered[["NAME", "Call Count", "AHT", "Hold", "Wrap", "CSAT Resolution", "CSAT Behaviour"]])
        else:
            st.warning("No daily data found for selected date.")

    elif view_mode == "Week":
        week_selected = st.selectbox("Select Week", sorted(df_day["Week"].unique()))
        weekly_data = df_day[(df_day["EMP ID"] == emp_id) & (df_day["Week"] == week_selected)]
        csat_data = df_csat[(df_csat["EMP ID"] == emp_id) & (df_csat["Week"] == week_selected)]

        if not weekly_data.empty:
            avg_values = weekly_data[["Call Count", "AHT", "Hold", "Wrap"]].apply(pd.to_numeric, errors='coerce').mean()
            summary = {
                "Call Count": round(avg_values["Call Count"], 2),
                "AHT": round(avg_values["AHT"], 2),
                "Hold": round(avg_values["Hold"], 2),
                "Wrap": round(avg_values["Wrap"], 2)
            }

            if not csat_data.empty:
                summary["CSAT Resolution"] = csat_data["CSAT Resolution"].values[0]
                summary["CSAT Behaviour"] = csat_data["CSAT Behaviour"].values[0]
            else:
                summary["CSAT Resolution"] = "N/A"
                summary["CSAT Behaviour"] = "N/A"

            st.subheader("📌 Weekly Summary")
            st.write(summary)
        else:
            st.warning("No weekly data found for selected week.")
