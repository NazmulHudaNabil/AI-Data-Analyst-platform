import os
from utils.database import DatabaseUtils
import json

db_connections = json.load(open("data/connections.json"))
if db_connections:
    conn_str = list(db_connections.values())[0]["connection_string"]
    db = DatabaseUtils(conn_str)
    print(db.schema_details("public"))
else:
    print("No connections found.")
