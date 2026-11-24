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
| *(bạn yêu cầu)* **một hộp toàn bộ để điều phối, kiểm tra, điều chỉnh** TIN, lưới ô vuông… | **`SN_QL`** (mục đầu menu SAN NỀN; từ khóa `Quanly` của menu `SN`) | bảng điều khiển trung tâm, xem mục dưới |
| *(bạn yêu cầu)* **bảng DỌC dock được, nhiều tab** (cây quản lý như Civil 3D Toolspace) | **`SN_PALETTE`** (ngay dưới `SN_QL` trong menu; từ khóa `Palette` của menu `SN`); đóng: `SN_PALETTE_DONG` | palette .NET, xem mục `Palette SAN NỀN` dưới |
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

## Bảng điều khiển trung tâm `SN_QL` (giai đoạn 15)

Một hộp thoại gom mọi thứ; mở bằng `SN_QL`, mục **BẢNG ĐIỀU KHIỂN TRUNG TÂM…** đầu menu SAN NỀN, hoặc `SN` → `Quanly`.

- **Đầu hộp:** mã lô · đợt · thư mục; các bước đã chạy (`[x] nhập [x] mặt TIN … [ ] xuất → kế tiếp`); ba cổng duyệt (đã/chưa, còn bao
  nhiêu việc CHẶN); dòng **cảnh báo kết quả cũ** (lưới đã đổi mà chưa `luoi`/`tinh` lại; khối lượng tính trên lưới/đầu vào khác;
  hiệu chỉnh đỉnh sau lần `tinh`; cổng đã duyệt nhưng kết quả đổi nên mất hiệu lực).
- **Danh sách nhóm đối tượng** (chọn nhiều bằng Ctrl/Shift): TIN mốc `SN-3DF-MOC` · TIN đo `SN-3DF-DO` · tam giác thiếu dữ liệu
  `SN-QC` · lưới ô `SN-LUOI` · nhãn đỉnh `SN-LUOI-NHAN` · nhãn ô `SN-LUOI-O` · ranh đào–đắp `SN-RANH-DAODAP` · mặt cắt `SN-MATCAT`
  · bảng in `SN-BANG` · khối lượng (chỉ số liệu) · dữ liệu nguồn của nhà thầu `SN-DIEM-*`, `SN-DUTGAY`, `SN-DONGMUC`, `SN-BIENLO`,
  `SN-LOAITRU`. Mỗi hàng: **số đối tượng đang có trong bản vẽ của ĐÚNG lô và đợt** (đếm theo layer + XDATA `SANNEN`; layer đang tắt vẫn
  đếm) và **Hiện / Ẩn / Một phần / Đóng băng / Chưa có lớp** — đọc lại từ bản vẽ mỗi lần mở hộp. Layer đợt n là `SN-…-Dnn`.
- **Nút ẩn/hiện:** [Hiện] [Ẩn] [Chỉ hiện nhóm này] [Hiện tất cả SAN NỀN] [Ẩn tất cả SAN NỀN] — **chỉ `ON/OFF` layer** (không đóng băng,
  không xóa, không đổi layer hiện hành; layer đang là hiện hành thì **không bị tắt**, hộp báo rõ). Chỉ đụng layer `SN-*`; layer của
  bản vẽ nhà thầu và cơ chế "Chỉ hiển thị mặt 3D" của `SN_TIN3D` (danh sách `LOP_AN`, nút Khôi phục lớp) không bị đụng. Một layer có thể chứa
  đối tượng của nhiều lô: ẩn layer là ẩn của mọi lô trong cùng bản vẽ.
