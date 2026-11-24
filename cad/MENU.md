# Menu SAN NỀN trong AutoCAD (giai đoạn 9)

Menu để QS **chủ động kiểm tra, xem và xuất** ngay trong AutoCAD. Menu chỉ lo giao diện; **mọi phép tính vẫn ở lõi Python**
(RULES 1). Mỗi lệnh gọi cầu nối `sannen_cad.cau_noi`, lõi tính, rồi CAD nạp một file LISP vẽ kết quả vào bản vẽ đang mở.

    AutoCAD (sannen.lsp + sannen.dcl)  →  cau_noi.py  →  lõi sannen-core  →  10_process/, 20_output/
            ▲                                   │
            └──── nạp file .lsp do cầu nối sinh (entmake) ◄──┘

## Cài một lần

    cd core && pip install -e ".[dev]"                       # cần Python có gói sannen
    .\cad\cai_dat_cad.ps1 -Python <python.exe> -Lot <thư mục lô>   # ghi %APPDATA%\SanNen\sannen.cfg
    Trong AutoCAD:  APPLOAD → chọn cad\lisp\sannen.lsp → Contents → Add   (tự nạp mỗi lần mở AutoCAD)

Nạp xong sẽ có menu **SAN NỀN** trên thanh menu và dòng "SAN NỀN đã nạp". Gõ `SN` để mở menu dòng lệnh dự phòng
(dùng được cả khi menu thả xuống không hiện). `SN_LOT` chọn lô khác.

## Đối chiếu với SNVN

| SNVN | Lệnh SAN NỀN | Ghi chú |
|---|---|---|
| Xây/cập nhật mô hình địa hình | `SN_MAT`, `SN_NHAP` | dựng lại TIN từ số liệu khảo sát |
| *(bạn yêu cầu)* xem bề mặt TIN dạng 3D | **`SN_TIN3D`** | hộp thoại: Mốc / Đo / Cả hai; mỗi bề mặt là **một polyface** (xem mục dưới); SW Iso + view `SN_TIN3D`; tô bóng; "Chỉ hiển thị mặt 3D"; nút Tắt 3D, Khôi phục lớp |
| *(mới)* trình xem 3D xoay trong trình duyệt | **`SN_XEM3D`** | gọi `python -m sannen.cli xem3d --lot <lô> --mo` qua cầu nối; cũng có nút trong hộp thoại `SN_TIN3D` và mục `Xem3d` của menu `SN` |
| Tạo lưới `DD_TAOLUOI` (nhập `Số×KT,Số×KT`) | **`SN_LUOI`** | hộp thoại; "Chọn vùng…" tự tính số cột/hàng |
| Hiệu chỉnh lưới (Ctrl + chuột phải) | `SN_LUOI` (nút), `SN_DOICOT`, `SN_CHENCOT`, `SN_XOACOT`, `SN_DOIHANG`, `SN_CHENHANG`, `SN_XOAHANG`, `SN_DICHLUOI`, `SN_XOAYLUOI` | chỉ số cột/hàng tính từ 1; xoay quanh TÂM lưới |
| Gán cao độ nút lưới | tự động trong `SN_LUOITINH` | nội suy từ hai TIN |
| Nâng cao độ thiết kế `DD_NANGCDTK`, sửa từng nút | **`SN_CAPDO`**, `SN_NANGCD`, `SN_SUADINH` | chênh cao **tự tính lại**, không có bước "cập nhật chênh cao" để quên |
| Tính đào đắp `DD_TINHDAODAP` | `SN_TINH`, `SN_VE` | số nộp (lưới) + số kiểm (lăng trụ) |
| Bảng đào đắp / tổng hợp / từng ô, xuất Excel | **`SN_BANG`**, `SN_EXCEL` | bảng tổng · tổng hợp (nộp + kiểm) · từng ô; Excel 7 sheet |
| Cộng ô `DD_MC` | `SN_CONGO` | |
| *(bạn yêu cầu)* mặt cắt địa hình | **`SN_MATCAT`** | tuyến A–B, biểu đồ + bảng cao độ + diện tích đào/đắp trên mặt cắt; CSV ở `20_output/`. Biểu đồ mặc định đặt **dưới toàn bộ kết quả của lô** (không đè bảng), xem mục dưới |
| *(mới)* cảnh báo QC, zoom tới điểm nghi vấn | `SN_CANHBAO` | |
| *(mới)* duyệt ba cổng | `SN_DUYET` | ghi `cong.json` + `decisions.md`; cần nguyên văn câu đồng ý |
| *(mới)* đồng bộ nhãn sửa tay | `SN_DONGBO` | báo chênh lệch trước, hỏi rồi mới nhận (`luoi --resync`) |

