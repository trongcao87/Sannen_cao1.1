# RULES.md — 12 điều bất biến

Nạp đầu mọi phiên. Ràng buộc phải chặn TRƯỚC khi ghi, không phải phát hiện sau:
một con số sai đã vào biên bản nghiệm thu thì sửa rất đắt.

1. Agent không tự tính một con số khối lượng nào. Mọi số đến từ `sannen-core`;
   agent gọi, đọc, diễn giải.
2. Dữ liệu đo là bằng chứng: không sửa, không dời điểm, không nội suy bù điểm
   thiếu. Nghi vấn thì báo, người quyết.
3. `00_input/` chỉ đọc. Mọi file agent sinh ra nằm ở `10_process/` hoặc `20_output/`.
4. Mọi verb có side-effect chạy ở chế độ xem trước. Ghi đè file hay vẽ vào bản vẽ
   chỉ sau khi người duyệt.
5. Trước khi vẽ kết quả, xóa sạch đối tượng kết quả cũ của chính lô đó
   (`cad_purge_sn`). Không bao giờ để hai lớp nhãn đè nhau.
6. Không đoán vai trò layer. Gặp layer `SN-` không có trong quy ước thì hỏi.
7. Sai schema thì dừng. Không tự vá dữ liệu cho hợp lệ để chạy tiếp.
8. Vùng thiếu dữ liệu nằm trong biên lô thì không tính khối lượng chỗ đó —
   yêu cầu đo bổ sung.
9. Số nộp là số theo phương pháp khai trong `lot.yaml`; số lăng trụ chỉ là số kiểm.
   Agent không tự đổi số nộp.
10. Mỗi lần tính ghi một dòng log kèm hash dữ liệu đầu vào và phiên bản lõi.
    Không có log thì kết quả không dùng cho hồ sơ.
11. Ngưỡng QC lấy từ `kb/nguong-qc.md` hoặc `lot.yaml`, không tự nghĩ ra. Đổi ngưỡng
    là quyết định của người và phải ghi vào `90_log/decisions.md`.
12. Khối lượng âm bất thường giữa hai đợt — đào đi phần đã đắp đợt trước — phải
    cảnh báo trước khi xuất, không âm thầm bù trừ.

## Nguồn sự thật (mục 13 của SPEC)

- Đầu vào: DXF trong `00_input/`, KHÔNG phải DWG đang mở. Biên lô hay đứt gãy đổi
  thì phải xuất DXF lại; agent so hash với `phieu_truy_vet.json` và dừng nếu lệch.
- Cao độ đỉnh lưới: `10_process/grid_adjusted.json`, KHÔNG phải nhãn trong bản vẽ.
  Người sửa thẳng nhãn trong CAD thì phải chạy `luoi --resync`.
- Mọi đối tượng kết quả trong DWG mang Xrecord ghi mã lô + đợt + hash phiếu truy vết.
