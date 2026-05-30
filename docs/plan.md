# Kế hoạch kiến trúc

> Sinh tự động bởi **PlanningAgent**.

## `workspace/backend/db.py`

- `get_conn` — Tạo hoặc lấy kết nối SQLite. Tham số: Không. Trả về: sqlite3.Connection object.
- `init_db` — Khởi tạo cơ sở dữ liệu bằng cách gọi create_billiard_tables_table() và create_table_sessions_table(). Tham số: Không. Trả về: Không.
- `create_billiard_tables_table` — Tạo bảng billiard_tables với cột: id (PK), table_name (TEXT), status (TEXT: 'available'/'occupied'), price_per_hour (REAL). Tham số: conn (sqlite3.Connection). Trả về: Không.
- `create_table_sessions_table` — Tạo bảng table_sessions với cột: id (PK), table_id (INTEGER FK → billiard_tables.id), start_time (DATETIME), end_time (DATETIME nullable), total_charge (REAL). Tham số: conn (sqlite3.Connection). Trả về: Không.
- `validate_price` — Kiểm tra giá bàn có hợp lệ (phải > 0). Tham số: price_per_hour (float). Trả về: True nếu hợp lệ, raise ValueError nếu price <= 0.
- `check_table_available` — Kiểm tra bàn có sẵn sàng (status='available') hay đang bận (status='occupied'). Tham số: table_id (int). Trả về: True nếu trống, raise Exception nếu đang occupied hoặc table không tồn tại.

## `workspace/backend/app.py`

- `login` — Xác thực người dùng (staff hoặc admin) dựa username/password. Lưu role vào session. Tham số: username (str), password (str). Trả về: session_token (str) hoặc raise Exception nếu thất bại.
- `open_table` — Nhân viên mở bàn: kiểm tra trống (gọi db.check_table_available), tạo record mới trong table_sessions (start_time=now, end_time=NULL), cập nhật status bàn→'occupied'. Tham số: table_id (int). Trả về: session_id (int), raise Exception nếu bàn occupied.
- `calculate_current_charge` — Tính tiền tạm thời cho session đang mở: lấy start_time từ record, tính duration = (now - start_time) / 3600 giờ, tính charge = duration * price_per_hour (lấy giá từ bảng billiard_tables). Tham số: session_id (int). Trả về: current_charge (float).
- `close_table` — Đóng bàn & thanh toán: ghi nhận end_time=now, tính total_charge cuối cùng, lưu vào bảng table_sessions, cập nhật status bàn→'available'. Tham số: session_id (int). Trả về: invoice (dict) = {table_name: str, duration_hours: float, total_charge: float}.
- `get_revenue_report` — Admin xem báo cáo doanh thu: query table_sessions có end_time nằm trong [start_date, end_date], tính tổng tiền, đếm số session, tính trung bình. Tham số: start_date (date), end_date (date). Trả về: report (dict) = {total_revenue: float, session_count: int, avg_charge_per_session: float}.
- `add_billiard_table` — Admin thêm bàn bida mới: gọi db.validate_price(price_per_hour), insert vào bảng billiard_tables (status='available'). Tham số: table_name (str), price_per_hour (float). Trả về: table_id (int), raise Exception nếu giá không hợp lệ.
- `configure_table_price` — Admin cấu hình/cập nhật giá bàn: gọi db.validate_price(new_price_per_hour), update bảng billiard_tables set price_per_hour. Tham số: table_id (int), new_price_per_hour (float). Trả về: True nếu thành công, raise Exception nếu giá không hợp lệ hoặc table_id không tồn tại.

