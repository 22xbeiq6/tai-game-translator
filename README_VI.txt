TAI GAME TRANSLATOR ULTIMATE 1.0

TÍNH NĂNG ĐƯỢC TÍCH HỢP TRONG MÃ NGUỒN
- Giao diện nhiều tab tiếng Việt.
- Chọn vùng màn hình game.
- OCR đa ngôn ngữ: Anh, Trung giản thể/phồn thể, Nhật, Hàn, Pháp, Đức, Tây Ban Nha, Nga, Ý, Bồ Đào Nha, Thái, Việt (tùy khả năng hỗ trợ mô hình EasyOCR).
- Dịch bằng mô hình AI qua API tương thích OpenAI Chat Completions; tùy chỉnh endpoint, model, API key và temperature.
- Quét tự động theo chu kỳ.
- Cửa sổ phụ đề nổi luôn trên cùng, kéo thả được.
- Tùy chỉnh phông chữ, cỡ chữ, màu chữ, màu nền, độ đục.
- Phím tắt toàn hệ thống có thể chỉnh: chọn vùng, bắt đầu, dừng, ẩn/hiện phụ đề.
- Lưu cấu hình người dùng bằng QSettings.
- Khay hệ thống.

ĐIỀU KIỆN ĐỂ DỊCH AI
Bạn cần tự có API key của nhà cung cấp AI tương thích OpenAI Chat Completions. Ứng dụng không kèm API key miễn phí và không nhúng khóa bí mật vào phần mềm. API có thể tính phí tùy nhà cung cấp.

GIỚI HẠN HIỆN TẠI
- Đây là mã nguồn và quy trình build, không phải EXE Windows đã biên dịch/kiểm thử.
- OCR cần tải mô hình ở lần đầu, cần Internet.
- Tự động quét theo chu kỳ, không phải dịch mọi khung hình tức thời.
- Một số ngôn ngữ OCR phụ thuộc mô hình EasyOCR; độ chính xác thay đổi theo font/độ phân giải.
- API tương thích cần hỗ trợ endpoint /chat/completions.
- Phím tắt toàn hệ thống có thể bị Windows hoặc phần mềm khác chiếm; cần chọn tổ hợp không trùng.
- Nếu game chụp màn hình đen, thử chế độ Borderless hoặc Windowed.
- Một số game/anti-cheat có thể chặn overlay hoặc capture.

BUILD WINDOWS PORTABLE
Máy build cần Windows 10/11 64-bit và Python 3.11 x64:
1. Cài Python 3.11 x64 (chỉ máy build cần Python).
2. Mở Terminal trong thư mục dự án.
3. Chạy:
   py -3.11 -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
4. Chạy lệnh:
   pyinstaller --noconfirm --clean --windowed --name TaiGameTranslatorUltimate --collect-all easyocr --collect-all torch --collect-all torchvision --collect-all cv2 --collect-all scipy --collect-all skimage --collect-all numpy --collect-all PySide6 --collect-all pynput --hidden-import=python_bidi --hidden-import=pyclipper src\main.py
5. Thư mục portable nằm tại dist\TaiGameTranslatorUltimate\
6. Chép nguyên thư mục này sang máy cần dùng. Người dùng cuối không cần cài Python.

GITHUB ACTIONS
Workflow .github/workflows/build-windows.yml có thể build trên Windows runner và tạo artifact ZIP.
