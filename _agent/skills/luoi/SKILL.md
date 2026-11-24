---
name: luoi
mo_ta: Đặt lưới ô vuông vừa biên lô, nội suy cao độ hai bề mặt lên từng đỉnh lưới.
giai_doan: 4
---
# luoi

## Lệnh
    python -m sannen.cli luoi --lot <thư mục lô> [--o 20] [--goc 0] [--goc-luoi E,N]
    python -m sannen.cli luoi --lot <thư mục lô> --resync

## Đặt lưới
Định nghĩa bằng: điểm gốc, góc xoay, kích thước ô (cho phép mỗi hàng/cột một kích
thước). Khác SNVN: chọn biên lô trước, tool tự tính hộp bao xoay theo cạnh dài của lô
và đặt lưới vừa khít — không phải chỉnh tay từng hàng cột.

Sửa lưới: đổi kích thước từng hàng/cột, chèn/xóa hàng cột, di chuyển và xoay toàn
lưới. Lưới bám sát biên làm giảm số ô vắt ranh đào–đắp — nguồn sai số chính của
phương pháp lưới ô vuông.

## Cắt mảnh theo ô — cách làm rẻ
Đừng dùng thư viện cắt đa giác tổng quát. Đổi toạ độ mọi mảnh về hệ của lưới (dời gốc,
xoay ngược góc lưới) thì đường lưới thành đường song song trục → chỉ cần
Sutherland–Hodgman cắt bằng đường thẳng, lặp theo số đường lưới đi qua hộp bao của
mảnh, thường chỉ một hoặc hai đường.

## --resync
Đọc ngược cao độ đỉnh lưới từ nhãn trong bản vẽ (`cad_read_grid_z`) khi người sửa
thẳng trong CAD thay vì ra lệnh cho agent. Agent BÁO chênh lệch trước khi nhận —
nếu không, bảng Excel và bản vẽ sẽ nói hai con số khác nhau mà không ai biết.

## Ra
`grid.json` — nút lưới với cao độ nội suy từ hai TIN, danh sách ô và diện tích hữu
hiệu sau cắt biên. Layer `SN-LUOI`, `SN-LUOI-NHAN`.

## Hỏi người trước khi chạy
Kích thước ô, góc và gốc lưới — theo yêu cầu hồ sơ. Nếu chỉ dẫn đo bóc đã chốt thì
dùng đúng, không tự chọn.

## Đã cài (giai đoạn 4)
- Lệnh: `luoi --lot <lô> [--o 20] [--goc 17.5|auto] [--goc-luoi E,N] [--preview]`; `--resync --tu-file <json|csv> [--chap-nhan]`.
  `goc: auto` = phương cạnh dài hộp bao có hướng nhỏ nhất của lô. `lot.yaml` cho phép `luoi.cot_m` / `luoi.hang_m`
  (kích thước từng cột/hàng).
- Mã đỉnh `D03-05` (cột 3, hàng 5, tính từ 1); mã ô `O03-05`. Ô là giao của hình vuông lưới với lô đã trừ loại trừ,
  tính bằng cắt đa giác (Sutherland–Hodgman với ô lồi) — không dùng thư viện cắt tổng quát.
- Kiểm tổng: **Σ diện tích ô = diện tích lô** (sai số < 1e-9 tương đối), lệch là lỗi phần mềm (CHẶN).
- Ô có đỉnh ngoài TIN hoặc chạm tam giác thiếu dữ liệu trong lô → `thieu_du_lieu`, KHÔNG tính khối lượng (RULES 8).
- Cao độ đỉnh nội suy lưu 6 chữ số (0,001 mm): làm tròn 0,1 mm × hàng nghìn m² là hàng chục lít.
- `--resync`: nhận danh sách `{ma, be_mat, z}` do `cad_read_grid_z` xuất, BÁO chênh lệch, chỉ nhận khi có `--chap-nhan`.
- **Ngoại suy đỉnh ngoài vùng đo — mặc định CẤM (RULES 8).** Lưới 4 góc cần cao độ ở đỉnh nằm NGOÀI biên lô; khảo sát
  chỉ đo trong biên thì mọi ô sát biên bị loại (trên 01-CGP: 18/23 ô). Người có thể chấp nhận có điều kiện:
      luoi: {ngoai_suy_m: 10, ngoai_suy_kieu: gan_nhat}      # hoặc --ngoai-suy 10 --ngoai-suy-kieu gan_nhat
  `gan_nhat` (mặc định): lấy cao độ tại điểm gần nhất của vùng đo. `mat_phang`: kéo dài mặt phẳng tam giác — **dễ sai
  nặng trên mái dốc** (01-CGP, 20 m: đào 4.521 m³ so với lăng trụ 68 m³). Mọi ô dùng ngoại suy mang cờ `ngoai_suy` và
  có việc cảnh báo; ghi quyết định vào `decisions.md`. Cách đúng vẫn là đo bù ra ngoài biên vài mét.
