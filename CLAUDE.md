# SanNen-Agent — hướng dẫn cho phiên Claude Code

## Dự án này là gì
Hệ thống tính khối lượng san nền đào/đắp cho QS chủ đầu tư, phục vụ nghiệm thu
thanh toán theo đợt. Bốn lớp: con người quyết định · agent điều phối ·
`sannen-core` tính deterministic · AutoCAD 2022 hiển thị và hiệu chỉnh qua MCP.

Đọc `_agent/SPEC.md` trước khi viết dòng mã đầu tiên. Đọc `_agent/RULES.md` và
tuân thủ 12 điều trong đó — chúng là ràng buộc nghiệp vụ, không phải gợi ý.

## Nguyên tắc kiến trúc không được phá
1. **Lõi không biết AutoCAD là gì.** `core/sannen/` chỉ làm việc với số và file.
   Nhờ vậy test chạy trong vài giây và không cần mở AutoCAD.
2. **Đầu vào DXF đọc headless, đầu ra DWG qua MCP CAD.** Hai chiều hai cơ chế.
3. **Deterministic.** Cùng đầu vào luôn cho cùng số. Đảo thứ tự điểm, xoay hay
   dịch toàn bộ dữ liệu không được làm đổi kết quả — có test cho việc này.
4. **Dời gốc toạ độ về trọng tâm trước mọi phép tính hình học.** VN-2000 có
   E≈445.000, N≈1.113.000; bình phương những số này trong phép thử đường tròn
   ngoại tiếp làm mất gần hết chữ số có nghĩa. Bỏ bước này là nguồn lỗi khó tìm
   nhất của cả dự án.

## Lộ trình — làm theo thứ tự, mỗi giai đoạn một commit

| GĐ | Nội dung | Điều kiện qua cửa |
|---|---|---|
| 0 ✅ | Khung thư mục, schema, KB, skill, CLI 7 verb, `nhap` chạy thật | `pytest` xanh; `nhap` đọc đúng số điểm |
| 1 | `nhap` đầy đủ: thêm nguồn Excel, ánh xạ cột nhớ lại được | Báo đúng điểm lỗi cố ý cài; 11.000 điểm dưới 5 s |
| 2 | `mat`: TIN có ràng buộc đứt gãy, QC tam giác, tra cứu cao độ | Sai số nội suy so mặt giải tích ≈ 0; không cạnh nào cắt qua đứt gãy |
| 3 | `lo`: chuẩn hóa biên, phép cắt | Diện tích khớp lệnh AREA dưới 0,01 % |
| 4 | `luoi` + `hieuchinh` | Tổng diện tích các ô = diện tích lô |
| 5 | `tinh`: ô lưới + lăng trụ + `--sweep` | Khớp nghiệm giải tích; lệch Civil 3D dưới 0,1 % |
| 6 | `xuat`: workbook 7 sheet, bảng in CAD, truy vết, thuyết minh | Dòng 3 và dòng 8 bảng tổng khớp = 0 |
| 7 | MCP server bọc CLI | Agent chạy trọn một lô từ yêu cầu bằng lời, dừng đúng 3 cổng |
| 8 | MCP CAD: 13 tool + 3D Face | Vẽ vào bản vẽ thật rồi purge sạch, chạy hai lần không đè nhau |

Giai đoạn 2 là chỗ dễ sa lầy nhất. Nếu sau hai tuần ràng buộc đứt gãy chưa ổn,
bỏ ràng buộc ở bản đầu (chuyển đứt gãy thành chuỗi điểm dày) để đi tiếp, quay lại sau.

## Cách làm việc
- Chạy test trước khi commit: `cd core && python -m pytest -q`
- Mỗi giai đoạn qua cửa là một commit. Mục 14 của SPEC yêu cầu chạy lại bộ dữ liệu
  chuẩn mỗi lần sửa lõi — có git mới biết lần sửa nào làm số lệch đi.
- Thêm test vào `core/tests/` theo ba tầng: nghiệm giải tích · kiểm tra tính chất ·
  đối chiếu phần mềm khác.
- Không thêm dependency nặng. Hiện chỉ `ezdxf` và `PyYAML`; `openpyxl` cho giai đoạn 6.
- Viết comment và thông báo bằng tiếng Việt — người đọc là QS, không phải lập trình viên.

## Cài
    cd core && pip install -e ".[dev]"
    python -m sannen.cli nhap --lot ../projects/KDT-DaiThanh/lots/01-CGP --preview