- **Khung số liệu** (cập nhật khi đổi dòng; nguồn là cầu nối `thong-tin` → `core/sannen/thong_tin.py`, chỉ ĐỌC file của lô, thiếu thì ghi
  «Chưa có — chạy …»): TIN (số đỉnh, tam giác, thiếu dữ liệu, dẹt/rác, diện tích phủ, cao độ min/max/TB, đứt gãy/đoạn ép/cạnh ràng buộc,
  xung đột đứt gãy, điểm nghi ngờ/trùng từ QC) · lưới (cột×hàng, kích thước, góc, gốc E,N, tổng diện tích ô so với diện tích lô,
  ô thiếu dữ liệu/vắt ranh/lệch lớn/ngoại suy, có lưới tùy chỉnh không) · khối lượng (số nộp, số kiểm lăng trụ, chênh %) · ranh đào–đắp
  (số đoạn, chiều dài) · mặt cắt (từng mặt cắt: chiều dài, diện tích đào/đắp) · bảng in (số khối/dòng). *«Cạnh bị cắt đứt gãy»*: TIN có
  ràng buộc nên không cạnh nào cắt đứt gãy; hộp hiện số đoạn đứt gãy đã ép và số cạnh ràng buộc, không đếm giao cắt.
- **Nút điều phối:** [Xem 3D…] `SN_TIN3D` · [Trình xem HTML] `SN_XEM3D` · [Hiệu chỉnh lưới…] `SN_LUOI` · [Mặt cắt…] `SN_MATCAT` · [Cao độ
  đỉnh…] `SN_CAPDO` · [Cảnh báo QC…] `SN_CANHBAO` · [Bảng biểu…] `SN_BANG` · [Tính lại] `SN_TINH` · [Duyệt cổng…] `SN_DUYET` ·
  [Vẽ lại nhóm đang chọn] (`ve --lop`, hỏi xác nhận; mặt cắt vẽ lại bằng `SN_MATCAT`; vẽ lại 3D thì cả mốc lẫn đo, mặc định tắt) ·
  [Zoom tới nhóm] (`ZOOM Object` trên đối tượng đang hiện của đúng lô) · [Làm mới]. Mỗi nút đóng hộp, chạy lệnh có sẵn (lệnh ghi vẫn
  xem trước và xin xác nhận — RULES 4), rồi **mở lại hộp** với số liệu mới; dòng đang chọn được nhớ. [Đóng] / ESC để thoát.
  Hộp **không tự tính** (RULES 1).
- **Lỗi:** lõi/Python không gọi được → đầu hộp ghi lý do và chỉ tới file cấu hình `%APPDATA%\SanNen\sannen.cfg` (`python=`, `cad=`,
  `lot=`); khung số liệu ghi «Chưa có» còn phần Hiện/Ẩn vẫn dùng được.

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

- **Cổng duyệt chặn cả lệnh trong menu.** Lõi tự từ chối khi chưa duyệt cổng (xem `_agent/AGENTS.md`, mục «Chốt chặn cổng»):
  `SN_MAT`/`SN_LO` cần cổng 1; `SN_LUOI` (hộp thoại và lệnh nhanh), `SN_CAPDO`/`SN_SUADINH`, `SN_TINH` cần cổng 2; `SN_EXCEL`
  cần cổng 3. Bị từ chối thì lô được khôi phục nguyên trạng và thông báo nói rõ cổng nào — dùng `SN_DUYET` rồi chạy lại.

- **00_input không bao giờ bị ghi.** Kết quả vẽ vào bản vẽ đang mở của bạn; chỉ mất khi bạn lưu.
- Lệnh ghi hỏi xác nhận (RULES 4). `SN_XOA` chỉ xóa đối tượng có dấu truy vết **của đúng lô này**.
- Vẽ lại luôn xóa kết quả cũ cùng loại trước (RULES 5): chạy hai lần không đè nhau; mặt cắt cùng tên thì thay, khác tên thì cộng thêm.
- Chỉnh lưới trong CAD ghi `luoi_tuy_chinh.yaml` (không sửa `lot.yaml`) và một dòng `decisions.md`. Nếu hình học lưới đổi,
  hiệu chỉnh đỉnh cũ **được cất** (`grid_adjusted.cu_*.json`) vì mã đỉnh đã đổi nghĩa. Lưới không phủ hết lô thì bị chặn và
  **khôi phục nguyên trạng**. `xuat` từ chối xuất số cũ khi lưới đã đổi mà chưa tính lại.
- Mọi đối tượng kết quả mang XDATA `SANNEN` (mã lô, đợt, hash, loại); layer mới `SN-MATCAT` cho mặt cắt.

## Palette SAN NỀN — bảng dọc dock được, nhiều tab (giai đoạn 16)

