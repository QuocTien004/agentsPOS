import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, session, request, flash

# Import db module (same directory)
import db

# Initialize Flask app with correct template & static paths
app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
)
app.secret_key = "agentspos-demo"

# Initialize database
db.init_db()

# ============================================================================
# BUSINESS LOGIC FUNCTIONS
# ============================================================================

def login(username, password):
    """
    Authenticate user (staff or admin) by username/password.
    Returns session_token (str) if success, raises Exception if failed.
    
    Demo credentials:
      staff / pass123 → staff role
      admin / admin123 → admin role
    """
    users = {
        "staff": ("pass123", "staff"),
        "admin": ("admin123", "admin"),
    }
    
    if username not in users:
        raise Exception(f"User '{username}' not found")
    
    expected_password, role = users[username]
    if password != expected_password:
        raise Exception("Invalid password")
    
    session_token = f"{username}_{datetime.now().timestamp()}"
    return session_token


def open_table(table_id):
    """
    Staff opens a table: check if available, create session record.
    Returns: session_id (int), raises Exception if table occupied.
    Implements [POS-3]
    """
    db.check_table_available(table_id)
    
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO table_sessions (table_id, start_time, end_time, total_charge)
            VALUES (?, ?, NULL, NULL)
            """,
            (table_id, now)
        )
        session_id = cursor.lastrowid
        
        cursor.execute(
            "UPDATE billiard_tables SET status = 'occupied' WHERE id = ?",
            (table_id,)
        )
        
        conn.commit()
        return session_id
    finally:
        if conn:
            conn.close()


def calculate_current_charge(session_id):
    """
    Calculate current charge for an open session.
    Returns: current_charge (float)
    Implements [POS-4]
    """
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT ts.start_time, bt.price_per_hour
            FROM table_sessions ts
            JOIN billiard_tables bt ON ts.table_id = bt.id
            WHERE ts.id = ?
            """,
            (session_id,)
        )
        result = cursor.fetchone()
        
        if result is None:
            raise Exception(f"Session {session_id} not found")
        
        start_time_str, price_per_hour = result
        start_time = datetime.fromisoformat(start_time_str)
        now = datetime.now()
        
        duration_hours = (now - start_time).total_seconds() / 3600
        current_charge = duration_hours * price_per_hour
        
        return round(current_charge, 2)
    finally:
        if conn:
            conn.close()


def close_table(session_id):
    """
    Close table and settle payment.
    Returns: invoice (dict) with {table_name, duration_hours, total_charge}
    Implements [POS-5]
    """
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT ts.table_id, ts.start_time, bt.table_name, bt.price_per_hour
            FROM table_sessions ts
            JOIN billiard_tables bt ON ts.table_id = bt.id
            WHERE ts.id = ?
            """,
            (session_id,)
        )
        result = cursor.fetchone()
        
        if result is None:
            raise Exception(f"Session {session_id} not found")
        
        table_id, start_time_str, table_name, price_per_hour = result
        start_time = datetime.fromisoformat(start_time_str)
        now = datetime.now()
        
        duration_hours = (now - start_time).total_seconds() / 3600
        total_charge = round(duration_hours * price_per_hour, 2)
        
        now_iso = now.isoformat()
        cursor.execute(
            """
            UPDATE table_sessions
            SET end_time = ?, total_charge = ?
            WHERE id = ?
            """,
            (now_iso, total_charge, session_id)
        )
        
        cursor.execute(
            "UPDATE billiard_tables SET status = 'available' WHERE id = ?",
            (table_id,)
        )
        
        conn.commit()
        
        return {
            "table_name": table_name,
            "duration_hours": round(duration_hours, 2),
            "total_charge": total_charge,
        }
    finally:
        if conn:
            conn.close()


def get_revenue_report(start_date, end_date):
    """
    Get revenue report: query sessions in [start_date, end_date].
    Returns: {total_revenue, session_count, avg_charge_per_session}
    Implements [POS-6]
    """
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT COUNT(*), SUM(total_charge)
            FROM table_sessions
            WHERE end_time IS NOT NULL
              AND DATE(end_time) >= ? AND DATE(end_time) <= ?
            """,
            (start_date, end_date)
        )
        result = cursor.fetchone()
        session_count = result[0] if result[0] else 0
        total_revenue = result[1] if result[1] else 0.0
        
        avg_charge = total_revenue / session_count if session_count > 0 else 0.0
        
        return {
            "total_revenue": round(total_revenue, 2),
            "session_count": session_count,
            "avg_charge_per_session": round(avg_charge, 2),
        }
    finally:
        if conn:
            conn.close()


