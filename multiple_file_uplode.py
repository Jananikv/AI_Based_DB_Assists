import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text, create_engine
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Streamlit UI Setup
st.set_page_config(page_title="SQL Agent", layout="wide")
st.title("💡 AI-Powered SQL Agent")

# Database Setup
db_uri = "sqlite:///example.db"
engine = create_engine(db_uri)

# Initialize session state
if "uploaded" not in st.session_state:
    st.session_state.uploaded = False
if "query_results" not in st.session_state:
    st.session_state.query_results = None
if "chart_results" not in st.session_state:
    st.session_state.chart_results = None
if "sql_queries" not in st.session_state:
    st.session_state.sql_queries = {}

# File Upload (Multiple Files)
uploaded_files = st.file_uploader("📂 Upload CSV/Excel (Multiple Allowed)", type=["csv", "xlsx"], accept_multiple_files=True)

if uploaded_files:
    try:
        table_names = []
        for uploaded_file in uploaded_files:
            filename = uploaded_file.name.split(".")[0]  # Get file name without extension
            
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
                df.to_sql(filename, con=engine, if_exists='replace', index=False)
                table_names.append(filename)

            elif uploaded_file.name.endswith('.xlsx'):
                xls = pd.ExcelFile(uploaded_file)
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                    table_name = f"{filename}_{sheet_name}"  # Unique table name
                    df.to_sql(table_name, con=engine, if_exists='replace', index=False)
                    table_names.append(table_name)

        st.session_state.uploaded = True
        st.success(f"✅ Files uploaded successfully! Tables created: {', '.join(table_names)}")

        # Quick View of First Table
        st.subheader("👀 Quick Preview of Uploaded Tables")
        preview_table = st.selectbox("Select Table to Preview", table_names)
        preview_df = pd.read_sql(f"SELECT * FROM {preview_table} LIMIT 5", con=engine)
        st.dataframe(preview_df)

    except Exception as e:
        st.error(f"❌ File upload error: {e}")

# Functions
def get_schema(db):
    """Get the schema of the uploaded database."""
    return db.get_table_info()

def execute_sql_query(sql_query):
    """Execute SQL query on the uploaded database."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df
    except Exception as e:
        st.error(f"❌ Error executing SQL query: {e}")
        return pd.DataFrame()

def sql_query(user_question):
    """Generates SQL query using AI for multi-table queries."""
    if user_question in st.session_state.sql_queries:
        return st.session_state.sql_queries[user_question]

    try:
        db = SQLDatabase.from_uri(db_uri)
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key="AIzaSyD5dG8SU3sxIW2zczxJ-NAteTGOPoc4PyQ")  # Replace with actual key
        # AI Prompt Template
        template = """Based on this database schema, write a valid SQL query:
        {schema}
        Question: {question}
        """
        prompt = ChatPromptTemplate.from_template(template)
        sql_chain = RunnablePassthrough.assign(schema=lambda x: get_schema(db)) | prompt | llm | StrOutputParser()

        raw_sql = sql_chain.invoke({"question": user_question})
        cleaned_sql = raw_sql.replace("```sql", "").replace("```", "").strip()

        st.session_state.sql_queries[user_question] = cleaned_sql
        return cleaned_sql
    except Exception as e:
        st.error(f"❌ Error generating SQL query: {e}")
        return ""

def generate_chart(chart_df):
    """Generates charts based on query results."""
    try:
        if df.empty:
            st.warning("⚠️ No data available for visualization.")
            return

        chart_type = st.selectbox("📊 Choose Visualization", ["None", "Bar Chart", "Pie Chart", "Scatter Plot", "Line Chart", "Histogram"])
        if chart_type == "None":
            return

        x_axis = st.selectbox("📌 Select X-axis", df.columns)
        y_axis = None
        if chart_type != "Pie Chart":
            y_axis = st.selectbox("📌 Select Y-axis", df.columns)

        chart_mapping = {
            "Bar Chart": px.bar,
            "Pie Chart": px.pie,
            "Scatter Plot": px.scatter,
            "Line Chart": px.line,
            "Histogram": px.histogram
        }

        fig = chart_mapping[chart_type](df, x=x_axis, y=y_axis, title=f"{chart_type} of {x_axis} vs {y_axis}")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Chart generation error: {e}")

# User Query for Data Retrieval
if st.session_state.uploaded:
    st.subheader("🔍 SQL Query for Data Retrieval")
    user_query = st.text_input("Enter Your SQL Query")

    if user_query.strip():
        if user_query not in st.session_state.sql_queries:
            text_sql_query = sql_query(user_query)
            st.session_state.sql_queries[user_query] = text_sql_query
        else:
            text_sql_query = st.session_state.sql_queries[user_query]

        st.text_area("📝 Generated SQL Query", value=text_sql_query, height=100)

        df = execute_sql_query(text_sql_query)
        st.session_state.query_results = df

        if not df.empty:
            st.dataframe(df)
            st.download_button("📥 Download Results as CSV", df.to_csv(index=False), file_name="query_results.csv", mime="text/csv")

# User Query for Chart Visualization
if st.session_state.uploaded:
    st.subheader("📊 SQL Query for Chart Visualization")
    chart_query = st.text_input("Enter SQL Query for Chart")

    if chart_query.strip():
        if chart_query not in st.session_state.sql_queries:
            chart_sql_query = sql_query(chart_query)
            st.session_state.sql_queries[chart_query] = chart_sql_query
        else:
            chart_sql_query = st.session_state.sql_queries[chart_query]

        st.text_area("📝 Generated SQL Query for Chart", value=chart_sql_query, height=100)

        chart_df = execute_sql_query(chart_sql_query)
        st.session_state.chart_results = chart_df

        if not chart_df.empty:
            generate_chart(chart_df)
