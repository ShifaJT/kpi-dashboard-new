import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Google Sheets setup ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key("19aDfELEExMn0loj_w6D69ngGG4haEm6lsgqpxJC1OAA")

sheet_month = sheet.worksheet("KPI Month")
sheet_day = sheet.worksheet("KPI Day")
sheet_csat = sheet.worksheet("CSAT Score")

# --- Streamlit UI ---
st.title("📊 KPI Dashboard")
st.markdown("---")

emp_id = st.text_input("Enter your EMP ID:")

view_option = st.selectbox("Select View Type:", ["Month", "Week", "Day"])

month_list = list(pd.DataFrame(sheet_month.get_all_records())["Month"].unique())
week_list = sorted(list(set(sheet_day.col_values(10)[1:])))
day_list = sorted(list(set(sheet_day.col_values(2)[1:])))

selected_value = None
if view_option == "Month":
    selected_value = st.selectbox("Select Month:", month_list)
elif view_option == "Week":
    selected_value = st.selectbox("Select Week:", week_list)
elif view_option == "Day":
    selected_value = st.selectbox("Select Day:", day_list)

if emp_id and selected_value:
    df_month = pd.DataFrame(sheet_month.get_all_records())
    df_day = pd.DataFrame(sheet_day.get_all_records())
    df_csat = pd.DataFrame(sheet_csat.get_all_records())

    def clean_time_columns(df, cols):
        for col in cols:
            df[col] = pd.to_timedelta(df[col])
        return df

    if view_option == "Month":
        data = df_month[(df_month["EMP ID"] == emp_id) & (df_month["Month"] == selected_value)]
        if not data.empty:
            st.subheader("Performance")
            performance_data = {
                "Description": ["Total Calls", "AHT", "Hold Time", "Wrap Time"],
                "Metric Name": ["Call Count", "AHT", "Hold", "Wrap"],
                "Value": [data["Call Count"].values[0], data["AHT"].values[0], data["Hold"].values[0], data["Wrap"].values[0]],
                "Unit": ["Count", "HH:MM:SS", "HH:MM:SS", "HH:MM:SS"]
            }
            st.dataframe(pd.DataFrame(performance_data))

            st.subheader("KPI Score")
            kpi_data = {
                "Weightage": ["40%", "30%", "30%"],
                "KPI Metrics": ["PKT", "CSAT (Agent Behaviour)", "Quality"],
                "Score": [data["PKT"].values[0], data["CSAT (Agent Behaviour)"].values[0], data["Quality"].values[0]]
            }
            st.dataframe(pd.DataFrame(kpi_data))

            prev_month = month_list[month_list.index(selected_value) - 1] if selected_value in month_list and month_list.index(selected_value) > 0 else None
            if prev_month:
                prev_data = df_month[(df_month["EMP ID"] == emp_id) & (df_month["Month"] == prev_month)]
                if not prev_data.empty:
                    prev_score = prev_data["Grand Total"].values[0]
                    curr_score = data["Grand Total"].values[0]
                    diff = round(curr_score - prev_score, 2)
                    st.subheader("📈 Comparison With Previous Month")
                    st.write(f"Grand Total KPI last month: {prev_score}")
                    st.write(f"Grand Total KPI this month: {curr_score}")
                    st.write(f"Change: {'🔺' if diff > 0 else '🔻'} {abs(diff)}")

            st.subheader("🌟 Motivational Quote")
            quote = "Keep pushing your limits! You're doing great."
            st.success(quote)

            st.subheader("🎯 Target Committed")
            st.write("Target Committed for PKT: ", data["Target Committed for PKT"].values[0])
            st.write("Target Committed for CSAT (Agent Behaviour): ", data["Target Committed for CSAT (Agent Behaviour)"].values[0])
            st.write("Target Committed for Quality: ", data["Target Committed for Quality"].values[0])

    elif view_option == "Week":
        df_day = clean_time_columns(df_day, ["AHT", "Hold", "Wrap"])
        df_week = df_day[(df_day["EMP ID"] == emp_id) & (df_day["Week"] == selected_value)]
        csat_week = df_csat[(df_csat["EMP ID"] == emp_id) & (df_csat["Week"].astype(str) == str(selected_value))]

        if not df_week.empty:
            st.subheader("Performance (Weekly)")
            performance_data = {
                "Description": ["Total Calls", "AHT", "Hold Time", "Wrap Time"],
                "Metric Name": ["Call Count", "AHT", "Hold", "Wrap"],
                "Value": [df_week["Call Count"].astype(int).sum(), str(df_week["AHT"].mean()), str(df_week["Hold"].mean()), str(df_week["Wrap"].mean())],
                "Unit": ["Count", "HH:MM:SS", "HH:MM:SS", "HH:MM:SS"]
            }
            st.dataframe(pd.DataFrame(performance_data))

            st.subheader("KPI Score (Weekly)")
            if not csat_week.empty:
                kpi_data = {
                    "Weightage": ["30%", "30%"],
                    "KPI Metrics": ["CSAT Resolution", "CSAT Behaviour"],
                    "Score": [csat_week["CSAT Resolution"].values[0], csat_week["CSAT Behaviour"].values[0]]
                }
                st.dataframe(pd.DataFrame(kpi_data))
            else:
                st.warning("No CSAT Score found for selected week.")

    elif view_option == "Day":
        try:
            parsed_date = datetime.strptime(selected_value, "%m/%d/%Y").strftime("%m/%d/%Y")
            df_day = clean_time_columns(df_day, ["AHT", "Hold", "Wrap"])
            df_date = df_day[(df_day["EMP ID"] == emp_id) & (df_day["Date"] == parsed_date)]
            if not df_date.empty:
                st.subheader("Performance (Day)")
                row = df_date.iloc[0]
                performance_data = {
                    "Description": ["Total Calls", "AHT", "Hold Time", "Wrap Time"],
                    "Metric Name": ["Call Count", "AHT", "Hold", "Wrap"],
                    "Value": [row["Call Count"], str(row["AHT"]), str(row["Hold"]), str(row["Wrap"])],
                    "Unit": ["Count", "HH:MM:SS", "HH:MM:SS", "HH:MM:SS"]
                }
                st.dataframe(pd.DataFrame(performance_data))

                st.subheader("KPI Score (Day)")
                kpi_data = {
                    "Weightage": ["30%", "30%"],
                    "KPI Metrics": ["CSAT Resolution", "CSAT Behaviour"],
                    "Score": [row["CSAT Resolution"], row["CSAT Behaviour"]]
                }
                st.dataframe(pd.DataFrame(kpi_data))
            else:
                st.warning("No daily data found for selected date.")
        except Exception as e:
            st.error(f"Date parsing error: {str(e)}")
