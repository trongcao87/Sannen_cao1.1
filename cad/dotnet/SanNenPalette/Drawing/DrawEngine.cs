// DrawEngine THẬT nằm ở SanNenDraw.dll (cad/dotnet/SanNenDraw/DrawEngine.cs, namespace SanNen.Draw, không phụ thuộc giao diện):
// thực thi "kế hoạch vẽ JSON" do Python xuất (`ve-ke-hoach`) bằng API AutoCAD — polyface, polyline, text có XDATA "SANNEN";
// vẽ/purge theo đúng lô+đợt. Palette KHÔNG vẽ trực tiếp: các nút "Vẽ lại", "Xem 3D" gọi lệnh SN_VE_NET / SN_TIN3D_NET (xem CadLenh).
// Lớp này chỉ giữ chỗ để cấu trúc thư mục (Services/Models/Drawing/Ui) không đổi.
namespace SanNen.Palette.Drawing
{
    public static class DrawEngine
    {
    }
}