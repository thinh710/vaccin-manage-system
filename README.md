# Vaccin Manage System

Hệ thống quản lý tiêm chủng vắc xin gồm các module:
- người dùng và phân quyền
- booking lịch tiêm
- khám sàng lọc và tiêm chủng
- quản lý kho, nhà cung cấp, vị trí bảo quản

## Yêu cầu môi trường

### Chạy local bằng Python
- Python 3.13+ hoặc 3.14
- `pip`

Lưu ý:
- Trên Windows có thể dùng `py` thay cho `python`
- Nếu không cấu hình `.env`, dự án sẽ chạy với SQLite mặc định

### Chạy bằng Docker
- Docker Desktop
- Docker Compose

## Cách dựng bằng Python

### 1. Clone source
```bash
git clone <repo-url>
cd vaccin-manage-system
```

### 2. Tạo virtual environment

Windows:
```bash
py -m venv venv
venv\Scripts\activate
```

macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Cài dependencies
```bash
pip install -r requirements.txt
```

### 4. Chạy migrate

Windows:
```bash
py manage.py migrate
```

macOS / Linux:
```bash
python manage.py migrate
```

### 5. Chạy server

Windows:
```bash
py manage.py runserver
```

macOS / Linux:
```bash
python manage.py runserver
```

### 6. Truy cập hệ thống
- App: `http://localhost:8000`
- Django Admin: `http://localhost:8000/admin/`

## Cách dựng bằng Docker

### 1. Clone source
```bash
git clone <repo-url>
cd vaccin-manage-system
```

### 2. Build và chạy
```bash
docker compose up --build
```

Nếu muốn chạy nền:
```bash
docker compose up --build -d
```

### 3. Truy cập hệ thống
- App: `http://localhost:8000`
- Django Admin: `http://localhost:8000/admin/`

## Một số lệnh hữu ích

### Docker

Xem log:
```bash
docker compose logs -f
```

Dừng container:
```bash
docker compose down
```

Build lại sau khi pull code mới:
```bash
docker compose up --build
```

Vào shell Django trong container:
```bash
docker compose exec web python manage.py shell
```

Chạy migrate trong Docker:
```bash
docker compose exec web python manage.py migrate
```

Nếu bị lỗi do volume database cũ:
```bash
docker compose down -v
docker compose up --build
```

## Tạo tài khoản quản trị

### Django superuser cho `/admin/`

Chạy local:
```bash
python manage.py createsuperuser
```

Hoặc trong Docker:
```bash
docker compose exec web python manage.py createsuperuser
```


