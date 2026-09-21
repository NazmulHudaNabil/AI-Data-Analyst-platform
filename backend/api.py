from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import uuid

# Import our compiled LangGraph agents
from main import supervisor_agent
from agents.etl_agent import etl_analyst
from agents.sql_agent import sql_analyst
from agents.data_analyst_agent import data_analyst
from langchain_core.messages import HumanMessage

app = FastAPI(
    title="AI Data Analyst API",
    description="REST API for the Multi-Agent Data Analyst Platform",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins
    allow_credentials=False, # Must be False if allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.staticfiles import StaticFiles

# Ensure directories exist
os.makedirs("data", exist_ok=True)
os.makedirs("visualizations", exist_ok=True)

# Mount directories so generated files can be downloaded via URL
app.mount("/downloads/data", StaticFiles(directory="data"), name="data")
app.mount("/downloads/visualizations", StaticFiles(directory="visualizations"), name="visualizations")

# ---------------------------------------------------------
# Models
# ---------------------------------------------------------
class ChatRequest(BaseModel):
    query: str
    connection_id: str | None = None

class ConnectionRequest(BaseModel):
    name: str
    connection_string: str

class ConnectionResponse(BaseModel):
    id: str
    name: str
    connection_string: str

import json

CONNECTIONS_FILE = "data/connections.json"

def load_connections() -> Dict[str, dict]:
    if os.path.exists(CONNECTIONS_FILE):
        try:
            with open(CONNECTIONS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_connections(conns: Dict[str, dict]):
    with open(CONNECTIONS_FILE, "w") as f:
        json.dump(conns, f, indent=4)

db_connections: Dict[str, dict] = load_connections()


# ---------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------
@app.get("/api/v1/health")
def health_check():
    """Check if the API is running."""
    return {"status": "ok", "message": "AI Data Analyst API is online and ready."}


from fastapi import Header, Depends

# ---------------------------------------------------------
# Connections Endpoints
# ---------------------------------------------------------
@app.post("/api/v1/connections", response_model=ConnectionResponse)
def add_connection(req: ConnectionRequest, x_user_id: str = Header(default="anonymous")):
    """
    Save a new database connection string tied to a user session.
    """
    conn_id = str(uuid.uuid4())
    db_connections[conn_id] = {
        "id": conn_id,
        "user_id": x_user_id,
        "name": req.name,
        "connection_string": req.connection_string
    }
    save_connections(db_connections)
    return db_connections[conn_id]


@app.get("/api/v1/connections", response_model=List[ConnectionResponse])
def get_connections(x_user_id: str = Header(default="anonymous")):
    """Retrieve database connections specific to this user session."""
    user_conns = [conn for conn in db_connections.values() if conn.get("user_id", "anonymous") == x_user_id]
    return user_conns


@app.delete("/api/v1/connections/{conn_id}")
def delete_connection(conn_id: str, x_user_id: str = Header(default="anonymous")):
    """Delete a stored database connection by ID if it belongs to the user."""
    if conn_id in db_connections:
        # Check if the connection belongs to the user
        if db_connections[conn_id].get("user_id", "anonymous") != x_user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this connection")
            
        del db_connections[conn_id]
        save_connections(db_connections)
        return {"message": f"Connection {conn_id} deleted successfully."}
    raise HTTPException(status_code=404, detail="Connection not found")


# ---------------------------------------------------------
# Agent Endpoints
# ---------------------------------------------------------
@app.post("/api/v1/chat")
def chat_endpoint(req: ChatRequest):
    """
    General entry point that uses the Supervisor Agent to route the query
    to the correct specialized sub-agent dynamically.
    """
    db_conn_string = ""
    if req.connection_id and req.connection_id in db_connections:
        db_conn_string = db_connections[req.connection_id]["connection_string"]
        
    test_state = {
        "messages": [],
        "user_input": req.query,
        "selected_agent": "",
        "extracted_file_path": "",
        "final_response": "",
        "db_connection_string": db_conn_string
    }
    
    try:
        result = supervisor_agent.invoke(
            test_state, 
            config={
                "run_name": "Chat Endpoint (Supervisor)",
                "tags": ["chat", "supervisor"],
                "metadata": {"connection_id": req.connection_id}
            }
        )
        
        return {
            "routed_agent": result.get("selected_agent"),
            "response": result.get("final_response")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze")
def analyze_endpoint(req: ChatRequest):
    """Directly invokes the Data Analyst Agent for deep statistical analysis."""
    test_state = {
        "messages": [],
        "user_question": req.query,
        "sql_agent_query": "",
        "sql_execution_result": "",
        "statistical_analysis": "",
        "final_answer": ""
    }
    
    try:
        result = data_analyst.invoke(
            test_state, 
            config={
                "run_name": "Data Analyst Endpoint",
                "tags": ["analyze", "data_analyst"]
            }
        )
        return {"response": result.get("final_answer")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/etl")
def etl_endpoint(req: ChatRequest):
    """Directly invokes the ETL Agent for data extraction and transformation."""
    
    try:
        db_conn_string = ""
        if req.connection_id and req.connection_id in db_connections:
            db_conn_string = db_connections[req.connection_id]["connection_string"]
            
        etl_input = {
            "messages": [],
            "user_input": req.query,
            "python_code": "",
            "execution_result": "",
            "db_connection_string": db_conn_string
        }
        result = etl_analyst.invoke(
            etl_input,
            config={
                "run_name": "ETL Endpoint",
                "tags": ["etl", "data_engineering"],
                "metadata": {"connection_id": req.connection_id}
            }
        )
        return {"response": result['messages'][-1].content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/sql")
def sql_endpoint(req: ChatRequest):
    """Directly invokes the SQL Agent for raw database queries."""
    test_state = {
        "messages": [],
        "user_question": req.query,
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "Yes",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }
    
    try:
        result = sql_analyst.invoke(
            test_state,
            config={
                "run_name": "SQL Analyst Endpoint",
                "tags": ["sql", "data_extraction"]
            }
        )
        
        return {
            "generated_sql": result.get("generated_sql_query"),
            "raw_data": result.get("sql_query_execution_result"),
            "response": result.get("final_answer")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