DCL không dock được, nên đây là add-in **.NET** (`cad/dotnet/SanNenPalette`, `PaletteSet` dock trái/phải/thả nổi, có nút Auto-hide;
AutoCAD tự nhớ kích thước/vị trí theo GUID, tab đang mở nhớ ở `%APPDATA%\SanNen\palette.ini`). C# chỉ **hiển thị và lấy chọn** —
không tính, không đọc `10_process/`; số liệu lấy qua `python -m sannen_cad.cau_noi thong-tin --json` (chạy nền, không chặn giao diện).

**Xây DLL một lần** (ngoài AutoCAD, Windows PowerShell; không cần SDK/NuGet, dùng `csc.exe` .NET Framework 4.x):

    powershell -ExecutionPolicy Bypass -File cad\dotnet\xay_palette.ps1

ra `cad\dotnet\bin\SanNenPalette.dll` (không commit vào git). Sửa mã C# thì xây lại; nếu AutoCAD đang giữ DLL cũ, script báo "đóng AutoCAD rồi chạy lại".

**Nạp:** gõ `SN_PALETTE` (sau khi đã nạp `sannen.lsp`): LISP tự `NETLOAD` DLL theo `cad=` trong `sannen.cfg` rồi gọi lệnh .NET
`SN_PALETTE_MO`; gõ lại để tắt. Chưa có DLL thì lệnh in đúng câu lệnh xây ở trên. Nếu AutoCAD hỏi tin cậy DLL (`SECURELOAD`), chọn
**Always Load** hoặc tự thêm `cad\dotnet\bin` vào `TRUSTEDPATHS` — hệ thống **không** sửa biến hệ thống của bạn. Muốn tự nạp mỗi lần mở
AutoCAD: thêm DLL vào APPLOAD → Startup Suite (hoặc để `sannen.lsp` nạp khi gõ `SN_PALETTE`).

| Tab | Nội dung | Nút (ghi → gọi lệnh LISP sẵn có, vẫn hỏi xác nhận trên dòng lệnh) |
|---|---|---|
| **QL ĐH** | Cây: Lô → Mô hình địa hình (MHTN mặt mốc / MHTK mặt đo, tam giác thiếu dữ liệu, đứt gãy, đồng mức, biên lô, loại trừ) → Lưới ô → Ranh đào–đắp → Mặt cắt (từng mặt cắt) → Bảng in. Hộp kiểm = Hiện/Ẩn layer (chỉ `IsOff`; không đóng băng/xoá; không đổi layer hiện hành; chỉ `SN-*`); số đối tượng của đúng lô+đợt. Chuột phải: Hiện/Ẩn · Chỉ hiện nhóm này · Zoom tới nhóm · Chọn đối tượng nhóm; bấm đúp = Zoom | Hiện/Ẩn tất cả SAN NỀN |
| **Biên lô** | số đỉnh, chu vi, diện tích, vùng loại trừ | Hiện/Ẩn biên · Zoom · `SN_NHAP` · `SN_LO` |
| **Lưới** | thông số lưới, ô thiếu dữ liệu, tổng diện tích ô vs lô; ô nhập Cột / Hàng (Số×KT,…) / Bù dữ liệu (m) | Áp dụng (`SN_LUOIAPDUNG`) · `SN_DICHLUOI` · `SN_XOAYLUOI` · Vẽ lại lưới (`SN_VE_NET` khi có `SanNenDraw.dll`, không thì `SN_VE`) · `SN_LUOI` |
| **Mặt cắt** | các mặt cắt đã tạo (dài, đào, đắp, thiếu) | `SN_MATCAT` · Zoom tới · Zoom tuyến A–B · Xoá (`SN_XOAMATCAT`, chỉ xoá bản vẽ, hỏi Yes/No) |
| **Khối lượng** | số nộp (lưới), số kiểm (lăng trụ), chênh %, ô lệch lớn, ba cổng, cảnh báo kết quả cũ | `SN_TINH` · `SN_BANG` · `SN_EXCEL` · `SN_XEM3D` · `SN_DUYET` (palette **không** tự duyệt cổng; chốt chặn ở `core/sannen/cong.py`) |
| **Cảnh báo** | cảnh báo QC, việc cần làm (`viec_can_lam.md`), kết quả cũ; bấm đúp = zoom tới điểm | `SN_CANHBAO` |