def add_billiard_table(table_name, price_per_hour):
    """
    Admin adds a new billiard table.
    Returns: table_id (int), raises Exception if price invalid.
    Implements [POS-10]
    """
    db.validate_price(price_per_hour)
    
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO billiard_tables (table_name, status, price_per_hour)
            VALUES (?, 'available', ?)
            """,
            (table_name, price_per_hour)
        )
        table_id = cursor.lastrowid
        conn.commit()
        return table_id
    finally:
        if conn:
            conn.close()


def configure_table_price(table_id, new_price_per_hour):
    """
    Admin configures/updates table price.
    Returns: True if success, raises Exception if price invalid or table not found.
    Implements [POS-7]
    """
    db.validate_price(new_price_per_hour)
    
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM billiard_tables WHERE id = ?", (table_id,))
        if cursor.fetchone() is None:
            raise Exception(f"Table {table_id} not found")
        
        cursor.execute(
            "UPDATE billiard_tables SET price_per_hour = ? WHERE id = ?",
            (new_price_per_hour, table_id)
        )
        conn.commit()
        return True
    finally:
        if conn:
            conn.close()


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route("/")
def index():
    """Home: redirect to login or dashboard based on session."""
    if "user" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("tables"))
    return redirect(url_for("login_route"))


@app.route("/login", methods=["GET", "POST"])
def login_route():
    """Login page and handler."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        try:
            session_token = login(username, password)
            session["user"] = username
            
            if username == "admin":
                session["role"] = "admin"
                return redirect(url_for("admin_dashboard"))
            else:
                session["role"] = "staff"
                return redirect(url_for("tables"))
        except Exception as e:
            flash(f"Login failed: {str(e)}", "error")
    
    return render_template("login.html")


@app.route("/logout")
def logout_route():
    """Logout: clear session and redirect to login."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login_route"))


@app.route("/tables", methods=["GET"])
def tables():
    """Staff: view all billiard tables and their status."""
    if "user" not in session:
        return redirect(url_for("login_route"))
    
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, table_name, status, price_per_hour FROM billiard_tables ORDER BY id"
        )
        tables_list = [
            {
                "id": row[0],
                "table_name": row[1],
                "status": row[2],
                "price_per_hour": row[3],
            }
            for row in cursor.fetchall()
        ]
    finally:
        if conn:
            conn.close()
    
    return render_template(
        "tables.html",
        username=session.get("user"),
        tables=tables_list,
    )


@app.route("/tables/<int:table_id>/open", methods=["POST"])
def open_table_route(table_id):
    """Staff: open a table (create session)."""
    if "user" not in session:
        return redirect(url_for("login_route"))
    
    try:
        session_id = open_table(table_id)
        flash(f"Table opened successfully.", "success")
        return redirect(url_for("session_view", session_id=session_id))
    except Exception as e:
        flash(f"Failed to open table: {str(e)}", "error")
        return redirect(url_for("tables"))


@app.route("/session/<int:session_id>", methods=["GET"])
def session_view(session_id):
    """View current session details and calculate current charge."""
    if "user" not in session:
        return redirect(url_for("login_route"))
    
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT ts.id, ts.table_id, ts.start_time, bt.table_name, bt.price_per_hour
            FROM table_sessions ts
            JOIN billiard_tables bt ON ts.table_id = bt.id
            WHERE ts.id = ? AND ts.end_time IS NULL
            """,
            (session_id,)
        )
        result = cursor.fetchone()
        
        if result is None:
            flash("Session not found or already closed.", "error")
            return redirect(url_for("tables"))
        
        session_id_db, table_id, start_time_str, table_name, price_per_hour = result
        
        current_charge = calculate_current_charge(session_id)
        start_time = datetime.fromisoformat(start_time_str)
        duration_mins = int((datetime.now() - start_time).total_seconds() / 60)
        
        return render_template(
            "session.html",
            username=session.get("user"),
            session_id=session_id,
            table_name=table_name,
            table_id=table_id,
            start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
            price_per_hour=price_per_hour,
            duration_mins=duration_mins,
            current_charge=current_charge,
        )
    finally:
        if conn:
            conn.close()


@app.route("/session/<int:session_id>/close", methods=["POST"])
def close_table_route(session_id):
    """Staff: close table and settle payment."""
    if "user" not in session:
        return redirect(url_for("login_route"))
    
    try:
        invoice = close_table(session_id)
        flash(
            f"Table '{invoice['table_name']}' closed. Duration: {invoice['duration_hours']}h, Total: ${invoice['total_charge']:.2f}",
            "success",
        )
        return redirect(url_for("tables"))
    except Exception as e:
        flash(f"Failed to close table: {str(e)}", "error")
        return redirect(url_for("session_view", session_id=session_id))


