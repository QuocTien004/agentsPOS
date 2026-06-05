# Billiard Hall POS

Hệ thống quản lý và tính tiền tự động cho phòng chơi billiard.

## Tính năng

- Quản lý bàn chơi với trạng thái (trống/đang dùng) và vị trí
- Mở/đóng session chơi theo bàn, theo dõi khách hàng
- Cấu hình giá theo khung giờ (peak/off-peak)
- Tính tiền tự động dựa trên thời gian chơi thực tế
- Thêm dịch vụ phụ (ăn vặt, nước, etc.) vào session
- Validate điều kiện trước khi mở/đóng session
- Báo cáo doanh thu chi tiết theo thời gian
- Quản lý cấu hình bàn và giá theo yêu cầu

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
cd billiard-pos
cp .env.example .env
pip install -r requirements.txt
cd backend
python app.py
```

## Test

```bash
cd backend
pytest -q
```

## License

MIT
