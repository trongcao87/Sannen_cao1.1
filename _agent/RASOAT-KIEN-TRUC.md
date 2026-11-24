# Rà soát kiến trúc SanNen-Agent — 2026-11-24

Phạm vi: đọc SPEC, RULES, AGENTS, CLAUDE, `core/sannen/*`, `cad/*` (LISP, DCL, cầu nối, backend, MCP CAD),
MCP lõi, danh mục test. **Chưa chạy lại bộ test** (máy này không có `python` trong PATH của phiên) —
mọi con số "đã kiểm" dưới đây lấy từ tài liệu của dự án, không phải do tôi tái kiểm.
Báo cáo này CHỈ đề xuất; chưa sửa dòng mã nào.

---

## 1. Hình dạng thật của hệ thống (khác với sơ đồ trong SPEC)

SPEC §1 vẽ bốn lớp, trong đó agent điều khiển AutoCAD "qua MCP CAD". Thực tế đã hình thành **ba lối vào**
cùng đổ về một CLI:

    Agent ──MCP lõi (11 tool)──┐
    Người ──dòng lệnh──────────┼──► sannen.cli ──► lõi tính ──► 10_process / 20_output
    Người ──AutoCAD: sannen.lsp (33 lệnh) ──► cau_noi.py (17 lệnh) ──┘
                                              └──► backend_lisp ──► file .lsp ──► nạp vào bản vẽ

    Agent ──MCP CAD (13 tool) ──► BackendDXF (file DXF)         ← KHÔNG chạm bản vẽ đang mở
                              └─► BackendCOM (khung rỗng)       ← chưa bao giờ cài

Quy mô (ước theo dung lượng file): lõi Python ≈ 290 KB; lớp CAD ≈ 205 KB (LISP 100 KB + DCL 14 KB + Python 94 KB);
test phục vụ lớp CAD (gd8, gd11, gd12, gd14, gd15) ≈ 138 KB trên tổng ≈ 242 KB test — **hơn một nửa công test
nằm ở phần "hiển thị"**, và phần khó kiểm nhất (hộp thoại, menu) vẫn chưa kiểm được (MENU.md, bảng ❌).

## 2. Phát hiện (xếp theo mức nghiêm trọng)

### P1 — Cổng duyệt chỉ chặn ở MCP, không chặn ở CLI và CAD  *(rủi ro nghiệp vụ thật)*
- `cong_da_duyet` được gọi duy nhất trong `mcp_server.goi_verb`. `cli.py` không kiểm cổng.
- `cau_noi.l_chay` và nút `SN_EXCEL`/`SN_TINH`/`SN_MAT` đi thẳng `sannen.cli` → xuất Excel khi cổng 3 chưa duyệt vẫn chạy
  (chỉ còn "hỏi xác nhận" trong hộp thoại LISP, đó là thói quen chứ không phải ràng buộc).
- RULES 4 và ba cổng là xương sống của hệ thống; hiện chúng là tính năng của *một* lối vào.
- Hệ quả liên quan: logic cổng sống trong `mcp_server.py` nên `thong_tin.py` (lõi) và `cau_noi.py` (CAD) phải
  `import mcp_server` — phụ thuộc ngược tầng (lõi → lớp giao thức).

### P1 — Vòng lặp "agent vẽ → người xoay 3D" trong SPEC §8 chưa có đường thật
- Agent chỉ có `sannen_cad.mcp_cad_server`, mà server này chỉ dựng được backend `dxf` (ghi file mới) hoặc `com` (khung rỗng).
- Vẽ vào bản vẽ đang mở thực ra chỉ xảy ra khi **người** gõ lệnh `SN_*` trong AutoCAD (backend LISP).
- Nghĩa là 13 tool CAD cho agent là *hợp đồng không có người dùng*: agent không có cách nào kích hoạt bản vẽ của QS.

