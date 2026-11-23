"""Streamlit UI: streamlit run app.py"""
import pandas as pd
import streamlit as st

from text2sql.agent import TextToSQL
from text2sql.db import DEFAULT_DB, build

st.set_page_config(page_title="Text-to-SQL Demo", page_icon="🔎")
st.title("Ask the data")
st.caption("Plain-language questions → validated, read-only SQL → results. Synthetic job-marketplace data.")

if not DEFAULT_DB.exists():
    build()


@st.cache_resource
def engine():
    return TextToSQL(DEFAULT_DB)


examples = [
    "How many open job posts are there per city?",
    "Average max salary for Senior Data roles by work mode",
    "Which 5 companies had the most hires in the last 6 months?",
    "Application-to-hire conversion rate by job category",
]
q = st.text_input("Question", placeholder=examples[0])
cols = st.columns(2)
for i, ex in enumerate(examples):
    if cols[i % 2].button(ex, use_container_width=True):
        q = ex

if q:
    with st.spinner("Thinking…"):
        ans = engine().ask(q)
    if ans.sql:
        st.code(ans.sql, language="sql")
    if ans.explanation:
        st.write(ans.explanation)
    if ans.error:
        st.error(ans.error)
    else:
        st.dataframe(pd.DataFrame(ans.rows, columns=ans.columns), use_container_width=True)
    st.caption("Attempts: %d" % ans.attempts)
