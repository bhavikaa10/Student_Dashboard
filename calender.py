import streamlit as st
import fitz  # PyMuPDF
from dateutil import parser
import re
from ics import Calendar, Event

def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    return "\n".join([page.get_text() for page in doc])


def extract_dates(text):
    date_strings = re.findall(r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2}, \d{4})\b', text)
    return [(parser.parse(ds, fuzzy=True), ds) for ds in date_strings]


def create_ics_file(dates):
    c = Calendar()
    for date, label in dates:
        e = Event()
        e.name = f"Event near {label}"
        e.begin = date
        c.events.add(e)
    return c


st.title("Schedule")
uploaded_file = st.file_uploader("Upload a syllabus or timetable (PDF)", type="pdf")

if uploaded_file:
    text = extract_text_from_pdf(uploaded_file)
    dates = extract_dates(text)


    st.write("✅ Extracted Events:")
    for d, label in dates:
        st.write(f"- {label} → {d.strftime('%Y-%m-%d')}")

    if st.button("📥 Export Calendar (.ics)"):
        calendar = create_ics_file(dates)
        with open("my_calendar.ics", "w") as f:
            f.writelines(calendar)
        st.success("Downloaded as my_calendar.ics")

