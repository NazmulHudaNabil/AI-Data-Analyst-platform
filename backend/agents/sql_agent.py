import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.database import DatabaseUtils
from utils.llm_pick import pick_llm
from models.schema import SqlAgentSchema, SqlJudgeSchema
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END



def curate_ques(state:SqlAgentSchema):
    user_question = state.user_question.strip().lower()

    llm = pick_llm("low")

    chain = llm | StrOutputParser()
    prompt = f"""
    You are an AI assistant tasked with refining a user's question into a clean, precise data extraction request. 
    Output ONLY the refined question. Do not provide explanations, best practices, or extra formatting. 
    If the question is already clear, output it exactly as is.
    
    User Question: {user_question}
    """
    
    response = chain.invoke(prompt)

    state.curated_ques = response.strip()

    state.messages = state.messages + [HumanMessage(content=f"Curated user question: {state.curated_ques}")]

    return state




def prompt_query_context(state:SqlAgentSchema):

    curated_question = state.curated_ques

    if hasattr(state, 'db_connection_string') and state.db_connection_string:
        conn_details = state.db_connection_string
    else:
        conn_details = {
            "host": os.environ.get('host', ''),
            "port": os.environ.get('port', ''),
            "user": os.environ.get('user', ''),
            "password": os.environ.get('password', ''),
            "dbname": os.environ.get('database', '')
        }

    obj = DatabaseUtils(conn_details)

    schema_info = obj.schema_details("public")

     # Constructing the prompt query for the agent to generate the SQL query
    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language 
    query into Postgres SQL query that can be executed on the database. You are provided 
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that 
    you can understand the structure of the database and generate an accurate SQL query.
    
    IMPORTANT RULES:
    1. Unless the user explicitly asks for a specific number of rows, or the query is an aggregation (like COUNT), always limit the output to 10 rows.
    2. Whenever you perform a JOIN, you MUST strictly alias or fully qualify every single column name in the SELECT, GROUP BY, and ORDER BY clauses (e.g., use `products.unitprice` instead of just `unitprice`) to prevent ambiguous column reference errors.
    3. Watch out for columns typed as `json` that contain scalar numeric values (like `unitprice` or `discount`). PostgreSQL CANNOT directly cast `json` to `numeric`. You MUST extract the scalar value as text first using `#>>'{{}}'` before casting. For example: `CAST(products.unitprice#>>'{{}}' AS NUMERIC)`.
    
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    query only.  
    
    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}
    
    """

    state.prompt_query_context = prompt

    return state



# Generate SQL Query Node
def generate_sql(state:SqlAgentSchema):

    prompt = state.prompt_query_context

    llm = pick_llm("medium")

    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)

    # Postgres doesn't understand Markdown, so we must clean it out before executing!
    cleaned_sql = response.replace("```sql", "").replace("```", "").strip()

    state.generated_sql_query = cleaned_sql

    return state


# Is safe node
def is_safe_sql(state:SqlAgentSchema):

    sql_query = state.generated_sql_query

    llm = pick_llm("medium")

    llm_judge = llm.with_structured_output(SqlJudgeSchema)

    prompt = f"""
    You are an SQL Judge for data security. Your task is to determine whether the SQL query is 
    safe or not. The SQL query should only be used for data retrieval and should not modify the 
    database in any way. Neither the SQL query nor the prompt should contain any SQL commands that can modify the
    database, such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change
    the structure or content of the database. If the SQL query is safe, respond with 'Yes' otherwise respond with 
    'No'. Additionally, provide comments explaining your decision.
    Here's the SQL query to evaluate:
    {sql_query}"""

    response = llm_judge.invoke(prompt).model_dump()
    state.is_safe = response['answer']
    state.comments = response['comments']

    return state



# Canceled Sql Query Node
def canceled_sql_query(state:SqlAgentSchema):

    comments = state.comments

    state.final_answer = f"The generated SQL query was deemed unsafe to execute. The reason provided by the judge is: {comments}. Therefore, the SQL query will not be executed."
    state.messages = state.messages + [AIMessage(content=state.final_answer)]

    return state


# Execute SQL Query Node
def execute_sql_query(state:SqlAgentSchema):

    sql_query = state.generated_sql_query

    if hasattr(state, 'db_connection_string') and state.db_connection_string:
        conn_details = state.db_connection_string
    else:
        conn_details = {
            "host": os.environ.get('host', ''),
            "port": os.environ.get('port', ''),
            "user": os.environ.get('user', ''),
            "password": os.environ.get('password', ''),
            "dbname": os.environ.get('database', '')
        }

    obj = DatabaseUtils(conn_details)

    result = obj.execute_sql(sql_query)

    # If the SQL query fails, it returns None. Pydantic expects a string.
    # So we handle it cleanly by converting None to a string message.
    if result is None:
        result = "Error: SQL execution failed."
    else:
        result = f"The executed SQL query '{sql_query}' returned the following raw data:\n{result}"

    state.sql_query_execution_result = result

    return state


# Represent final answer node
def represent_final_answer(state:SqlAgentSchema):

    curated_question = state.curated_ques
    execution_result = state.sql_query_execution_result

    llm = pick_llm("low")

    prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {execution_result} \n
    Here is the user's original question: {curated_question}
    """

    chain = llm | StrOutputParser()
    response = chain.invoke(prompt)
    state.final_answer = response
    state.messages = state.messages + [AIMessage(content=state.final_answer)]

    return state





