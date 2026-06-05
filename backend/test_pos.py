import os
import tempfile
import pytest
from datetime import datetime, timedelta

_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
_temp_db_path = _temp_file.name
_temp_file.close()
os.environ["POS_DB"] = _temp_db_path

import db
import billiard
from app import app


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(_temp_db_path):
        os.remove(_temp_db_path)
    db.init_db()
    yield
    if os.path.exists(_temp_db_path):
        os.remove(_temp_db_path)


def test_db_get_conn():
    conn = db.get_conn()
    assert conn is not None
    conn.close()


def test_db_init_db():
    result = db.init_db()
    assert result is True


def test_open_session_success():
    billiard.configure_system('add_table', {'name': 'Table 1', 'location': 'Area 1'})
    
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tables WHERE name = 'Table 1'")
    table_id = cursor.fetchone()[0]
    conn.close()
    
    result = billiard.open_session(table_id, 'John Doe')
    assert isinstance(result, int)
    assert result > 0


def test_open_session_table_not_found():
    result = billiard.open_session(999, 'John Doe')
    assert isinstance(result, dict)
    assert 'error' in result


def test_add_service_success():
    billiard.configure_system('add_table', {'name': 'Table 1', 'location': 'Area 1'})
    
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tables LIMIT 1")
    table_id = cursor.fetchone()[0]
    cursor.execute("INSERT INTO services (name, price) VALUES ('Coffee', 25000)")
    cursor.execute("SELECT last_insert_rowid()")
    service_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    session_id = billiard.open_session(table_id, 'Jane Doe')
    result = billiard.add_service(session_id, service_id, 2)
    
    assert isinstance(result, float)
    assert result == 50000.0


def test_add_service_invalid_session():
    result = billiard.add_service(999, 1, 1)
    assert isinstance(result, dict)
    assert 'error' in result


def test_close_session_success():
    billiard.configure_system('add_table', {'name': 'Table 1', 'location': 'Area 1'})
    billiard.configure_system('set_pricing', {'start_hour': 0, 'end_hour': 24, 'price_per_hour': 50000})
    
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tables LIMIT 1")
    table_id = cursor.fetchone()[0]
    conn.close()
    
    session_id = billiard.open_session(table_id, 'John Doe')
    result = billiard.close_session(session_id)
    
    assert isinstance(result, dict)
    assert 'error' not in result
    assert 'total_amount' in result


def test_close_session_invalid():
    result = billiard.close_session(999)
    assert isinstance(result, dict)
    assert 'error' in result


def test_configure_system_add_table_success():
    result = billiard.configure_system('add_table', {'name': 'Table X', 'location': 'Lounge'})
    assert result['success'] is True


def test_configure_system_add_table_invalid():
    result = billiard.configure_system('add_table', {'name': '', 'location': 'Lounge'})
    assert result['success'] is False
    assert 'error' in result


def test_configure_system_set_pricing_success():
    result = billiard.configure_system('set_pricing', {
        'start_hour': 9,
        'end_hour': 17,
        'price_per_hour': 100000
    })
    assert result['success'] is True


def test_configure_system_set_pricing_invalid():
    result = billiard.configure_system('set_pricing', {
        'start_hour': 9,
        'end_hour': 17,
        'price_per_hour': -100
    })
    assert result['success'] is False
    assert 'error' in result


def test_get_revenue_report():
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    report = billiard.get_revenue_report(start_date, end_date)
    
    assert isinstance(report, dict)
    assert 'total_revenue' in report
    assert 'revenue_by_table' in report
    assert 'revenue_by_day' in report


def test_flask_app_login_get():
    client = app.test_client()
    response = client.get('/login')
    assert response.status_code == 200


def test_flask_app_login_valid_credentials():
    client = app.test_client()
    response = client.post('/login', data={
        'username': 'staff',
        'password': 'pass'
    }, follow_redirects=False)
    assert response.status_code == 302
