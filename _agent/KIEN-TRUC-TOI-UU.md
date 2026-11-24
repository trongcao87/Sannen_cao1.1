# Kiến trúc tối ưu — C# là lớp CAD duy nhất, vai trò Người · Agent · Tool · Add-in

Ngày chốt: 2026-11-24. Tài liệu này **thay thế** sơ đồ bốn lớp ở SPEC §1 về phần "AutoCAD qua MCP CAD" và
tiếp thu bản rà soát `RASOAT-KIEN-TRUC.md`. RULES 1–12 không đổi.

## 1. Quyết định

| | Trước (đã xây) | Tối ưu (chốt) |
|---|---|---|
| Lớp CAD | LISP 1.544 dòng + DCL + cầu nối s-expression + backend sinh `.lsp` + COM rỗng | **Một add-in C#** (.NET Framework 4.8, build bằng `csc.exe`, không SDK/NuGet): palette dock nhiều tab + lệnh `SN_*` |
| Vẽ vào bản vẽ | Python sinh file `.lsp`, AutoCAD nạp bằng `entmake` | Python xuất **kế hoạch vẽ JSON** (`ve-ke-hoach`), C# đọc và vẽ trực tiếp bằng API (polyface, polyline, text, bảng) có XDATA `SANNEN` |
| Hộp thoại | DCL, chữ không dấu, không dock | Palette `PaletteSet` dock trái/phải, TreeView + tab, chữ Unicode |
| Lõi tính | Python thuần, headless | **Giữ nguyên** — C# không chứa dòng logic nghiệp vụ nào |
| Agent | MCP lõi (11 tool) + MCP CAD (13 tool, không dùng được) | **Một MCP** theo ý định (`sannen_ve`, `sannen_thong_tin`, `sannen_canh_bao`…) |

Vì sao C# là tối ưu cho lớp CAD: dock được (LISP/DCL không làm được); chọn điểm/đối tượng, bật tắt layer, zoom, xoay 3D
bằng API chính thức; vẽ hàng chục nghìn thực thể nhanh và có giao dịch (Transaction) nên hoàn tác được; chữ Unicode đầy
đủ; biên dịch bắt lỗi trước khi chạy (LISP chỉ lộ lỗi lúc nạp); một ngôn ngữ cho một lớp. Cái giá: cần AutoCAD có giao diện
để kiểm tra hiển thị (headless không chạy `PaletteSet`) — vì vậy C# phải **mỏng**, phần kiểm được dồn về lõi.

## 2. Hình dạng hệ thống

    NGƯỜI ── chat ──► AGENT ── MCP (một server) ──┐
       │                                          ▼
       │                                   sannen.cli  ◄── cong.py: MỘT chốt chặn ba cổng cho mọi lối vào
       │                                          ▼
       │                                   LÕI Python (số, file, headless) ──► 10_process · 20_output · 90_log
       │                                          ▲
       └── AutoCAD ── Add-in C# (mỏng) ── JSON ───┘
              palette + SN_VE + chọn điểm       thong-tin --json · ve-ke-hoach · luoi-sua · …

Hợp đồng C# ↔ Python: **chỉ JSON qua tiến trình con** (`python -m sannen_cad.cau_noi …`), chạy nền, không chặn giao diện.
C# không đọc `10_process/` trực tiếp, không tự tính, không giữ trạng thái riêng ngoài trạng thái hiển thị.

## 3. Phân vai theo từng bước của quy trình

| Bước | NGƯỜI (QS) quyết/làm | AGENT điều phối | TOOL lõi (CLI/MCP) tính | ADD-IN C# hiển thị/lấy chọn |
|---|---|---|---|---|
| 1. Nhập | Chọn file khảo sát, biên lô, trả lời mã việc `V-xx` (giữ/bỏ điểm) | Chạy `nhap` preview, soạn `viec_can_lam.md`, hỏi gọn | Đọc DXF/Excel, QC, đánh số `V-xx`, log + hash | Bảng cảnh báo, zoom tới điểm nghi vấn |
| 2. Bề mặt | Chấp nhận/giữ đứt gãy, ngưỡng QC | Chạy `mat` + `lo`, đọc kết quả, diễn giải | TIN ràng buộc, nội suy, chuẩn hóa biên | Xem 3D (polyface), mặt cắt A–B (người chọn 2 điểm) |
| **Cổng 2** | **Duyệt bề mặt (nguyên văn)** | Trình `viec_can_lam.md`, **không tự duyệt** | Ghi dấu vân tay; chặn `luoi/tinh` nếu chưa duyệt | Nút "Duyệt" tại chỗ nhìn kết quả |
| 3. Lưới | Quyết kích thước ô, gốc, góc, cách bù thiếu (RULES 9) | Đề xuất phương án, chạy `--sweep`, nêu cận dưới | Dựng lưới, đánh giá ô, sweep | Chọn vùng/gốc bằng chuột, hộp lưới, vẽ lưới |
| 4. Tính | Chỉ định đỉnh cần sửa tay nếu có | Chạy `tinh`, so số nộp–số kiểm, giải thích chênh lệch | Số nộp (lưới) + số kiểm (lăng trụ), kiểm diện tích | Nhãn ô, ranh đào–đắp, bảng tổng |
| **Cổng 3** | **Duyệt số liệu** | Trình số + chênh lệch, **không tự duyệt** | Chặn `xuat` nếu chưa duyệt | Nút "Duyệt" |
| 5. Xuất | Ký hồ sơ | Chạy `xuat`, soạn thuyết minh | Workbook 7 sheet, bảng in, truy vết (dòng 3 & 8 = 0) | Vẽ bảng in vào bản vẽ |