# ---------------------------------- Graph Building --------------------------

sql_agent_graph = StateGraph(SqlAgentSchema)

# Nodes

sql_agent_graph.add_node("curate_ques", curate_ques)
sql_agent_graph.add_node("prompt_query_context", prompt_query_context)
sql_agent_graph.add_node("generate_sql", generate_sql)
sql_agent_graph.add_node("is_safe_sql", is_safe_sql)
sql_agent_graph.add_node("canceled_sql_query", canceled_sql_query)
sql_agent_graph.add_node("execute_sql_query", execute_sql_query)
sql_agent_graph.add_node("represent_final_answer", represent_final_answer)



# Edges

sql_agent_graph.add_edge(START, "curate_ques")
sql_agent_graph.add_edge("curate_ques", "prompt_query_context")
sql_agent_graph.add_edge("prompt_query_context", "generate_sql")
sql_agent_graph.add_edge("generate_sql", "is_safe_sql")

def is_safe_sql_edge(state: SqlAgentSchema):
    is_safe = state.is_safe

    if is_safe.lower() == "yes":
        return "execute_sql_query"
    else:
        return "canceled_sql_query"

sql_agent_graph.add_conditional_edges("is_safe_sql", is_safe_sql_edge,
                                      {
                                          "execute_sql_query": "execute_sql_query",
                                          "canceled_sql_query": "canceled_sql_query"
                                      })

sql_agent_graph.add_edge("canceled_sql_query", END)
sql_agent_graph.add_edge("execute_sql_query", "represent_final_answer")
sql_agent_graph.add_edge("represent_final_answer", END)


# Compile the graph
sql_analyst = sql_agent_graph.compile()


if __name__ == "__main__":

    from IPython.display import display, Image

    img = Image(sql_analyst.get_graph().draw_mermaid_png())
    with open("sql_agent_graph.png", "wb") as f:
        f.write(img.data)

    # Example
    input_schema = {
        "messages": [],
        "user_question": "What are the top 5 products with the highest sales?",
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }

    sql_analyst_response = sql_analyst.invoke(input_schema)

    # print(sql_analyst_response['messages'])  # Print the final output of the graph execution
    # print("********************************")

    print(sql_analyst_response['generated_sql_query'])  # Print the generated SQL query

    print("********************************")

    print(sql_analyst_response['final_answer'])  # Print whether the SQL query is safe to execute