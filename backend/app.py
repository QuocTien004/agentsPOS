import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, session, redirect, url_for, flash

from billiard import (
    open_session,
    close_session,
    add_service,
    configure_system,
    get_revenue_report,
)
from db import get_conn, init_db

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
)
app.secret_key = "agentspos-demo"

DEMO_USERS = {
    "staff": {"password": "pass", "role": "staff"},
    "admin": {"password": "pass", "role": "admin"},
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            flash("Please log in", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session or session["user"]["role"] != "admin":
            flash("Admin only", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("tables"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        if username in DEMO_USERS and DEMO_USERS[username]["password"] == password:
            session["user"] = {"username": username, "role": DEMO_USERS[username]["role"]}
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for("tables"))
        
        flash("Invalid credentials", "danger")
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out", "info")
    return redirect(url_for("login"))


@app.route("/tables", methods=["GET", "POST"])
@login_required
def tables():
    conn = get_conn()
    if not conn:
        flash("DB error", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST" and session["user"]["role"] == "admin":
        action = request.form.get("action", "").strip()
        if action == "add_table":
            table_name = request.form.get("table_name", "").strip()
            location = request.form.get("location", "").strip()
            result = configure_system("add_table", {"name": table_name, "location": location})
            if result.get("success"):
                flash(f"Table {table_name} added", "success")
            else:
                flash(f"Error: {result.get('error')}", "danger")
            return redirect(url_for("tables"))
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, location, status FROM tables ORDER BY id")
    tables_list = [dict(zip(["id", "name", "location", "status"], row)) for row in cursor.fetchall()]
    conn.close()
    
    return render_template("tables.html", tables=tables_list, user=session["user"])


@app.route("/session/open", methods=["GET", "POST"])
@login_required
def session_open():
    conn = get_conn()
    if not conn:
        flash("DB error", "danger")
        return redirect(url_for("tables"))
    
    if request.method == "POST":
        table_id = request.form.get("table_id", "").strip()
        customer_name = request.form.get("customer_name", "").strip()
        
        if table_id and customer_name:
            try:
                result = open_session(int(table_id), customer_name)
                if isinstance(result, dict) and "error" in result:
                    flash(f"Error: {result['error']}", "danger")
                else:
                    flash(f"Session {result} opened", "success")
                    return redirect(url_for("session_detail", session_id=result))
            except (ValueError, TypeError):
                flash("Invalid input", "danger")
        else:
            flash("Fill all fields", "danger")
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, location FROM tables WHERE status = 'empty' ORDER BY id")
    available = [dict(zip(["id", "name", "location"], row)) for row in cursor.fetchall()]
    conn.close()
    
    return render_template("session_open.html", available=available, user=session["user"])


@app.route("/session/<int:session_id>", methods=["GET"])
@login_required
def session_detail(session_id):
    conn = get_conn()
    if not conn:
        flash("DB error", "danger")
        return redirect(url_for("tables"))
    
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.id, s.table_id, s.customer_name, s.start_time, t.name
        FROM sessions s JOIN tables t ON s.table_id = t.id
        WHERE s.id = ? AND s.status = 'open'
    """, (session_id,))
    row = cursor.fetchone()
    
    if not row:
        flash("Session not found", "danger")
        conn.close()
        return redirect(url_for("tables"))
    
    session_info = dict(zip(["id", "table_id", "customer_name", "start_time", "table_name"], row))
    
    cursor.execute("SELECT id, service_id, quantity, unit_price FROM order_items WHERE session_id = ?", (session_id,))
    services = [dict(zip(["id", "service_id", "quantity", "unit_price"], r)) for r in cursor.fetchall()]
    
    total = sum(s["quantity"] * s["unit_price"] for s in services)
    
    cursor.execute("SELECT id, name, price FROM services ORDER BY name")
    available_services = [dict(zip(["id", "name", "price"], r)) for r in cursor.fetchall()]
    
    conn.close()
    
    return render_template(
        "session_detail.html",
        session=session_info,
        services=services,
        available_services=available_services,
        total=total,
        user=session["user"],
    )


@app.route("/session/<int:session_id>/service", methods=["POST"])
@login_required
def add_service_to_session(session_id):
    service_id = request.form.get("service_id", "").strip()
    quantity = request.form.get("quantity", "").strip()
    
    if service_id and quantity:
        try:
            result = add_service(session_id, int(service_id), int(quantity))
            if isinstance(result, dict) and "error" in result:
                flash(f"Error: {result['error']}", "danger")
            else:
                flash(f"Service added, total: {result:.2f}", "success")
        except (ValueError, TypeError):
            flash("Invalid input", "danger")
    else:
        flash("Fill all fields", "danger")
    
    return redirect(url_for("session_detail", session_id=session_id))


@app.route("/session/<int:session_id>/close", methods=["GET", "POST"])
@login_required
def session_close(session_id):
    conn = get_conn()
    if not conn:
        flash("DB error", "danger")
        return redirect(url_for("tables"))
    
    if request.method == "POST":
        result = close_session(session_id)
        if isinstance(result, dict) and "error" not in result:
            flash(f"Session closed. Total: {result['total_amount']:.2f}", "success")
            return redirect(url_for("tables"))
        else:
            flash(f"Error: {result.get('error', 'Unknown')}", "danger")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.table_id, s.customer_name, s.start_time, t.name
        FROM sessions s JOIN tables t ON s.table_id = t.id
        WHERE s.id = ? AND s.status = 'open'
    """, (session_id,))
    row = cursor.fetchone()
    
    if not row:
        flash("Session not found", "danger")
        conn.close()
        return redirect(url_for("tables"))
    
    session_info = dict(zip(["id", "table_id", "customer_name", "start_time", "table_name"], row))
    
    cursor.execute("""
        SELECT COALESCE(SUM(quantity * unit_price), 0) FROM order_items WHERE session_id = ?
    """, (session_id,))
    services_total = cursor.fetchone()[0]
    
    conn.close()
    
    now = datetime.now()
    start = datetime.fromisoformat(session_info["start_time"])
    hours = (now - start).total_seconds() / 3600
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT price_per_hour FROM pricing_config
        WHERE start_hour <= ? AND end_hour > ? LIMIT 1
    """, (now.hour, now.hour))
    pricing_row = cursor.fetchone()
    price_per_hour = pricing_row[0] if pricing_row else 50.0
    conn.close()
    
    total = hours * price_per_hour + services_total
    
    return render_template(
        "session_close.html",
        session=session_info,
        hours=round(hours, 2),
        price_per_hour=price_per_hour,
        services_total=round(services_total, 2),
        total=round(total, 2),
        user=session["user"],
    )


@app.route("/admin/pricing", methods=["GET", "POST"])
@admin_required
def admin_pricing():
    conn = get_conn()
    if not conn:
        flash("DB error", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        start_hour = request.form.get("start_hour", "").strip()
        end_hour = request.form.get("end_hour", "").strip()
        price_per_hour = request.form.get("price_per_hour", "").strip()
        
        if start_hour and end_hour and price_per_hour:
            try:
                result = configure_system("set_pricing", {
                    "start_hour": int(start_hour),
                    "end_hour": int(end_hour),
                    "price_per_hour": float(price_per_hour),
                })
                if result.get("success"):
                    flash("Pricing added", "success")
                else:
                    flash(f"Error: {result.get('error')}", "danger")
            except (ValueError, TypeError):
                flash("Invalid input", "danger")
        else:
            flash("Fill all fields", "danger")
        return redirect(url_for("admin_pricing"))
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, start_hour, end_hour, price_per_hour FROM pricing_config ORDER BY start_hour")
    pricing_list = [dict(zip(["id", "start_hour", "end_hour", "price_per_hour"], row)) for row in cursor.fetchall()]
    conn.close()
    
    return render_template("admin_pricing.html", pricing=pricing_list, user=session["user"])


@app.route("/admin/config", methods=["GET", "POST"])
@admin_required
def admin_config():
    conn = get_conn()
    if not conn:
        flash("DB error", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        action = request.form.get("action", "").strip()
        
        if action == "add_table":
            table_name = request.form.get("table_name", "").strip()
            location = request.form.get("location", "").strip()
            result = configure_system("add_table", {"name": table_name, "location": location})
            if result.get("success"):
                flash(f"Table {table_name} added", "success")
            else:
                flash(f"Error: {result.get('error')}", "danger")
        
        elif action == "delete_table":
            table_id = request.form.get("table_id", "").strip()
            try:
                result = configure_system("delete_table", {"table_id": int(table_id)})
                if result.get("success"):
                    flash("Table deleted", "success")
                else:
                    flash(f"Error: {result.get('error')}", "danger")
            except (ValueError, TypeError):
                flash("Invalid ID", "danger")
        
        return redirect(url_for("admin_config"))
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, location, status FROM tables ORDER BY id")
    tables_list = [dict(zip(["id", "name", "location", "status"], row)) for row in cursor.fetchall()]
    conn.close()
    
    return render_template("admin_config.html", tables=tables_list, user=session["user"])


@app.route("/admin/report", methods=["GET"])
@admin_required
def admin_report():
    end_date = request.args.get("end_date", "").strip() or datetime.now().strftime("%Y-%m-%d")
    start_date = request.args.get("start_date", "").strip() or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    report = get_revenue_report(start_date, end_date)
    
    return render_template(
        "admin_report.html",
        report=report,
        start_date=start_date,
        end_date=end_date,
        user=session["user"],
    )


if __name__ == "__main__":
    init_db()
    
    conn = get_conn()
    if conn:
        cursor = conn.cursor()
        
        # Demo data
        if cursor.execute("SELECT COUNT(*) FROM tables").fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO tables (name, location, status) VALUES
                ('Table 1', 'Pool Area', 'empty'),
                ('Table 2', 'Pool Area', 'empty'),
                ('Table 3', 'VIP Room', 'empty'),
                ('Table 4', 'VIP Room', 'empty')
            """)
        
        if cursor.execute("SELECT COUNT(*) FROM pricing_config").fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO pricing_config (start_hour, end_hour, price_per_hour) VALUES
                (6, 12, 50000),
                (12, 18, 70000),
                (18, 24, 100000),
                (0, 6, 40000)
            """)
        
        if cursor.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO services (name, price) VALUES
                ('Beer', 50000),
                ('Soft Drink', 25000),
                ('Snack', 75000),
                ('Cue Rental', 10000)
            """)
        
        conn.commit()
        conn.close()
    
    app.run(port=5000, debug=True)
