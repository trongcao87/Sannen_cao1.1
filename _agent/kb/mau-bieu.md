# Mẫu biểu

## Workbook nộp — bảy sheet

| Sheet | Nội dung |
|---|---|
| `00_TONGKHOP` | Bảng tổng khớp (dưới) — mở file thấy đầu tiên |
| `01_BANG_O` | Từng ô: tên ô, diện tích hữu hiệu, cao độ TB mốc, cao độ TB đo, chênh cao TB, KL đào, KL đắp, DT đào, DT đắp |
| `02_TONGHOP_LO` | Tổng theo lô và theo đợt, có dòng lũy kế các đợt |
| `03_DOICHIEU` | Theo từng ô: lưới · lăng trụ · chênh m³ · chênh % · cờ ô lệch lớn |
| `04_MA_TRAN_PA` | Toàn bộ PA bảng A và B, kèm phân bố quét gốc × phương |
| `05_QC` | Điểm nghi vấn, tam giác dẹt/quá lớn, vùng thiếu dữ liệu, kèm tọa độ |
| `06_TRUYVET` | File gốc, số điểm, hash đầu vào, tham số lưới, phiên bản lõi, ngày giờ |

Mọi ô tổng trong `00_TONGKHOP` là CÔNG THỨC tham chiếu sang sheet chi tiết,
không phải số dán cứng.

## Bảng tổng khớp `00_TONGKHOP`

| # | Chỉ tiêu | Đào (m³) | Đắp (m³) | DT đào (m²) | DT đắp (m²) | Điều kiện khớp |
|---|---|---|---|---|---|---|
| 1 | Cộng từ bảng chi tiết từng ô | Σ 01_BANG_O | Σ | Σ | Σ | — |
| 2 | Bảng tổng hợp lô | Σ 02_TONGHOP_LO | Σ | Σ | Σ | (2) = (1) |
| 3 | Chênh lệch (1) − (2) | | | | | **phải bằng 0** |
| 4 | Số kiểm theo lăng trụ (PA B3) | | | | | — |
| 5 | Chênh lệch (1) − (4), m³ và % | | | | | ≤ ngưỡng ô lệch lớn |
| 6 | Tổng diện tích đào + đắp | — | — | cộng ngang | | — |
| 7 | Diện tích lô theo AREA, trừ vùng loại trừ | — | — | | | (7) = (6) |
| 8 | Chênh lệch (6) − (7) | — | — | | | **phải bằng 0** |

Dòng 3 hoặc 8 khác 0 là LỖI PHẦN MỀM: dừng, tìm nguyên nhân, không làm tròn cho khớp.
Dòng 5 vượt ngưỡng không phải lỗi — là chuyện phải giải thích, và `03_DOICHIEU` chỉ ra
nó nằm ở những ô nào.

## Bảng in trong bản vẽ

Khổ A3 ngang, ba khối:
- **Tiêu đề**: tên dự án, tên lô, đợt nghiệm thu, phương pháp đo bóc, ngày,
  ba ô ký Lập – Kiểm – Duyệt.
- **Thân**: 7 cột từ `01_BANG_O` (tên ô, diện tích, cao độ TB mốc, cao độ TB đo,
  chênh cao TB, KL đào, KL đắp) + dòng TỔNG.
- **Chân**: tổng đào, tổng đắp, tổng diện tích, ghi chú phương pháp và bề mặt mốc.

Lô nhiều ô: tách nhiều khối cạnh nhau trên cùng khung, mỗi khối tối đa 40 dòng,
chỉ khối cuối mang dòng TỔNG — và tổng đó phải bằng đúng dòng 1 của bảng tổng khớp.

## Ghi chú triển khai (giai đoạn 6)

- Ô **thiếu dữ liệu** (RULES 8) không vào số nộp và không cộng vào DT đào/đắp. Vì vậy dòng 7 = diện tích lô theo AREA
  trừ vùng loại trừ **trừ diện tích các ô thiếu dữ liệu**, để dòng 8 vẫn phải bằng đúng 0. Ô thiếu dữ liệu được liệt kê
  trong `01_BANG_O` (cột Ghi chú), `03_DOICHIEU` (cờ) và `05_QC`.
- Dòng 5: cột E, F mang **%** (so với lăng trụ), cột C, D mang m³. Ô `00_TONGKHOP!C14:C15` giữ hai ngưỡng.
- Hai ngưỡng ô lệch lớn vẫn CHƯA CHỐT (SPEC mục 10).
