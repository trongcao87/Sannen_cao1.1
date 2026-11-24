// CHỖ DÀNH CHO DrawEngine (bước 2 của lộ trình, _agent/KIEN-TRUC-TOI-UU.md §5): thực thi "kế hoạch vẽ JSON" do Python
// xuất (lệnh `ve-ke-hoach`) bằng API AutoCAD — polyface, polyline, text, bảng có XDATA "SANNEN"; vẽ/purge theo đúng lô+đợt.
// Hiện CHƯA làm: việc vẽ vẫn do LISP (SN_VE, SN_TIN3D...) thực hiện. Lớp này chỉ giữ chỗ để các tab không phụ thuộc cách vẽ.
// Nguyên tắc: DrawEngine KHÔNG tính toán — chỉ vẽ đúng những gì kế hoạch ghi.
namespace SanNen.Palette.Drawing
{
    public static class DrawEngine
    {
    }
}
