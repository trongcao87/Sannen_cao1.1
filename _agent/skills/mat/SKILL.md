---
name: mat
mo_ta: Dựng TIN Delaunay có ràng buộc đứt gãy, soát tam giác xấu, dựng mặt 3D để soát mắt.
giai_doan: 2
---
# mat

## Lệnh
    python -m sannen.cli mat --lot <thư mục lô> [--be-mat moc|do|ca-hai]

Hai bề mặt dựng ĐỒNG THỜI được. Verb này chạy song song với `lo`.

## Bắt buộc trước mọi phép tính
Dời gốc toạ độ về trọng tâm khu đất trước khi tính, cộng lại khi vẽ ra CAD.
Toạ độ VN-2000 (E≈445.000, N≈1.113.000) bình phương trong phép thử đường tròn ngoại
tiếp sẽ mất gần hết chữ số có nghĩa → lưới sinh tam giác chồng chéo. Kèm theo đó dùng
phép thử hình học chính xác thích nghi (orient2d, incircle). Bỏ hai thứ này là nguồn
lỗi khó tìm nhất của cả dự án.

## Hai pha
1. **Delaunay thuần** — O(n log n).
2. **Ép ràng buộc** — với mỗi đoạn breakline, lật cạnh để tạo đúng cạnh đó, rồi khôi
   phục Delaunay quanh vùng nhưng không lật cạnh đã ràng buộc.

Trước khi ép: làm sạch tập breakline. Tìm giao điểm, chèn đỉnh, cắt đoạn. Nếu cao độ
nội suy của hai đường tại giao điểm lệch quá `giao_dutgay_cm` thì BÁO LỖI, không tự
chọn — đó là mâu thuẫn dữ liệu thật.

## QC bề mặt
- **Tam giác dẹt**: góc nhỏ nhất < `goc_tam_giac_det_do`. Nội suy trên tam giác gần
  suy biến khuếch đại sai số. Ở mép thì là tam giác rác → loại. Trong vùng dữ liệu →
  cảnh báo, KHÔNG tự dời điểm đo.
- **Tam giác quá lớn**: cạnh > `tam_giac_lon_boi` × khoảng cách điểm trung bình → đục lỗ.
  Nếu nằm trong biên lô cần tính → cảnh báo "vùng thiếu dữ liệu", yêu cầu đo bổ sung
  (RULES 8).

## Ra
`surface_moc.json`, `surface_do.json`, `qc_surface.json`, và layer `SN-3DF-*`,
`SN-QC` trong bản vẽ khi MCP CAD có sẵn.

## Cổng 2
Người xoay mặt 3D, soi gai nhọn, zoom điểm cảnh báo, rồi quyết. Tam giác bị loại hoặc
sửa phải ghi vào `decisions.md` — thuyết minh phương pháp sẽ nêu lại.

## Đã cài (giai đoạn 2)
- Lệnh: `python -m sannen.cli mat --lot <lô> [--be-mat moc|do|ca-hai] [--preview]`. Đọc `points_*.csv` và
  `breaklines.geojson` do `nhap` sinh; **so hash** file nguồn với lần `nhap` — lệch thì dừng (mã 2).
- Một gốc toạ độ chung (trọng tâm hai bề mặt, làm tròn mét) cho cả hai TIN. Điểm trùng (< `trung_mat_bang_mm`)
  được GỘP, cao độ lấy trung bình — không phụ thuộc thứ tự đầu vào. Thứ tự chèn điểm là thứ tự chính tắc nên
  hai lần chạy cho file y hệt từng byte.
- Hai đứt gãy cắt nhau mà cao độ lệch > `giao_dutgay_cm` → việc **CHẶN** (không tự chọn). Đỉnh đứt gãy trùng điểm đo
  nhưng lệch cao độ → cảnh báo, TIN dùng cao độ điểm đo (dữ liệu đo là bằng chứng).
- Tam giác **rác ở mép** (góc nhỏ nhất < `goc_tam_giac_det_do`) bị loại; tam giác dẹt trong vùng chỉ cảnh báo.
- Tam giác **quá lớn** = cạnh dài hơn k·d **và** diện tích hơn tam giác đều cạnh k·d (d = √(diện tích TIN / số đỉnh)).
  Chỉ xét cạnh thì điểm đo thưa ngẫu nhiên bị báo oan. Tam giác loại này mang nhãn `thiếu dữ liệu` (không bị xóa,
  để B3 gồm và B5 loại), và nếu nằm trong biên lô → việc cảnh báo (RULES 8).
- Ra: `surface_moc.json`, `surface_do.json`, `qc_surface.json`. Mã việc tiền tố **M**. `viec_can_lam.md` của cổng 2
  gộp `mat` + `lo`.
- Mã thoát: 0 sạch · 1 có việc chặn · 2 dừng (đầu vào đổi / chưa `nhap` / TIN không dựng được).