Làm mới: nút **↻ Làm mới** đầu mỗi tab; tự làm mới (trễ 0,6 s) khi một lệnh `SN_*` kết thúc và khi đổi bản vẽ. Python/cấu hình lỗi → dòng đỏ chỉ rõ
`sannen.cfg` (`python=`, `cad=`, `lot=`); Hiện/Ẩn layer vẫn dùng được. Mã C# theo lớp (`Models` · `Services/PythonBridge` · `Drawing` · `Ui/*Tab`);
các chỗ gọi lệnh LISP là tạm thời, sẽ chuyển sang C# ở bước 3 của `_agent/KIEN-TRUC-TOI-UU.md`.
## SanNenDraw — vẽ / xóa / vẽ lại bằng API từ KẾ HOẠCH JSON (bước 2 lộ trình kiến trúc tối ưu)

Python **quyết định vẽ gì**, C# **chỉ vẽ**. Lệnh cầu nối mới `ve-ke-hoach` (chỉ ĐỌC lô) xuất một file JSON `phien_ban: 1`; assembly thứ hai
`cad/dotnet/SanNenDraw/` → `SanNenDraw.dll` đọc và vẽ trong **một DocumentLock + một Transaction** (một lần Ctrl+Z hoàn tác cả lần vẽ).
Chỉ tham chiếu `accoremgd.dll` + `acdbmgd.dll` (không `acmgd`, không WinForms) nên cũng NETLOAD được trong `accoreconsole.exe`.

**Xây** (một lệnh xây cả hai DLL, `SanNenDraw.dll` trước vì palette tham chiếu nó; hai file phải nằm cùng `cad\dotnet\bin`):

    powershell -ExecutionPolicy Bypass -File cad\dotnet\xay_palette.ps1      # = xay_draw.ps1 rồi palette
    powershell -ExecutionPolicy Bypass -File cad\dotnet\xay_draw.ps1         # chỉ SanNenDraw.dll

| Lệnh .NET (nhóm `SANNEN_DRAW`) | Việc | Thay cho |
|---|---|---|
| `SN_VE_NET` | hỏi nhóm (`luoi,nhan,o,ranh,3d,bang`; **Enter = tất cả**) → Python dựng kế hoạch → xóa nhóm cũ của đúng lô+đợt → vẽ → in số đối tượng xóa/vẽ theo loại | `SN_VE` |
| `SN_XOA_NET` | đếm rồi **hỏi Yes/No** (mặc định No, RULES 4) → xóa đối tượng có XDATA khớp **lô + đợt hiện tại**; lô khác, đợt khác, nguồn không đụng | `SN_XOA` |
| `SN_XOA_NET_Y` | như trên **không hỏi** (cho kịch bản / LISP đã hỏi người dùng rồi) | — |
| `SN_TIN3D_NET` | hỏi Mốc / Đo / Cả hai → vẽ polyface (mỗi bề mặt MỘT đối tượng), bật lớp đã chọn + `SN-QC`, tắt lớp còn lại → SW Isometric + zoom + lưu view `SN_TIN3D`. **Không** ẩn layer khác (việc đó là của palette: Hiện/Ẩn) | `SN_TIN3D` (phần vẽ + view) |
| `SN_KEHOACH_NET` | vẽ thẳng một file kế hoạch JSON có sẵn (kịch bản, kiểm thử) | — |

**Chuyển tự động trong LISP:** nếu có `cad\dotnet\bin\SanNenDraw.dll`, `SN_VE`, `SN_XOA`, `SN_TIN3D` (và các chỗ LISP tự gọi `sn:ve`, như sau `SN_TINH`)
tự `NETLOAD` rồi gọi bản `_NET`; hộp thoại `SN_TIN3D` vẫn là DCL (chọn bề mặt / chỉ hiện 3D / tô bóng). **Thiếu DLL, hoặc đặt biến môi trường
`SANNEN_KHONG_NET=1`, thì chạy LISP cũ y nguyên.** Nút palette *Vẽ lại lưới* (tab Lưới) và *Xem 3D* (tab QL ĐH) gọi `SN_VE_NET` / `SN_TIN3D_NET` khi có DLL.
LISP và DCL chỉ gỡ ở bước 4 của lộ trình.

