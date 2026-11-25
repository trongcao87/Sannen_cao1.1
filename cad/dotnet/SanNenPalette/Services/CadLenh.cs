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

        // ---- lệnh VẼ bằng C# (SanNenDraw.dll — bước 2 của lộ trình). Có DLL cạnh palette thì gọi lệnh _NET, không thì lệnh LISP cũ.
        public static bool CoDraw()
        {
            try
            {
                string dir = System.IO.Path.GetDirectoryName(typeof(CadLenh).Assembly.Location);
                return System.IO.File.Exists(System.IO.Path.Combine(dir, "SanNenDraw.dll"));
            }
            catch (Exception) { return false; }
        }

        /// <summary>Vẽ lại MỌI nhóm kết quả của lô (xóa nhóm cũ của đúng lô trước). `(sn:nap-draw)` do sannen.lsp định nghĩa: NETLOAD SanNenDraw.dll một lần.</summary>
        public static string VeLai()
        {
            if (!CoDraw()) return Gui("SN_VE ");
            return Gui("(if sn:nap-draw (sn:nap-draw)) SN_VE_NET\n\n");        // dòng trống = nhóm mặc định "tất cả"
        }

        /// <summary>Xem mặt 3D (polyface): hỏi bề mặt trên dòng lệnh rồi SW Isometric + zoom + lưu view SN_TIN3D.</summary>
        public static string Xem3D()
        {
            if (!CoDraw()) return Gui("SN_TIN3D ");
            return Gui("(if sn:nap-draw (sn:nap-draw)) SN_TIN3D_NET ");
        }

        static string GoiNet(string lenhNet, string lenhLisp)
        {
            if (!CoDraw()) return Gui(lenhLisp);
            return Gui("(if sn:nap-draw (sn:nap-draw)) " + lenhNet);
        }

        public static string MatCat() { return Gui("SN_MATCAT "); }
        public static string Bang() { return Gui("SN_BANG "); }
        public static string Luoi() { return Gui("SN_LUOI "); }
        public static string TaoMat() { return Gui("SN_TAOMAT "); }
        public static string ChonBien() { return Gui("SN_CHONBIEN "); }
        public static string ChonDutGay() { return Gui("SN_CHONDUTGAY "); }
        public static string LamMoiXoaCu() { return Gui("SN_LAMMOI "); }
        public static string DichLuoi() { return Gui("SN_DICHLUOI "); }
        public static string XoayLuoi() { return Gui("SN_XOAYLUOI "); }
        public static string Duyet() { return Gui("SN_DUYET "); }

        public static string XoaMatCat(string ten)
        {
            return Gui("(setq *sn-pal-ten* \"" + ten + "\") SN_XOAMATCAT ");
        }

        public static string LuoiApDung(string cot, string hang, string bu)
        {
            return Gui("(setq *sn-pal-luoi* (list \"" + cot + "\" \"" + hang + "\" \"" + bu + "\")) SN_LUOIAPDUNG ");
        }
        /// <summary>Đặt một biến LISP chứa chuỗi ASCII rồi chạy lệnh (cách truyền giá trị vào lệnh LISP có xác nhận).</summary>
        public static string LenhCoBien(string bienLisp, string giaTri, string lenh)
        {
            string s = giaTri == null ? "" : giaTri.Replace("\\", "").Replace("\"", "");
            return Gui("(setq " + bienLisp + " \"" + s + "\") " + lenh + " ");
        }
    }
}