### P2 — Add-in AutoCAD đã trôi từ "hiển thị + hiệu chỉnh" sang "sao chép SNVN"
- MENU.md tự ghi "Không làm: taluy, thiết kế…, vì đây là công cụ *thiết kế*", nhưng bảng đối chiếu SNVN cho thấy vẫn
  dựng lại 8 lệnh sửa lưới theo cột/hàng, cộng ô, nâng cao độ hàng loạt, quản lý lớp theo nhóm.
- Thư mục `Tham khao/` (bản sao ứng dụng SNVN, 31 file được git theo dõi) là nguồn kéo phạm vi; nó không thuộc hệ thống.
- LISP 1.544 dòng là file lớn nhất repo, bằng ngôn ngữ khó test nhất, 33 lệnh. Ba phần lớn nhất đều là
  pass-through: hộp thoại gọi CLI rồi nạp .lsp.

### P2 — Nhiều nơi giữ "sự thật" và "quyết định"
`lot.yaml` · `luoi_tuy_chinh.yaml` · `grid_adjusted.json` · `cong.json` · `decisions.md` · `%APPDATA%\SanNen\sannen.cfg`.
Dấu hiệu rò: `decisions.md` của lô 01-CGP có **hai dòng "Hộp thoại SN_LUOI" y hệt nhau lúc 12:30** (ghi trùng).
RULES 11 nói đổi ngưỡng/quyết định phải vào `decisions.md`; hiện cả quyết định của người lẫn nhật ký thao tác của công cụ
cùng đổ vào đó nên không còn là sổ quyết định sạch.

### P3 — Trùng lặp và tồn đọng
| Mục | Vấn đề |
|---|---|
| Hai cách xem 3D | `SN_TIN3D` (polyface + ẩn/khôi phục lớp ≈ 100 dòng LISP) và `xem3d` HTML (28 KB mẫu, kiểm được headless) |
| `SN_QL` (≈ 400 dòng LISP, chưa commit) | Trùng `SN_TRANGTHAI` + `SN_CANHBAO` + trạng thái lớp có sẵn của AutoCAD; `thong_tin.py` chưa được phơi cho agent (không có `sannen_thong_tin`) |
| Menu thả xuống tạo bằng COM | Chưa kiểm trên giao diện; `SN` dòng lệnh đã đủ |
| `BackendCOM` | Khung rỗng, docstring thôi; mang theo cờ `--backend com` và tài liệu |
| `AGENTS.md` (Codex) và `CLAUDE.md` | Hai bản gần giống nhau, sẽ lệch dần; `README.md` còn ghi "Giai đoạn 0 xong" |
| Lộ trình CLAUDE.md dừng ở GĐ8 | MENU.md nói GĐ9–15 đã làm; commit duy nhất gộp GĐ1–9 trái luật "mỗi giai đoạn một commit"; GĐ10–15 còn nằm trong working tree |

## 3. Kiến trúc đề xuất

Nguyên tắc: **một đường thực thi, một nơi chặn cổng, add-in chỉ làm điều CAD làm tốt nhất.**

    NGƯỜI ── chat ──► AGENT ── MCP (một server) ──► sannen.cli ──► LÕI
       │                                              ▲   ▲
       └── AutoCAD add-in (mỏng) ──► cau_noi ─────────┘   └─ cong.py: MỘT chốt chặn cổng cho mọi lối vào

1. **`core/sannen/cong.py`** (mới): chuyển `TEN_CONG, CONG_CAN, dau_van_tay, doc_cong, viec_chan, cong_da_duyet,
   duyet_cong` ra khỏi `mcp_server.py`. **CLI tự chặn** mọi verb ghi khi `--preview` không bật mà cổng chưa duyệt
   (hoặc kết quả đã đổi từ lúc duyệt). MCP, CLI, CAD đều hưởng cùng một chốt. Test cổng viết một lần ở tầng CLI.
