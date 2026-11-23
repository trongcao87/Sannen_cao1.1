---
name: tinh
mo_ta: Tính khối lượng theo ô lưới và theo lăng trụ, đối chiếu, quét ma trận phương án.
giai_doan: 5
---
# tinh

## Lệnh
    python -m sannen.cli tinh --lot <thư mục lô>
    python -m sannen.cli tinh --lot <thư mục lô> --sweep

## Hai phương pháp — chạy đồng thời
- **Lưới ô vuông (trung bình 4 góc)**: V = (chênh cao TB 4 góc) × diện tích ô.
  Đây là **SỐ NỘP** vì hồ sơ dự án bắt buộc.
- **Lăng trụ tam giác**: V = diện tích chiếu × (d1+d2+d3)/3. Tam giác vắt ranh được
  cắt theo mức 0 rồi tách đào · đắp. Đây là **SỐ KIỂM** — chính xác tuyệt đối khi hai
  mặt phẳng trên từng tam giác.

Chúng lệch nhau ở hai chỗ: (1) ô vắt ranh đào–đắp — một ô có chênh cao 4 góc
+1,+1,−1,−1 cho lưới ra 0 m³ trong khi lăng trụ ra 100 đào + 100 đắp; (2) địa hình bên
trong ô — lưới chỉ lấy 4 góc, lăng trụ dùng toàn bộ điểm đo.

## --sweep: ma trận phương án

**Bảng A — quét cách đặt lưới**, giữ nguyên kích thước ô:
A1 gốc+phương theo bản vẽ nhà thầu · A2 gốc tây-nam hộp bao, phương theo cạnh dài lô ·
A3 A2 dời ½ ô theo X · A4 dời ½ ô theo Y · A5 dời ½ ô cả hai trục · A6 xoay thêm 45° ·
A7 phương song song ranh giới đào–đắp chủ đạo · A8 quét 16 vị trí gốc × phương 0–90°
bước 15°.

**Bảng B — quét phương pháp**, giữ cách đặt lưới A1:
B1 ô 10×10 · B2 ô 5×5 · B3 lăng trụ có đứt gãy, đã lọc tam giác rác ·
B4 lăng trụ bỏ đứt gãy · B5 loại vùng thiếu dữ liệu khỏi phạm vi tính.

## Quy tắc đọc — QUAN TRỌNG
Phương án cho số THẤP NHẤT chính là phương án có nhiều ô vắt ranh nhất, tức là bỏ sót
nhiều công tác thật nhất. Khoảng cách từ nó tới B3 là phần khối lượng bị triệt tiêu.
Gọi nó là "cận dưới của phương pháp lưới" thì đúng; gọi là "tối ưu" thì không đứng
được trước người phản biện.

Agent KHÔNG tự đổi số nộp (RULES 9). Số nộp là A1 đặt theo tham số hồ sơ duyệt.

## Kết quả phụ miễn phí
Tập các đoạn cắt mức 0 chính là đường ranh giới đào–đắp → layer `SN-RANH-DAODAP`.
Luôn khớp với con số đã tính vì là sản phẩm phụ của phép tính.

## Ra
`volume.json`. Cổng 3: người xem kết quả, chấp nhận hoặc yêu cầu soát lại.
