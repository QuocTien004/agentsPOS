import sqlite3
from datetime import datetime
from db import get_conn


def validate_action(id_val, action):
    """Validate action before open/close session."""
    if action not in ('open', 'close'):
        return False, "Invalid action"
    
    conn = get_conn()
    if not conn:
        return False, "DB error"
    
    cursor = conn.cursor()
    
    if action == 'open':
        # Check table exists and is empty
        cursor.execute("SELECT status FROM tables WHERE id = ?", (id_val,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Table not found"
        if row[0] != 'empty':
            conn.close()
            return False, "Table is not empty"
    
    elif action == 'close':
        # Check session exists and is open
        cursor.execute("SELECT status FROM sessions WHERE id = ?", (id_val,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Session not found"
        if row[0] != 'open':
            conn.close()
            return False, "Session not open"
    
    conn.close()
    return True, ""


def open_session(table_id, customer_name):
    """Open session for table."""
    is_valid, err = validate_action(table_id, 'open')
    if not is_valid:
        return {'error': err}
    
    conn = get_conn()
    if not conn:
        return {'error': 'DB error'}
    
    try:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO sessions (table_id, customer_name, start_time, status)
            VALUES (?, ?, ?, 'open')
        """, (table_id, customer_name, now))
        
        session_id = cursor.lastrowid
        
        # Update table status
        cursor.execute("UPDATE tables SET status = 'in_use' WHERE id = ?", (table_id,))
        
        conn.commit()
        return session_id
    except Exception as e:
        return {'error': str(e)}
    finally:
        conn.close()


def close_session(session_id):
    """Close session and calculate total."""
    is_valid, err = validate_action(session_id, 'close')
    if not is_valid:
        return {'error': err}
    
    conn = get_conn()
    if not conn:
        return {'error': 'DB error'}
    
    try:
        cursor = conn.cursor()
        
        # Get session info
        cursor.execute("""
            SELECT table_id, start_time FROM sessions WHERE id = ?
        """, (session_id,))
        row = cursor.fetchone()
        table_id, start_time_str = row
        
        # Calculate hours and price
        end_time = datetime.now()
        start_time = datetime.fromisoformat(start_time_str)
        total_hours = (end_time - start_time).total_seconds() / 3600
        
        # Get price per hour for current time
        cursor.execute("""
            SELECT price_per_hour FROM pricing_config
            WHERE start_hour <= ? AND end_hour > ?
            LIMIT 1
        """, (end_time.hour, end_time.hour))
        pricing_row = cursor.fetchone()
        price_per_hour = pricing_row[0] if pricing_row else 50.0
        
        # Get services total
        cursor.execute("""
            SELECT COALESCE(SUM(quantity * unit_price), 0) FROM order_items
            WHERE session_id = ?
        """, (session_id,))
        services_total = cursor.fetchone()[0]
        
        total_amount = total_hours * price_per_hour + services_total
        
        # Update session
        end_time_iso = end_time.isoformat()
        cursor.execute("""
            UPDATE sessions SET status = 'closed', end_time = ?
            WHERE id = ?
        """, (end_time_iso, session_id))
        
        # Update table
        cursor.execute("UPDATE tables SET status = 'empty' WHERE id = ?", (table_id,))
        
        conn.commit()
        
        return {
            'session_id': session_id,
            'table_id': table_id,
            'total_hours': round(total_hours, 2),
            'price_per_hour': price_per_hour,
            'total_amount': round(total_amount, 2)
        }
    except Exception as e:
        return {'error': str(e)}
    finally:
        conn.close()


def add_service(session_id, service_id, quantity):
    """Add service to session."""
    conn = get_conn()
    if not conn:
        return {'error': 'DB error'}
    
    try:
        cursor = conn.cursor()
        
        # Validate session exists and is open
        cursor.execute("SELECT status FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if not row or row[0] != 'open':
            return {'error': 'Session not found or not open'}
        
        # Get service price
        cursor.execute("SELECT price FROM services WHERE id = ?", (service_id,))
        row = cursor.fetchone()
        if not row:
            return {'error': 'Service not found'}
        
        unit_price = row[0]
        
        # Add order item
        cursor.execute("""
            INSERT INTO order_items (session_id, service_id, quantity, unit_price)
            VALUES (?, ?, ?, ?)
        """, (session_id, service_id, quantity, unit_price))
        
        # Get total for session
        cursor.execute("""
            SELECT COALESCE(SUM(quantity * unit_price), 0) FROM order_items
            WHERE session_id = ?
        """, (session_id,))
        order_total = cursor.fetchone()[0]
        
        conn.commit()
        return round(order_total, 2)
    except Exception as e:
        return {'error': str(e)}
    finally:
        conn.close()


def configure_system(action, data):
    """Configure system (tables, pricing)."""
    conn = get_conn()
    if not conn:
        return {'success': False, 'error': 'DB error'}
    
    try:
        cursor = conn.cursor()
        
        if action == 'add_table':
            name = data.get('name', '').strip()
            location = data.get('location', '').strip()
            if not name:
                return {'success': False, 'error': 'Table name required'}
            cursor.execute("""
                INSERT INTO tables (name, location, status)
                VALUES (?, ?, 'empty')
            """, (name, location))
        
        elif action == 'update_table':
            table_id = data.get('table_id')
            name = data.get('name', '').strip()
            location = data.get('location', '').strip()
            if not name:
                return {'success': False, 'error': 'Table name required'}
            cursor.execute("""
                UPDATE tables SET name = ?, location = ?
                WHERE id = ?
            """, (name, location, table_id))
        
        elif action == 'delete_table':
            table_id = data.get('table_id')
            cursor.execute("DELETE FROM tables WHERE id = ?", (table_id,))
        
        elif action == 'set_pricing':
            start_hour = data.get('start_hour')
            end_hour = data.get('end_hour')
            price_per_hour = data.get('price_per_hour')
            if not all([start_hour is not None, end_hour is not None, price_per_hour is not None]):
                return {'success': False, 'error': 'Invalid pricing data'}
            if price_per_hour <= 0:
                return {'success': False, 'error': 'Price must be > 0'}
            cursor.execute("""
                INSERT INTO pricing_config (start_hour, end_hour, price_per_hour)
                VALUES (?, ?, ?)
            """, (start_hour, end_hour, price_per_hour))
        
        else:
            return {'success': False, 'error': 'Unknown action'}
        
        conn.commit()
        return {'success': True, 'message': f'{action} completed'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def get_revenue_report(start_date, end_date):
    """Get revenue report for date range."""
    conn = get_conn()
    if not conn:
        return {'total_revenue': 0, 'revenue_by_table': {}, 'revenue_by_day': {}}
    
    try:
        cursor = conn.cursor()
        
        # Total revenue
        cursor.execute("""
            SELECT COALESCE(SUM(
                (julianday(s.end_time) - julianday(s.start_time)) * 24 * p.price_per_hour
                + COALESCE(oi.total, 0)
            ), 0)
            FROM sessions s
            LEFT JOIN pricing_config p ON p.start_hour <= ? AND p.end_hour > ?
            LEFT JOIN (
                SELECT session_id, SUM(quantity * unit_price) as total
                FROM order_items GROUP BY session_id
            ) oi ON oi.session_id = s.id
            WHERE s.status = 'closed'
            AND DATE(s.end_time) BETWEEN ? AND ?
        """, (datetime.now().hour, datetime.now().hour, start_date, end_date))
        
        total_revenue = cursor.fetchone()[0] or 0
        
        # Revenue by table
        cursor.execute("""
            SELECT t.name, SUM(
                (julianday(s.end_time) - julianday(s.start_time)) * 24 * p.price_per_hour
                + COALESCE(oi.total, 0)
            ) as revenue
            FROM sessions s
            JOIN tables t ON t.id = s.table_id
            LEFT JOIN pricing_config p ON p.start_hour <= ? AND p.end_hour > ?
            LEFT JOIN (
                SELECT session_id, SUM(quantity * unit_price) as total
                FROM order_items GROUP BY session_id
            ) oi ON oi.session_id = s.id
            WHERE s.status = 'closed'
            AND DATE(s.end_time) BETWEEN ? AND ?
            GROUP BY t.id
        """, (datetime.now().hour, datetime.now().hour, start_date, end_date))
        
        revenue_by_table = {row[0]: round(row[1], 2) for row in cursor.fetchall()}
        
        # Revenue by day
        cursor.execute("""
            SELECT DATE(s.end_time), SUM(
                (julianday(s.end_time) - julianday(s.start_time)) * 24 * p.price_per_hour
                + COALESCE(oi.total, 0)
            )
            FROM sessions s
            LEFT JOIN pricing_config p ON p.start_hour <= ? AND p.end_hour > ?
            LEFT JOIN (
                SELECT session_id, SUM(quantity * unit_price) as total
                FROM order_items GROUP BY session_id
            ) oi ON oi.session_id = s.id
            WHERE s.status = 'closed'
            AND DATE(s.end_time) BETWEEN ? AND ?
            GROUP BY DATE(s.end_time)
        """, (datetime.now().hour, datetime.now().hour, start_date, end_date))
        
        revenue_by_day = {row[0]: round(row[1], 2) for row in cursor.fetchall()}
        
        conn.close()
        return {
            'total_revenue': round(total_revenue, 2),
            'revenue_by_table': revenue_by_table,
            'revenue_by_day': revenue_by_day
        }
    except Exception as e:
        print(f"Error in revenue report: {e}")
        return {'total_revenue': 0, 'revenue_by_table': {}, 'revenue_by_day': {}}
