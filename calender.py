"""
Syllabus → Calendar Streamlit App
--------------------------------
Displays syllabus deadlines in an interactive **month‑grid calendar** (FullCalendar)
plus export to .ics & PDF.

Requires:
    pip install streamlit streamlit-calendar pymupdf python-dateutil ics fpdf pandas
"""

import streamlit as st
from streamlit_calendar import calendar  # FullCalendar wrapper

import fitz  # PyMuPDF
from dateutil import parser as dtparse
import re
from ics import Calendar, Event
from fpdf import FPDF
import pandas as pd
import datetime as dt
import io

# ---------- CONSTANTS ----------
KEYWORDS = (
    "assignment",
    "quiz",
    "midterm",
    "exam",
    "presentation",
    "project",
    "lab",
)

ABS_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},\s*\d{4})\b",
    re.I,
)

# Week 5, Week 5-6, 2nd week, etc.
WEEK_RE = re.compile(
    r"\b(?:week(?:s)?\s*(\d{1,2})(?:\s*-\s*(\d{1,2}))?|"  # Week 5 or Week 5-6
    r"(\d{1,2})(st|nd|rd|th)\s+week)\b",
    re.I,
)

# ---------- HELPERS ----------

def extract_text(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> str:
    """Read all text from a PDF syllabus."""
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    return "\n".join(p.get_text() for p in doc)


def parse_absolute_dates(text: str):
    seen = set()
    events = []
    for ds in ABS_DATE_RE.findall(text):
        try:
            dt_obj = dtparse.parse(ds, fuzzy=True).date()
            if dt_obj not in seen:
                seen.add(dt_obj)
                events.append((dt_obj, ds))
        except Exception:
            continue
    return events


def parse_relative_weeks(text: str, semester_start: dt.date):
    events = []
    for m in WEEK_RE.finditer(text):
        # Case 1: Week 5 or Week 5-6
        if m.group(1):
            start_week = int(m.group(1))
            end_week = int(m.group(2)) if m.group(2) else start_week
            for wk in range(start_week, end_week + 1):
                event_date = semester_start + dt.timedelta(weeks=wk - 1)
                events.append((event_date, f"week {wk}"))
        # Case 2: 2nd week
        elif m.group(3):
            wk_num = int(m.group(3))
            event_date = semester_start + dt.timedelta(weeks=wk_num - 1)
            events.append((event_date, f"{wk_num} week"))
    return events


def window_context(text: str, keyword: str, win: int = 80) -> str:
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return "Event"
    start = max(0, idx - win)
    end = idx + len(keyword) + win
    return text[start:end].replace("\n", " ")


def extract_title(context: str) -> str:
    ctx = context.lower()
    for kw in KEYWORDS:
        if kw in ctx:
            return kw.capitalize()
    return (context.strip()[:40] + "…") if len(context) > 40 else context.strip()


def filter_by_semester(events, sem_start: dt.date, sem_end: dt.date):
    return [(d, lbl) for d, lbl in events if sem_start <= d <= sem_end]


def build_calendar_df(events, text):
    return pd.DataFrame(
        {
            "Date": [d.isoformat() for d, _ in events],
            "Event Description": [extract_title(window_context(text, lbl)) for _, lbl in events],
        }
    ).sort_values("Date")


def ics_bytes(events, text) -> bytes:
    cal = Calendar()
    for date_obj, lbl in events:
        ev = Event()
        ev.name = extract_title(window_context(text, lbl))
        ev.begin = date_obj.isoformat()
        cal.events.add(ev)
    return cal.serialize().encode()


def pdf_bytes(events, text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "📅 Course Calendar", ln=True, align="C")
    for d, lbl in events:
        title = extract_title(window_context(text, lbl))
        pdf.cell(0, 8, f"{d.isoformat()}: {title}", ln=True)
    return io.BytesIO(pdf.output(dest="S").encode("latin1"))


def fullcalendar(events_df):
    """Render month grid using streamlit‑calendar."""
    cal_events = [
        {"title": row["Event Description"], "start": row["Date"]}
        for _, row in events_df.iterrows()
    ]
    options = {
        "initialView": "dayGridMonth",
        "height": 650,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay",
        },
    }
    calendar(cal_events, options=options, key="fullcalendar")

# ---------- STREAMLIT APP ----------

st.set_page_config(page_title="Syllabus → Calendar", page_icon="📘", layout="centered")

st.title("📘 Syllabus → Smart Calendar")

uploaded_file = st.file_uploader("📎 Upload syllabus (PDF)", type=["pdf"])

col1, col2 = st.columns(2)
with col1:
    semester_start = st.date_input("Semester Start Date")
with col2:
    semester_end = st.date_input("Semester End Date")

if semester_start and semester_end and semester_start >= semester_end:
    st.error("Start date must be before end date.")
    st.stop()

if uploaded_file and semester_start and semester_end:

    @st.cache_data(show_spinner="🔍 Parsing syllabus…")
    def process(file_bytes: bytes, sem_start: dt.date, sem_end: dt.date):
        text = extract_text(uploaded_file)
        abs_events = parse_absolute_dates(text)
        rel_events = parse_relative_weeks(text, sem_start)
        all_events = filter_by_semester(abs_events + rel_events, sem_start, sem_end)
        df = build_calendar_df(all_events, text)
        ics = ics_bytes(all_events, text)
        pdf = pdf_bytes(all_events, text)
        return df, ics, pdf

    df, ics_data, pdf_data = process(uploaded_file.getvalue(), semester_start, semester_end)

    if df.empty:
        st.warning("❌ No valid deadlines or week references found in this date range.")
        st.stop()

    st.subheader("🗓️ Generated Calendar")
    fullcalendar(df)  # interactive grid

    with st.expander("Show table view"):
        st.dataframe(df, hide_index=True)

    st.download_button(
        "📆 Download .ics",
        ics_data,
        file_name="course_calendar.ics",
        mime="text/calendar",
    )

    st.download_button(
        "🖨️ Download PDF",
        pdf_data,
        file_name="course_calendar.pdf",
        mime="application/pdf",
    )
