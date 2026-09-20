import os
import sys
import contextlib
from io import StringIO
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.llm_pick import pick_llm
from models.schema import ETLAgentSchema
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END


def generate_etl_code(state: ETLAgentSchema):
    """Generate a single Python script to perform the ETL task."""
    print(f"\n[ETL Agent] Analyzing task: {state.user_input}")
    llm = pick_llm("medium")  # Use flash model to save tokens
    
    # Using sqlalchemy or psycopg2 for DB
    # Determine which DB connection strategy to tell the LLM to use
    db_conn_instructions = ""
    if hasattr(state, 'db_connection_string') and state.db_connection_string:
        db_conn_instructions = f"- Use this exact SQLAlchemy URI to connect: '{state.db_connection_string}'"
    else:
        db_conn_instructions = "- Read the connection details from environment variables (`host`, `port`, `user`, `password`, `database`) using `os.environ` to build the SQLAlchemy URI."

    prompt = f"""
    You are an expert Data Engineer. The user wants you to perform an ETL (Extract, Transform, Load) task.
    User Request: "{state.user_input}"
    
    Write a complete, standalone Python script to accomplish this.
    
    Rules:
    1. If pulling from an API, use the `requests` library.
    2. If transforming data, use `pandas`.
    3. If saving to PostgreSQL, use `sqlalchemy` and `pandas.to_sql()` or `psycopg2`. 
       {db_conn_instructions}
    4. If saving to a file, ensure the directory exists first using `os.makedirs()`.
    5. Print clear success messages to standard output so we know what happened.
    6. Write a flat script. Do NOT wrap your code in `if __name__ == '__main__':` blocks.
    
    Output ONLY pure Python code. No markdown formatting, no quotes.
    """
    
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    state.python_code = response.replace("```python", "").replace("```", "").strip()
    return state


def execute_etl_code(state: ETLAgentSchema):
    """Execute the generated python code and capture the output."""
    print(f"\n[ETL Agent] Generated Python Code:\n{state.python_code}\n")
    print("[ETL Agent] Executing ETL script...")
    
    output_buffer = StringIO()
    try:
        # Standard libraries often used in ETL
        exec_globals = {"__name__": "__main__"}
        with contextlib.redirect_stdout(output_buffer):
            exec(state.python_code, exec_globals)
        state.execution_result = output_buffer.getvalue()
    except Exception as e:
        state.execution_result = f"Error during ETL execution:\n{traceback.format_exc()}"
        
    print(f"\n[ETL Agent] Execution Result:\n{state.execution_result}\n")
    return state


def summarize_etl_result(state: ETLAgentSchema):
    """Format the raw execution result into a clean response."""
    llm = pick_llm("low")
    
    prompt = f"""
    The ETL task has finished executing. 
    User Request: {state.user_input}
    Execution Output: {state.execution_result}
    
    Write a short, professional response to the user summarizing whether the task succeeded or failed based on the output.
    """
    
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    state.messages = state.messages + [AIMessage(content=response)]
    return state


# Build the Graph
workflow = StateGraph(ETLAgentSchema)

workflow.add_node("generate_etl_code", generate_etl_code)
workflow.add_node("execute_etl_code", execute_etl_code)
workflow.add_node("summarize_etl_result", summarize_etl_result)

workflow.add_edge(START, "generate_etl_code")
workflow.add_edge("generate_etl_code", "execute_etl_code")
workflow.add_edge("execute_etl_code", "summarize_etl_result")
workflow.add_edge("summarize_etl_result", END)

etl_analyst = workflow.compile()


if __name__ == "__main__":
    test_state = {
        "messages": [],
        "user_input": "Extract pokemon data from https://pokeapi.co/api/v2/pokemon, and save it to a CSV file in data/extracted_pokemon.csv",
        "python_code": "",
        "execution_result": ""
    }
    
    result = etl_analyst.invoke(test_state)
    print("\n" + "="*50)
    print(result['messages'][-1].content)
