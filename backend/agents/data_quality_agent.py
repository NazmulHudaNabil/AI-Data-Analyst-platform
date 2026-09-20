import os
import sys
import pandas as pd
from io import StringIO
import contextlib
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.schema import DataQualitySchema
from utils.llm_pick import pick_llm

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END


def read_dataset_context(state: DataQualitySchema):
    """Read the dataset headers and top 5 rows to provide context to the LLM."""
    print(f"\n[Data Quality Agent] Reading dataset...")
    
    try:
        if state.db_connection_string and state.target_table:
            # Connect to PostgreSQL and load the table
            from sqlalchemy import create_engine
            print(f"[Data Quality Agent] Extracting table '{state.target_table}' from PostgreSQL...")
            engine = create_engine(state.db_connection_string)
            df = pd.read_sql_table(state.target_table, con=engine)
            state.dataset_path = f"SQL Table: {state.target_table}" # Just for context string
        else:
            # Fallback to CSV
            path = state.dataset_path if state.dataset_path else "data/employees.csv"
            print(f"[Data Quality Agent] Extracting from CSV: {path}")
            df = pd.read_csv(path, encoding='iso-8859-1')
            state.dataset_path = path

        buffer = StringIO()
        df.info(buf=buffer)
        info_str = buffer.getvalue()
        
        sample_data = df.head().to_string()
        
        state.dataset_info = f"Total Rows: {len(df)}\n\n--- Dataset Info ---\n{info_str}\n\n--- Sample Data ---\n{sample_data}"
    except Exception as e:
        state.dataset_info = f"Error reading dataset: {e}"
    
    return state


def generate_quality_code(state: DataQualitySchema):
    """Generate pandas code to check for missing values, duplicates, and invalid data."""
    llm = pick_llm("medium")
    
    if state.db_connection_string and state.target_table:
        load_instruction = f"1. Connect to PostgreSQL using sqlalchemy and load the table '{state.target_table}' into a pandas dataframe using `pd.read_sql_table`. The connection string is '{state.db_connection_string}'. Import create_engine from sqlalchemy."
    else:
        load_instruction = f"1. Load the CSV file '{state.dataset_path}' (use encoding='iso-8859-1')."
    
    prompt = f"""
    You are a Data Quality Expert. 
    You need to write a standalone Python script using `pandas` to check the quality of a dataset.
    
    Dataset Path/Table: "{state.dataset_path}"
    Dataset Context (Info & Sample):
    {state.dataset_info}
    
    The script must:
    {load_instruction}
    2. Calculate total rows.
    3. Calculate the number and percentage of missing values per column.
    4. Calculate the number of duplicate rows.
    5. Check for invalid or outlier values (e.g., negative numbers for prices/quantities, missing foreign keys, weird strings) based on the specific columns present in this dataset. Be creative and thorough.
    6. Print all these findings clearly to the standard output (using print()) so it can be captured.
    
    Output ONLY the Python code. Do not include markdown code blocks (```python). Just pure Python code.
    """
    
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    cleaned_code = response.replace("```python", "").replace("```", "").strip()
    state.python_code = cleaned_code
    return state


def execute_quality_code(state: DataQualitySchema):
    """Execute the generated python code and capture the output."""
    # print(f"\n[Data Quality Agent] Generated Python Code:\n{state.python_code}\n")
    # print("[Data Quality Agent] Executing quality check code...")
    
    # Capture standard output
    output_buffer = StringIO()
    try:
        exec_globals = {'pd': pd, '__name__': '__main__'}
        with contextlib.redirect_stdout(output_buffer):
            exec(state.python_code, exec_globals)
        state.execution_result = output_buffer.getvalue()
        print(f"\n[Data Quality Agent] Raw Execution Result:\n{state.execution_result}\n")
    except Exception as e:
        state.execution_result = f"Error executing quality check code: {traceback.format_exc()}"
        
    return state


def generate_quality_report(state: DataQualitySchema):
    """Generate a clean, structured data quality report."""
    llm = pick_llm("medium")
    
    prompt = f"""
    You are a Data Quality Analyst. 
    Review the raw execution result of the data quality checks and format it into a professional, easy-to-read Markdown report.
    
    Raw Execution Result:
    {state.execution_result}
    
    The report should include:
    - Total Rows Analyzed
    - Missing Values summary (percentages)
    - Duplicates count
    - Invalid Values / Anomalies
    - Recommendations for cleaning the data (e.g. "Impute missing ages", "Remove duplicate rows", etc.)
    
    Make it look like a highly professional, well-formatted report.
    """
    
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    state.quality_report = response
    state.messages = state.messages + [AIMessage(content=response)]
    return state


# ---------------------------------- Graph Building --------------------------

workflow = StateGraph(DataQualitySchema)

# Nodes
workflow.add_node("read_dataset_context", read_dataset_context)
workflow.add_node("generate_quality_code", generate_quality_code)
workflow.add_node("execute_quality_code", execute_quality_code)
workflow.add_node("generate_quality_report", generate_quality_report)

# Edges
workflow.add_edge(START, "read_dataset_context")
workflow.add_edge("read_dataset_context", "generate_quality_code")
workflow.add_edge("generate_quality_code", "execute_quality_code")
workflow.add_edge("execute_quality_code", "generate_quality_report")
workflow.add_edge("generate_quality_report", END)

# Compile
data_quality_agent = workflow.compile()


if __name__ == "__main__":
    
    # Save graph diagram (optional)
    try:
        from IPython.display import Image
        img = Image(data_quality_agent.get_graph().draw_mermaid_png())
        with open("data_quality_agent_graph.png", "wb") as f:
            f.write(img.data)
    except Exception:
        pass

    # Provide an existing dataset from the project for the test run
    test_state = {
        "messages": [],
        "dataset_path": "data/employees.csv",  
        "dataset_info": "",
        "python_code": "",
        "execution_result": "",
        "quality_report": ""
    }
    
    result = data_quality_agent.invoke(test_state)
    
    print("\n" + "="*50)
    print("DATA QUALITY REPORT:")
    print("="*50)
    print(result['quality_report'])
