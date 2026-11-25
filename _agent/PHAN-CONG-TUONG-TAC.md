# Bảng phân công và cách tương tác — Người · Agent · Tool lõi · Add-in C#

Dành cho QS chủ đầu tư. Căn cứ: `KIEN-TRUC-TOI-UU.md` (đã duyệt 2026-11-24) và RULES 1–12.
Cột **Trạng thái** ghi thật: ✅ chạy rồi · 🟡 có nhưng đang dùng đường tạm (LISP) · ⏳ theo lộ trình, chưa làm.

## 1. Bốn vai, một câu mỗi vai

| Vai | Một câu | Không bao giờ |
|---|---|---|
| **Bạn (QS)** | Quyết định và duyệt; nhìn trên bản vẽ và chỉ chỗ cần sửa | Phải gõ từng lệnh kỹ thuật |
| **Agent (Claude)** | Điều phối thứ tự, chạy xem trước, trình việc cần quyết, diễn giải kết quả | Tính số · tự duyệt cổng · tự chọn kích thước ô/gốc/góc |
| **Tool lõi** (`sannen` CLI + MCP) | Sinh mọi con số, chặn cổng, ghi log và hash | Biết AutoCAD là gì |
| **Add-in C#** (palette `SN_PALETTE`) | Vẽ vào bản vẽ, bật/tắt lớp, lấy điểm/đối tượng bạn chọn, hiện trạng thái | Tính toán · tự ghi quyết định |

## 2. Ai làm gì ở từng bước

| # | Bước | Bạn quyết / làm | Agent làm | Tool lõi tính | Add-in hiển thị / nhận chọn | Trạng thái |
|---|---|---|---|---|---|---|
| 1 | **Nhập** số liệu khảo sát | Chọn file; trả lời mã việc `V-xx` (giữ/bỏ điểm) | Chạy `nhap --preview`, soạn việc cần làm | Đọc DXF/Excel, QC, đánh số `V-xx` | Tab Cảnh báo, zoom tới điểm nghi vấn | ✅ lõi · 🟡 CAD |
| 2 | **Bề mặt** (TIN mốc/đo) + biên lô | Chấp nhận đứt gãy, ngưỡng QC, biên lô | Chạy `mat`, `lo`; đọc QC; diễn giải | TIN ràng buộc, chuẩn hóa biên | Xem 3D (`SN_TIN3D`), cây QL ĐH, mặt cắt A–B (bạn chọn 2 điểm) | ✅ · 🟡 |
| ◆ | **CỔNG 2 — duyệt bề mặt** | **Bạn nói rõ "duyệt"** | Trình `viec_can_lam.md`, không tự duyệt | Ghi dấu vân tay; **chặn `luoi`, `tinh` khi chưa duyệt** | Nút Duyệt (`SN_DUYET`) | ✅ |
| 3 | **Lưới** ô vuông | **Bạn quyết**: kích thước ô, gốc, góc, cách bù thiếu | Đề xuất phương án, chạy `--sweep`, nêu cận dưới | Dựng lưới, đánh giá ô | Tab Lưới, `SN_LUOI` (chọn vùng/gốc), vẽ lưới | ✅ · 🟡 |
| 4 | **Tính** khối lượng | Chỉ định đỉnh cần sửa tay nếu có (`SN_SUADINH`) | Chạy `tinh`, đặt số nộp cạnh số kiểm, giải thích chênh lệch | Số nộp (lưới) + số kiểm (lăng trụ), kiểm diện tích | Nhãn ô, ranh đào–đắp, tab Khối lượng | ✅ · 🟡 |
| ◆ | **CỔNG 3 — duyệt số liệu** | **Bạn nói rõ "duyệt"** | Trình số + chênh lệch, không tự duyệt | **Chặn `xuat` khi chưa duyệt** | Nút Duyệt | ✅ |
| 5 | **Xuất** hồ sơ | Ký | Chạy `xuat`, soạn thuyết minh | Workbook 7 sheet, bảng in, truy vết (dòng 3 và 8 = 0) | Vẽ bảng in vào bản vẽ | ✅ · 🟡 |

(Cổng 1 — dữ liệu sau `nhap` — cùng cơ chế: người duyệt mới chạy tiếp.)

## 3. Ba kênh để bạn tương tác

| Kênh | Dùng khi | Ví dụ |
|---|---|---|
| **Chat với Agent** | Quyết định, duyệt, hỏi "vì sao", nhờ chạy bước | "Duyệt cổng 2." · "V-02 b" · "Chạy lưới 20 m, gốc như cũ." |
| **Palette trong AutoCAD** (`SN_PALETTE`) | Nhìn, bật/tắt lớp, zoom, chọn điểm/đối tượng, xem số liệu | Tab QL ĐH tích Hiện/Ẩn · tab Khối lượng xem số nộp/số kiểm |
| **Dòng lệnh** (`python -m sannen.cli …`) | Chạy tay, kiểm tra, kịch bản hóa | `… cli tinh --lot <thư mục lô> --preview` |

Palette và CLI **không bao giờ** tự ghi quyết định thay bạn; chúng chỉ ghi lại lời bạn.

## 4. Cách trả lời để Agent hiểu đúng

- **Mã việc:** trả lời ngắn theo mã. `V-02 b` = chọn phương án b cho việc V-02. Agent không đoán khi bạn chưa chọn.
- **Duyệt cổng:** viết rõ cổng nào, ví dụ "Duyệt cổng 2 — bề mặt." Hệ thống ghi **nguyên văn câu của bạn** vào
  `cong.json` và `decisions.md`. Chỉ "ok" hoặc im lặng thì Agent **không** được coi là duyệt.