2. **Một MCP server** `sannen-mcp`: gộp nhóm lõi (verb, trạng thái, việc, quyết định, duyệt) và nhóm CAD, nhưng
   đổi mức trừu tượng — agent gọi **ý định**, không gọi **nguyên thủy**:
   `sannen_ve(lop=[…], preview)` thay cho `cad_draw_grid/cad_label_cells/cad_draw_3dface/…`;
   thêm `sannen_thong_tin` (nuôi cả agent lẫn bảng trạng thái CAD) và `sannen_canh_bao`.
   Bỏ khỏi tầm agent: `cad_read_points`, `cad_read_polylines` (lõi đã đọc DXF headless), `cad_export_dxf`, `cad_zoom_to`
   (để add-in lo — zoom là việc của mắt người).
3. **Add-in thu về 10 lệnh** (từ 33), mỗi lệnh có lý do tồn tại mà chat/CLI không thay được:

   | Giữ | Vì sao phải ở trong CAD |
   |---|---|
   | `SN` (một hộp thoại trung tâm: lô, trạng thái ba cổng, danh sách cảnh báo, các nút bên dưới) | cửa vào duy nhất, thay `SN_LOT`, `SN_TRANGTHAI`, `SN_QL`, `SN_MENU` |
   | `SN_VE` (vẽ/vẽ lại theo nhóm, tự purge) | chỉ CAD mới nạp được .lsp |
   | `SN_XOA` | purge theo XDATA của đúng lô |
   | `SN_TIN3D` (vẽ polyface + SWISO) | người cần xoay bằng mắt (đã là yêu cầu của anh/chị) |
   | `SN_LUOI` (một hộp thoại) | chọn vùng trên bản vẽ |
   | `SN_SUADINH` (gộp `SN_CAPDO`, `SN_NANGCD`) | chọn đỉnh bằng chuột |
   | `SN_MATCAT` | chọn hai điểm A, B |
   | `SN_CANHBAO` (zoom tới điểm nghi vấn) | zoom là mắt người |
   | `SN_DONGBO` | đọc nhãn sửa tay — chỉ CAD đọc được |
   | `SN_DUYET` | người bấm duyệt tại chỗ nhìn kết quả |

   **Đề xuất bỏ:** `SN_NHAP`, `SN_MAT`, `SN_LO`, `SN_LUOITINH`, `SN_TINH`, `SN_EXCEL` (chỉ bọc CLI — làm bằng chat hoặc
   một nút "Chạy bước kế tiếp" trong hộp thoại `SN`); `SN_DOICOT/CHENCOT/XOACOT/DOIHANG/CHENHANG/XOAHANG/DICHLUOI/XOAYLUOI`
   (tám lệnh nhanh — hộp thoại `SN_LUOI` đã làm đủ); `SN_CONGO` (tra bằng `o-tai` hoặc Excel); `SN_QL` (hấp thụ vào `SN`);
   tính năng "Chỉ hiển thị mặt 3D" + khôi phục lớp (dùng `LAYISO/LAYUNISO` sẵn có); tạo menu COM (dùng `SN`, hoặc
   partial CUIX sau khi kiểm giao diện); `SN_XEM3D` giữ như một **nút**, không phải lệnh riêng.
   Ước lượng: LISP 1.544 → khoảng 700 dòng; DCL còn 4–5 hộp thoại.
4. **Thay "sửa lưới tay" bằng "đọc lưới nhà thầu"** (đề xuất nghiên cứu): A1 = *lưới theo bản vẽ nhà thầu*. Nếu `luoi`
   đọc thẳng đường lưới trong DXF (layer đã khai) thì không cần 8 lệnh dựng lại lưới bằng tay và `luoi_sua.py` co lại.
   Cần xác nhận với dữ liệu thật trước khi chốt.
5. **Dọn nợ**: xóa `BackendCOM` và `--backend com`; ghi rõ trong SPEC rằng backend LISP là đường vào CAD chính thức;
   chuyển `Tham khao/` ra ngoài repo (hoặc `docs/tham-khao/`, bỏ khỏi git); hợp nhất `AGENTS.md` vào một file
   (CLAUDE.md trỏ tới `_agent/AGENTS.md`); cập nhật README và lộ trình GĐ9–15; sửa lỗi ghi trùng `decisions.md`.
