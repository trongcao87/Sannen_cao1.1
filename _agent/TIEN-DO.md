# Nhật ký tiến độ và bàn giao — SanNen-Agent

Dành cho mô hình/phiên làm việc tiếp theo. Đọc theo thứ tự: `CLAUDE.md` → `_agent/RULES.md` → `_agent/KIEN-TRUC-TOI-UU.md`
→ `_agent/PHAN-CONG-TUONG-TAC.md` → file này. **Cập nhật mục 1 và mục 6 mỗi khi xong một việc.**

Cập nhật lần cuối: 2026-11-24 (sau bước 2 lộ trình, commit `c447956`, đã push lên
`https://github.com/trongcao87/Sannen_cao1.1.git`, nhánh `master`).

## 1. Trạng thái hiện tại (một nhìn)

| Hạng mục | Trạng thái |
|---|---|
| Lõi Python (nhập, mặt TIN, biên lô, lưới, tính, xuất, MCP lõi, cổng duyệt ở CLI) | ✅ chạy trên lô thật 01-CGP + mở rộng nhận nguồn chọn thủ công từ CAD/Excel (`nguon_tuy_chinh.yaml`, `khoi-tao-be-mat`) |
| Test | **304 pass, 1 skip** (`cd core; python -m pytest -q`) |
| Palette C# 6 tab (`SN_PALETTE`) | ✅ build, nạp, hiển thị cây QL ĐH, Biên lô, Lưới, Mặt cắt, Khối lượng, Cảnh báo; có nút khởi tạo bề mặt (`DD_DH`), chọn Breakline, chọn Biên lô, Tạo lưới |
| DrawEngine C# (`SanNenDraw.dll`: `SN_VE_NET`, `SN_XOA_NET`, `SN_TIN3D_NET`, `SN_MATCAT_NET`, `SN_XOAMATCAT_NET`, `SN_BANG_NET`, `SN_LUOI_NET`, `SN_DICHLUOI_NET`, `SN_XOAYLUOI_NET`, `SN_LUOI_BO_NET`, `SN_SUADINH_NET`, `SN_DONGBO_NET`, `SN_DUYET_NET`, `SN_TAOMAT_NET`, `SN_CHONBIEN_NET`, `SN_CHONDUTGAY_NET`) | ✅ Bước 3 hoàn thành 100% lệnh C# và biên dịch sạch; script build sửa tên assembly chuẩn `SanNenDraw` + `AssemblyResolve` |
| MCP (`core/sannen/mcp_server.py`) | ✅ Đã gộp `sannen_thong_tin`, `sannen_canh_bao`, `sannen_ve` + thêm `sannen_ra_soat_phuong_an` (chỉ chạy rà soát/chuẩn hóa/quét phương án khi người dùng đã khởi tạo bề mặt thành công) |
| LISP/DCL (`cad/lisp/sannen.lsp`, `sannen.dcl`) | ✅ Đã dọn và tự động định tuyến sang lệnh `*_NET` của C# khi có `SanNenDraw.dll` (tự xử lý `FILEDIA=0` khi `NETLOAD`), giữ tương thích 100% với bộ test GĐ11–17 |
| Bước tiếp theo | **Kiểm tra GUI Bước 3** rồi sang **Bước 4** (gỡ LISP/DCL) |

Lô 01-CGP (đợt 1): lưới 7×5 ô 20 m, 23 ô trong lô; **số nộp** đào 10.985 m³, đắp 5.576,452 m³; **số kiểm** (lăng trụ)
đào 68,299 m³, đắp 7.812,175 m³; diện tích ô = diện tích lô 4.974,2839 m². Cổng 2 và 3 đã duyệt ngày 2026-11-24 12:45
(bằng chứng «Duyệt, tính lại»); chênh số nộp–số kiểm còn lớn (đào −83,9 %, đắp −28,6 %, 19 ô lệch lớn) → "CẦN GIẢI THÍCH".

## 2. Các mốc commit

| Commit | Nội dung |
|---|---|
| `14df3c0` | GĐ0: khung, schema, KB, skill, CLI 7 verb, `nhap` |
| `8e6b13c` | GĐ1–9: nhập, mặt TIN, biên lô, lưới, tính, xuất, MCP, MCP CAD, menu SAN NỀN, polyface, trình xem 3D HTML |
| `feec7f8` | GĐ10–16: bảng điều khiển `SN_QL`, `thong_tin`, cổng duyệt ở CLI (`cong.py`), palette C# nhiều tab, kiến trúc tối ưu |
| `c447956` | Bước 2: `ve-ke-hoach` (JSON), `SanNenDraw.dll`, `SN_VE_NET`/`SN_XOA_NET`/`SN_TIN3D_NET` |

Quy ước: mỗi bước một commit; người dùng tự `git push` (máy phiên Claude không đăng nhập GitHub được).

## 3. Môi trường và cách chạy

- Python: `C:\Users\Mr.Cao\AppData\Local\Programs\Python\Python314\python.exe` (đã `pip install -e ".[dev]"` trong `core`).
  Dùng `-X utf8` hoặc `PYTHONIOENCODING=utf-8` khi in tiếng Việt từ PowerShell.
