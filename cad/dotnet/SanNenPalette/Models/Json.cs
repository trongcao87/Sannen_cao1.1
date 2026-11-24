// Đọc JSON tối giản — lớp CHUYỂN TIẾP mỏng tới SanNen.Draw.J (SanNenDraw.dll, lớp thuần dùng chung với DrawEngine).
// Giữ tên SanNen.Palette.Models.J để mã của các tab không phải đổi. Lớp THUẦN, không dùng API AutoCAD.
using System.Collections.Generic;

namespace SanNen.Palette.Models
{
    public static class J
    {
        public static object Parse(string s) { return SanNen.Draw.J.Parse(s); }

        /// <summary>Đi theo chuỗi khoá từ gốc; thiếu khoá → null.</summary>
        public static object Get(object o, params string[] khoa) { return SanNen.Draw.J.Get(o, khoa); }

        public static string S(object o, string macDinh) { return SanNen.Draw.J.S(o, macDinh); }

        public static string S(object o) { return SanNen.Draw.J.S(o); }

        public static double? D(object o) { return SanNen.Draw.J.D(o); }

        public static int I(object o, int macDinh) { return SanNen.Draw.J.I(o, macDinh); }

        public static bool B(object o) { return SanNen.Draw.J.B(o); }

        public static List<object> L(object o) { return SanNen.Draw.J.L(o); }
    }
}