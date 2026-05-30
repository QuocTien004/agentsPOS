# Billiards POS
Hệ thống quản lý và thanh toán cho phòng bida với theo dõi giờ chơi bàn.

## Tính năng
- Quản lý bàn bida: Tạo, cấu hình giá và theo dõi trạng thái của từng bàn
- Mở bàn chơi: Nhân viên khởi động session chơi trên bàn
- Tính tiền tạm thời: Hiển thị chi phí hiện tại dựa trên thời gian chơi
- Thanh toán bàn: Đóng session, tính tiền cuối cùng, in hóa đơn
- Báo cáo doanh thu: Thống kê tổng tiền, số session, giá trung bình trong khoảng thời gian
- Cấu hình giá động: Admin thay đổi giá bàn theo giờ
- Kiểm tra sẵn sàng: Xác định bàn có sẵn sàng hay đang bận
- Quản lý bàn mới: Admin thêm bàn bida vào hệ thống
- Validate dữ liệu: Đảm bảo giá bàn hợp lệ và dương
- Theo dõi lịch sử: Lưu trữ đầy đủ dữ liệu session để báo cáo

## Công nghệ
- Python 3.10+
- Flask 3.x
- SQLite

## Cấu trúc thư mục
```
backend/        # Python: db.py, app.py, test_pos.py
frontend/       # HTML templates + CSS
```

## Cài đặt và chạy
```bash
git clone <repo-url>
cd <repo>
cp .env.example .env
pip install -r requirements.txt
cd backend
python app.py              # http://127.0.0.1:5000
```

## Test
```bash
cd backend
pytest -q
```

## License
MIT