@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    """Admin: main dashboard with overview."""
    if "user" not in session or session.get("role") != "admin":
        flash("Access denied. Admin role required.", "error")
        return redirect(url_for("login_route"))
    
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM billiard_tables")
        table_count = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM billiard_tables WHERE status = 'occupied'"
        )
        occupied_count = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT SUM(total_charge) FROM table_sessions WHERE end_time IS NOT NULL"
        )
        result = cursor.fetchone()
        total_revenue = result[0] if result[0] else 0.0
        
        cursor.execute(
            """
            SELECT ts.id, bt.table_name, ts.start_time, ts.end_time, ts.total_charge
            FROM table_sessions ts
            JOIN billiard_tables bt ON ts.table_id = bt.id
            WHERE ts.end_time IS NOT NULL
            ORDER BY ts.end_time DESC
            LIMIT 5
            """
        )
        recent_sessions = [
            {
                "id": row[0],
                "table_name": row[1],
                "start_time": row[2],
                "end_time": row[3],
                "total_charge": row[4],
            }
            for row in cursor.fetchall()
        ]
    finally:
        if conn:
            conn.close()
    
    return render_template(
        "admin_dashboard.html",
        username=session.get("user"),
        table_count=table_count,
        occupied_count=occupied_count,
        total_revenue=round(total_revenue, 2),
        recent_sessions=recent_sessions,
    )


@app.route("/admin/revenue", methods=["GET"])
def admin_revenue():
    """Admin: revenue report."""
    if "user" not in session or session.get("role") != "admin":
        flash("Access denied. Admin role required.", "error")
        return redirect(url_for("login_route"))
    
    today = datetime.now().date()
    start_date = request.args.get("start_date", str(today - timedelta(days=30)))
    end_date = request.args.get("end_date", str(today))
    
    try:
        report = get_revenue_report(start_date, end_date)
    except Exception as e:
        flash(f"Error generating report: {str(e)}", "error")
        report = {
            "total_revenue": 0.0,
            "session_count": 0,
            "avg_charge_per_session": 0.0,
        }
    
    return render_template(
        "admin_revenue.html",
        username=session.get("user"),
        start_date=start_date,
        end_date=end_date,
        report=report,
    )


@app.route("/admin/tables", methods=["GET", "POST"])
def admin_tables():
    """Admin: manage tables (view, add)."""
    if "user" not in session or session.get("role") != "admin":
        flash("Access denied. Admin role required.", "error")
        return redirect(url_for("login_route"))
    
    if request.method == "POST":
        table_name = request.form.get("table_name", "").strip()
        try:
            price_str = request.form.get("price_per_hour", "").strip()
            price_per_hour = float(price_str)
        except ValueError:
            flash("Price must be a valid number.", "error")
            return redirect(url_for("admin_tables"))
        
        if not table_name:
            flash("Table name is required.", "error")
            return redirect(url_for("admin_tables"))
        
        try:
            table_id = add_billiard_table(table_name, price_per_hour)
            flash(f"Table '{table_name}' added successfully.", "success")
            return redirect(url_for("admin_tables"))
        except Exception as e:
            flash(f"Failed to add table: {str(e)}", "error")
    
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, table_name, status, price_per_hour FROM billiard_tables ORDER BY id"
        )
        tables_list = [
            {
                "id": row[0],
                "table_name": row[1],
                "status": row[2],
                "price_per_hour": row[3],
            }
            for row in cursor.fetchall()
        ]
    finally:
        if conn:
            conn.close()
    
    return render_template(
        "admin_tables.html",
        username=session.get("user"),
        tables=tables_list,
    )


@app.route("/admin/tables/<int:table_id>/edit", methods=["GET", "POST"])
def edit_table_price(table_id):
    """Admin: edit table price."""
    if "user" not in session or session.get("role") != "admin":
        flash("Access denied. Admin role required.", "error")
        return redirect(url_for("login_route"))
    
    conn = None
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, table_name, price_per_hour FROM billiard_tables WHERE id = ?",
            (table_id,)
        )
        result = cursor.fetchone()
        
        if result is None:
            flash(f"Table {table_id} not found.", "error")
            return redirect(url_for("admin_tables"))
        
        table_id_db, table_name, current_price = result
    finally:
        if conn:
            conn.close()
    
    if request.method == "POST":
        try:
            new_price_str = request.form.get("price_per_hour", "").strip()
            new_price = float(new_price_str)
        except ValueError:
            flash("Price must be a valid number.", "error")
            return redirect(url_for("edit_table_price", table_id=table_id))
        
        try:
            configure_table_price(table_id, new_price)
            flash(f"Table '{table_name}' price updated to ${new_price:.2f}.", "success")
            return redirect(url_for("admin_tables"))
        except Exception as e:
            flash(f"Failed to update price: {str(e)}", "error")
    
    return render_template(
        "admin_tables.html",
        username=session.get("user"),
        tables=[],
        edit_mode=True,
        edit_table_id=table_id,
        table_name=table_name,
        current_price=current_price,
    )


if __name__ == "__main__":
    app.run(port=5000, debug=True)