- **Quyết định kỹ thuật** (kích thước ô, gốc, góc, bù thiếu, ngưỡng QC): bạn nêu giá trị; Agent đề xuất nhưng không tự chọn.
- **Đổi ý sau khi duyệt:** nếu số liệu đổi, phê duyệt cũ **mất hiệu lực** (dấu vân tay lệch) → duyệt lại.

## 5. Chuỗi thao tác một lô, từ lời bạn đến hồ sơ

    1  Bạn: "Chạy lô 01-CGP." → Agent: nhap --preview → trình danh sách V-xx
    2  Bạn: trả lời mã việc          → Agent: nhap (ghi), mat, lo → trình bề mặt; bạn xem 3D trong CAD
    3  Bạn: "Duyệt cổng 2."         → Tool ghi duyệt → mở khóa luoi, tinh
    4  Bạn: nêu ô/gốc/góc/bù thiếu  → Agent: luoi, (sweep), tinh → trình số nộp, số kiểm, chênh lệch
    5  Bạn xem nhãn ô, ranh, mặt cắt trong CAD; sửa đỉnh nếu cần
    6  Bạn: "Duyệt cổng 3."         → Tool mở khóa xuat → Agent: xuat → Excel + bảng in + thuyết minh
    7  Bạn ký

## 6. Quy tắc an toàn (cứng)

1. **Con số chỉ sinh ra ở lõi.** Agent và add-in không tính.
2. **Cổng do người duyệt**; CLI từ chối ghi khi cổng chưa duyệt, cho **mọi lối vào** (chat, MCP, CAD, dòng lệnh).
3. **`00_input/` không bao giờ bị ghi.** Kết quả vẽ vào bản vẽ đang mở, chỉ mất khi bạn lưu.
4. **Lệnh ghi thử nghiệm chạy trên bản sao lô**, không chạy trên lô thật (lô 01-CGP từng bị ghi đè lưới 10×10 do chạy thử;
   đã khôi phục, có dòng đính chính trong `decisions.md`).
5. **`decisions.md` chỉ ghi quyết định của người và duyệt cổng**; nhật ký thao tác của công cụ nằm ở `90_log/run_*.jsonl`.
6. Vẽ lại luôn xóa kết quả cũ **của đúng lô** trước (không đè nhau); `SN_XOA` chỉ xóa đối tượng có dấu truy vết của lô này.

## 7. Đang ở đâu so với lộ trình

| Bước lộ trình | Nội dung | Trạng thái |
|---|---|---|
| 0 | Commit mốc hiện trạng | ✅ `feec7f8` (đã push) |
| 1 | Palette C# 6 tab | ✅ build + nạp; hiển thị cây và tab Khối lượng đã thấy đúng; các tab còn lại chưa thử |
| 2 | Python xuất kế hoạch vẽ JSON (`ve-ke-hoach`) · C# `DrawEngine` (`SanNenDraw.dll`) · `SN_VE_NET`, `SN_XOA_NET`, `SN_TIN3D_NET` (LISP `SN_VE`/`SN_XOA`/`SN_TIN3D` tự chuyển sang khi có DLL) | ✅ **phần kiểm được không giao diện** (accoreconsole thật: vẽ hai lần không đè, purge đúng lô+đợt, XDATA khớp LISP, 100.000 thực thể ≈ 3,5 s); ⏳ chưa kiểm trên GUI: hộp Yes/No, nút palette *Vẽ lại lưới*/*Xem 3D*, góc nhìn thấy được, Ctrl+Z |
| 3 | `SN_LUOI_NET`, `SN_DICHLUOI_NET`, `SN_XOAYLUOI_NET`, `SN_LUOI_BO_NET`, `SN_SUADINH_NET`, `SN_DONGBO_NET`, `SN_DUYET_NET`, `SN_MATCAT_NET`, `SN_XOAMATCAT_NET`, `SN_BANG_NET`, `SN_TAOMAT_NET`, `SN_CHONBIEN_NET`, `SN_CHONDUTGAY_NET` sang C#; gộp MCP thành một server `sannen-mcp` theo ý định (`sannen_ve`, `sannen_thong_tin`, `sannen_canh_bao`, `sannen_ra_soat_phuong_an`) | ✅ **Hoàn tất mã C#, LISP định tuyến tự động sang C#, MCP & kiểm thử** |
| 4 | Gỡ LISP/DCL, cầu nối s-expression, backend COM rỗng | ⏳ (chỉ sau khi C# qua checklist GUI từng lệnh) |
| 5 | Dọn `Tham khao/`, hợp nhất `AGENTS.md`, cập nhật README | ⏳ |

## 8. Việc còn chờ bạn quyết (chưa chốt)

- Ngưỡng "ô lệch lớn" (hiện 5 % / 10 m³): **chưa chốt**.
- Lớp "Bờ đắp cao/thấp" có coi là đường đứt gãy không.
- Đối chiếu biên san lấp 74 đỉnh với bản vẽ thiết kế lần cuối.
- Số nộp theo lưới hiện dùng giá trị **bù** ở vùng thiếu dữ liệu (lấy điểm gần nhất, tối đa 25 m); cần thay bằng số đo thật khi khảo sát đo bù ra ngoài biên.