6. **Tách sổ**: `decisions.md` chỉ giữ quyết định của người (mã việc, duyệt cổng). Nhật ký thao tác công cụ
   (đổi lưới từ CAD, resync…) ghi vào `90_log/run_*.jsonl` — đã sẵn có.

## 4. Vai trò sau tối ưu

| | Làm | Không làm |
|---|---|---|
| **Người (QS)** | Quyết: biên lô, ô lưới, cách bù thiếu, ngưỡng QC, giữ/bỏ điểm, chấp nhận số, ký. Nhìn và chỉ: xoay 3D, chọn đỉnh/tuyến, zoom cảnh báo. Trả lời gọn bằng mã việc (`V-02 b`). | Gõ lệnh từng verb; sửa file trong `10_process/`; thao tác lặp (vẽ lại, purge) |
| **Agent** | Điều phối thứ tự verb; chạy preview; đọc kết quả; soạn `viec_can_lam.md` sáu trường; diễn giải chênh lệch lưới–lăng trụ; ghi quyết định đúng nguyên văn; gợi ý bước kế tiếp từ `sannen_thong_tin` | Tính số (RULES 1); tự duyệt cổng; tự chọn kích thước ô/gốc/góc (RULES 9); gọi nguyên thủy vẽ CAD; sửa dữ liệu đo |
| **Tool (lõi + CLI)** | Mọi con số; **chặn cổng** (RULES 4) cho mọi lối vào; ghi log + hash (RULES 10); kiểm schema; sinh file .lsp | Biết AutoCAD là gì; hỏi người |
| **Add-in CAD** | Vẽ/purge theo XDATA; lấy điểm/đối tượng bằng chuột; đọc nhãn sửa tay; hiển thị trạng thái + cảnh báo; nút duyệt tại chỗ | Chạy logic nghiệp vụ; giữ trạng thái riêng; tính; tái tạo công cụ thiết kế |

Tác dụng: người chạm hệ thống ở **ba cổng + các mã việc**; agent không có đường tắt vòng qua người; mọi lối vào chia sẻ
một chốt chặn; lớp CAD co lại còn khoảng một phần ba, dồn công test về lõi (kiểm được headless).

## 5. Thứ tự thực hiện đề xuất

| # | Việc | Rủi ro | Ghi chú |
|---|---|---|---|
| 1 | Commit hiện trạng (GĐ10–15) làm mốc, trước khi đụng gì | thấp | working tree đang có 4 file sửa + 3 file chưa theo dõi |
| 2 | `cong.py` + CLI chặn cổng + test cổng ở tầng CLI | trung (đụng đường chính) | sửa P1 nghiệp vụ; làm trước mọi cắt gọt |
| 3 | `sannen_thong_tin`, `sannen_ve`, `sannen_canh_bao`; gộp hai MCP; bỏ BackendCOM | thấp | không đổi số liệu |
| 4 | Cắt add-in: bỏ lệnh bọc CLI, 8 lệnh nhanh, `SN_CONGO`, COM menu, ẩn lớp; gộp `SN_QL` vào `SN` | trung | cần AutoCAD có giao diện để kiểm lại — hiện vẫn ❌ |
| 5 | Dọn tài liệu, `Tham khao/`, tách sổ quyết định | thấp | |
| 6 | Thử đọc lưới nhà thầu từ DXF | cần dữ liệu | chỉ làm nếu lô thật có lưới trong DXF |

## 6. Điều tôi chưa kiểm
- Chưa chạy `pytest` (không có `python` trong PATH của phiên này).
- Chưa xác nhận bằng chạy thật việc CLI/`SN_EXCEL` vượt cổng — kết luận P1 dựa trên đọc mã (không thấy lời gọi
  kiểm cổng nào ngoài `mcp_server.py` và `test_gd7_mcp.py`).
- Không rõ `luoi_tuy_chinh.yaml` và các sửa đổi chưa commit có đang được anh/chị dùng cho đợt nghiệm thu nào không.
