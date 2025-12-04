"""Database abstraction layer for SQLite and PostgreSQL"""
import os
import sqlite3
import pandas as pd

PSYCOPG2_AVAILABLE = False
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    pass

USE_POSTGRES = "DATABASE_URL" in os.environ

class DBConnection:
    """Unified database connection handler for SQLite and PostgreSQL"""
    
    def __init__(self):
        self.is_postgres = USE_POSTGRES and PSYCOPG2_AVAILABLE
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establish database connection"""
        if self.is_postgres:
            try:
                self.conn = psycopg2.connect(os.environ["DATABASE_URL"])
                self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            except Exception as e:
                print(f"PostgreSQL connection failed: {e}. Falling back to SQLite.")
                self.is_postgres = False
                self._connect_sqlite()
        
        if not self.is_postgres:
            self._connect_sqlite()
            
        return self.conn, self.cursor
    
    def _connect_sqlite(self):
        """Connect to SQLite database"""
        db_path = os.path.join(os.getcwd(), "caballebrios.db")
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def execute(self, query, params=None):
        """Execute query (handles both SQL dialects)"""
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
    
    def executemany(self, query, params_list):
        """Execute multiple queries"""
        self.cursor.executemany(query, params_list)
    
    def fetchone(self):
        """Fetch one result"""
        return self.cursor.fetchone()
    
    def fetchall(self):
        """Fetch all results"""
        return self.cursor.fetchall()
    
    def commit(self):
        """Commit transaction"""
        self.conn.commit()
    
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()

def read_sql_query(query, conn, params=None):
    """Read SQL query into DataFrame (works with both SQLite and PostgreSQL)"""
    try:
        if isinstance(conn, tuple):  # Tuple of (connection, cursor)
            actual_conn = conn[0]
        else:
            actual_conn = conn
        
        return pd.read_sql_query(query, actual_conn, params=params)
    except Exception as e:
        print(f"Error reading SQL: {e}")
        return pd.DataFrame()
