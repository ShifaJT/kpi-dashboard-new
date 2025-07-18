
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="KPI Dashboard", layout="wide")

st.title("KPI Dashboard")

# Function to authenticate and load Google Sheet
@st.cache_resource
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open("YTD KPI Sheet")
    month_data = pd.DataFrame(sheet.worksheet("KPI Month").get_all_records())
    return month_data

data = load_data()

emp_id = st.text_input("Enter your EMP ID")

if emp_id:
    emp_data = data[data["EMP ID"] == emp_id]
    if not emp_data.empty:
        st.subheader("Performance Data")
        st.dataframe(emp_data[["Hold", "Wrap", "Auto-On", "Schedule Adherence", "Resolution CSAT", 
                               "Agent Behaviour", "Quality", "PKT"]])

        st.subheader("KPI Achieved Scores")
        st.dataframe(emp_data[["Hold KPI Score", "Wrap KPI Score", "Auto-On KPI Score", 
                               "Schedule Adherence KPI Score", "Resolution CSAT KPI Score", 
                               "Agent Behaviour KPI Score", "Quality KPI Score", "PKT KPI Score"]])

        st.subheader("Grand Total KPI")
        st.metric(label="Total KPI", value=emp_data["Grand Total"].values[0])

        st.subheader("Target Committed for Next Month")
        st.write("PKT:", emp_data["Target Committed for PKT"].values[0])
        st.write("CSAT (Agent Behaviour):", emp_data["Target Committed for CSAT (Agent Behaviour)"].values[0])
        st.write("Quality:", emp_data["Target Committed for Quality"].values[0])
    else:
        st.warning("No data found for this EMP ID.")
