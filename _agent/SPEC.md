# SPEC — Hệ thống tính khối lượng san nền cộng tác người–Agent, v1.0

Bản rút gọn, đủ để dựng mà không cần đọc lại hội thoại. Bản đầy đủ là tài liệu
"SanNen Agent v1.0 — Quy trình chuẩn hóa" trên claude.ai.

## 1. Kiến trúc bốn lớp

    CON NGƯỜI (QS chủ đầu tư)   ra lệnh · quyết ngưỡng, biên, lưới, cao độ đỉnh · duyệt · ký
    AGENT (cửa sổ LLM)          skill · rule · KB — điều phối, kiểm tra, diễn giải
    LÕI sannen-core (Python)    TIN · nội suy · lưới ô · lăng trụ — deterministic, headless
    AUTOCAD 2022 qua MCP CAD    vẽ lưới, nhãn, 3D Face, bảng; hiệu chỉnh tại chỗ

    THƯ MỤC LÔ: 00_input / 10_process / 20_output / 90_log — nơi bốn lớp gặp nhau

Agent KHÔNG tính số. LLM tính số không đáng tin, và số này đem đi thanh toán.

## 2. Thư mục — một lô một thư mục

    _agent/{AGENTS,RULES,SPEC}.md  skills/<verb>/SKILL.md  kb/*.md  schema/*.json
    core/sannen/  core/tests/  core/cli.py  core/mcp_server.py
    cad/
    projects/<dự án>/project.yaml
      lots/<lô>/lot.yaml
        00_input/    *.dxf, *.xlsx            NGƯỜI NỘP — agent không bao giờ ghi
        10_process/  points_*.csv, *.geojson, surface_*.json, grid*.json,
                     volume.json, qc_*.json, viec_can_lam.md    AGENT SINH, xóa được
        20_output/   KL_*.xlsx, doi_chieu_2pp.xlsx, bang_in_cad.json,
                     phieu_truy_vet.json, thuyet_minh_phuong_phap.md
        90_log/      run_*.jsonl, decisions.md

`10_process/` sinh lại 100% từ `00_input/` nên không bao giờ giữ quyết định của người
— quyết định sống ở `90_log/decisions.md`. Mỗi file `20_output/` đi kèm hash bộ input.

## 3. Quy ước layer
Xem `kb/layer-convention.md`. Tiền tố `SN-`. Nguồn: DIEM-MOC, DIEM-DO, DUTGAY,
DONGMUC, BIENLO, LOAITRU. Kết quả: LUOI, LUOI-NHAN, LUOI-O, RANH-DAODAP, 3DF-*,
QC, BANG. Layer `SN-` lạ → hỏi, không đoán.

## 4. Bảy verb

    nhap → mat ∥ lo → luoi → (hieuchinh) → tinh → xuat

Chạy đồng thời được: hai bề mặt khi nhập và khi dựng TIN; `mat` với `lo`;
hai phương pháp trong `tinh`. Chi tiết từng verb ở `skills/<verb>/SKILL.md`.

## 5. Ba cổng duyệt
1. **Cổng dữ liệu** sau `nhap` — không đạt thì về đơn vị khảo sát hoặc về quyết định
   giữ/bỏ điểm.
2. **Cổng bề mặt** sau `mat` và `lo` — không đạt thì xử lý bề mặt hoặc yêu cầu đo bù.
3. **Cổng số liệu** sau `tinh` — không đạt thì về lưới hoặc về bề mặt.

Mỗi cổng ghi `10_process/viec_can_lam.md`. Mỗi việc sáu trường: mã · loại · mô tả ·
vị trí (toạ độ VN-2000 để `cad_zoom_to`) · lựa chọn · hệ quả nếu bỏ qua. Người trả lời
gọn bằng mã (`V-01 a, V-02 b`); mỗi lựa chọn ghi vào `decisions.md` kèm giờ, và đó
chính là phần "đã xử lý gì trên mô hình" mà thuyết minh phương pháp phải nêu.

## 6. Hai phương pháp tính
- **Lưới ô vuông (trung bình 4 góc)** — V = (chênh cao TB 4 góc) × diện tích ô.
  SỐ NỘP, vì hồ sơ dự án bắt buộc.
- **Lăng trụ tam giác** — V = diện tích chiếu × (d1+d2+d3)/3; tam giác vắt ranh cắt
  theo mức 0 rồi tách đào · đắp. SỐ KIỂM, chính xác tuyệt đối khi hai mặt phẳng trên
  từng tam giác.

Lệch nhau ở hai chỗ: ô vắt ranh đào–đắp (một ô chênh cao 4 góc +1,+1,−1,−1 cho lưới
ra 0 m³ trong khi lăng trụ ra 100 đào + 100 đắp), và địa hình bên trong ô.

### Ma trận phương án — `tinh --sweep`
Bảng A quét CÁCH ĐẶT LƯỚI, giữ nguyên kích thước ô: A1 theo bản vẽ nhà thầu ·
A2 gốc tây-nam hộp bao + phương theo cạnh dài lô · A3/A4/A5 dời ½ ô theo X, Y, cả hai ·
A6 xoay thêm 45° · A7 phương song song ranh giới đào–đắp chủ đạo · A8 quét 16 vị trí
gốc × phương 0–90° bước 15°.
Bảng B quét PHƯƠNG PHÁP, giữ cách đặt lưới A1: B1 ô 10×10 · B2 ô 5×5 ·
B3 lăng trụ có đứt gãy đã lọc tam giác rác · B4 lăng trụ bỏ đứt gãy ·
B5 loại vùng thiếu dữ liệu.

**Quy tắc đọc.** Phương án cho số THẤP NHẤT là phương án có nhiều ô vắt ranh nhất,
tức bỏ sót nhiều công tác thật nhất; khoảng cách tới B3 là phần bị triệt tiêu. Gọi là
"cận dưới của phương pháp lưới" thì đúng, gọi là "tối ưu" thì không đứng được.
Số nộp vẫn là A1 đặt theo tham số hồ sơ duyệt (RULES 9).

## 7. Bảng biểu
Workbook 7 sheet, `00_TONGKHOP` mở ra thấy đầu tiên, mọi ô tổng là công thức tham
chiếu chứ không phải số dán cứng. Ba điều kiện khớp: dòng 3 = 0 (chi tiết = tổng hợp),
dòng 8 = 0 (DT đào + đắp = DT lô trừ loại trừ), dòng 5 ≤ ngưỡng ô lệch lớn.
Chi tiết ở `kb/mau-bieu.md`.

## 8. Hợp đồng vào/ra với bản vẽ
| Chiều | Định dạng | Cơ chế |
|---|---|---|
| Vào | DXF | `ezdxf` headless, không mở AutoCAD. DWG thì đổi qua DXF bằng ODA File Converter |
| Ra | DWG | MCP CAD ghi thẳng vào bản vẽ đang mở |

Vòng hiệu chỉnh bằng mắt: agent vẽ → người xoay 3D, soi gai nhọn, zoom cảnh báo →
agent trình phiếu việc → người ra lệnh → agent sửa, tính lại, vẽ lại. Vài giây một vòng.

Nguồn sự thật: đầu vào là DXF (không phải DWG đang mở); cao độ đỉnh lưới là
`grid_adjusted.json` (không phải nhãn trong bản vẽ — sửa tay trong CAD thì phải
`luoi --resync`). Mọi đối tượng kết quả mang Xrecord ghi mã lô + đợt + hash truy vết.

## 9. Kiểm chứng kết quả — ba tầng
1. **Nghiệm giải tích**: mặt phẳng nghiêng trên hình chữ nhật · chóp đều · mặt cắt
   chéo qua lô · lô có lỗ · chỏm cầu (kiểm tra hội tụ khi tăng mật độ điểm).
2. **Kiểm tra tính chất**: tổng các ô = tổng lô · tổng đại số đổi tuyến tính khi nâng
   hạ cao độ thiết kế · xoay hoặc dịch dữ liệu không đổi kết quả · đảo thứ tự điểm
   không đổi kết quả · DT đào + DT đắp = DT lô.
3. **Đối chiếu phần mềm khác**: Civil 3D trên cùng cặp bề mặt, ngưỡng 0,1 %.

Bộ dữ liệu chuẩn: lô 01-CGP, 604 điểm trước / 413 điểm sau, khu ~154×90 m, cao độ tự
nhiên 0,7–4,5 m, sau san lấp ~2,8 m, hệ VN-2000. Còn thiếu số khối lượng đã duyệt —
cửa giai đoạn 5 vẫn đóng được bằng tầng 1 và 2 cộng đối chiếu Civil 3D.

## 10. Việc còn mở
- Ngưỡng ô lệch lớn giữa lưới và lăng trụ: đề xuất 5 % hoặc 10 m³, lấy lớn hơn. CHƯA CHỐT.
- Số khối lượng đào/đắp đã duyệt của lô 01-CGP, để giải thích chênh lệch với hồ sơ cũ.
- Mẫu bảng khối lượng thực tế của dự án, soát lại so `kb/mau-bieu.md`.
