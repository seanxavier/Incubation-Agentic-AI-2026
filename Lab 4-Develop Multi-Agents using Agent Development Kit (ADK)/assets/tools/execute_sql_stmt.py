"""
Execute SQL Statement Tool for watsonx Orchestrate ADK
This tool accepts SQL statements as input and executes them on PostgreSQL database.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
from ibm_watsonx_orchestrate.run import connections



def fetch_all_dicts(cur) -> List[Dict[str, Any]]:
    """Fetch all rows as list of dictionaries."""
    rows = cur.fetchall()
    if cur.description:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    return []


# ============================================================
# JSON-SAFE HELPERS
# ============================================================
def _json_safe(obj: Any) -> Any:
    """Convert object to JSON-safe format."""
    return json.loads(json.dumps(obj, default=str))


MY_APP_ID = 'postgres-connection-<YourName>'
POSTGRES_DB = 'watsonxdb'

@tool(
    name="execute_sql_statement_<YourName>",
    description=(
        "Execute a SQL SELECT statement on PostgreSQL database and return results. "
        "Only SELECT queries are allowed for security. "
        "Use this tool to retrieve data from the database dynamically."
    ),
    permission=ToolPermission.ADMIN,
    expected_credentials=[  # type: ignore[arg-type]
        {"app_id": MY_APP_ID, "type": ConnectionType.KEY_VALUE}
    ],
)
def execute_sql_statement(sql_statement: str) -> Dict[str, Any]:
    """
    Execute a SQL SELECT statement on PostgreSQL database.
    
    Args:
        sql_statement: SQL SELECT query to execute (e.g., "SELECT * FROM table_name LIMIT 10")
    
    Returns:
        Dictionary containing status, count, and results array
    """
    creds = connections.key_value(MY_APP_ID)
    
    def connect_postgres(database: str) -> psycopg2.extensions.connection:
        """
        Create PostgreSQL database connection.
        
        Args:
            database: Database name to connect to
            
        Returns:
            PostgreSQL connection object
        """
        return psycopg2.connect(
            user=creds.get('POSTGRES_USER', ''),
            password=creds.get('POSTGRES_PASSWORD', ''),
            database=creds.get('POSTGRES_DB', database),
            host=creds.get('POSTGRES_HOST', 'localhost'),
            port=creds.get('POSTGRES_PORT', '5432'),
            connect_timeout=15
        )
    
    # Validate SQL statement (security check)
    sql_upper = sql_statement.upper().strip()
    
    # Check if it's a SELECT query
    if not sql_upper.startswith('SELECT'):
        return _json_safe({
            "status": "error",
            "message": "Only SELECT queries are allowed for security reasons",
            "sql_statement": sql_statement,
            "count": 0,
            "results": []
        })
    
    # Check for dangerous keywords
    dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE']
    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            return _json_safe({
                "status": "error",
                "message": f"Query contains forbidden keyword: {keyword}",
                "sql_statement": sql_statement,
                "count": 0,
                "results": []
            })
    
    # DB connect
    conn = None
    cur = None
    
    try:
        conn = connect_postgres(POSTGRES_DB)
        
        # Execute query with RealDictCursor for dictionary results
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql_statement)
        
        # Fetch results
        results = cur.fetchall()
        
        # Convert to list of dictionaries
        data = [dict(row) for row in results]
        
        return _json_safe({
            "status": "success",
            "sql_statement": sql_statement,
            "count": len(data),
            "results": data,
            "message": f"Query executed successfully. Returned {len(data)} rows."
        })
        
    except psycopg2.Error as e:
        return _json_safe({
            "status": "error",
            "message": f"Database error: {str(e)}",
            "sql_statement": sql_statement,
            "count": 0,
            "results": []
        })
    except Exception as e:
        return _json_safe({
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "sql_statement": sql_statement,
            "count": 0,
            "results": []
        })
    finally:
        # Clean up resources
        if cur:
            cur.close()
        if conn:
            conn.close()


