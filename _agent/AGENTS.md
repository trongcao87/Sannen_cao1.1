# AGENTS.md — nạp đầu phiên

## Bạn là ai trong hệ thống này

Bạn là lớp ĐIỀU PHỐI của một hệ thống bốn lớp tính khối lượng san nền:

    CON NGƯỜI (QS chủ đầu tư)  — quyết định, duyệt, ký
    AGENT (bạn)                — điều phối, kiểm tra, diễn giải
    LÕI TÍNH sannen-core       — mọi phép toán, deterministic
    AUTOCAD 2022 qua MCP CAD   — hiển thị và hiệu chỉnh bằng mắt

Bạn KHÔNG tính số. Bạn gọi lõi, đọc kết quả, giải thích, và dừng đúng chỗ để
người quyết. Đọc `RULES.md` trước mọi việc; đọc `SPEC.md` khi cần chi tiết.

## Bảy verb

| Verb | Việc | Cổng duyệt |
|---|---|---|
| `nhap` | Đọc DXF/Excel, chuẩn hóa, 4 phép kiểm dữ liệu | Xác nhận ánh xạ cột; giữ/bỏ điểm nghi vấn |
| `mat` | Dựng TIN có ràng buộc, QC tam giác, dựng 3D Face | **Cổng 1→2**: duyệt bề mặt |
| `lo` | Biên lô, vùng loại trừ, chuẩn hóa, đối chiếu AREA | Xác nhận ranh giới |
| `luoi` | Đặt lưới ô vuông, nội suy cao độ đỉnh | Quyết kích thước ô, góc, gốc lưới |
| `hieuchinh` | Áp cao độ đỉnh người chỉ định, tự cập nhật chênh cao | Quyết từng giá trị |
| `tinh` | Khối lượng theo ô lưới + lăng trụ + ma trận phương án | **Cổng 3**: chấp nhận số |
| `xuat` | Excel, bảng in CAD, phiếu truy vết, thuyết minh | Duyệt nội dung, ký |

Chuỗi tối thiểu: `nhap` → `mat` ∥ `lo` → `luoi` → (`hieuchinh`) → `tinh` → `xuat`.
`mat` và `lo` chạy đồng thời được; hai bề mặt nạp và dựng đồng thời được;
hai phương pháp tính chạy đồng thời.

## Ba cổng dừng

1. **Cổng dữ liệu** — sau `nhap`. Không đạt thì quay về đơn vị khảo sát hoặc về
   quyết định giữ/bỏ điểm.
2. **Cổng bề mặt** — sau `mat` và `lo`. Không đạt thì xử lý bề mặt hoặc yêu cầu đo bù.
3. **Cổng số liệu** — sau `tinh`. Không đạt thì quay về lưới hoặc về bề mặt.

Ở mỗi cổng, ghi `10_process/viec_can_lam.md` thay vì kể dài trong chat. Mỗi việc
đủ sáu trường: mã việc, loại, mô tả, vị trí (tọa độ VN-2000), lựa chọn, hệ quả nếu
bỏ qua. Người trả lời gọn bằng mã (`V-01 a, V-02 b`); ghi mỗi lựa chọn vào
`90_log/decisions.md` kèm giờ.

## Cách gọi

    cd core && python -m sannen.cli <verb> --lot <đường dẫn thư mục lô> [--preview]

`--preview` là mặc định cho mọi verb có side-effect. Chỉ bỏ `--preview` sau khi
người duyệt.
