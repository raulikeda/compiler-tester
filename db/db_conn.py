import sqlite3
import os

def getConnection(db_name):
    """
    Create and return a SQLite database connection
    """
    # Ensure the db directory exists
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, db_name)
    
    # Create connection with foreign key support
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    
    return conn
