import os
import tempfile
import pytest
from datetime import datetime, timedelta

# CRITICAL: Set temp database BEFORE importing modules
temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
temp_db_path = temp_db_file.name
temp_db_file.close()
os.environ["POS_DB"] = temp_db_path

# Import modules after env setup
import db
import app


@pytest.fixture(autouse=True)
def clean_db():
    """Autouse fixture: clean and reinitialize database for each test."""
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except:
            pass
    db.init_db()
    yield


def test_login_valid_credentials():
    """Test login succeeds with valid staff credentials."""
    token = app.login("staff", "pass123")
    assert token is not None
    assert isinstance(token, str)
    assert "staff" in token


def test_login_invalid_password():
    """Test login raises on invalid password."""
    with pytest.raises(Exception, match="Invalid password"):
        app.login("staff", "wrongpassword")


def test_add_billiard_table_success():
    """Test successfully adding a billiard table."""
    table_id = app.add_billiard_table("Table 1", 20.0)
    assert isinstance(table_id, int)
    assert table_id > 0
    
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT table_name, price_per_hour FROM billiard_tables WHERE id = ?", (table_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == "Table 1"
    assert row[1] == 20.0


def test_add_billiard_table_invalid_price():
    """Test adding table raises on invalid price."""
    with pytest.raises(ValueError):
        app.add_billiard_table("Bad Table", 0)
    
    with pytest.raises(ValueError):
        app.add_billiard_table("Bad Table", -10.0)


def test_open_table_success():
    """Test successfully opening an available table."""
    table_id = app.add_billiard_table("Table 2", 25.0)
    
    session_id = app.open_table(table_id)
    assert isinstance(session_id, int)
    assert session_id > 0
    
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT table_id FROM table_sessions WHERE id = ?", (session_id,))
    assert cursor.fetchone() is not None
    cursor.execute("SELECT status FROM billiard_tables WHERE id = ?", (table_id,))
    assert cursor.fetchone()[0] == "occupied"
    conn.close()


def test_open_table_occupied():
    """Test opening table raises when already occupied."""
    table_id = app.add_billiard_table("Table 3", 25.0)
    app.open_table(table_id)
    
    with pytest.raises(Exception, match="occupied"):
        app.open_table(table_id)


def test_calculate_current_charge():
    """Test calculating current charge for an open session."""
    table_id = app.add_billiard_table("Table 4", 60.0)
    session_id = app.open_table(table_id)
    
    charge = app.calculate_current_charge(session_id)
    assert isinstance(charge, float)
    assert charge >= 0.0


def test_close_table():
    """Test closing a table and generating invoice."""
    table_id = app.add_billiard_table("Table 5", 60.0)
    session_id = app.open_table(table_id)
    
    invoice = app.close_table(session_id)
    
    assert isinstance(invoice, dict)
    assert invoice["table_name"] == "Table 5"
    assert invoice["duration_hours"] >= 0.0
    assert invoice["total_charge"] >= 0.0
    
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM billiard_tables WHERE id = ?", (table_id,))
    assert cursor.fetchone()[0] == "available"
    conn.close()


def test_get_revenue_report():
    """Test generating revenue report."""
    table_id = app.add_billiard_table("Table 6", 50.0)
    session_id = app.open_table(table_id)
    app.close_table(session_id)
    
    today = datetime.now().date()
    report = app.get_revenue_report(str(today), str(today))
    
    assert isinstance(report, dict)
    assert report["session_count"] == 1
    assert report["total_revenue"] >= 0.0
    assert report["avg_charge_per_session"] >= 0.0


def test_configure_table_price_invalid():
    """Test configure_table_price raises on invalid price."""
    table_id = app.add_billiard_table("Table 7", 15.0)
    
    with pytest.raises(ValueError):
        app.configure_table_price(table_id, 0)
