# Kế hoạch Triển khai: SNVN Studio — Ứng dụng Tính toán San nền & Cầu nối MCP AutoCAD 2022

Xây dựng ứng dụng web kỹ thuật chạy local theo quy trình chuẩn của phần mềm **SNVN (TDT)**, tích hợp lõi xử lý bề mặt **TIN Delaunay có đường đứt gãy**, **lưới ô vuông biến thiên**, **tính toán Taluy**, **tự động vẽ đường đồng mức**, **chú giải mặt cắt ngang TCVN**, **mô hình 3D WebGL** và **bộ cầu nối MCP hai chiều cho AutoCAD 2022** (hỗ trợ đồng thời **Python ActiveX COM** và **C# .NET ObjectARX**).

---

## Xác nhận Quyết định & Phạm vi (User Review & Critical Decisions)

> [!IMPORTANT]
> Toàn bộ 4 định hướng kiến trúc dưới đây đã được chốt theo lựa chọn của bạn. Vui lòng kiểm tra trước khi chuyển sang giai đoạn lập trình.

- **Cầu nối AutoCAD 2022 MCP (Đã xác nhận)**: Tích hợp sẵn **MCP Client trực tiếp** trên trình duyệt (kết nối `localhost` qua HTTP/JSON-RPC & SSE) đi kèm **trình tạo & tải gói mã nguồn hoàn chỉnh cho cả 2 nền tảng**:
  1. **Python ActiveX COM MCP Server** (`win32com.client` / `pyautocad` + FastAPI MCP Server).
  2. **C# .NET ObjectARX Plugin** (`.NET 4.8` cho AutoCAD 2022 `acdbmgd`/`acmgd`/`accoremgd`, mở lệnh `SNVN_MCP_START` lắng nghe cục bộ).
  Đồng thời ứng dụng có **chế độ chạy độc lập (Local Sandbox / DXF & Excel)** để tính toán, hiển thị và kiểm thử toàn bộ quy trình ngay lập tức ngay cả khi chưa kết nối AutoCAD.
- **Phạm vi Module Kỹ thuật (Đã xác nhận)**: Đầy đủ quy trình SNVN (Chương II–VII): TIN Delaunay có đường đứt gãy (MHTN & MHTK) → Tạo/hiệu chỉnh lưới ô vuông → Xác định biên & vùng bỏ qua → Nội suy & hiệu chỉnh cao độ nút → Tính đào đắp & cân bằng tối ưu → Thiết kế & tính Taluy → Tự động vẽ đường đồng mức → Cắt & chú giải mặt cắt ngang chuẩn TCVN → 5 bảng biểu chuẩn SNVN & xuất Excel `.xlsx`.
- **Giao diện (Đã xác nhận)**: **Dark CAD Drafting Studio** (phong cách bản vẽ AutoCAD tối sắc nét, độ tương phản cao, số liệu bảng dạng tabular monospace).
- **Trực quan hóa (Đã xác nhận)**: Tích hợp đồng bộ **Bản vẽ 2D CAD vector tương tác** + **Mô hình 3D WebGL (Three.js)** so sánh MHTN/MHTK/Taluy + **Hệ biểu đồ phân tích địa hình & cân bằng đào đắp**.

> [!NOTE]
> **Lưu ý vận hành thực tế với AutoCAD 2022**: Vì trình duyệt web bị sandbox không thể gọi trực tiếp COM/DLL của Windows, cầu nối MCP sẽ đóng vai trò máy chủ cục bộ chạy song song trên máy Windows có cài AutoCAD 2022 (`http://127.0.0.1:8765`). Ứng dụng web giao tiếp hai chiều với cầu nối này qua chuẩn **JSON-RPC 2.0 / MCP Tools**, đồng thời hỗ trợ nhập/xuất tệp **DXF**, **Excel (.xlsx/.csv)** và **AutoCAD Script (.scr)** làm phương án dự phòng không cần cài đặt.

---

## 1. Tổng quan & Giá trị Cốt lõi

- **Ứng dụng thực hiện điều gì**: Số hóa và tự động hóa hoàn toàn chuỗi công việc thiết kế & bóc tách khối lượng san nền theo tài liệu SNVN, loại bỏ thao tác thủ công rời rạc trên các phiên bản AutoCAD cũ (2005–2008) để vận hành mượt mà với **AutoCAD 2022** thông qua giao thức MCP và giao diện trực quan hiện đại.
- **Đối tượng sử dụng**: Kỹ sư hạ tầng kỹ thuật, kỹ sư quy hoạch san nền, kỹ sư trắc địa và chuyên viên dự toán (QS) cần tính toán chính xác, tối ưu cân bằng đào đắp và kết xuất hồ sơ bản vẽ – bảng biểu chuẩn.
- **Giá trị nổi bật**:
  - Giữ nguyên **ký hiệu bản vẽ quen thuộc của SNVN** (4 góc nút lưới $H_{TN}$/$H_{TK}$/$\Delta H$/chỉ số hàng-cột, vòng tròn diện tích–chênh cao–thể tích, đường ranh giới đào đắp $\Delta H = 0$, vạch dài–ngắn Taluy).
  - Bổ sung những công cụ mạnh mẽ hơn SNVN cổ điển: **tối ưu tự động cao độ cân bằng đào đắp**, **đường đồng mức tự động**, **mặt cắt ngang chuẩn TCVN**, **xem trước 3D WebGL** và **xuất Excel đa sheet một chạm**.

---

## 2. Trải nghiệm Người dùng & Thiết kế Thị giác

### Luồng thao tác chuẩn hóa theo 6 bước SNVN
Người dùng đi tuần tự (hoặc chuyển tự do) qua thanh quy trình 6 bước bên thanh công cụ trái, mọi thay đổi cập nhật tức thời lên khung vẽ chính ở trung tâm:

1. **Bước 1 — Dữ liệu & Mô hình Địa hình (MHTN / MHTK)**:
   - Chọn nguồn: Đọc trực tiếp từ AutoCAD 2022 qua MCP (lọc 6 loại đối tượng SNVN: `Point`, `Block`, `Single Text`, `Line`, `2D Polyline`, `3D Polyline`), tải tệp Excel/CSV (`X, Y, Z, BreaklineID`), tải tệp DXF, hoặc chọn bộ dự án mẫu thực tế (Khu công nghiệp có đường đứt gãy & vùng hồ bỏ qua).
   - Tự động dựng lưới **TIN Delaunay ràng buộc đường đứt gãy** (cạnh tam giác không cắt qua đường đứt gãy).
   - Tạo **MHTK** theo 4 phương án SNVN: Cao độ phẳng (có nút *Tự động cân bằng đào–đắp*), Thiết kế mặt phẳng dốc đơn giản (điểm khống chế + độ dốc % + góc phương vị), Thiết kế hướng dốc (tuyến sống lưng $i_{\text{dọc}}\%$ + mái hai bên $i_{\text{ngang}}\%$), hoặc nhập tọa độ thiết kế.
2. **Bước 2 — Lưới ô vuông & Ranh giới Đào đắp**:
   - Khai báo kích thước hàng/cột linh hoạt đúng cú pháp SNVN (ví dụ: `5x20,5x15,5x20` và `10x20,5x15`), tự động tính số hàng/cột vừa khít biên đào đắp (`Biên đào đắp`), chỉnh điểm chèn $(X_0, Y_0)$ và góc nghiêng $\theta^\circ$.
   - Hiệu chỉnh trực tiếp lưới: thay đổi kích thước từng hàng/cột, chèn/xóa hàng cột, định nghĩa vùng ranh giới tính toán và vùng bỏ qua (`Vùng bỏ qua`), cộng gộp ô liền kề (`Cộng ô`) và bật/tắt trục tổng (`Lập trục`).
3. **Bước 3 — Nội suy, Hiệu chỉnh Nút & Tính Đào đắp**:
   - Nội suy cao độ $H_{TN}$, $H_{TK}$, $\Delta H$ tại toàn bộ nút lưới và điểm giao biên.
   - Cho phép nâng/hạ hàng loạt cao độ thiết kế (`Nâng/hạ CĐTK`) hoặc click chọn từng nút trên bản vẽ 2D để sửa $H_{TK}$ trực tiếp.
   - Tách chính xác vùng đào (vàng) / vùng đắp (đỏ) trong từng ô chứa đường chuyển tiếp $\Delta H = 0$, tính thể tích và vẽ ký hiệu vòng tròn chuẩn SNVN.
4. **Bước 4 — Thiết kế & Tính toán Taluy**:
   - Tự động phân loại các đoạn biên thành ranh giới Taluy đào (vàng) và Taluy đắp (đỏ).
   - Thiết lập độ dốc `1:n`, chiều rộng giật cơ $B_{gc}$, chiều cao giật cơ $H_{gc}$, độ dốc giật cơ $i_{gc}\%$, tùy chọn tường chắn đất và bước chia mặt cắt $L$.
   - Tính khối lượng từng cạnh (`C1..Cn`) và góc lồi (`G1..Gn`) theo công thức mặt cắt trung bình, tự động vẽ ký hiệu mặt bằng Taluy (vạch dài, vạch ngắn).
5. **Bước 5 — Đường đồng mức & Mặt cắt ngang TCVN**:
   - Tự động nội suy và làm mượt **đường đồng mức** (đồng mức cái / đồng mức con, ghi nhãn cao độ dọc đường) cho cả MHTN và MHTK.
   - Kẻ trực tiếp tuyến cắt bất kỳ trên bản vẽ 2D (hoặc chọn tuyến ngang/dọc theo trục lưới) để sinh **bản vẽ mặt cắt ngang chuẩn TCVN** đầy đủ: đường tự nhiên, đường thiết kế, tô gạch đào/đắp, mức so sánh, tỷ lệ ngang/đứng và bảng gióng chân mặt cắt (khoảng cách lẻ, cộng dồn, $H_{TN}$, $H_{TK}$, chênh cao).
6. **Bước 6 — Báo cáo, Biểu đồ, 3D WebGL & Đồng bộ AutoCAD / Excel**:
   - Chuyển đổi tức thời giữa 4 chế độ nhìn ở khung trung tâm: **Bản vẽ 2D CAD** · **Mô hình 3D WebGL** · **Mặt cắt ngang TCVN** · **Bảng biểu & Biểu đồ**.
   - Xem trước đủ **5 bảng thống kê chuẩn SNVN**, tải file **Excel (.xlsx) nhiều sheet định dạng chuẩn**, hoặc nhấn **Đẩy bản vẽ sang AutoCAD 2022 (MCP)** / xuất **DXF & Script (.scr)**.

### Bản sắc Thị giác & Quy ước Thiết kế (Dark CAD Drafting Studio)
- **Định hướng thẩm mỹ**: Studio kỹ thuật CAD tối (lấy cảm hứng từ không gian Model Space của AutoCAD kết hợp bảng công cụ công nghiệp hiện đại), giữ khung bản vẽ chiếm tối đa diện tích (không lồng thẻ chồng chéo, không viền trái dày, không chấm tròn nhấp nháy trang trí).
- **Hệ màu 60–30–10 & Màu ngữ nghĩa chuẩn SNVN** (luôn đi kèm nhãn chữ, không chỉ dựa vào màu):
  - *60% Nền bản vẽ & Canvas*: `#0B0F17` (Model Space tối sâu) và `#0F1521` (nền vùng làm việc).
  - *30% Bề mặt cấu trúc*: `#141B29` (sidebar/panel), `#1C2538` (bề mặt tương tác), đường kẻ `1px solid #263248`.
  - *10% Màu nhấn & Ký hiệu kỹ thuật SNVN*:
    - Nhấn hành động chính: Blueprint Cyan `#0EA5E9` / `#38BDF8`
    - Cao độ tự nhiên / TIN MHTN: Xanh lục `#22C55E`
    - Cao độ thiết kế / Vùng đắp / Taluy đắp: Đỏ san hô `#EF4444`
    - Vùng đào / Chênh cao / Taluy đào: Vàng kỹ thuật `#EAB308`
    - Đường đứt gãy (Breaklines): Tím magenta `#D946EF`
    - Chỉ số hàng–cột / Ranh giới lô: Lam sáng `#60A5FA`
- **Hệ chữ (Typography)**:
  - Tiêu đề & giao diện điều khiển: `Plus Jakarta Sans` (rõ nét, hỗ trợ dấu tiếng Việt xuất sắc, không dùng `Inter`/`Geist`).
  - Toàn bộ tọa độ, cao độ, diện tích, thể tích, bảng khối lượng và dòng lệnh CAD: `JetBrains Mono` kết hợp `tabular-nums` để căn thẳng hàng dấu thập phân.
- **Cấu trúc khung màn hình (Desktop 1440px)**:
  - **Thanh tiêu đề 3 vùng gọn gàng (1 dòng)**: Tên ứng dụng `SNVN Studio` — 4 tab chế độ chính (`Bản vẽ 2D`, `3D WebGL`, `Mặt cắt TCVN`, `Báo cáo & Biểu đồ`) — 1 nút hành động chính (`Cầu nối AutoCAD MCP`).
  - **Cột trái (272px)**: Quy trình 6 bước SNVN có thể mở/đóng theo từng bước + bảng quản lý Layer hiển thị (TIN, Đường đứt gãy, Đồng mức, Lưới, Nút lưới, Vòng tròn KL, Taluy, Tuyến cắt).
  - **Khung trung tâm (chiếm toàn bộ phần còn lại)**: Viewport 2D CAD tương tác (pan/zoom mượt bằng con lăn chuột, tọa độ X/Y/Z trỏ chuột thực theo TIN, công cụ đo/chọn nút/vẽ tuyến cắt) hoặc 3D WebGL Viewport với **thanh điều khiển đáy gọn có thể thu gọn** (tránh che khuất mô hình 3D).
  - **Cột phải (280px, có thể ẩn)**: Bảng tóm tắt khối lượng tức thời (Tổng đào, Tổng đắp, Chênh lệch cân bằng, Khối lượng Taluy) và bảng thuộc tính đối tượng đang chọn (nút lưới / ô lưới / đoạn Taluy).

---

## 3. Các Quyết định Kỹ thuật & Đánh đổi Quan trọng

- **Quyết định 1: Thuật toán TIN có đường đứt gãy (Constrained Delaunay Triangulation — CDT)**
  - *Giải pháp chọn*: Triển khai thuật toán Delaunay Triangulation thuần TypeScript (Bowyer–Watson + bước ép cạnh đứt gãy bằng kỹ thuật lật cạnh / tái tam giác hóa cục bộ hai phía đường đứt gãy) kèm chỉ mục không gian để nội suy cao độ barycentric cực nhanh.
  - *Lý do*: Đảm bảo đúng nguyên tắc Chương III của SNVN (không có cạnh tam giác nào cắt ngang đường đứt gãy địa hình như chân taluy, bờ kênh, mép đường), chạy tức thời ngay trên trình duyệt với hàng nghìn điểm mà không cần biên dịch C++.
  - *Phương án đã loại*: Delaunay không ràng buộc (Delaunator mặc định) sẽ làm sai lệch địa hình tại các khu vực có đường đứt gãy hoặc vách dốc.

- **Quyết định 2: Xử lý chính xác ô lưới cắt biên & ô hỗn hợp vừa đào vừa đắp**
  - *Giải pháp chọn*: Áp dụng cắt đa giác **Sutherland–Hodgman** cho từng ô lưới với `Biên đào đắp` và trừ các đa giác `Vùng bỏ qua`. Với các ô có cả nút dương ($\Delta H > 0$, đắp) và nút âm ($\Delta H < 0$, đào), thuật toán tìm chính xác các giao điểm $\Delta H = 0$ trên cạnh ô để tách thành đa giác đào và đa giác đắp riêng biệt, đồng thời nối liền các điểm $\Delta H = 0$ thành **đường ranh giới đào đắp** liên tục.
  - *Lý do*: Khắc phục sai số của phương pháp chỉ lấy trung bình thô cả ô, phù hợp sát thực tế bản vẽ SNVN (trang 33–35 tài liệu đính kèm) nơi mỗi ô hỗn hợp hiển thị rõ vùng đào màu vàng và vùng đắp màu đỏ tách biệt bởi đường ranh giới đào đắp.

- **Quyết định 3: Kiến trúc cầu nối MCP kép (Python ActiveX COM & C# ObjectARX) + Sandbox độc lập**
  - *Giải pháp chọn*: Định nghĩa một bộ hợp đồng **MCP Tools chuẩn hóa (JSON-RPC 2.0)** thống nhất giữa ứng dụng Web và hai bộ mã nguồn cầu nối cho AutoCAD 2022. Giao diện Web cho phép kết nối trực tiếp tới cổng local (`http://127.0.0.1:8765`), kiểm tra kết nối, gọi lệnh đọc/ghi thực tế với AutoCAD 2022, đồng thời xem/sao chép/tải toàn bộ mã nguồn dự án cầu nối Python (ActiveX) và C# (ObjectARX) kèm hướng dẫn cài đặt từng bước.
  - *Lý do*: Đáp ứng chính xác yêu cầu sử dụng được với cả 2 hệ sinh thái kỹ sư (Python ActiveX triển khai nhanh không cần Visual Studio; C# ObjectARX chạy nội tuyến trong tiến trình AutoCAD 2022 với hiệu năng cực cao cho bản vẽ hàng trăm nghìn đối tượng).

- **Quyết định 4: Hiệu năng 3D WebGL an toàn trên mọi cấu hình máy**
  - *Giải pháp chọn*: Dựng lưới bề mặt 3D bằng `THREE.BufferGeometry` có tô màu theo đỉnh (vertex colors) cho cao độ/đào-đắp, ánh sáng studio 3 điểm + `RoomEnvironment`, cơ chế vẽ theo yêu cầu (`requestRender`) và phát hiện software WebGL để tự điều chỉnh pixel ratio/bóng đổ mà không làm thay đổi hình học.
  - *Lý do*: Đảm bảo mượt mà cả trên máy trạm CAD lẫn máy văn phòng không có GPU rời.

---

## 4. Kiến trúc Hệ thống & Chiến lược Dữ liệu *(Tài liệu Tham chiếu Kỹ thuật)*

### Sơ đồ Kiến trúc Tổng thể

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                     ỨNG DỤNG WEB LOCAL — SNVN STUDIO                         │
│                                                                              │
│  ┌─────────────────────┐  ┌─────────────────────────┐  ┌──────────────────┐  │
│  │  Lõi Nhập / Xuất    │  │   Lõi Tính toán Kỹ thuật│  │  Trực quan hóa   │  │
│  │  • Excel / CSV      │  │   • TIN CDT + Breakline │  │  • 2D CAD Canvas │  │
│  │  • DXF Parser/Write │─▶│   • MHTK Builder & Opt. │─▶│  • 3D WebGL TIN  │  │
│  │  • 5 Bảng SNVN .xlsx│  │   • Grid Clip & Cut/Fill│  │  • Mặt cắt TCVN  │  │
│  │  • AutoCAD .SCR     │  │   • Taluy End-Area Calc │  │  • Biểu đồ KL    │  │
│  └──────────▲──────────┘  │   • Marching Contours   │  └──────────────────┘  │
│             │             │   • Section Sampler     │                        │
│             │             └────────────▲────────────┘                        │
│             │                          │                                     │
│  ┌──────────┴──────────────────────────┴──────────────────────────────────┐  │
│  │           Trạng thái Dự án & Bộ Điều phối MCP Client (JSON-RPC)        │  │
│  │   (Quản lý MHTN, MHTK, Lưới, Nút, Ô gộp, Taluy, Đồng mức, Tuyến cắt)   │  │
│  └─────────────────────────────────────┬──────────────────────────────────┘  │
└────────────────────────────────────────┼─────────────────────────────────────┘
                                         │ HTTP / SSE (JSON-RPC 2.0)
                                         │ localhost:8765/mcp
                ┌────────────────────────┴────────────────────────┐
                ▼                                                 ▼
┌────────────────────────────────────┐    ┌────────────────────────────────────┐
│  CẦU NỐI 1: PYTHON ACTIVEX MCP     │    │  CẦU NỐI 2: C# .NET OBJECTARX MCP  │
│  • FastAPI + MCP Tool Schema       │    │  • Class Library (.NET 4.8)        │
│  • win32com.client (AutoCAD.App.24)│    │  • acdbmgd / acmgd / accoremgd     │
│  • Đọc 6 đối tượng SNVN + Biên     │    │  • Lệnh SNVN_MCP_START (HttpList.) │
│  • Ghi Layer Lưới/Đồng mức/Bảng    │    │  • Transaction đọc/ghi siêu tốc    │
└──────────────────┬─────────────────┘    └─────────────────┬──────────────────┘
                   └────────────────────┬───────────────────┘
                                        ▼
                       ┌─────────────────────────────────┐
                       │     AUTOCAD 2022 (WINDOWS)      │
                       │  Bản vẽ DWG Trắc địa & San nền  │
                       └─────────────────────────────────┘
```

### Mô hình Dữ liệu & Trạng thái Chính

- **SurveyDataset (Dữ liệu đầu vào)**: Danh sách điểm 3D (`id, x, y, z, sourceType, layer`), danh sách đường đứt gãy (`id, vertices[], is3D, layer`), đa giác `boundary` (biên lô đào đắp) và danh sách đa giác `exclusions[]` (vùng bỏ qua).
- **TinSurface (Bề mặt TIN — dùng chung cho MHTN & MHTK)**: Danh sách đỉnh chuẩn hóa, mảng tam giác `(a, b, c)` tuân thủ đường đứt gãy, hộp bao (bounding box) và hàm nội suy `interpolateZ(x, y)` + tính pháp tuyến.
- **DesignSpec (Cấu hình MHTK)**: Chế độ tạo bề mặt (`flat`, `single_slope`, `ridge_slope`, `custom_tin`), cao độ khống chế $H_0$, điểm gốc, góc phương vị, $i_{\text{dọc}}\%$, $i_{\text{ngang}}\%$, độ dịch chỉnh tối ưu $\Delta Z$.
- **GridModel (Mô hình Lưới SNVN)**:
  - Tham số lưới: Tên lưới, chuỗi cột (`colSpec`), chuỗi hàng (`rowSpec`), tọa độ chèn `(originX, originY)`, góc nghiêng `angleDeg`.
  - Danh sách nút (`GridNode`): `row, col, x, y, hTN, hTK, deltaH, isCustomHTK, insideBoundary`.
  - Danh sách ô (`GridCell`): Đa giác đã cắt biên, danh sách đa giác con đào/đắp, diện tích đào $S_{\text{đào}}$, diện tích đắp $S_{\text{đắp}}$, chênh cao trung bình, thể tích đào $V_{\text{đào}}$, thể tích đắp $V_{\text{đắp}}$, nhóm ô đã cộng gộp (`mergedGroupId`).
  - Đường ranh giới đào đắp (`zeroLines[]`): Tập các đoạn thẳng $\Delta H = 0$.
- **TaluyModel**: Danh sách các đoạn biên phân loại đào/đắp (`C1..Cn`) và góc lồi (`G1..Gn`), tham số mái đào/mái đắp (`slope1N`, `bGiatCo`, `hGiatCo`, `iGiatCo`, `retainingWall`, `stepLength`), các mặt cắt ngang Taluy, diện tích/thể tích từng đoạn và danh sách vạch ký hiệu 2D (vạch dài/vạch ngắn).
- **ContourModel**: Tập đường đồng mức con & đồng mức cái tách riêng cho MHTN và MHTK, kèm vị trí và góc xoay nhãn cao độ.
- **CrossSectionModel**: Danh sách tuyến cắt (điểm đầu–cuối, tên tuyến `MC 1-1`, `MC 2-2`...), các cọc mẫu (tại nút lưới, đỉnh địa hình và điểm giao đào/đắp), cao độ $H_{TN}$/$H_{TK}$, diện tích mặt cắt đào/đắp và tham số tỷ lệ ngang/đứng TCVN.

### Ánh xạ Tương tác & Hợp đồng Giao thức MCP (AutoCAD 2022)

1. **Tương tác Bản vẽ 2D CAD**:
   - Pan (kéo chuột giữa/phải hoặc chế độ Pan), Zoom quanh trỏ chuột, Zoom Extents (`Z`).
   - Chế độ **Chọn & Sửa Nút**: Click vào nút lưới để sửa trực tiếp $H_{TK}$ và tự động tính lại toàn bộ ô lân cận + bảng biểu + 3D.
   - Chế độ **Cộng ô (`DD_MC`)**: Click lần lượt 2 ô liền kề cùng tính chất đào hoặc đắp để gộp khối lượng và diện tích đúng như Chương VII SNVN.
   - Chế độ **Kẻ Mặt cắt ngang**: Click 2 điểm trên mặt bằng để sinh ngay bản vẽ mặt cắt ngang TCVN mới.
2. **Tối ưu Cân bằng Đào – Đắp Tự động**:
   - Nút *Tối ưu cân bằng* chạy tìm kiếm nhị phân dịch chuyển cao độ thiết kế $\Delta Z$ sao cho $|\sum V_{\text{đào}} - \sum V_{\text{đắp}}| \to 0$ (có tùy chọn tính gộp cả khối lượng Taluy và hệ số đầm chặt $K$).
3. **Bộ Công cụ MCP chuẩn cho AutoCAD 2022 (JSON-RPC 2.0)**:
   - `autocad_ping`: Kiểm tra phiên bản AutoCAD 2022, tên file DWG đang mở và danh sách Layer.
   - `autocad_read_survey_entities`: Trích xuất 6 loại đối tượng SNVN (`POINT`, `INSERT`, `TEXT`, `LINE`, `LWPOLYLINE`, `POLYLINE3D`) theo bộ lọc Layer/Selection để nạp vào MHTN/MHTK.
   - `autocad_read_boundaries`: Đọc Polyline khép kín của `Biên đào đắp` và `Vùng bỏ qua`.
   - `autocad_draw_grid_results`: Vẽ lưới ô vuông, block thuộc tính 4 góc nút lưới (`GridNodeInfo`), đường ranh giới đào đắp và vòng tròn khối lượng SNVN vào đúng Layer trên AutoCAD 2022.
   - `autocad_draw_contours_taluy`: Vẽ đường đồng mức (LWPOLYLINE kèm nhãn TEXT xoay dọc đường) và ký hiệu Taluy 2D (vạch dài, vạch ngắn).
   - `autocad_draw_cross_section`: Vẽ bản vẽ mặt cắt ngang kèm khung bảng chú giải TCVN tại điểm chèn trên Model Space.
   - `autocad_insert_snvn_tables`: Chèn trực tiếp bảng khối lượng chuẩn SNVN (`AcDbTable`) vào bản vẽ DWG.
4. **Xuất hồ sơ Excel & CAD Offline**:
   - Sinh workbook `.xlsx` 5 sheet chuẩn SNVN (`1_KL_SanNen`, `2_KL_Taluy`, `3_TongHop`, `4_DienTich_TheoO`, `5_KhoiLuong_TheoO`) + sheet danh sách tọa độ nút lưới.
   - Xuất file `.dxf` (ASCII R2010) và AutoCAD Script `.scr` chứa đầy đủ lớp lưới, đường đồng mức, ranh giới đào đắp và mặt cắt để mở thẳng trên AutoCAD 2022 mà không cần chạy cầu nối.
