import os
import sys
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.schema import VisualizationSchema
from utils.llm_pick import pick_llm
from agents.sql_agent import sql_analyst

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END


# Ensure the visualizations directory exists
os.makedirs("visualizations", exist_ok=True)


def understand_data_needs(state: VisualizationSchema):
    """Decide what data is needed and ask the SQL Agent."""
    llm = pick_llm("low")
    prompt = f"""
    You are a Visualization Expert. The user wants to see a chart based on this request:
    "{state.user_question}"
    
    What exact data do we need from the PostgreSQL database to make this chart?
    Write a precise request for our SQL Agent to fetch the data. 
    Ask for the exact metrics, grouping, ordering, and date filtering if needed.
    Only return the request text, without any markdown formatting or quotes.
    """
    chain = llm | StrOutputParser()
    state.sql_agent_query = chain.invoke(prompt).strip()
    return state


def fetch_data(state: VisualizationSchema):
    """Invoke the SQL agent to get the data."""
    print(f"\n[Viz Agent] Requesting Data: {state.sql_agent_query}")
    sql_input = {
        "messages": [],
        "user_question": state.sql_agent_query,
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "Yes",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
        "db_connection_string": getattr(state, "db_connection_string", "")
    }
    sql_result = sql_analyst.invoke(sql_input)
    state.sql_execution_result = sql_result['sql_query_execution_result']
    print(f"[Viz Agent] Received data from SQL Agent.")
    return state


def decide_and_generate_code(state: VisualizationSchema):
    """Decide the chart type and write the Python code to generate it."""
    llm = pick_llm("medium")
    
    # We dynamically set a unique image path
    image_path = "visualizations/generated_chart.png"
    state.image_path = image_path
    
    prompt = f"""
    You are a Data Visualization Expert. 
    User's Goal: {state.user_question}
    Data from Database: {state.sql_execution_result}
    
    1. Decide the most appropriate chart type (line chart, bar chart, scatter plot, etc.).
    2. Write a complete, standalone Python script using `matplotlib.pyplot` to create the chart.
    3. The script must parse the provided 'Data from Database' string directly (just hardcode the parsed lists into the script variables).
    4. Make the chart look professional with titles, labels, and colors.
    5. The script MUST save the chart to the exact path: `{image_path}` using `plt.savefig('{image_path}', bbox_inches='tight')`. Do NOT use `plt.show()`.
    
    Output ONLY the Python code. Do not include markdown code blocks (```python). Just pure Python code.
    """
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    # Clean just in case it added markdown
    cleaned_code = response.replace("```python", "").replace("```", "").strip()
    
    state.chart_type = "Determined by LLM (see code)"
    state.python_code = cleaned_code
    return state


def execute_and_validate(state: VisualizationSchema):
    """Execute the generated Python code to create the chart."""
    print("[Viz Agent] Executing Python code to generate chart...")
    try:
        # Enforce Agg backend for headless plotting
        safe_code = "import matplotlib\nmatplotlib.use('Agg')\n" + state.python_code
        exec_globals = {'__name__': '__main__'}
        exec(safe_code, exec_globals)
        print(f"[Viz Agent] Successfully generated chart at: {state.image_path}")
    except Exception as e:
        error_msg = f"Failed to generate chart. Error: {traceback.format_exc()}"
        print(error_msg)
        state.image_path = f"Error generating chart. (Details: {str(e)})"
    return state


def explain_chart(state: VisualizationSchema):
    """Generate a business-friendly explanation of the chart."""
    llm = pick_llm("medium")
    prompt = f"""
    You are a Data Analyst presenting a chart to a stakeholder.
    User's Question: {state.user_question}
    Raw Data: {state.sql_execution_result}
    Chart generated at: {state.image_path}
    
    Write a concise explanation of what the chart shows, including the main trend, anomaly, or insight.
    Keep it clear, simple, and use markdown formatting.
    """
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    state.final_explanation = response
    state.messages = state.messages + [AIMessage(content=response)]
    return state


# ---------------------------------- Graph Building --------------------------

workflow = StateGraph(VisualizationSchema)

# Nodes
workflow.add_node("understand_data_needs", understand_data_needs)
workflow.add_node("fetch_data", fetch_data)
workflow.add_node("decide_and_generate_code", decide_and_generate_code)
workflow.add_node("execute_and_validate", execute_and_validate)
workflow.add_node("explain_chart", explain_chart)

# Edges
workflow.add_edge(START, "understand_data_needs")
workflow.add_edge("understand_data_needs", "fetch_data")
workflow.add_edge("fetch_data", "decide_and_generate_code")
workflow.add_edge("decide_and_generate_code", "execute_and_validate")
workflow.add_edge("execute_and_validate", "explain_chart")
workflow.add_edge("explain_chart", END)

# Compile
viz_agent = workflow.compile()


if __name__ == "__main__":
    
    # Save graph diagram (optional)
    try:
        from IPython.display import Image
        img = Image(viz_agent.get_graph().draw_mermaid_png())
        with open("viz_agent_graph.png", "wb") as f:
            f.write(img.data)
    except Exception:
        pass

    test_state = {
        "messages": [],
        "user_question": "Show me a bar chart of the top 5 products with the highest sales and explain the difference.",
        "sql_agent_query": "",
        "sql_execution_result": "",
        "chart_type": "",
        "python_code": "",
        "image_path": "",
        "final_explanation": ""
    }
    
    print(f"User Question: {test_state['user_question']}")
    
    result = viz_agent.invoke(test_state)
    
    print("\n" + "="*50)
    print("FINAL EXPLANATION:")
    print("="*50)
    print(result['final_explanation'])
    print(f"\nChart saved at: {result['image_path']}")
