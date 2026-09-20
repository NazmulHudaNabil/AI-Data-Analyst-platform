import os
import sys

from models.schema import SupervisorSchema, RouteDecision
from utils.llm_pick import pick_llm

from agents.etl_agent import etl_analyst
from agents.sql_agent import sql_analyst
from agents.data_analyst_agent import data_analyst
from agents.visualization_agent import viz_agent
from agents.data_quality_agent import data_quality_agent

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END


def route_request(state: SupervisorSchema):
    """Analyze the user's request and determine the correct agent to handle it."""
    print(f"\n[Supervisor] Analyzing user intent: '{state.user_input}'")
    
    llm = pick_llm("low")
    llm_router = llm.with_structured_output(RouteDecision)
    
    prompt = f"""
    You are the central Supervisor Router for an AI Data Analyst Platform.
    Your job is to read the user's request and route it to the correct specialized sub-agent.
    
    The available agents are:
    1. "etl": For extracting data from an API or file, transforming it, and loading it somewhere.
    2. "sql": For raw, direct database queries (e.g., "Give me a list of all products").
    3. "data_analysis": For complex analytical questions requiring statistical reasoning and "Why" explanations based on database data (e.g. "Which product has the highest sales and why?").
    4. "visualization": For generating charts, graphs, or visual plots based on database data.
    5. "data_quality": For analyzing a CSV dataset or SQL Table for missing values, duplicates, and invalid data (e.g. "Check the quality of users.csv" or "Check quality of products table").
    
    User's Request: {state.user_input}
    
    Determine the best 'agent' to route to. 
    If the user mentions a CSV file for data quality, extract its exact path into 'file_path'.
    If the user mentions a SQL database table for data quality, extract its exact name into 'table_name'.
    """
    
    decision = llm_router.invoke(prompt)
    
    state.selected_agent = decision.agent
    state.extracted_file_path = decision.file_path
    state.extracted_table_name = decision.table_name
    
    print(f"[Supervisor] Routing task to -> {state.selected_agent.upper()} Agent")
    return state


def call_etl(state: SupervisorSchema):
    """Invoke the ETL Agent."""
    print("[Supervisor] Handing off to ETL Agent...")
    
    etl_input = {
        "messages": [],
        "user_input": state.user_input,
        "python_code": "",
        "execution_result": "",
        "db_connection_string": getattr(state, "db_connection_string", "")
    }
    
    response = etl_analyst.invoke(etl_input)
    state.final_response = response['messages'][-1].content
    return state


def call_sql(state: SupervisorSchema):
    """Invoke the SQL Agent."""
    print("[Supervisor] Handing off to SQL Agent...")
    sql_input = {
        "messages": [],
        "user_question": state.user_input,
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "Yes",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
        "db_connection_string": state.db_connection_string
    }
    response = sql_analyst.invoke(sql_input)
    state.final_response = response['final_answer']
    return state


def call_data_analyst(state: SupervisorSchema):
    """Invoke the Data Analyst Agent."""
    print("[Supervisor] Handing off to Data Analyst Agent...")
    da_input = {
        "messages": [],
        "user_question": state.user_input,
        "sql_agent_query": "",
        "sql_execution_result": "",
        "statistical_analysis": "",
        "final_answer": "",
        "db_connection_string": state.db_connection_string
    }
    response = data_analyst.invoke(da_input)
    state.final_response = response['final_answer']
    return state


def call_visualization(state: SupervisorSchema):
    """Invoke the Visualization Agent."""
    print("[Supervisor] Handing off to Visualization Agent...")
    viz_input = {
        "messages": [],
        "user_question": state.user_input,
        "sql_agent_query": "",
        "sql_execution_result": "",
        "chart_type": "",
        "python_code": "",
        "image_path": "",
        "final_explanation": "",
        "db_connection_string": state.db_connection_string
    }
    response = viz_agent.invoke(viz_input)
    
    chart_msg = f"\n[Chart Saved at: {response['image_path']}]\n\n"
    state.final_response = chart_msg + response['final_explanation']
    return state


def call_data_quality(state: SupervisorSchema):
    """Invoke the Data Quality Agent."""
    print("[Supervisor] Handing off to Data Quality Agent...")
    
    dq_input = {
        "messages": [],
        "dataset_path": state.extracted_file_path or "",
        "target_table": state.extracted_table_name or "",
        "db_connection_string": state.db_connection_string or "",
        "dataset_info": "",
        "python_code": "",
        "execution_result": "",
        "quality_report": ""
    }
    response = data_quality_agent.invoke(dq_input)
    state.final_response = response['quality_report']
    return state


def route_decision(state: SupervisorSchema):
    """Return the name of the next node based on the selected agent."""
    agent_map = {
        "etl": "call_etl",
        "sql": "call_sql",
        "data_analysis": "call_data_analyst",
        "visualization": "call_visualization",
        "data_quality": "call_data_quality"
    }
    return agent_map.get(state.selected_agent, "call_data_analyst") # Default if unknown


# ---------------------------------- Graph Building --------------------------

supervisor_workflow = StateGraph(SupervisorSchema)

# Nodes
supervisor_workflow.add_node("route_request", route_request)
supervisor_workflow.add_node("call_etl", call_etl)
supervisor_workflow.add_node("call_sql", call_sql)
supervisor_workflow.add_node("call_data_analyst", call_data_analyst)
supervisor_workflow.add_node("call_visualization", call_visualization)
supervisor_workflow.add_node("call_data_quality", call_data_quality)

# Edges
supervisor_workflow.add_edge(START, "route_request")

supervisor_workflow.add_conditional_edges(
    "route_request", 
    route_decision,
    {
        "call_etl": "call_etl",
        "call_sql": "call_sql",
        "call_data_analyst": "call_data_analyst",
        "call_visualization": "call_visualization",
        "call_data_quality": "call_data_quality"
    }
)

supervisor_workflow.add_edge("call_etl", END)
supervisor_workflow.add_edge("call_sql", END)
supervisor_workflow.add_edge("call_data_analyst", END)
supervisor_workflow.add_edge("call_visualization", END)
supervisor_workflow.add_edge("call_data_quality", END)

# Compile
supervisor_agent = supervisor_workflow.compile()


if __name__ == "__main__":
    
    # Save graph diagram (optional)
    try:
        from IPython.display import Image
        img = Image(supervisor_agent.get_graph().draw_mermaid_png())
        with open("supervisor_graph.png", "wb") as f:
            f.write(img.data)
    except Exception:
        pass

    # A simple interactive CLI loop to test the supervisor!
    print("\n" + "="*70)
    print("🤖 AI Data Analyst Platform - Supervisor Ready!")
    print("="*70)
    print("Welcome! I am the main Supervisor Agent.")
    print("You can ask me to extract data, query SQL, analyze trends, make charts, or check data quality.")
    print("Type 'exit' or 'quit' to quit.\n")
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ['exit', 'quit', "break"]:
                break
            if not user_input.strip():
                continue
                
            test_state = {
                "messages": [],
                "user_input": user_input,
                "selected_agent": "",
                "extracted_file_path": "",
                "final_response": ""
            }
            
            result = supervisor_agent.invoke(test_state)
            
            print("\n" + "-"*70)
            print(f"🤖 Agent Response ({result['selected_agent'].upper()}):")
            print("-"*70)
            print(result['final_response'])
            print("-"*70 + "\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"An error occurred: {e}")
