// Lệnh mặt cắt & bảng biểu bằng C# (.NET): SN_MATCAT_NET, SN_XOAMATCAT_NET, SN_BANG_NET.
// Người chọn điểm bằng chuột (tạm tắt osnap, khôi phục kể cả khi ESC); Python tính và xuất kế hoạch vẽ JSON; DrawEngine vẽ.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Rt = Autodesk.AutoCAD.Runtime;

[assembly: Rt.CommandClass(typeof(SanNen.Draw.LenhMatCatBang))]

namespace SanNen.Draw
{
    public sealed class LenhMatCatBang
    {
        static string F4(double v) { return v.ToString("F4", CultureInfo.InvariantCulture); }

        static string En(Point3d p) { return F4(p.X) + "," + F4(p.Y); }

        static double? HoiSoDuong(Editor ed, string cau, double macDinh)
        {
            PromptDoubleOptions o = new PromptDoubleOptions(cau);
            o.DefaultValue = macDinh;
            o.UseDefaultValue = true;
            o.AllowZero = false;
            o.AllowNegative = false;
            PromptDoubleResult r = ed.GetDouble(o);
            if (r.Status != PromptStatus.OK) return null;
            return r.Value;
        }

        /// <summary>Tìm hộp bao (minX, minY) của các đối tượng kết quả thuộc đúng lô+đợt (trừ mặt cắt).</summary>
        static bool HopBaoKetQua(Document doc, string lo, int dot, out double traiX, out double duoiY)
        {
            traiX = 0; duoiY = 0;
            bool co = false;
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTableRecord ms = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForRead);
                foreach (ObjectId id in ms)
                {
                    Entity e = tr.GetObject(id, OpenMode.ForRead, false, true) as Entity;
                    if (e == null) continue;
                    List<string> xd = DrawEngine.DocXd(e);
                    if (xd == null || xd[0] != lo || xd[1] != dot.ToString() || xd[3] == "mat_cat") continue;
                    try
                    {
                        Extents3d ex = e.GeometricExtents;
                        if (!co) { traiX = ex.MinPoint.X; duoiY = ex.MinPoint.Y; co = true; }
                        else { if (ex.MinPoint.X < traiX) traiX = ex.MinPoint.X; if (ex.MinPoint.Y < duoiY) duoiY = ex.MinPoint.Y; }
                    }
                    catch (Exception) { }
                }
                tr.Commit();
            }
            return co;
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_MATCAT_NET", Rt.CommandFlags.Modal)]
        public void MatCat()
        {
            LenhDraw.Chay("SN_MATCAT_NET", delegate(Document doc, Editor ed)
            {
                Point3d pa, pb;
                if (!LenhDraw.ChonDiemKhongOsnap(ed, "\nĐiểm đầu tuyến mặt cắt (A): ", null, false, out pa)) return;
                if (!LenhDraw.ChonDiemKhongOsnap(ed, "\nĐiểm cuối tuyến mặt cắt (B): ", pa, false, out pb)) return;
                double? buoc = HoiSoDuong(ed, "\nBước lấy mẫu (m) <1.0>: ", 1.0);
                if (!buoc.HasValue) return;
                double? tyLe = HoiSoDuong(ed, "\nTỷ lệ đứng (so với ngang) <5.0>: ", 5.0);
                if (!tyLe.HasValue) return;
                string ten = LenhDraw.HoiChuoi(ed, "\nTên mặt cắt <MC1>: ");
                if (ten == null) return;
                if (ten.Length == 0) ten = "MC1";

                Point3d gocVe;
                bool coGoc = LenhDraw.ChonDiemKhongOsnap(ed, "\nĐiểm đặt biểu đồ (góc trên-trái; Enter = tự đặt dưới kết quả lô): ", null, true, out gocVe);

                CauHinh c = CauHinh.Doc();
                string lo; int dot;
                c.MaLoDot(out lo, out dot);
                List<string> args = new List<string>();
                args.Add("--a"); args.Add(En(pa));
                args.Add("--b"); args.Add(En(pb));
                args.Add("--buoc"); args.Add(buoc.Value.ToString("G", CultureInfo.InvariantCulture));
                args.Add("--ty-le-dung"); args.Add(tyLe.Value.ToString("G", CultureInfo.InvariantCulture));
                args.Add("--ten"); args.Add(ten);
                if (coGoc) { args.Add("--goc-ve"); args.Add(En(gocVe)); }
                double tx = 0, dy = 0;
                bool coHb = !coGoc && lo.Length > 0 && HopBaoKetQua(doc, lo, dot, out tx, out dy);
                if (coHb) { args.Add("--trai-x"); args.Add(F4(tx)); args.Add("--duoi-y"); args.Add(F4(dy)); }

                string ra = Path.Combine(CauNoiPython.ThuMucTam(), "sn_matcat_ra.json");
                object goc = CauNoiPython.ChayArgs(c, "mat-cat", args.ToArray(), ra);
                string tb = J.S(J.Get(goc, "thong_bao"));
                if (tb.Length > 0) ed.WriteMessage("\n" + tb);

                List<string> khArgs = new List<string>();
                khArgs.Add("--ten"); khArgs.Add(ten);
                khArgs.Add("--ty-le-dung"); khArgs.Add(tyLe.Value.ToString("G", CultureInfo.InvariantCulture));
                if (coGoc) { khArgs.Add("--goc-ve"); khArgs.Add(En(gocVe)); }
                else if (coHb) { khArgs.Add("--trai-x"); khArgs.Add(F4(tx)); khArgs.Add("--duoi-y"); khArgs.Add(F4(dy)); }

                KeHoach kh = LenhDraw.DungKeHoachArgs("mat-cat", khArgs.ToArray());
                LenhDraw.VeVaBao(doc, ed, "SN_MATCAT_NET", kh);
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_XOAMATCAT_NET", Rt.CommandFlags.Modal)]
        public void XoaMatCat()
        {
            LenhDraw.Chay("SN_XOAMATCAT_NET", delegate(Document doc, Editor ed)
            {
                CauHinh c = CauHinh.Doc();
                string lo; int dot;
                c.MaLoDot(out lo, out dot);
                if (lo.Length == 0) { ed.WriteMessage("\nChưa chọn lô — gõ SN_LOT."); return; }
                string ten = LenhDraw.HoiChuoi(ed, "\nTên mặt cắt cần xoá khỏi bản vẽ <MC1>: ");
                if (ten == null) return;
                if (ten.Length == 0) ten = "MC1";

                XoaDef x = new XoaDef();
                x.Loai = "mat_cat";
                x.Ex.Add("ten=" + ten);
                List<XoaDef> mau = new List<XoaDef>();
                mau.Add(x);
                int n = DrawEngine.Xoa(doc, lo, dot, mau, true).TongXoa;
                if (n == 0) { ed.WriteMessage("\nBản vẽ không có mặt cắt «" + ten + "» của lô " + lo + " đợt " + dot + "."); return; }
                if (!LenhDraw.HoiYesNo(ed, "\nXoá " + n + " đối tượng của mặt cắt «" + ten + "» (file số liệu giữ nguyên)?", false))
                {
                    ed.WriteMessage("\nĐã hủy — giữ nguyên mặt cắt.");
                    return;
                }
                KetQuaVe kq = DrawEngine.Xoa(doc, lo, dot, mau, false);
                ed.WriteMessage("\nSN_XOAMATCAT_NET — đã xoá " + kq.TongXoa + " đối tượng của mặt cắt «" + ten + "».");
                try { ed.Regen(); } catch (Exception) { }
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_BANG_NET", Rt.CommandFlags.Modal)]
        public void Bang()
        {
            LenhDraw.Chay("SN_BANG_NET", delegate(Document doc, Editor ed)
            {
                PromptKeywordOptions o = new PromptKeywordOptions("\nLoại bảng cần chèn [Tong/Tonghop/O] (Tổng / Tổng hợp 2 PP / Từng ô) <O>: ");
                o.Keywords.Add("Tong", "Tong", "Tổng");
                o.Keywords.Add("Tonghop", "Tonghop", "Tổng hợp");
                o.Keywords.Add("O", "O", "Từng ô");
                o.Keywords.Default = "O";
                o.AllowNone = true;
                PromptResult r = ed.GetKeywords(o);
                if (r.Status != PromptStatus.OK && r.Status != PromptStatus.None) return;
                string kw = r.Status == PromptStatus.OK ? r.StringResult : "O";
                string loai = kw == "Tong" ? "tong" : (kw == "Tonghop" ? "tong-hop" : "o");

                Point3d gocVe;
                if (!LenhDraw.ChonDiemKhongOsnap(ed, "\nGóc trên-trái đặt bảng: ", null, false, out gocVe)) return;

                KeHoach kh = LenhDraw.DungKeHoachArgs("bang", new string[] { "--loai", loai, "--goc-ve", En(gocVe) });
                LenhDraw.VeVaBao(doc, ed, "SN_BANG_NET", kh);
            });
        }
    }
}
