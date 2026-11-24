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

## Ghi chú triển khai (giai đoạn 1–3, ghi 23/11/2026)

- **Cung tròn.** Mục "đã kiểm chứng" ở trên dùng cách bung đỉnh-nằm-trên-đường-tròn. Cách đó thiếu diện tích cỡ
  4s/(3r) — cung bán kính nhỏ có thể vượt 0,01 %. Lõi giờ tự bung bulge và đặt đỉnh giữa ở bán kính
  ρ = r·√(Δθ/sinΔθ) để giữ nguyên diện tích hình quạt; `cung_tron_sai_so_mm` giờ là độ lệch hình học tối đa tới cung thật.
  Sai số diện tích đo được ~1e-6 (50× dưới ngưỡng).
- **Cao độ bất thường (`mad_he_so`).** Trên lô 01-CGP, 9 % điểm bị đánh dấu — toàn là đỉnh ta luy / mặt bãi của bờ đắp,
  lân cận là nền thấp. Phép kiểm giờ hai vòng: (1) lệch khỏi trung vị 8 điểm lân cận; (2) điểm nào lọt vòng 1 mà
  **khớp được mặt phẳng của 8 điểm lân cận** (trong `mad_he_so` lần độ lệch chuẩn dư, sàn `mad_san_m`) thì không
  báo. Lỗi gõ nằm giữa nền sạch vẫn bị bắt. Số điểm bị đánh dấu trên 01-CGP: 55 → 5 mỗi bề mặt.
- **Tam giác quá lớn (`tam_giac_lon_boi`).** Cạnh dài hơn k·d **và** diện tích hơn tam giác đều cạnh k·d. Chỉ xét
  cạnh thì điểm đo phân bố ngẫu nhiên tự sinh ra ~2 % tam giác "quá lớn" mà không có lỗ hổng dữ liệu nào.
- **Dải mép.** Tam giác dẹt ở mép TIN (góc < `goc_tam_giac_det_do`) bị loại đúng đặc tả — nghĩa là điểm đo phải phủ
  THỪA ra ngoài biên lô vài mét, nếu không dải sát biên thành "thiếu dữ liệu".