**Ranh giới cứng** (không ai được vượt):
- Con số chỉ sinh ra ở lõi (RULES 1). Agent và C# **không tính**.
- Cổng duyệt do **người** nói; agent và add-in chỉ ghi lại nguyên văn câu của người (RULES 4). Chốt chặn nằm ở `cong.py`,
  CLI từ chối ghi khi cổng chưa duyệt — cho mọi lối vào, không chỉ MCP.
- Kích thước ô/gốc/góc/cách bù thiếu: **người quyết** (RULES 9); agent đề xuất, không tự chọn.
- `00_input/` không bao giờ bị ghi. Add-in vẽ vào bản vẽ đang mở, chỉ mất khi người lưu.
- Thử nghiệm lệnh ghi chạy trên **bản sao lô**, không bao giờ trên lô thật (bài học 2026-11-24: lần chạy thử đã ghi đè lưới
  lô 01-CGP; đã khôi phục và ghi đính chính trong `decisions.md`).
- `decisions.md` chỉ chứa quyết định của người và duyệt cổng; nhật ký thao tác công cụ vào `90_log/run_*.jsonl`.

## 4. Add-in C# — phạm vi (mỏng)

Palette "SAN NỀN" (tab: QL ĐH · Biên lô · Lưới · Mặt cắt · Khối lượng · Cảnh báo) cộng các lệnh chỉ CAD làm được:

| Lệnh | Vì sao ở trong CAD |
|---|---|
| `SN_PALETTE` | cửa vào duy nhất: lô, trạng thái ba cổng, cây quản lý, cảnh báo |
| `SN_VE` / `SN_XOA` | vẽ/vẽ lại theo nhóm, purge theo XDATA của đúng lô |
| `SN_TIN3D` | polyface liền khối + góc nhìn SWISO |
| `SN_LUOI` | chọn vùng/gốc trên bản vẽ |
| `SN_SUADINH` | chọn đỉnh bằng chuột |
| `SN_MATCAT` | chọn hai điểm A, B |
| `SN_CANHBAO` | zoom tới điểm nghi vấn |
| `SN_DONGBO` | đọc nhãn sửa tay |
| `SN_DUYET` | người bấm duyệt tại chỗ |

Không đưa vào add-in: bọc CLI từng verb (`SN_NHAP`, `SN_MAT`, `SN_TINH`… → làm bằng chat hoặc nút "Chạy bước kế tiếp"),
tám lệnh sửa lưới nhanh (một hộp lưới đủ), công cụ thiết kế (taluy, hướng dốc, offset 3D).

Cấu trúc mã C# để dễ kiểm: `Services/PythonBridge` (gọi CLI, parse JSON), `Models` (DTO), `Drawing/DrawEngine`
(thực thi kế hoạch vẽ), `Ui/*Tab`. Logic phân tích JSON và ánh xạ nhóm→layer tách khỏi lớp giao diện để biên dịch và test tĩnh được.

## 5. Lộ trình chuyển đổi (mỗi bước một commit, mỗi bước có cửa kiểm)

| # | Việc | Cửa qua |
|---|---|---|
| 0 | Commit hiện trạng GĐ10–15 làm mốc | `pytest` xanh |
| 1 | Palette C# (6 tab) gọi lệnh LISP sẵn có cho thao tác ghi | build `csc` sạch; thử GUI checklist |
| 2 | `ve-ke-hoach` (Python) + `DrawEngine` (C#): vẽ/purge/vẽ lại bằng API; `SN_VE`, `SN_XOA`, `SN_TIN3D` | vẽ hai lần không đè; purge sạch; 100.000 đối tượng nạp < ngưỡng đo được |
| 3 | `SN_LUOI`, `SN_SUADINH`, `SN_MATCAT`, `SN_DONGBO`, `SN_DUYET` sang C#; gộp hai MCP thành một theo ý định | GUI: toàn bộ checklist qua |
| 4 | **Gỡ LISP/DCL, backend LISP, cầu nối s-expression, BackendCOM** | không còn tham chiếu; test lõi giữ nguyên số |
| 5 | Dọn `Tham khao/`, hợp nhất `AGENTS.md`, cập nhật README + lộ trình | tài liệu khớp mã |

Quy tắc chuyển: **không gỡ LISP cho tới khi C# qua checklist GUI của từng lệnh**; hai lớp cùng tồn tại tới bước 4.

## 6. Điều chưa kiểm / rủi ro
- Palette C# chưa từng chạy trong AutoCAD có giao diện; `SECURELOAD`/`TRUSTEDPATHS` có thể hỏi tin cậy DLL lần đầu.
- `csc.exe` của .NET Framework 4.x chỉ hỗ trợ C# 5 — đủ cho add-in này, không dùng cú pháp mới.
- Hiệu năng (đã đo ở bước 2, accoreconsole): 100.000 thực thể vẽ trong một transaction ≈ 1,4 s, cả lệnh gồm đọc JSON 14 MB ≈ 3,5 s; chưa đo trên bản vẽ thật có sẵn hàng triệu đối tượng.
- Đề xuất "đọc lưới nhà thầu từ DXF" (RASOAT §3.4) chỉ làm nếu lô thật có lưới trong DXF.
