import sqlite3
import os


def get_conn():
    try:
        db_path = os.environ.get("POS_DB", "pos.db")
        conn = sqlite3.connect(db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None


def _ensure_schema(cursor, table, create_sql, expected_cols):
    existing = {r[1] for r in cursor.execute(f"PRAGMA table_info({table})")}
    if existing and existing != set(expected_cols):
        cursor.execute(f"DROP TABLE {table}")
    cursor.execute(create_sql)


def init_tables_table():
    conn = get_conn()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS tables (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            location TEXT,
            status TEXT DEFAULT 'empty',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        expected_cols = ['id', 'name', 'location', 'status', 'created_at']
        _ensure_schema(cursor, 'tables', create_sql, expected_cols)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error initializing tables table: {e}")
        return False
    finally:
        conn.close()


def init_sessions_table():
    conn = get_conn()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY,
            table_id INTEGER,
            customer_name TEXT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (table_id) REFERENCES tables(id)
        )
        """
        expected_cols = ['id', 'table_id', 'customer_name', 'start_time', 'end_time', 'status', 'created_at']
        _ensure_schema(cursor, 'sessions', create_sql, expected_cols)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error initializing sessions table: {e}")
        return False
    finally:
        conn.close()


def init_pricing_table():
    conn = get_conn()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS pricing_config (
            id INTEGER PRIMARY KEY,
            start_hour INTEGER,
            end_hour INTEGER,
            price_per_hour REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        expected_cols = ['id', 'start_hour', 'end_hour', 'price_per_hour', 'created_at']
        _ensure_schema(cursor, 'pricing_config', create_sql, expected_cols)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error initializing pricing_config table: {e}")
        return False
    finally:
        conn.close()


def init_services_table():
    conn = get_conn()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        expected_cols = ['id', 'name', 'price', 'created_at']
        _ensure_schema(cursor, 'services', create_sql, expected_cols)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error initializing services table: {e}")
        return False
    finally:
        conn.close()


def init_order_items_table():
    conn = get_conn()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY,
            session_id INTEGER,
            service_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
        """
        expected_cols = ['id', 'session_id', 'service_id', 'quantity', 'unit_price', 'created_at']
        _ensure_schema(cursor, 'order_items', create_sql, expected_cols)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error initializing order_items table: {e}")
        return False
    finally:
        conn.close()


def init_db():
    success = True
    for fn in [init_tables_table, init_sessions_table, init_pricing_table, init_services_table, init_order_items_table]:
        if not fn():
            print(f"Failed to initialize {fn.__name__}")
            success = False
    return success
