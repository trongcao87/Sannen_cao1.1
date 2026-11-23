---
name: xuat
mo_ta: Soạn workbook 7 sheet, bảng in trong CAD, phiếu truy vết, thuyết minh phương pháp.
giai_doan: 6
---
# xuat

## Lệnh
    python -m sannen.cli xuat --lot <thư mục lô> [--preview]

`--preview` là MẶC ĐỊNH. Bỏ nó chỉ sau khi người duyệt nội dung (RULES 4).

## Ra
`20_output/`: `KL_<lô>_<đợt>.xlsx`, `doi_chieu_2pp.xlsx`, `bang_in_cad.json`,
`phieu_truy_vet.json`, `thuyet_minh_phuong_phap.md`.

Mẫu biểu lấy từ `kb/mau-bieu.md`. Căn cứ pháp lý nêu trong thuyết minh lấy từ
`kb/can-cu-phap-ly.md`.

## Ba điều kiện khớp phải đạt trước khi ghi
- Dòng 3 bảng tổng khớp = 0 (tổng bảng chi tiết = tổng bảng tổng hợp)
- Dòng 8 = 0 (diện tích đào + đắp = diện tích lô trừ vùng loại trừ)
- Dòng 5 ≤ ngưỡng ô lệch lớn, hoặc giải thích được bằng `03_DOICHIEU`

Dòng 3 hoặc 8 khác 0 là lỗi phần mềm: DỪNG, không làm tròn cho khớp.

## Thuyết minh phương pháp phải nêu
Phương pháp đo bóc, nguồn số liệu khảo sát, bề mặt mốc, biên lô, và "đã xử lý gì trên
mô hình" — phần cuối lấy từ `90_log/decisions.md`.

## Cổng cuối
Người duyệt nội dung và ký biên bản nghiệm thu.
