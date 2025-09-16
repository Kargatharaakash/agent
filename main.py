import streamlit as st
import pandas as pd
import requests
import time
import re
from datetime import datetime
from io import BytesIO
import os
from fpdf import FPDF
import xlsxwriter

# --- Minimal, Clean UI Styling ---
st.set_page_config(page_title="🇮🇳 Indian Students in USA Masters Finder", layout="centered", page_icon="🎓")
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2.5rem;
        padding-bottom: 2.5rem;
        max-width: 700px;
        background: #fff;
        border-radius: 18px;
        box-shadow: 0 2px 16px 0 rgba(0,0,0,0.07);
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 700;
        background: #e11d48 !important;
        color: #fff !important;
        border: none;
        padding: 0.9em 2.2em;
        margin: 0.5em 0 1.2em 0;
        font-size: 1.2em;
        box-shadow: 0 2px 8px #e11d4822;
        transition: background 0.2s;
    }
    .stButton>button:hover {
        background: #be123c !important;
        color: #fff !important;
    }
    .stTextInput>div>div>input {
        border-radius: 8px;
        border: 1.5px solid #e11d48;
        padding: 0.5em;
        font-size: 1.1em;
    }
    .stDataFrame th, .stDataFrame td {
        white-space: normal !important;
        word-break: break-word !important;
        font-size: 1em;
        padding: 8px 6px;
    }
    .stMarkdown h3, .stMarkdown h2, .stMarkdown h1 {
        margin-top: 1.5em;
    }
    .download-popup {
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 2px 16px #0002;
        padding: 2em 2em 1.5em 2em;
        max-width: 350px;
        margin: 0 auto;
        text-align: center;
    }
    .download-popup .stButton>button {
        background: #2563eb !important;
        color: #fff !important;
        font-size: 1em;
        margin: 0.5em 0.2em 0.5em 0.2em;
        padding: 0.5em 1.2em;
    }
    .download-popup .stButton>button:hover {
        background: #1e40af !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Header ---
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 1.2em; margin-bottom:1.5em;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/41/Flag_of_India.svg" width="48" style="border-radius:8px;box-shadow:0 2px 8px #0001; display: block; align-self: center;">
        <span style="display: flex; align-items: center; height: 48px;">
            <h1 style="margin-bottom:0.2em;font-size:2.1em; line-height: 1.1; margin-top:0; display: flex; align-items: center;">Find Indian Students in USA Masters</h1>
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Minimal Info ---
st.info(
    "Find real Indian students currently pursuing or recently admitted to Masters programs in the USA. "
)

# --- Use SERPER_API_KEY from environment variable for security ---
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
if not SERPER_API_KEY:
    st.error("Serper API key not found in environment variable 'SERPER_API_KEY'. Please set it in your environment for security. If running locally, you can add it to a `.env` file in your project root as:\n\nSERPER_API_KEY=your_api_key_here\n\nIf running on Streamlit Cloud, set it as a secret or environment variable in the app settings.")
    st.stop()

# --- Year Range Selection (Top, prominent, not sidebar) ---
st.markdown("#### 🎓 Select Year Range")
current_year = datetime.now().year
min_year = 2018
# Do not allow selecting a year more than 2025
max_year = min(2025, current_year + 2)
default_from = current_year - 1 if current_year > min_year else min_year
default_to = current_year + 1 if current_year + 1 <= max_year else max_year

col_from, col_to = st.columns(2)
with col_from:
    year_from = st.number_input("From Year", min_value=min_year, max_value=max_year, value=default_from, step=1, key="from_year")
with col_to:
    year_to = st.number_input("To Year", min_value=min_year, max_value=max_year, value=default_to, step=1, key="to_year")

if year_from > year_to:
    st.error("From Year must be less than or equal to To Year.")

# --- Build dynamic year string for queries ---
selected_years = [str(y) for y in range(int(year_from), int(year_to) + 1)]
years_or = " OR ".join([f'"{y}"' for y in selected_years])
fall_years = " OR ".join([f'"Fall {y}"' for y in selected_years])
spring_years = " OR ".join([f'"Spring {y}"' for y in selected_years])
class_years = " OR ".join([f'"Class of {y}"' for y in selected_years])

def build_queries():
    return [
        f'site:linkedin.com/in "Indian student" "Masters" "United States" ({years_or})',
        f'site:linkedin.com/in "MS in USA" "Indian" ({years_or})',
        f'site:linkedin.com/in "Indian" "Master of Science" "United States" ({years_or})',
        f'site:linkedin.com/in "Indian" "graduate student" "USA" ({years_or})',
        f'site:linkedin.com/in "Indian" "MS" "admitted" "USA" ({years_or})',
        f'site:linkedin.com/in "Indian" "MS" {fall_years}',
        f'site:linkedin.com/in "Indian" "Masters" {spring_years}',
        f'site:linkedin.com/in "Indian" "MS" {class_years}',
        f'site:linkedin.com/in "Indian" "MS" "University" "USA" ({years_or})',
        f'site:linkedin.com/in "Indian" "MS" "admit" "USA" ({years_or})',
    ]

QUERIES = build_queries()

def extract_name_from_title(title):
    title = re.sub(r' - .*', '', title)
    title = re.sub(r'\s*\|.*', '', title)
    title = re.sub(r'\b(Indian|student|MS|Masters?|USA|United States|admit|admitted|graduate|Class of \d{4}|Fall \d{4}|Spring \d{4})\b', '', title, flags=re.IGNORECASE)
    name = title.strip()
    if len(name.split()) >= 2 and all(x.isalpha() or x == '.' for x in name.replace(' ', '')):
        return name
    return ""

def is_recent(snippet, title):
    for y in selected_years:
        if y in snippet or y in title:
            return True
    return False

def search_google_serper(query, num_results=15):
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": num_results
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("organic", []):
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            if "linkedin.com/in/" not in link:
                continue
            if not is_recent(snippet, title):
                continue
            name = extract_name_from_title(title)
            if not name:
                username = link.split("linkedin.com/in/")[-1].split("/")[0]
                username = username.replace("-", " ").replace("_", " ").title()
                if len(username.split()) >= 2:
                    name = username
            if name and len(name.split()) >= 2 and all(x.isalpha() or x == '.' for x in name.replace(' ', '')):
                results.append({
                    "Name": name,
                    "LinkedIn URL": link,
                    "Profile Title": title,
                    "Snippet": snippet
                })
        return results
    except Exception as e:
        st.error(f"Google Serper API failed: {e}")
        return []

def filter_df(df, search_text):
    if not search_text:
        return df
    search_text = search_text.lower()
    mask = pd.Series([False]*len(df))
    for col in df.columns:
        mask = mask | df[col].astype(str).str.lower().str.contains(search_text)
    return df[mask]

def to_excel_bytes(df):
    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Students')
            worksheet = writer.sheets['Students']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(idx, idx, max_len)
        output.seek(0)
        return output.read()
    except Exception as e:
        st.error(f"Excel export failed: {e}")
        return b""

def to_pdf_bytes(df):
    def to_latin1(text):
        if not isinstance(text, str):
            text = str(text)
        try:
            return text.encode('latin1', errors='replace').decode('latin1')
        except Exception:
            return ''.join((c if ord(c) < 256 else '?') for c in text)

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    col_widths = []
    max_width = 270
    n_cols = len(df.columns)
    for col in df.columns:
        max_content = max([len(str(x)) for x in df[col]] + [len(col)])
        col_widths.append(max(30, min(70, max_content * 2.5)))
    total_width = sum(col_widths)
    if total_width > max_width:
        scale = max_width / total_width
        col_widths = [w * scale for w in col_widths]
    for i, col in enumerate(df.columns):
        pdf.cell(col_widths[i], 10, to_latin1(col), border=1, align='C')
    pdf.ln()
    for idx, row in df.iterrows():
        for i, col in enumerate(df.columns):
            text = str(row[col])
            if len(text) > 60:
                text = text[:57] + "..."
            text = to_latin1(text)
            pdf.cell(col_widths[i], 8, text, border=1)
        pdf.ln()
    try:
        pdf_bytes = pdf.output(dest='S').encode('latin1')
    except Exception as e:
        st.error(f"PDF export failed: {e}")
        return b""
    return pdf_bytes

if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'search_history' not in st.session_state:
    st.session_state.search_history = []
if 'show_download_popup' not in st.session_state:
    st.session_state.show_download_popup = False

# --- Main UI: Clean, Minimal, Focused ---
st.markdown("---")

# --- Big Red Search Button ---
search_trigger = st.button(
    f"Find Students",
    use_container_width=True,
    key="main_search_btn"
)

# --- Search Logic ---
if search_trigger:
    if year_from > year_to:
        st.error("Please select a valid year range (From Year <= To Year).")
    else:
        all_results = []
        with st.spinner(f"Searching for Indian students in USA Masters ({year_from}-{year_to})..."):
            for idx, query in enumerate(QUERIES):
                results = search_google_serper(query, num_results=10)
                all_results.extend(results)
                time.sleep(1.2)
            seen = set()
            unique_results = []
            for r in all_results:
                if r["LinkedIn URL"] not in seen:
                    seen.add(r["LinkedIn URL"])
                    unique_results.append(r)
            st.session_state.search_results = unique_results
            if unique_results:
                st.session_state.search_history.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "count": len(unique_results),
                    "results": unique_results.copy(),
                    "year_from": year_from,
                    "year_to": year_to
                })
                st.success(f"✅ Found {len(unique_results)} Indian student profiles in USA Masters ({year_from}-{year_to}).")
            else:
                st.warning(f"No Indian student data found for USA Masters ({year_from}-{year_to}). Try again or check your API key/internet connection.")

