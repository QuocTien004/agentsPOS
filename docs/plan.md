# Kế hoạch kiến trúc

> Sinh tự động bởi **PlanningAgent**.

## `workspace/backend/db.py`

- `get_conn` — Lấy kết nối đến cơ sở dữ liệu SQLite. Input: none. Output: sqlite3.Connection object hoặc None nếu lỗi.
- `init_db` — Khởi tạo tất cả bảng (tables, sessions, pricing_config) bằng cách gọi các hàm init_*_table(). Input: none. Output: boolean success.
- `init_tables_table` — Tạo bảng 'tables' với cột: id (INTEGER PRIMARY KEY), name (TEXT), location (TEXT), status (TEXT: trống/đang dùng/bảo trì), created_at (TIMESTAMP). Input: none. Output: boolean success.
- `init_sessions_table` — Tạo bảng 'sessions' với cột: id (INTEGER PRIMARY KEY), table_id (INTEGER FOREIGN KEY), customer_name (TEXT), start_time (TIMESTAMP), end_time (TIMESTAMP NULL), status (TEXT: mở/đóng), created_at (TIMESTAMP). Input: none. Output: boolean success.
- `init_pricing_table` — Tạo bảng 'pricing_config' với cột: id (INTEGER PRIMARY KEY), start_hour (INTEGER), end_hour (INTEGER), price_per_hour (REAL), created_at (TIMESTAMP). Input: none. Output: boolean success.

## `workspace/backend/app.py`

- `open_session` — Mở session cho bàn bi-a. Input: table_id (int), customer_name (str). Logic: kiểm tra trạng thái bàn (phải trống), tạo record session mới (status=mở), cập nhật status bàn thành 'đang dùng'. Output: session_id (int) nếu thành công, hoặc dict {'error': message} nếu lỗi.
- `close_session` — Đóng session và tính tổng tiền. Input: session_id (int). Logic: tính end_time, tính total_hours từ start_time-end_time, truy vấn pricing_config để lấy price_per_hour theo khung giờ, tính total_amount, cập nhật session (status=đóng, end_time), cập nhật bàn (status=trống). Output: dict {'session_id': int, 'table_id': int, 'total_hours': float, 'price_per_hour': float, 'total_amount': float}.
- `add_service` — Thêm dịch vụ phụ vào session (thêm order_item). Input: session_id (int), service_id (int), quantity (int). Logic: validate session tồn tại và status=mở, thêm order_item (session_id, service_id, quantity, giá), tính order_total = tổng tiền service cho session này. Output: order_total (float) nếu thành công, hoặc dict {'error': message} nếu lỗi.
- `configure_system` — Cấu hình hệ thống quản lý bàn và giá. Input: action (str: 'add_table'|'update_table'|'delete_table'|'set_pricing'), data (dict). Logic: validate dữ liệu (giá > 0, table_id hợp lệ), thực hiện action tương ứng (INSERT/UPDATE/DELETE). Output: dict {'success': true, 'message': str} hoặc {'success': false, 'error': str}.
- `get_revenue_report` — Lấy báo cáo doanh thu theo khoảng thời gian. Input: start_date (str: YYYY-MM-DD), end_date (str: YYYY-MM-DD). Logic: truy vấn tất cả sessions đóng trong khoảng [start_date, end_date], tính total_revenue, tính revenue_by_table {table_id: tổng_tiền}, tính revenue_by_day {ngày: tổng_tiền}. Output: dict {'total_revenue': float, 'revenue_by_table': {}, 'revenue_by_day': {}}.
- `validate_action` — Validate điều kiện trước mở/đóng session. Input: table_id hoặc session_id (int), action (str: 'open'|'close'). Logic: nếu action='open' thì check table_id tồn tại và status=trống, nếu action='close' thì check session_id tồn tại và status=mở. Output: tuple (is_valid: bool, error_message: str) — nếu hợp lệ thì ('', '')*True, nếu không thì (False, 'reason').

