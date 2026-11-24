// Gửi lệnh AutoCAD từ palette. CÁC NÚT GHI TẠM GỌI LỆNH LISP SẴN CÓ (SN_LUOI, SN_TINH, SN_DUYET...) để vẫn xin xác nhận
// ngay trên dòng lệnh (RULES 4) và vẫn bị chốt chặn ba cổng của core/sannen/cong.py chặn. Palette KHÔNG tự ghi file lô,
// KHÔNG tự ghi duyệt cổng.
// CHUYỂN SANG C# ở BƯỚC 3 của lộ trình (_agent/KIEN-TRUC-TOI-UU.md §5): mọi chỗ gọi CadLenh.Gui(...) dưới đây sẽ thay bằng
// lệnh C# gọi PythonBridge (JSON) + hộp xác nhận; lúc đó LISP/DCL được gỡ.
using System;
using Autodesk.AutoCAD.ApplicationServices;
using SanNen.Palette.Models;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace SanNen.Palette.Services
{
    public static class CadLenh
    {
        /// <summary>Gửi chuỗi lệnh (kết thúc bằng khoảng trắng = Enter). Trả null nếu gửi được, ngược lại thông báo tiếng Việt.</summary>
        public static string Gui(string chuoi)
        {
            Document doc = CadLop.DocHienHanh();
            if (doc == null) return "Chưa mở bản vẽ nào.";
            try
            {
                int dang = Convert.ToInt32(AcApp.GetSystemVariable("CMDACTIVE"));
                if (dang != 0) return "AutoCAD đang chạy một lệnh khác — nhấn ESC ở bản vẽ rồi bấm lại.";
            }
            catch (Exception) { }
            doc.SendStringToExecute(chuoi, true, false, false);
            try { doc.Window.Focus(); } catch (Exception) { }          // để dòng lệnh nhận phím trả lời (xác nhận Yes/No)
            return null;
        }

        /// <summary>Chạy lệnh LISP có sẵn, vd "SN_TINH".</summary>
        public static string Lenh(string ten)
        {
            return Gui(ten + " ");
        }

        /// <summary>Đặt một biến LISP chứa chuỗi ASCII rồi chạy lệnh (cách truyền giá trị vào lệnh LISP có xác nhận).</summary>
        public static string LenhCoBien(string bienLisp, string giaTri, string lenh)
        {
            string s = giaTri == null ? "" : giaTri.Replace("\\", "").Replace("\"", "");
            return Gui("(setq " + bienLisp + " \"" + s + "\") " + lenh + " ");
        }
    }
}
