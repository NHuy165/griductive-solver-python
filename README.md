# Griductive

Game suy luận trên lưới: tìm ra ai là tội phạm, ai vô tội, chỉ từ những manh
mối đã mở, không đoán. Gồm engine game, DPLL SAT solver, logic agent và giao
diện web.

## Yêu cầu

- Python 3.10 trở lên
- Thư viện trong `requirements.txt` (Flask)

## Cài đặt (chỉ làm một lần)

Mở terminal tại thư mục gốc của project.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Chạy

Windows (PowerShell):

```powershell
.\.venv\Scripts\python.exe main.py
```

macOS / Linux:

```bash
.venv/bin/python main.py
```

Sau đó mở <http://127.0.0.1:5000>. Nhấn `Ctrl + C` để tắt server.

Nếu cổng 5000 đã bị chiếm, thêm `--port 8000` vào lệnh chạy rồi mở
<http://127.0.0.1:8000>.

## Cách dùng

- **Chọn màn** trong danh sách là vào màn đó ngay.
- **Chơi tay:** bấm một lá đang úp, chọn *Tội phạm* hoặc *Vô tội*.
- **Manh mối:** bấm vào một manh mối đã mở để tô sáng các ô liên quan.
- **Gợi ý:** chỉ ra một nhân vật đã có thể kết luận.
- **Tự động giải:** agent lật từng lá. Có thể tạm dừng (`Space`), đi từng bước
  (`→`), đổi tốc độ, tự chơi tiếp, và tải phụ đề `.srt` sau khi chạy xong.

Các màn chơi nằm trong `src/maps/`.