**Không làm (chủ ý):** taluy, thiết kế hướng dốc, offset 3D, hiệu chỉnh cao độ đối tượng thiết kế. Đó là công cụ *thiết kế*;
hệ thống này phục vụ *nghiệm thu* số liệu đã đo. Cần thì làm thành một giai đoạn riêng.

## Mặt 3D dạng polyface (giai đoạn 14)

- `SN_TIN3D` vẽ **mỗi bề mặt thành MỘT đối tượng POLYLINE polyface mesh** (layer `SN-3DF-MOC` xanh lá, `SN-3DF-DO` vàng; tam giác
  thiếu dữ liệu thành một polyface riêng trên `SN-QC`). Chọn / ẩn / xóa cả bề mặt bằng một lần bấm; không còn hàng nghìn 3DFACE rời.
- Giới hạn AutoCAD 32767 đỉnh/polyface: bề mặt lớn hơn **30000 đỉnh** được tự chia thành nhiều khối liên tiếp (tag `khoi=i/n`),
  và thông báo nói rõ số khối. Purge theo `loai` (`mat_3d`, `qc`) xóa mọi khối — vẽ hai lần không đè nhau (RULES 5); chỉ xóa đối tượng
  có XDATA `SANNEN` của đúng lô.
- Tham số `dang`: `polyface` (mặc định của menu CAD, `--dang` ở cầu nối) hoặc `3dface` (lối cũ). Công cụ MCP `cad_draw_3dface` vẫn là
  công cụ thứ 13 trong số 13, thêm tham số tùy chọn `dang` (mặc định `3dface` để không đổi hợp đồng cũ).
- Sau khi vẽ: `-VIEW SWISO` → `ZOOM Object` tới các khối polyface → lưu view **`SN_TIN3D`** (khôi phục: `-VIEW` → Restore). Tô bóng đặt
  `VSCURRENT` = *Shaded with Edges*.
- **Chỉ hiển thị mặt 3D**: tắt (chỉ `ON/OFF`, không đóng băng, không xóa) mọi layer ngoài `SN-3DF-*`/`SN-QC*`, trừ layer hiện hành. Danh sách
  layer đã tắt được lưu trong chính bản vẽ (`vlax-ldata` "SANNEN"/"LOP_AN"); nút **Khôi phục lớp** bật lại đúng những layer đó
  (layer vốn đã tắt từ trước thì giữ tắt).

## Chọn điểm không bị treo osnap

Mọi lần chọn điểm trong menu (A/B mặt cắt, điểm đặt biểu đồ, dịch lưới, chèn bảng, cộng ô, lệnh nhanh cột/hàng) đi qua `sn:lay-diem`:
đặt bit 16384 của `OSMODE` (osnap tạm tắt, vẫn nhớ các chế độ cũ), chọn điểm, rồi khôi phục **nguyên giá trị cũ** — kể cả khi ESC. Dòng lệnh báo
"đã tạm tắt osnap". Tránh lỗi *Too many objects selected for INTERSECT* trên đám đối tượng 3D dày.

## Hộp thoại tiếng Việt có dấu

`sannen.dcl` chỉ gồm ASCII (DCL đọc theo bảng mã ANSI, không kiểm chứng được UTF-8 khi không có giao diện). Mọi chữ hiển thị do
`sannen.lsp` đặt bằng `set_tile` lúc mở hộp thoại: tile `text`, nhãn nút, và **danh sách của `popup_list`** (nhóm lựa chọn đổi từ radio sang
popup vì `set_tile` không đổi được nhãn radio/toggle/edit_box). Nhãn cạnh ô nhập là tile `text` (`n_...`). Thanh tiêu đề cửa sổ DCL không
đổi được nên giữ ASCII ngắn ("SAN NEN - ..."); tiêu đề đầy đủ có dấu nằm ở dòng đầu hộp thoại. Ghi chú dài là 2–3 tile `text` xếp dọc
(`t_tt`, `t_tt2`, `t_tt3`), LISP tự ngắt dòng — không còn bị cắt cụt.

## Quy tắc an toàn (giữ nguyên từ RULES)

- **00_input không bao giờ bị ghi.** Kết quả vẽ vào bản vẽ đang mở của bạn; chỉ mất khi bạn lưu.
- Lệnh ghi hỏi xác nhận (RULES 4). `SN_XOA` chỉ xóa đối tượng có dấu truy vết **của đúng lô này**.
- Vẽ lại luôn xóa kết quả cũ cùng loại trước (RULES 5): chạy hai lần không đè nhau; mặt cắt cùng tên thì thay, khác tên thì cộng thêm.
- Chỉnh lưới trong CAD ghi `luoi_tuy_chinh.yaml` (không sửa `lot.yaml`) và một dòng `decisions.md`. Nếu hình học lưới đổi,
  hiệu chỉnh đỉnh cũ **được cất** (`grid_adjusted.cu_*.json`) vì mã đỉnh đã đổi nghĩa. Lưới không phủ hết lô thì bị chặn và
  **khôi phục nguyên trạng**. `xuat` từ chối xuất số cũ khi lưới đã đổi mà chưa tính lại.
