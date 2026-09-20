import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.schema import DataAnalystSchema
from utils.llm_pick import pick_llm
from agents.sql_agent import sql_analyst

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END


def understand_question(state: DataAnalystSchema):
    """Formulate a direct query for the SQL agent based on the user's analytical question."""
    llm = pick_llm("low")
    
    prompt = f"""
    You are an expert Data Analyst. The user has asked an analytical question: 
    "{state.user_question}"
    
    To answer this, we need data from our PostgreSQL database. 
    Write a precise and clean request for our SQL Agent to fetch the necessary data. 
    Make sure to ask for the exact metrics, grouping, and ordering needed.
    Only return the request text, nothing else. Do not use quotes around your request.
    """
    
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    state.sql_agent_query = response.strip()
    return state


def request_sql_agent(state: DataAnalystSchema):
    """Invoke the SQL agent to get the data."""
    print(f"\n[Data Analyst] Asking SQL Agent: {state.sql_agent_query}")
    
    sql_input = {
        "messages": [],
        "user_question": state.sql_agent_query,
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "Yes",  # Default starting state
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
        "db_connection_string": getattr(state, "db_connection_string", "")
    }
    
    # Run the SQL Agent as a sub-agent
    sql_result = sql_analyst.invoke(sql_input)
    
    # Extract the data returned by the database
    state.sql_execution_result = sql_result['sql_query_execution_result']
    print(f"[Data Analyst] Received data from SQL Agent.")
    return state


def analyze_data(state: DataAnalystSchema):
    """Analyze the retrieved data to find trends and anomalies."""
    llm = pick_llm("medium")  
    
    prompt = f"""
    You are an expert Data Analyst. You need to analyze the data below to answer the user's original question.
    
    User Question: {state.user_question}
    Data retrieved from database: {state.sql_execution_result}
    
    Perform a clear statistical analysis. Look for trends, anomalies, or top factors affecting the outcome.
    Provide a detailed breakdown of your findings based strictly on the data provided.
    """
    
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    state.statistical_analysis = response
    return state


def generate_explanation(state: DataAnalystSchema):
    """Generate a clean, easy-to-read final explanation for the user."""
    llm = pick_llm("medium")
    
    prompt = f"""
    You are a Data Analyst communicating with a business stakeholder.
    
    User Question: {state.user_question}
    Detailed Analysis: {state.statistical_analysis}
    
    Write a concise, business-friendly final explanation summarizing the insights.
    Do not use overly technical jargon. Provide actionable insights if applicable.
    Make it easy to read using markdown formatting.
    """
    
    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    
    state.final_answer = response
    state.messages = state.messages + [AIMessage(content=response)]
    return state


# ---------------------------------- Graph Building --------------------------

workflow = StateGraph(DataAnalystSchema)

# Nodes
workflow.add_node("understand_question", understand_question)
workflow.add_node("request_sql_agent", request_sql_agent)
workflow.add_node("analyze_data", analyze_data)
workflow.add_node("generate_explanation", generate_explanation)

# Edges
workflow.add_edge(START, "understand_question")
workflow.add_edge("understand_question", "request_sql_agent")
workflow.add_edge("request_sql_agent", "analyze_data")
workflow.add_edge("analyze_data", "generate_explanation")
workflow.add_edge("generate_explanation", END)

# Compile
data_analyst = workflow.compile()


if __name__ == "__main__":
    
    # Optional: Save graph diagram
    try:
        from IPython.display import Image
        img = Image(data_analyst.get_graph().draw_mermaid_png())
        with open("data_analyst_graph.png", "wb") as f:
            f.write(img.data)
    except Exception as e:
        pass

    # Test the Agent
    test_state = {
        "messages": [],
        "user_question": "Which product category generated the highest revenue, and why do you think it outperformed the others?",
        "sql_agent_query": "",
        "sql_execution_result": "",
        "statistical_analysis": "",
        "final_answer": ""
    }
    
    print(f"User Question: {test_state['user_question']}")
    
    result = data_analyst.invoke(test_state)
    
    print("\n" + "="*50)
    print("FINAL EXPLANATION:")
    print("="*50)
    print(result['final_answer'])
