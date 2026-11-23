---
name: hieuchinh
mo_ta: Áp cao độ đỉnh lưới người chỉ định, tự cập nhật chênh cao, vẽ lại nhãn.
giai_doan: 4
---
# hieuchinh

## Lệnh
    python -m sannen.cli hieuchinh --lot <thư mục lô> --dinh <mã đỉnh> --z <giá trị>
    python -m sannen.cli hieuchinh --lot <thư mục lô> --tu-file <đường dẫn>

## Vai trò
Người quyết TỪNG giá trị cao độ đỉnh. Agent chỉ chạy tool. Đây là khâu "hiệu chỉnh
bằng mắt" — người xoay mặt 3D, zoom, chỉ đỉnh cần sửa, agent thực thi và tính lại.

Khác SNVN: sửa cao độ xong KHÔNG phải chạy riêng lệnh cập nhật chênh cao. Tool tự
tính lại. Quên bước đó là bảng vẫn xuất ra bình thường nhưng sai — lỗi đã bỏ.

## Vòng lặp
1. Agent vẽ kết quả vào DWG
2. Người nhìn bằng mắt, zoom điểm cảnh báo
3. Agent trình `viec_can_lam.md`
4. Người ra lệnh: sửa đỉnh nào, giá trị bao nhiêu
5. Agent sửa → tính lại → vẽ lại → ghi `decisions.md`

Một vòng vài giây vì phép tính chỉ vài chục mili giây; thời gian thật nằm ở khâu vẽ.

## Ra
`grid_adjusted.json`. Đây là NGUỒN SỰ THẬT của cao độ đỉnh, không phải nhãn trong
bản vẽ (RULES — Nguồn sự thật).
