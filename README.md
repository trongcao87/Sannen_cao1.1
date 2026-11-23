# SanNen-Agent

Tính khối lượng san nền đào/đắp cho nghiệm thu thanh toán, có sự cộng tác của AI agent.

Đầu vào là DXF xuất từ AutoCAD; lõi Python tính headless; kết quả vẽ ngược vào DWG
qua MCP CAD để soát bằng mắt. Người giữ mọi quyết định ảnh hưởng số liệu và pháp lý.

## Bắt đầu

    cd core
    pip install -e ".[dev]"
    python -m pytest -q

Chạy thử trên một lô:

    python -m sannen.cli nhap --lot ../projects/KDT-DaiThanh/lots/01-CGP --preview

Đặt file `.dxf` xuất từ AutoCAD vào `00_input/` của lô trước. Layer đặt tên theo
`_agent/kb/layer-convention.md`.

## Thư mục

    _agent/     AGENTS.md, RULES.md, SPEC.md, skills/, kb/, schema/ — phần nhân bản được
    core/       sannen-core: lõi tính + CLI + (sau này) MCP server
    cad/        cầu nối AutoCAD 2022 — giai đoạn 8
    projects/   một dự án một thư mục, một lô một thư mục con

## Trạng thái
Giai đoạn 0 xong. `nhap` đọc DXF thật; sáu verb còn lại là khung, mỗi verb báo rõ
nó thuộc giai đoạn nào. Xem `CLAUDE.md` để biết làm tiếp cái gì.
