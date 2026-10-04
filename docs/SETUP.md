# Hướng dẫn cài đặt và chạy hệ thống (Local Setup)

Tài liệu hướng dẫn thiết lập môi trường phát triển, chạy cơ sở dữ liệu PostgreSQL, migration Alembic, Backend FastAPI, Frontend React, kiểm thử và tài liệu API Registration.

---

## 1. Yêu cầu môi trường (Prerequisites)

- **Git**
- **Docker Desktop** (hỗ trợ Docker Compose)
- **Python 3.11** trở lên
- **Node.js 18** trở lên cùng `npm`

---

## 2. Thứ tự thiết lập hệ thống (Setup Steps)

### Bước 1: Cấu hình biến môi trường
Sao chép file mẫu `.env.example` thành `.env` tại thư mục gốc của repository:

```powershell
Copy-Item .env.example .env
```

Kiểm tra nội dung `.env`:
- `DATABASE_URL`: Chuỗi kết nối PostgreSQL môi trường phát triển (`multi_agent_rag`).
- `CORS_ORIGINS`: Danh sách origin được phép kết nối từ Frontend (`http://localhost:5173,http://127.0.0.1:5173`).
- `TEST_DATABASE_URL`: Chuỗi kết nối PostgreSQL môi trường kiểm thử riêng biệt (`multi_agent_rag_test`).

*Lưu ý: Không commit file `.env` lên Git.*

### Bước 2: Khởi động PostgreSQL với pgvector
Tại thư mục gốc của repository, khởi động container cơ sở dữ liệu:

```powershell
docker compose up -d postgres
```

Kiểm tra trạng thái container:

```powershell
docker compose ps
```

Container `multi-agent-rag-postgres` lắng nghe trên cổng `localhost:5432`.

### Bước 3: Cài đặt dependencies Backend
Mở terminal và di chuyển vào thư mục `backend` (yêu cầu Python 3.11 trở lên):

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 4: Chạy Database Migration
Áp dụng toàn bộ migration Alembic lên Database phát triển:

```powershell
alembic upgrade head
```

Lệnh này sẽ thực hiện tạo bảng `users` và bổ sung các cột dữ liệu theo đúng mô hình SQLAlchemy.

### Bước 5: Khởi động Backend
Khởi chạy dịch vụ FastAPI ở chế độ reload:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Bước 6: Kiểm tra hoạt động Backend và Swagger UI
- Kiểm tra Health endpoint:
  Truy cập `http://127.0.0.1:8000/health` -> Nhận phản hồi `{"status":"ok"}`.
- Kiểm tra tài liệu API tương tác (Swagger UI):
  Truy cập `http://127.0.0.1:8000/docs` để xem và thử nghiệm các endpoint, bao gồm `POST /api/auth/register`.

### Bước 7: Cài đặt và khởi động Frontend
Mở một cửa sổ PowerShell mới tại thư mục gốc:

```powershell
Set-Location frontend
npm install
npm run dev
```

Truy cập ứng dụng giao diện theo địa chỉ hiển thị bởi Vite (thông thường là `http://localhost:5173`).

---

## 3. Tài liệu API: User Registration (`POST /api/auth/register`)

### Endpoint
`POST /api/auth/register`

### Request Body (JSON)
```json
{
  "email": "user@example.com",
  "name": "Nguyen Van A",
  "password": "Password123"
}
```

### Chi tiết các trường dữ liệu:
- `email`: Bắt buộc, chuỗi định dạng email hợp lệ. Hệ thống tự động chuyển thành chữ thường và loại bỏ khoảng trắng hai đầu.
- `name`: Bắt buộc, chuỗi tối đa 100 ký tự. Hệ thống tự động cắt tỉa khoảng trắng hai đầu. Không được để trống hoặc chỉ chứa khoảng trắng.
- `password`: Bắt buộc, tối thiểu 8 ký tự. Không được để trống hoặc chỉ chứa khoảng trắng. Mật khẩu được băm bằng thuật toán Argon2id trước khi lưu.

### Response thành công (HTTP 201 Created)
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Nguyen Van A",
  "message": "Đăng ký thành công"
}
```

*Lưu ý bảo mật: Response tuyệt đối không chứa mật khẩu gốc, chuỗi hash hoặc access token.*

### Các mã lỗi thường gặp:
- **HTTP 400 Bad Request:**
  - `{"detail": "Họ tên không được để trống"}` (khi name rỗng hoặc chỉ có khoảng trắng).
  - `{"detail": "Họ tên không được vượt quá 100 ký tự"}` (khi name dài hơn 100 ký tự).
  - `{"detail": "Mật khẩu không được để trống"}` (khi password rỗng hoặc chỉ có khoảng trắng).
  - `{"detail": "Mật khẩu phải có ít nhất 8 ký tự"}` (khi password ngắn hơn 8 ký tự).
- **HTTP 409 Conflict:**
  - `{"detail": "Email đã được đăng ký"}` (khi email đã tồn tại trong hệ thống, bao gồm cả trường hợp race condition).
- **HTTP 422 Unprocessable Entity:**
  - Khi thiếu một trong các trường `email`, `name`, `password` hoặc định dạng email không hợp lệ.
- **HTTP 500 Internal Server Error:**
  - `{"detail": "Lỗi hệ thống khi đăng ký người dùng"}` (lỗi cơ sở dữ liệu ngoài dự kiến).

### Hướng dẫn tích hợp cho Frontend:
Sau khi nhận phản hồi HTTP 201 Created từ API đăng ký, Frontend chuyển hướng người dùng sang màn hình Đăng nhập (Login screen). Trong phạm vi CAPONE-8, hệ thống không tự động đăng nhập, không trả về JWT token, session hay cookie.

---

## 4. Hướng dẫn chạy kiểm thử (Testing)

Kích hoạt môi trường ảo tại thư mục `backend`:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
```

### Chạy Unit Tests (SQLite in-memory)
Unit test kiểm thử validation logic, CORS, và HTTP status code độc lập trên SQLite in-memory:

```powershell
python -m pytest tests/test_auth.py tests/test_cors.py tests/test_health.py -v
```

### Chạy Integration Tests (PostgreSQL thật)
Integration test kiểm thử tương tác thực tế với PostgreSQL (kiểm tra hash Argon2id, ràng buộc Unique key, lưu trữ và đọc dữ liệu).

1. **Chuẩn bị Database kiểm thử:**
   Tạo database kiểm thử riêng biệt (nếu chưa có):

   ```powershell
   docker exec multi-agent-rag-postgres psql -U postgres -c "CREATE DATABASE multi_agent_rag_test;"
   ```

2. **Chạy Migration trên Database kiểm thử (PowerShell):**
   Áp dụng migration lên `multi_agent_rag_test` bằng biến môi trường tạm thời trong session PowerShell, bảo đảm không thay đổi file `.env` và không ảnh hưởng Database phát triển:

   ```powershell
   $env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/multi_agent_rag_test"
   alembic upgrade head
   $env:DATABASE_URL = $null
   ```

3. **Cấu hình biến môi trường kiểm thử:**
   Bảo đảm file `.env` có thiết lập:
   `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/multi_agent_rag_test`

4. **Chạy integration test:**

   ```powershell
   python -m pytest tests/test_auth_postgres.py -v
   ```

### Chạy toàn bộ bộ kiểm thử (31 bài test)

```powershell
python -m pytest -v
```