- Cấu hình CAD: `%APPDATA%\SanNen\sannen.cfg` (`python=`, `cad=`, `lisp=`, `lot=`), ghi bằng `cad\cai_dat_cad.ps1`
  (**file .ps1 phải có BOM UTF-8**, nếu không Windows PowerShell 5.1 lỗi dấu tiếng Việt).
- Build C#: `powershell -ExecutionPolicy Bypass -File cad\dotnet\xay_palette.ps1` (xây `SanNenDraw.dll` rồi `SanNenPalette.dll`
  vào `cad\dotnet\bin\`, không commit DLL). Chỉ `csc.exe` của .NET Framework 4.x → **C# 5 tối đa**, không SDK/NuGet.
  AutoCAD khoá DLL đang nạp: muốn xây lại `SanNenPalette.dll` phải **đóng AutoCAD** (script dùng file tạm và báo rõ).
- AutoCAD 2022 thật (cửa sổ người dùng đang dùng): nạp bằng `(load "F:/.../cad/lisp/sannen.lsp")`, rồi `SN_PALETTE`
  (gõ lần đầu nạp DLL, lần hai mở bảng). Test không giao diện dùng `accoreconsole.exe` (xem `test_gd11`, `test_gd12`, `test_gd14`, `test_gd17`).

## 4. BƯỚC 3 — việc tiếp theo (chưa làm)

Mục tiêu: chuyển các lệnh còn lại của LISP sang C# và gộp MCP. Chỉ gỡ LISP ở **bước 4**, sau khi từng lệnh C# qua checklist GUI.

1. `SN_MATCAT` C#: người chọn hai điểm A, B bằng chuột (`Editor.GetPoint`, tắt osnap tạm thời, khôi phục kể cả khi ESC) → gọi
   `ve-ke-hoach --che-do mat-cat` (đã có ở mức JSON) → `DrawEngine` vẽ. Vị trí đặt mặc định dưới toàn bộ kết quả của lô
   (đệm ≥ 30 m, canh trái theo hộp bao) như bản LISP.
2. `SN_LUOI` C#: hộp thoại/tab Lưới (kích thước ô, cột/hàng `Số×KT`, góc, gốc, bù thiếu), chọn vùng/gốc bằng chuột;
   ghi qua `luoi-sua` của cầu nối (ghi `luoi_tuy_chinh.yaml`, cất `grid_adjusted` cũ khi mã đỉnh đổi nghĩa, hỏi xác nhận RULES 4).
   Lưới không phủ hết lô → chặn và khôi phục nguyên trạng.
3. `SN_SUADINH` (gộp `SN_CAPDO`, `SN_NANGCD`): chọn đỉnh bằng chuột, nhập cao độ; chênh cao tự tính lại.
4. `SN_DONGBO`: đọc nhãn sửa tay trong bản vẽ → báo chênh lệch trước, hỏi rồi mới nhận (`luoi --resync`).
5. `SN_DUYET`: nút duyệt cổng tại chỗ; **bắt buộc ghi nguyên văn câu người nói** (`cong.duyet_cong`: `nguoi_duyet`, `bang_chung`).
   Add-in không được tự điền bằng chứng.
6. Gộp MCP: một server `sannen-mcp` theo **ý định** (`sannen_ve(lop=[…], preview)`, `sannen_thong_tin`, `sannen_canh_bao`),
   bỏ nguyên thủy `cad_draw_*` khỏi tầm agent; vẫn chặn cổng qua `cong.py`. Hiện còn `core/sannen/mcp_server.py` + `cad/sannen_cad/mcp_cad_server.py`.
7. Bảng đơn giản `SN_BANG` (tong / tong-hop / o) và `luoi-sua` chưa có chế độ kế hoạch riêng; nhóm `bang` trong `ve_ket_qua`
   đã đi qua kế hoạch. Bảng đang vẽ bằng LWPOLYLINE + TEXT, chưa dùng `Table` của AutoCAD.
8. Cập nhật `cad/MENU.md` (bảng Đã kiểm/Chưa kiểm), `PHAN-CONG-TUONG-TAC.md` §7, và mục 1 file này.

Sau bước 3: **bước 4** gỡ LISP/DCL, backend LISP, cầu nối s-expression, `BackendCOM` rỗng; **bước 5** dọn `Tham khao/`,
hợp nhất `AGENTS.md` với `CLAUDE.md`, cập nhật README + lộ trình CLAUDE.md. (Chi tiết: `KIEN-TRUC-TOI-UU.md` §5.)

## 5. Luật cứng và bài học đã trả giá

**Luật nghiệp vụ** (RULES, không thương lượng):
- Con số chỉ sinh ra ở lõi Python; Agent và add-in C# **không tính**.
- Cổng 1/2/3 do **người** duyệt; CLI từ chối ghi khi cổng chưa duyệt (cho mọi lối vào). Agent **không được tự duyệt**:
  phải có câu nguyên văn của người trong chat. Kết quả đổi sau khi duyệt → phê duyệt mất hiệu lực (dấu vân tay).
- Kích thước ô/gốc/góc/cách bù thiếu: người quyết. `00_input/` không bao giờ bị ghi. Đổi ngưỡng QC → ghi `decisions.md`.
- `decisions.md` chỉ chứa quyết định của người và duyệt cổng; nhật ký thao tác công cụ vào `90_log/run_*.jsonl`.

**Bài học vận hành (đã xảy ra thật):**
1. **Không chạy lệnh ghi lên lô thật 01-CGP để thử.** Lần chạy thử của một tác tử đã ghi `luoi_tuy_chinh.yaml` (lưới 10×10) và
   tính lại khối lượng sai, kèm 3 dòng giả vào `decisions.md`. Đã khôi phục (xoá file lưới, `luoi → tinh → xuat` theo `lot.yaml`) và ghi
   dòng đính chính. **Thử nghiệm ghi: dùng lô giải tích `core/tests/lot_giai_tich.py` hoặc bản sao lô trong thư mục tạm.**
   Chỉ lệnh đọc (`thong-tin`) được chạy trên lô thật.
2. **Đừng xoá file trong `20_output/` khi chưa chắc nguồn gốc** (đã lỡ xoá `matcat_MC2.csv` của người dùng; vẽ lại MC2 là có lại).
3. **Công cụ computer-use:** `open_application "AutoCAD 2022 - English"` **luôn mở thêm một phiên AutoCAD mới** thay vì đưa cửa sổ
   cũ lên trước — không dùng. Cửa sổ AutoCAD của người dùng nằm ở **màn hình thứ hai** (`switch_display` sang `EGM24F75`).
   Hệ thống chặn việc tắt tiến trình, nên phải nhờ người dùng đóng cửa sổ thừa. Gõ vào dòng lệnh: bấm vào dòng lệnh trước, dán bằng
   `type` (tiếng Việt qua clipboard được); nếu báo "Claude's own window has keyboard focus" thì bấm lại vào AutoCAD.
4. Chọn điểm trên bản vẽ có 3D dày: osnap Intersection báo "Too many objects selected" → tắt osnap tạm (bit 16384 của `OSMODE`)
   rồi khôi phục. `ZOOM W` trong LISP phải truyền điểm bằng hàm riêng (điểm không quote bị hiểu là lời gọi hàm → ZOOM treo).
5. DCL: file `.dcl` chỉ ASCII, mọi chữ có dấu do LISP đặt bằng `set_tile`; `load_dialog` trả −1 trong accoreconsole nên hộp thoại chỉ kiểm được trên GUI.
6. AutoCAD 2022 `(open f "r" "UTF-8")` không hỗ trợ; tránh `\` trong chuỗi LISP; không có `nthcdr`; tạo layer trước khi tạo thực thể.
7. PowerShell 5.1: file `.ps1` và `.cs` cần BOM; truyền chuỗi tiếng Việt vào lệnh dễ hỏng dấu (ghi file bằng công cụ Write thay vì
   `Set-Content`/here-string); `Set-Content -Encoding utf8` thêm BOM — Python `exec` file đó sẽ lỗi U+FEFF.
8. Nhiều tác tử song song: giao theo **tập file không giao nhau**; luôn tự chạy lại toàn bộ pytest sau khi tác tử báo xong
   (báo cáo của tác tử không phải bằng chứng).

## 6. Việc người dùng còn chờ quyết (chưa chốt)

- Ngưỡng "ô lệch lớn" (hiện 5 % / 10 m³).
- Lớp "Bờ đắp cao/thấp" có coi là đường đứt gãy không.
- Đối chiếu lần cuối biên san lấp 74 đỉnh với bản vẽ thiết kế.
- Số nộp theo lưới đang dùng giá trị **bù** ở vùng thiếu dữ liệu (`diem_gan_nhat`, tối đa 25 m); thay bằng số đo thật khi có đo bù.
- Chưa so với Civil 3D (chưa có phần mềm) — mục "lệch Civil 3D dưới 0,1 %" của GĐ5 còn treo.
- Chênh số nộp–số kiểm (19 ô lệch lớn) cần giải thích trong sheet `03_DOICHIEU`.

## 7. Chưa kiểm trên AutoCAD có giao diện (checklist cho phiên có GUI)

Palette: ô tích Hiện/Ẩn trên cây, chuột phải (Chỉ hiện nhóm này, Zoom, Chọn), nhấp đôi zoom, tab Biên lô/Lưới/Mặt cắt/Cảnh báo,
dock trái/phải/thả nổi, màu sáng/tối. Lệnh: `SN_VE_NET`, `SN_XOA_NET` (hộp Yes/No), tô bóng `VSCURRENT`, Ctrl+Z hoàn tác.
Hiệu năng nạp bản vẽ hàng chục nghìn đối tượng (headless đã đo: 100.000 thực thể ≈ 3,5 s cả lệnh). Chi tiết: cuối `cad/MENU.md`.
