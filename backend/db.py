import sqlite3
import os

def get_conn():
    """Create or get an SQLite connection."""
    db_path = os.environ.get("POS_DB", "pos.db")
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def _ensure_schema(cursor, table, create_sql, expected_cols):
    """Ensure table schema matches expected columns."""
    existing = {r[1] for r in cursor.execute(f"PRAGMA table_info({table})")}
    if existing and existing != set(expected_cols):
        cursor.execute(f"DROP TABLE {table}")
    cursor.execute(create_sql)

def create_billiard_tables_table(conn):
    """Create billiard_tables table."""
    cursor = conn.cursor()
    create_sql = """
    CREATE TABLE IF NOT EXISTS billiard_tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        status TEXT DEFAULT 'available',
        price_per_hour REAL NOT NULL
    )
    """
    expected_cols = ['id', 'table_name', 'status', 'price_per_hour']
    _ensure_schema(cursor, 'billiard_tables', create_sql, expected_cols)
    conn.commit()

def create_table_sessions_table(conn):
    """Create table_sessions table."""
    cursor = conn.cursor()
    create_sql = """
    CREATE TABLE IF NOT EXISTS table_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_id INTEGER NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME,
        total_charge REAL,
        FOREIGN KEY (table_id) REFERENCES billiard_tables(id)
    )
    """
    expected_cols = ['id', 'table_id', 'start_time', 'end_time', 'total_charge']
    _ensure_schema(cursor, 'table_sessions', create_sql, expected_cols)
    conn.commit()

def init_db():
    """Initialize the database with all required tables."""
    conn = None
    try:
        conn = get_conn()
        create_billiard_tables_table(conn)
        create_table_sessions_table(conn)
    finally:
        if conn:
            conn.close()

def validate_price(price_per_hour):
    """Validate price is positive."""
    if price_per_hour <= 0:
        raise ValueError(f"Price must be greater than 0, got {price_per_hour}")
    return True

def check_table_available(table_id):
    """Check if a table is available."""
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM billiard_tables WHERE id = ?", (table_id,))
        result = cursor.fetchone()
        
        if result is None:
            raise Exception(f"Table with id {table_id} does not exist")
        
        status = result[0]
        if status != 'available':
            raise Exception(f"Table {table_id} is occupied")
        
        return True
    finally:
        if conn:
            conn.close()