**Kế hoạch vẽ** (`python -X utf8 -m sannen_cad.cau_noi ve-ke-hoach --lot <lô> --ke-hoach <file.json> --ra <kq.json> --json [--lop luoi,nhan,o,ranh,3d,bang] [--dang polyface|3dface] [--che-do ve|tin3d|mat-cat --be-mat moc|do|ca-hai --ten <mặt cắt>]`;
hoặc trực tiếp `python -m sannen_cad.ke_hoach --lot <lô> --ra <file>`). Cùng lô + tham số → **cùng từng byte**. Lược đồ đầy đủ ở docstring `cad/sannen_cad/ke_hoach.py`:
`phien_ban`, `lenh`, `truy_vet {ma_lo, dot, hash_dau_vao}`, `xoa [{loai[, ex]}]`, `lop [{ten, mau, tat, dat_mau}]`,
`doi_tuong [{kieu: polyface|3dface|polyline|text|mtext, loai, lop, mau?, ex?, …}]`, `hien_lop`, `tom_tat`. Toạ độ làm tròn **4 chữ số thập phân**.
Mỗi đối tượng mang XDATA appid `SANNEN` đúng cấu trúc `sannen.lsp`: `(mã lô)(đợt)(hash)(loại)("k=v")…` — nên SN_QL, palette và `SN_XOA` đang có nhận ra đối tượng do C# vẽ.
Kết quả mỗi lệnh in ra dòng lệnh và ghi `sn_draw_kq.json` (thư mục `SANNEN_TMP` hoặc `%TEMP%`).

