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

## Đã cài (giai đoạn 5)
- Lệnh: `tinh --lot <lô> [--sweep] [--preview]`. Quy ước dấu: dz = z_đo − z_mốc; dz > 0 ĐẮP, dz < 0 ĐÀO.
- **Lưới**: ô có dz trung bình < 0 tính DT vào đào, còn lại vào đắp. **Lăng trụ**: chồng chính xác hai TIN trên
  từng ô (cắt tam giác ∩ tam giác ∩ ô), mảnh vắt dz = 0 cắt đôi — tổng không phụ thuộc cách đặt lưới (có test).
- Mảnh chạm tam giác `thiếu dữ liệu` được tính riêng: **B3** gồm chúng, **B5** loại.
- Cờ ô lệch lớn: |lưới − lăng trụ| (đào hoặc đắp) > max(`o_lech_lon_pct` % × lớn nhất của đào/đắp lăng trụ,
  `o_lech_lon_m3`). Hai ngưỡng này CHƯA CHỐT (xem SPEC mục 10) — đề xuất 5 % / 10 m³.
- `--sweep`: A1–A8 và B1–B5; A7 bỏ qua nếu không có ranh đào–đắp; A8 = 16 gốc × 7 phương = 112 tổ hợp.
  `can_duoi` lấy theo đào+đắp thấp nhất — đọc theo "Quy tắc đọc" ở trên, KHÔNG gọi là tối ưu.
- Kiểm tổng: DT đào + DT đắp + DT thiếu dữ liệu = DT lô (CHẶN nếu lệch). Ô thiếu dữ liệu không vào số nộp.
- RULES 12: khai `dot_truoc: {volume_json: đường/dẫn/volume_dot_truoc.json}` trong `lot.yaml` → ô đảo chiều đắp↔đào so với
  đợt trước bị CẢNH BÁO.
- Ra `volume.json` (số liệu từng ô để NGUYÊN độ chính xác), `qc_volume.json` (mã việc **T**), `ranh_dao_dap`
  (đoạn thẳng VN-2000, để vẽ `SN-RANH-DAODAP`).
- Chưa cài: hệ số đầm chặt `he_so_dam_chat`; đối chiếu Civil 3D 0,1 % (cần phần mềm ngoài).