- Mọi đối tượng kết quả mang XDATA `SANNEN` (mã lô, đợt, hash, loại); layer mới `SN-MATCAT` cho mặt cắt.

## Đã kiểm / chưa kiểm

| | Trạng thái |
|---|---|
| Lõi: hiệu chỉnh lưới, mặt cắt (nghiệm giải tích) | ✅ test `test_gd10_*` |
| Cầu nối 15 lệnh, backend LISP, vẽ/purge/vẽ lại trên **AutoCAD 2022 thật chạy không giao diện** | ✅ `test_gd11_*` |
| Nạp `sannen.lsp`, đủ 31 lệnh, hàm tiện ích, gọi cầu nối thật, xóa theo XDATA | ✅ `test_gd12_*` (accoreconsole) |
| Cú pháp DCL, mọi callback/khóa ô khớp giữa DCL và LISP; mọi chữ hiển thị đều do LISP đặt | ✅ kiểm tĩnh |
| Polyface: 1 POLYLINE/bề mặt trong AutoCAD thật không giao diện, XDATA trên POLYLINE, vẽ nhiều lần không nhân đôi, purge, chia khối | ✅ `test_gd14_*` (backend DXF + accoreconsole) |
| Ẩn / khôi phục layer, osnap khôi phục khi lỗi, hộp bao polyface, `-VIEW` + `ZOOM Object` | ✅ `test_gd14_*` (accoreconsole) |
| Biểu đồ mặt cắt mặc định nằm dưới kết quả lô ≥ 30 m, không đè bảng | ✅ `test_gd14_*` (tính toán); ❌ chưa nhìn trên bản vẽ thật |
| **Hiển thị hộp thoại DCL, menu thả xuống trên thanh menu, thao tác chọn điểm/đối tượng** | ❌ cần AutoCAD có giao diện — chưa kiểm |
| `VSCURRENT` Shaded with Edges (từ khóa `_E`) — accoreconsole treo khi gọi lệnh này nên không thử được | ❌ cần giao diện |
| Chữ có dấu trong DCL hiển thị đúng (set_tile trên text/nút/popup), bố cục các hộp thoại mới, ghi chú nhiều dòng | ❌ cần giao diện — chưa kiểm |
| Mở trình xem 3D (HTML) từ `SN_XEM3D`/nút: phụ thuộc verb `xem3d` của lõi và trình duyệt mặc định | ❌ chưa kiểm cuối-cuối (chỉ kiểm dòng lệnh do LISP/cầu nối dựng) |
| Bản vẽ rất lớn: thời gian nạp polyface hàng chục nghìn mặt (đã giảm số đối tượng từ hàng nghìn xuống 2) | ❌ chưa đo trên bản vẽ thật |

### Checklist 5 phút để bạn kiểm giao diện
1. `APPLOAD` → `sannen.lsp`: có menu **SAN NỀN**? (không có thì gõ `SN`).
2. `SN_LOT` chọn lô → `SN_TRANGTHAI` hiện bước đã chạy và ba cổng.
3. `SN_TIN3D` → chọn *Cả hai* → [Hiển thị]: thấy mặt 3D (hai đối tượng polyface, thử `SELECT` một cái là chọn cả bề mặt); [Tắt 3D] ẩn lại.
   Tích *Chỉ hiển thị mặt 3D* rồi [Hiển thị]: các lớp khác tắt; mở lại hộp thoại → [Khôi phục lớp]: các lớp đó hiện lại. Nút [Mở trình xem 3D (HTML)] và lệnh `SN_XEM3D`.
4. `SN_LUOI` → đổi cột thành `1x10,4x22.5` → [Áp dụng]: lưới vẽ lại, tổng diện tích ô = diện tích lô.
5. `SN_MATCAT` → chọn 2 điểm cắt qua vùng đắp → có biểu đồ nằm dưới bảng khối lượng (không đè), bảng cao độ và diện tích đào/đắp.
   Khi chọn điểm A/B, dòng lệnh báo "đã tạm tắt osnap" và không còn báo *Too many objects selected for INTERSECT*.
6. Hộp thoại nào hiển thị sai chữ/ô: chụp màn hình gửi lại để chỉnh `sannen.dcl`.
