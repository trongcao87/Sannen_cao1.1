# Ngưỡng QC mặc định

Ngưỡng riêng cho một lô thì ghi đè trong `lot.yaml` của lô đó; file này giữ nguyên.
Đổi ngưỡng là quyết định của người và phải ghi vào `90_log/decisions.md`.

| Khóa | Ngưỡng | Mặc định | Dùng ở verb |
|---|---|---|---|
| `trung_mat_bang_mm` | Hai điểm trùng mặt bằng | 1 mm | `nhap` |
| `mad_he_so` | \|Z − trung vị\| > k×MAD trên 8 điểm gần nhất | k = 3 | `nhap` |
| `mad_san_m` | Sàn cho MAD — xem ghi chú dưới | 0,02 m | `nhap` |
| `giao_dutgay_cm` | Chênh cao tại giao điểm hai đứt gãy | 1 cm | `mat` |
| `goc_tam_giac_det_do` | Góc nhỏ nhất của tam giác | 5° | `mat` |
| `tam_giac_lon_boi` | Cạnh dài hơn k lần khoảng cách điểm trung bình | k = 3 | `mat` |
| `cung_tron_sai_so_mm` | Sai số đỉnh cung khi bung LWPolyline | 5 mm | `lo` |
| `area_lech_pct` | Diện tích lệch so lệnh AREA | 0,01 % | `lo` |
| `o_lech_lon_pct` | Ô lệch lớn giữa lưới và lăng trụ | **CHƯA CHỐT** — đề xuất 5 % | `tinh` |
| `o_lech_lon_m3` | hoặc theo m³, lấy giá trị lớn hơn | **CHƯA CHỐT** — đề xuất 10 m³ | `tinh` |
| `civil3d_lech_pct` | Lệch khi đối chiếu Civil 3D | 0,1 % | kiểm chứng lõi |

## Đã kiểm chứng 23/11/2026

Cung tròn trong biên lô bắt buộc phải bung. Cùng một biên có một cạnh cung:
nối thẳng qua bulge → 6.000,00 m²; bung với sai số đỉnh 5 mm → 6.628,84 m².
Lệch 9,5 %. Bung 50 mm so 5 mm chỉ lệch 0,008 %, nằm trong ngưỡng 0,01 %,
nên 5 mm là đủ chặt.

## Vì sao MAD cần một cái sàn

Phát hiện 23/11/2026 khi chạy thử: bề mặt SAU san lấp gần như phẳng (cao độ dao động
vài centimet), nên MAD của 8 điểm lân cận tiến về 0 và gần như mọi điểm đều vượt
3×MAD — phép kiểm báo hàng trăm nghi vấn giả. Sàn `mad_san_m` đặt bằng sai số đo cao
độ cho phép của đơn vị khảo sát; dưới ngưỡng đó thì chênh lệch là nhiễu đo, không
phải lỗi nhập. Mặc định 2 cm; lô nào khảo sát chặt hơn thì ghi đè trong `lot.yaml`.
