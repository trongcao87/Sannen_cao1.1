// Cầu nối tới lõi Python cho palette. Phần THUẦN (CauHinh = đọc sannen.cfg, CauNoiPython = chạy tiến trình con) nằm ở SanNenDraw.dll; ở đây chỉ còn ThongTin. Gọi `python -m sannen_cad.cau_noi <lệnh> --json` bằng tiến trình con.
// Hợp đồng duy nhất là JSON (không parse s-expression). Hàm Chay* chạy ĐỒNG BỘ — chỉ gọi từ luồng nền (xem DieuPhoi).
// C# không đọc 10_process/ trực tiếp và không tự tính.
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using CauHinh = SanNen.Draw.CauHinh;
using CauNoiPython = SanNen.Draw.CauNoiPython;
using SanNen.Palette.Models;

namespace SanNen.Palette.Services
{
    public static class PythonBridge
    {
        /// <summary>Gọi `thong-tin --json` cho lô hiện tại. Không bao giờ ném ngoại lệ: lỗi nằm trong DuLieuPal.Loi.</summary>
        public static DuLieuPal ThongTin()
        {
            DuLieuPal r = new DuLieuPal();
            r.Luc = DateTime.Now;
            CauHinh c = CauHinh.Doc();
            string thieu = c.ThieuGi();
            if (thieu != null) { r.Loi = thieu; return r; }
            string ra = Path.Combine(Path.GetTempPath(), "sn_palette_" + Process.GetCurrentProcess().Id + ".json");
            try
            {
                if (File.Exists(ra)) File.Delete(ra);
                string args = "-X utf8 -m sannen_cad.cau_noi thong-tin --lot \"" + c.Lot + "\" --json --ra \"" + ra + "\"";
                string nhatKy;
                int ma = CauNoiPython.Chay(c, args, out nhatKy);
                if (!File.Exists(ra))
                {
                    r.Loi = "Python không trả kết quả (mã thoát " + ma + "). Kiểm tra python= trong " + c.File + " đã cài sannen-core chưa. " + CauNoiPython.Cat(nhatKy);
                    return r;
                }
                object goc = J.Parse(File.ReadAllText(ra, new UTF8Encoding(false)));
                if (!J.B(J.Get(goc, "ok")))
                {
                    r.Loi = "Lõi báo: " + J.S(J.Get(goc, "thong_bao"), "lỗi không rõ") + " (lot= trong " + c.File + ")";
                    return r;
                }
                r.Goc = J.Get(goc, "du_lieu");
                r.Ok = true;
            }
            catch (Exception ex)
            {
                r.Loi = "Không đọc được số liệu từ lõi: " + ex.Message + " — kiểm tra " + c.File + " (python=, cad=, lot=).";
            }
            finally
            {
                try { if (File.Exists(ra)) File.Delete(ra); } catch (Exception) { }
            }
            return r;
        }

    }
}
