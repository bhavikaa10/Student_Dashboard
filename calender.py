import streamlit as st
import fitz  # PyMuPDF
from dateutil import parser
import re
from ics import Calendar, Event
from fpdf import FPDF
import pandas as pd

# ------------ UTILITY FUNCTIONS ------------

def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    return "\n".join([page.get_text() for page in doc])

def extract_dates(text):
    # Match MM/DD/YYYY, DD-MM-YYYY, or "Month DD, YYYY"
    date_strings = re.findall(r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2}, \d{4})\b', text)
    unique = set()
    events = []
    for ds in date_strings:
        try:
            dt = parser.parse(ds, fuzzy=True)
            if dt not in unique:
                unique.add(dt)
                events.append((dt, ds))
        except:
            pass
    return events

def find_event_context(text, date_string, window=80):
    index = text.find(date_string)
    if index == -1:
        return "Event"
    start = max(0, index - window)
    end = index + len(date_string) + window
    return text[start:end].replace("\n", " ").strip()

def create_ics_file(events, full_text):
    c = Calendar()
    for date, label in events:
        e = Event()
        e.name = find_event_context(full_text, label)
        e.begin = date
        c.events.add(e)
    return c

def generate_calendar_pdf(events, full_text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="📅 Course Calendar", ln=True, align="C")

    for date, label in events:
        context = find_event_context(full_text, label)
        event_text = f"{date.strftime('%Y-%m-%d')}: {context}"
        pdf.multi_cell(0, 10, event_text)

    pdf.output("calendar.pdf")

# ------------ STREAMLIT INTERFACE ------------

st.title("📘 PDF → Calendar Generator")
st.write("Upload a syllabus or timetable (PDF) to extract important dates and create a custom calendar.")

uploaded_file = st.file_uploader("Upload your syllabus file", type="pdf")

if uploaded_file:
    text = extract_text_from_pdf(uploaded_file)
    dates = extract_dates(text)

    if not dates:
        st.warning("❌ No valid dates found in the document.")
    else:
        # Calendar table
        calendar_df = pd.DataFrame({
            "Date": [d.strftime("%Y-%m-%d") for d, label in dates],
            "Event Description": [find_event_context(text, label) for d, label in dates]
        })
        st.write("📅 **Extracted Course Calendar:**")
        st.dataframe(calendar_df)

        # Export buttons
        if st.button("📥 Download .ics Calendar File"):
            calendar = create_ics_file(dates, text)
            with open("my_calendar.ics", "w") as f:
                f.writelines(calendar)
            with open("my_calendar.ics", "rb") as f:
                st.download_button("📆 Download .ics", f, file_name="course_calendar.ics")

        if st.button("📄 Export Calendar as PDF"):
            generate_calendar_pdf(dates, text)
            with open("calendar.pdf", "rb") as f:
                st.download_button("🖨️ Download PDF", f, file_name="course_calendar.pdf")