# --- DataFrame Preparation ---
df = pd.DataFrame(st.session_state.search_results) if st.session_state.search_results else pd.DataFrame(
    columns=["Name", "LinkedIn URL", "Profile Title", "Snippet"]
)

# --- Filter Bar (only if data exists) ---
if not df.empty:
    search_text = st.text_input("🔍 Filter results (name, university, etc):", value="", key="search_text", help="Type any keyword to filter results")
    filtered_df = filter_df(df, search_text)
else:
    filtered_df = df

# --- Results Table ---
if not filtered_df.empty:
    st.markdown("### 🎓 Results")
    st.dataframe(
        filtered_df.style.format({
            "LinkedIn URL": lambda x: f"[Profile]({x})" if pd.notnull(x) else "",
        }),
        use_container_width=True,
        hide_index=True,
        column_order=["Name", "LinkedIn URL", "Profile Title", "Snippet"]
    )

    # --- Download Bar (inline, no popup) ---
    st.markdown(
        "<div style='display:flex;align-items:center;gap:0.7em;margin:1em 0 1.5em 0;'>"
        "<span style='font-weight:500;font-size:1.05em;'>Download as</span>"
        "</div>",
        unsafe_allow_html=True
    )
    col_csv, col_xlsx, col_pdf = st.columns([1,1,1])
    with col_csv:
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="CSV",
            data=csv,
            file_name=f"indian_students_usa_masters_{year_from}_{year_to}.csv",
            mime="text/csv",
            use_container_width=True,
            key="csv_dl"
        )
    with col_xlsx:
        excel_bytes = to_excel_bytes(filtered_df)
        st.download_button(
            label="Excel",
            data=excel_bytes,
            file_name=f"indian_students_usa_masters_{year_from}_{year_to}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="xlsx_dl"
        )
    with col_pdf:
        pdf_bytes = to_pdf_bytes(filtered_df)
        st.download_button(
            label="PDF",
            data=pdf_bytes,
            file_name=f"indian_students_usa_masters_{year_from}_{year_to}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="pdf_dl"
        )
else:
    if not df.empty:
        st.info("No data matches your filter. Try a different keyword.")
    else:
        st.markdown(
            "<div style='text-align:center;color:#64748b;font-size:1.1em;margin-top:2em;'>"
            "Start by selecting your year range and tapping the <b style='color:#e11d48;'>big red button</b> above."
            "</div>",
            unsafe_allow_html=True
        )

# --- Search History (minimal, optional) ---
if st.session_state.search_history:
    with st.expander("🕑 Show Search History (this session)", expanded=False):
        for i, hist in enumerate(reversed(st.session_state.search_history[-5:]), 1):
            year_range = f"({hist.get('year_from', '')}-{hist.get('year_to', '')})" if 'year_from' in hist and 'year_to' in hist else ""
            with st.expander(f"{hist['timestamp']} — {hist['count']} results {year_range}", expanded=False):
                hist_df = pd.DataFrame(hist["results"])
                st.dataframe(hist_df, use_container_width=True, hide_index=True)
                st.caption(f"Search #{len(st.session_state.search_history)-i+1}")

# --- Remove sidebar completely except for year selection (already moved above) ---