**Hiệu năng đo được** (accoreconsole, AutoCAD 2022, 100.000 thực thể = 60.000 polyline + 39.999 text + 1 polyface 20.100 đỉnh, JSON 14 MB):
vẽ 1,4 s trong một transaction; vẽ lần hai: purge 100.000 đối tượng 1,0 s + vẽ lại 1,3 s; cả lệnh (gồm đọc JSON) ≈ 3,5 s.
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
| `SN_QL`: lõi `thong_tin` đúng số liệu/«Chưa có»/deterministic/chỉ đọc/kết quả cũ; cầu nối `thong-tin`; ánh xạ nhóm→layer, đếm đúng lô (kể cả layer tắt), bật/tắt và khôi phục đúng, không đụng layer ngoài SN-*, không tắt layer hiện hành; cầu nối thật + vẽ thật rồi đếm khớp; `c:SN_QL` không sập khi không mở được hộp | ✅ `test_gd15_ql.py` (lõi + accoreconsole) |
| DCL `sn_ql` hợp lệ (ASCII, key khớp LISP, callback có định nghĩa, mã `done_dialog` đều được xử lý, vừa 1366) | ✅ kiểm tĩnh `test_gd12_*`, `test_gd15_ql.py` |
| **`SN_QL` hiển thị thật:** list_box nhiều cột bằng tab (`tabs`, font cố định), chọn nhiều dòng, cập nhật khung số liệu khi đổi dòng, vòng lặp đóng–chạy lệnh–mở lại, `REGEN` sau khi ẩn/hiện, zoom tới nhóm | ❌ cần AutoCAD có giao diện — chưa kiểm |
| **Palette .NET:** biên dịch sạch bằng `csc` (0 lỗi, C# 5); đủ 6 tab và lệnh `[CommandMethod]`; mọi lệnh LISP mà nút gọi đều tồn tại; ánh xạ nhóm→layer của C# khớp LISP và `LAYER_KET_QUA`; `thong-tin --json` parse được, đủ khoá, chỉ đọc; C# không tính/đọc `10_process/`; lệnh `SN_LUOIAPDUNG`/`SN_XOAMATCAT` có xác nhận | ✅ `test_gd16_palette.py` (tĩnh + biên dịch) |
| **Palette hiển thị thật:** dock trái/phải/thả nổi, nhiều tab, giao diện tối/sáng, cây + hộp kiểm Hiện/Ẩn, zoom/chọn, tự làm mới, `NETLOAD` + hỏi `SECURELOAD`, các nút gọi lệnh LISP | ❌ cần AutoCAD có giao diện — chưa kiểm || **Hiển thị hộp thoại DCL, menu thả xuống trên thanh menu, thao tác chọn điểm/đối tượng** | ❌ cần AutoCAD có giao diện — chưa kiểm |
| `VSCURRENT` Shaded with Edges (từ khóa `_E`) — accoreconsole treo khi gọi lệnh này nên không thử được | ❌ cần giao diện |
| Chữ có dấu trong DCL hiển thị đúng (set_tile trên text/nút/popup), bố cục các hộp thoại mới, ghi chú nhiều dòng | ❌ cần giao diện — chưa kiểm |
| Mở trình xem 3D (HTML) từ `SN_XEM3D`/nút: phụ thuộc verb `xem3d` của lõi và trình duyệt mặc định | ❌ chưa kiểm cuối-cuối (chỉ kiểm dòng lệnh do LISP/cầu nối dựng) |
| Bản vẽ rất lớn: thời gian nạp polyface hàng chục nghìn mặt (đã giảm số đối tượng từ hàng nghìn xuống 2) | ❌ chưa đo trên bản vẽ thật |
| **SanNenDraw (bước 2):** `ve-ke-hoach` đúng lược đồ, deterministic (hai lần cùng byte), chỉ đọc lô, số đối tượng khớp backend DXF; biên dịch sạch `SanNenDraw.dll` (chỉ accoremgd+acdbmgd) và palette tham chiếu nó | ✅ `test_gd17_drawengine.py` |
| **SanNenDraw trong AutoCAD 2022 thật không giao diện:** NETLOAD → `SN_KEHOACH_NET` / `SN_VE_NET` / `SN_XOA_NET(_Y)` / `SN_TIN3D_NET`: đếm theo layer + XDATA khớp kế hoạch **và khớp từng đối tượng do file .lsp vẽ**; vẽ hai lần không nhân đôi; purge chỉ đúng lô+đợt; mặt 3D = 1 polyface/bề mặt, layer 3D tắt, view `SN_TIN3D`; LISP `SN_VE`/`SN_XOA` chuyển sang `_NET` khi có DLL và lùi về LISP khi tắt; 100.000 thực thể | ✅ `test_gd17_drawengine.py` (accoreconsole) |
| **SanNenDraw trên giao diện:** hộp xác nhận Yes/No hiển thị, `SN_TIN3D` (DCL) → `SN_TIN3D_NET` → góc nhìn SW Isometric nhìn thấy được, nút palette *Vẽ lại lưới* / *Xem 3D*, tô bóng `VSCURRENT` sau `SN_TIN3D_NET`, hoàn tác (Ctrl+Z) một bước | ❌ cần AutoCAD có giao diện — chưa kiểm |
| Kế hoạch vẽ mặt cắt (`--che-do mat-cat`) có kiểm ở mức JSON; **lệnh C# vẽ mặt cắt (`SN_MATCAT`) chưa chuyển sang C#** (bước 3) | 🟡 |

### Checklist 5 phút để bạn kiểm giao diện
1. `APPLOAD` → `sannen.lsp`: có menu **SAN NỀN**? (không có thì gõ `SN`).
2. `SN_LOT` chọn lô → `SN_TRANGTHAI` hiện bước đã chạy và ba cổng. Rồi `SN_QL`: đầu hộp đúng lô/bước/cổng; bấm từng nhóm xem số liệu bên phải;
   [Ẩn] nhóm *Lưới ô* → lưới biến mất, số đối tượng vẫn hiện, [Hiện] → trở lại; [Chỉ hiện nhóm này] → mọi layer `SN-*` khác tắt, layer
   của nhà thầu vẫn hiện; [Hiện tất cả SAN NỀN]; [Zoom tới nhóm]; [Xem 3D…] → đóng xong hộp `SN_QL` tự mở lại.
3. `SN_TIN3D` → chọn *Cả hai* → [Hiển thị]: thấy mặt 3D (hai đối tượng polyface, thử `SELECT` một cái là chọn cả bề mặt); [Tắt 3D] ẩn lại.
   Tích *Chỉ hiển thị mặt 3D* rồi [Hiển thị]: các lớp khác tắt; mở lại hộp thoại → [Khôi phục lớp]: các lớp đó hiện lại. Nút [Mở trình xem 3D (HTML)] và lệnh `SN_XEM3D`.
4. `SN_LUOI` → đổi cột thành `1x10,4x22.5` → [Áp dụng]: lưới vẽ lại, tổng diện tích ô = diện tích lô.
5. `SN_MATCAT` → chọn 2 điểm cắt qua vùng đắp → có biểu đồ nằm dưới bảng khối lượng (không đè), bảng cao độ và diện tích đào/đắp.
   Khi chọn điểm A/B, dòng lệnh báo "đã tạm tắt osnap" và không còn báo *Too many objects selected for INTERSECT*.
6. Hộp thoại nào hiển thị sai chữ/ô: chụp màn hình gửi lại để chỉnh `sannen.dcl`.

### Checklist palette (5 phút, cần AutoCAD có giao diện)
1. Xây DLL: `powershell -ExecutionPolicy Bypass -File cad\dotnet\xay_palette.ps1` → "XONG". Trong AutoCAD: `APPLOAD` `sannen.lsp`, gõ `SN_PALETTE` (nếu hỏi tin cậy DLL → Always Load).
2. Hiện bảng dock trái, 6 tab, chữ có dấu, đúng màu tối/sáng; kéo sang phải / thả nổi / Auto-hide; gõ `SN_PALETTE` lần nữa → tắt.
3. Tab **QL ĐH**: số đối tượng đúng lô/đợt; bỏ tích *Lưới ô* → lưới biến mất, tích lại → hiện; layer hiện hành không bị tắt; chuột phải *Chỉ hiện nhóm này*, *Zoom tới nhóm*, *Chọn đối tượng nhóm*; bấm đúp = zoom.
4. Tab **Lưới**: nhập `1x10,4x22.5` → [Áp dụng] → dòng lệnh hỏi Yes/No (trả lời No thì lưới giữ nguyên). Tab **Mặt cắt**: [Xoá mặt cắt này] hỏi Yes/No.
5. Tab **Khối lượng / Cảnh báo / Biên lô**: số khớp `SN_TRANGTHAI`; bấm đúp một cảnh báo có toạ độ → zoom tới điểm. Tắt Python (đổi `python=` sai) → dòng đỏ nêu `sannen.cfg`, Hiện/Ẩn vẫn chạy.

### Checklist SanNenDraw (5 phút, cần AutoCAD có giao diện)
1. Xây hai DLL (`xay_palette.ps1`, đóng AutoCAD trước nếu nó đang giữ DLL cũ) → "XONG" hai lần. Trong AutoCAD: `APPLOAD` `sannen.lsp`.
2. Gõ `SN_VE` → dòng lệnh báo "Đang nạp SanNenDraw.dll" (lần đầu; chọn *Always Load* nếu hỏi) → hỏi nhóm: Enter. Phải thấy dòng "Đã xóa … đối tượng cũ … đã vẽ … đối tượng" và lưới/nhãn/ô/ranh hiện ra.
3. Gõ `SN_VE` lần nữa → "Đã xóa N … đã vẽ N" cùng N (không nhân đôi). `U` (hoàn tác) một lần → lần vẽ vừa rồi biến mất trọn.
4. `SN_TIN3D` → *Cả hai* → [Hiển thị]: hai polyface, góc nhìn SW Isometric vừa khít, view `SN_TIN3D` có trong `-VIEW`. Gõ `SN_TIN3D_NET` trực tiếp → hỏi Mốc/Đo/Cả hai.
5. `SN_XOA` → báo "Xóa N đối tượng … [Yes/No] <No>": trả lời No → không đổi; Yes → sạch lô này, lô khác (nếu có trong bản vẽ) còn nguyên.
6. Palette → tab **Lưới** [Vẽ lại lưới], tab **QL ĐH** [Xem 3D]: thấy cùng kết quả như trên.