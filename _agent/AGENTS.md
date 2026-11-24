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

## Chốt chặn cổng (`core/sannen/cong.py`)

Cổng được kiểm TRONG `cli.main`, nên dòng lệnh, MCP và menu AutoCAD đều bị chặn như nhau: verb ghi (`mat`, `lo` cần cổng 1;
`luoi`, `hieuchinh`, `tinh` cần cổng 2; `xuat` cần cổng 3) không chạy khi bỏ `--preview` mà cổng chưa duyệt hoặc kết quả đã
đổi từ lúc duyệt — thoát mã 2, chưa ghi file nào. `--preview`, `nhap`, `xem3d` không bị chặn. `cong.json` hỏng = chưa duyệt.

## Qua MCP (giai đoạn 7)

Máy chủ `sannen-mcp` (`python -m sannen.mcp_server`) bọc đúng các verb trên thành công cụ `sannen_<verb>`, cộng
`sannen_trang_thai` (gọi ĐẦU TIÊN mỗi phiên), `sannen_doc_viec`, `sannen_ghi_quyet_dinh`, `sannen_duyet_cong`.

- Verb ghi mặc định `preview=true`. `preview=false` bị **TỪ CHỐI** nếu cổng tương ứng chưa được duyệt hoặc kết quả đã
  đổi từ lúc duyệt: cổng 1 mở `mat`,`lo`; cổng 2 mở `luoi`,`hieuchinh`,`tinh`; cổng 3 mở `xuat`.
- `sannen_duyet_cong` chỉ gọi SAU KHI người nói rõ đồng ý, `bang_chung` là nguyên văn câu của người. Không tự duyệt.
- Mã việc có tiền tố theo verb: **V** nhap · **M** mat · **L** lo/luoi · **T** tinh. Người trả lời gọn: `V-02 b, M-01 a`;
  ghi mỗi câu trả lời bằng `sannen_ghi_quyet_dinh`.
- Excel mới: `sannen_nhap` trả mã thoát 2 kèm ánh xạ cột đề xuất. Đưa cho người xem (X là northing, Y là easting!)
  rồi mới gọi lại với `xac_nhan_anh_xa=true`.

Máy chủ CAD (`python -m sannen_cad.mcp_cad_server --vao <dxf> --ra <dxf>`) phơi 13 công cụ `cad_*`; công cụ ghi mặc định
`xem_truoc=true`. Bộ điều phối `python -m sannen_cad.ve --lot <lô> --vao <dxf> --ra <dxf>` vẽ cả lô theo đúng thứ tự
purge → lưới → nhãn → ranh → 3D → bảng.
