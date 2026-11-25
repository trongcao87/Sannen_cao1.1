// Lệnh .NET của SanNenDraw.dll (nhóm "SANNEN_DRAW"). Tên có hậu tố _NET để CÙNG TỒN TẠI với c:SN_VE, c:SN_XOA, c:SN_TIN3D của LISP
// (lộ trình KIEN-TRUC-TOI-UU §5: không gỡ LISP tới bước 4); sannen.lsp tự ưu tiên bản _NET khi thấy SanNenDraw.dll.
//   SN_VE_NET [nhóm]        hỏi nhóm (luoi,nhan,o,ranh,3d,bang; Enter = tất cả) → Python dựng kế hoạch → DrawEngine vẽ (xóa nhóm cũ trước)
//   SN_XOA_NET              đếm rồi HỎI Yes/No (RULES 4) → xóa đối tượng kết quả của đúng lô+đợt hiện tại
//   SN_XOA_NET_Y            như trên nhưng KHÔNG hỏi (cho kịch bản/LISP đã hỏi người dùng rồi)
//   SN_TIN3D_NET            hỏi bề mặt (Mốc/Đo/Cả hai) → vẽ polyface, bật lớp đã chọn, SW Isometric + zoom + lưu view "SN_TIN3D"
//   SN_KEHOACH_NET <file>   vẽ thẳng một file kế hoạch JSON có sẵn (kiểm thử / kịch bản; không gọi Python)
// Lệnh chạy trên luồng lệnh của AutoCAD và chờ Python vài giây. Kết quả (số đối tượng vẽ/xóa theo loại) in ra dòng lệnh và ghi
// <thư mục tạm>\sn_draw_kq.json. Không có phép tính nghiệp vụ nào ở đây.
using System;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Rt = Autodesk.AutoCAD.Runtime;
using CoreApp = Autodesk.AutoCAD.ApplicationServices.Core.Application;

[assembly: Rt.CommandClass(typeof(SanNen.Draw.LenhDraw))]

namespace SanNen.Draw
{
    public sealed class LenhDraw
    {
        static readonly Regex MauNhom = new Regex("^[a-z0-9,]*$");
        public const string TenView = "SN_TIN3D";

        [Rt.CommandMethod("SANNEN_DRAW", "SN_VE_NET", Rt.CommandFlags.Modal)]
        public void Ve()
        {
            Chay("SN_VE_NET", delegate(Document doc, Editor ed)
            {
                string lop = HoiChuoi(ed, "\nNhóm cần vẽ lại (luoi,nhan,o,ranh,3d,bang) <tất cả>: ");
                if (lop == null) return;
                if (!MauNhom.IsMatch(lop)) { ed.WriteMessage("\nTên nhóm chỉ gồm chữ thường, số và dấu phẩy — ví dụ: luoi,nhan,o"); return; }
                KeHoach kh = DungKeHoach("ve", (lop.Length > 0 ? "--lop " + lop + " " : "") + "--dang polyface");
                VeVaBao(doc, ed, "SN_VE_NET", kh);
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_KEHOACH_NET", Rt.CommandFlags.Modal)]
        public void KeHoachFile()
        {
            Chay("SN_KEHOACH_NET", delegate(Document doc, Editor ed)
            {
                string p = HoiChuoi(ed, "\nĐường dẫn file kế hoạch vẽ (.json): ");
                if (string.IsNullOrEmpty(p)) return;
                VeVaBao(doc, ed, "SN_KEHOACH_NET", KeHoach.DocFile(p));
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_XOA_NET", Rt.CommandFlags.Modal)]
        public void Xoa() { Chay("SN_XOA_NET", delegate(Document doc, Editor ed) { XoaLo(doc, ed, true); }); }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_XOA_NET_Y", Rt.CommandFlags.Modal)]
        public void XoaKhongHoi() { Chay("SN_XOA_NET_Y", delegate(Document doc, Editor ed) { XoaLo(doc, ed, false); }); }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_TIN3D_NET", Rt.CommandFlags.Modal)]
        public void Tin3D()
        {
            Chay("SN_TIN3D_NET", delegate(Document doc, Editor ed)
            {
                PromptKeywordOptions o = new PromptKeywordOptions("\nBề mặt cần xem [Moc/Do/Cahai] (Mốc / Đo / Cả hai) <Cahai>: ");
                o.Keywords.Add("Moc", "Moc", "Mốc");
                o.Keywords.Add("Do", "Do", "Đo");
                o.Keywords.Add("Cahai", "Cahai", "Cả hai");
                o.Keywords.Default = "Cahai";
                o.AllowNone = true;
                PromptResult r = ed.GetKeywords(o);
                if (r.Status != PromptStatus.OK && r.Status != PromptStatus.None) return;
                string kw = r.Status == PromptStatus.OK ? r.StringResult : "Cahai";
                string beMat = kw == "Moc" ? "moc" : (kw == "Do" ? "do" : "ca-hai");
                KeHoach kh = DungKeHoach("tin3d", "--be-mat " + beMat + " --dang polyface");
                KetQuaVe kq = VeVaBao(doc, ed, "SN_TIN3D_NET", kh);
                if (!kq.Co3D) { ed.WriteMessage("\nKhông có mặt 3D nào để xem (bề mặt chưa có tam giác)."); return; }
                try
                {
                    XemIso(doc, ed, kq.Hop3D);
                    ed.WriteMessage("\nĐã đổi sang góc nhìn SW Isometric, phóng tới bề mặt và lưu view \"" + TenView + "\" (khôi phục bằng -VIEW → Restore).");
                }
                catch (Exception ex)
                {
                    ed.WriteMessage("\nĐã vẽ mặt 3D nhưng không đặt được góc nhìn / lưu view: " + ex.Message);
                }
            });
        }

        // ------------------------------------------------------------------ chung
        internal delegate void HanhDong(Document doc, Editor ed);

        internal static void Chay(string ten, HanhDong h)
        {
            Document doc = CoreApp.DocumentManager.MdiActiveDocument;
            if (doc == null) return;
            Editor ed = doc.Editor;
            try { h(doc, ed); }
            catch (Exception ex) { ed.WriteMessage("\n" + ten + ": lỗi — " + ex.Message); }
        }

        /// <summary>Hỏi một chuỗi trên dòng lệnh. Enter = "" (trả chuỗi rỗng); ESC = null.</summary>
        internal static string HoiChuoi(Editor ed, string cau)
        {
            PromptStringOptions o = new PromptStringOptions(cau);
            o.AllowSpaces = true;
            PromptResult r = ed.GetString(o);
            if (r.Status == PromptStatus.Cancel || r.Status == PromptStatus.Error) return null;
            return (r.StringResult ?? "").Trim();
        }

        internal static bool HoiYesNo(Editor ed, string cau, bool macDinhYes)
        {
            PromptKeywordOptions o = new PromptKeywordOptions(cau + " [Yes/No] <" + (macDinhYes ? "Yes" : "No") + ">: ");
            o.Keywords.Add("Yes");
            o.Keywords.Add("No");
            o.Keywords.Default = macDinhYes ? "Yes" : "No";
            o.AllowNone = true;
            PromptResult r = ed.GetKeywords(o);
            if (r.Status == PromptStatus.None) return macDinhYes;
            return r.Status == PromptStatus.OK && r.StringResult == "Yes";
        }

        /// <summary>Chọn một điểm trên bản vẽ, tạm tắt osnap (bit 16384 của OSMODE) và khôi phục nguyên trạng kể cả khi ESC.</summary>
        internal static bool ChonDiemKhongOsnap(Editor ed, string cau, Point3d? goc, bool choEnter, out Point3d pt)
        {
            pt = Point3d.Origin;
            int cu = 0;
            bool daTat = false;
            try
            {
                cu = Convert.ToInt32(CoreApp.GetSystemVariable("OSMODE"));
                if ((cu & 16384) == 0)
                {
                    CoreApp.SetSystemVariable("OSMODE", cu | 16384);
                    daTat = true;
                    ed.WriteMessage("\n  (đã tạm tắt osnap)");
                }
            }
            catch (Exception) { }
            try
            {
                PromptPointOptions o = new PromptPointOptions(cau);
                o.AllowNone = choEnter;
                if (goc.HasValue) { o.UseBasePoint = true; o.BasePoint = goc.Value; o.UseDashedLine = true; }
                PromptPointResult r = ed.GetPoint(o);
                if (r.Status != PromptStatus.OK) return false;
                pt = r.Value;
                return true;
            }
            finally
            {
                if (daTat)
                {
                    try { CoreApp.SetSystemVariable("OSMODE", cu); } catch (Exception) { }
                }
            }
        }

        /// <summary>Gọi Python (`ve-ke-hoach`) và đọc kế hoạch. Kế hoạch chỉ ĐỌC lô; lỗi của lõi hiện nguyên văn tiếng Việt.</summary>
        internal static KeHoach DungKeHoach(string cheDo, string them)
        {
            CauHinh c = CauHinh.Doc();
            string tmp = CauNoiPython.ThuMucTam();
            string fileKh = Path.Combine(tmp, "sn_ke_hoach.json"), ra = Path.Combine(tmp, "sn_ke_hoach_ra.json");
            if (File.Exists(fileKh)) File.Delete(fileKh);
            CauNoiPython.ChayLenh(c, "ve-ke-hoach", "--che-do " + cheDo + " --ke-hoach " + CauNoiPython.Trich(fileKh) + " " + them, ra);
            if (!File.Exists(fileKh)) throw new InvalidOperationException("Lõi không ghi file kế hoạch vẽ " + fileKh + ".");
            return KeHoach.DocFile(fileKh);
        }

        internal static KeHoach DungKeHoachArgs(string cheDo, string[] cacDong)
        {
            CauHinh c = CauHinh.Doc();
            string tmp = CauNoiPython.ThuMucTam();
            string fileKh = Path.Combine(tmp, "sn_ke_hoach.json"), ra = Path.Combine(tmp, "sn_ke_hoach_ra.json");
            if (File.Exists(fileKh)) File.Delete(fileKh);
            System.Collections.Generic.List<string> ds = new System.Collections.Generic.List<string>();
            ds.Add("--che-do"); ds.Add(cheDo);
            ds.Add("--ke-hoach"); ds.Add(fileKh);
            if (cacDong != null) ds.AddRange(cacDong);
            CauNoiPython.ChayArgs(c, "ve-ke-hoach", ds.ToArray(), ra);
            if (!File.Exists(fileKh)) throw new InvalidOperationException("Lõi không ghi file kế hoạch vẽ " + fileKh + ".");
            return KeHoach.DocFile(fileKh);
        }

        internal static KetQuaVe VeVaBao(Document doc, Editor ed, string lenh, KeHoach kh)
        {
            KetQuaVe kq = DrawEngine.Ve(doc, kh);
            ed.WriteMessage("\n" + lenh + " — lô " + kh.MaLo + ", đợt " + kh.Dot + ": " + kq.TomTat());
            foreach (string g in kq.GhiChu) ed.WriteMessage("\n  " + g);
            GhiKq(lenh, kq);
            try { ed.Regen(); } catch (Exception) { }
            return kq;
        }

        static void GhiKq(string lenh, KetQuaVe kq)
        {
            try
            {
                string p = Path.Combine(CauNoiPython.ThuMucTam(), "sn_draw_kq.json");
                string j = kq.ToJson();
                j = "{\"lenh\":\"" + lenh + "\"," + j.Substring(1);
                File.WriteAllText(p, j, new UTF8Encoding(false));
            }
            catch (Exception) { }
        }

        // ------------------------------------------------------------------ xóa
        static void XoaLo(Document doc, Editor ed, bool hoi)
        {
            CauHinh c = CauHinh.Doc();
            string lo; int dot;
            c.MaLoDot(out lo, out dot);
            if (lo.Length == 0) { ed.WriteMessage("\nChưa chọn lô (lot= trong " + c.File + ") — gõ SN_LOT."); return; }
            System.Collections.Generic.Dictionary<string, int> dem = DrawEngine.Dem(doc, lo, dot);
            int tong = 0;
            foreach (System.Collections.Generic.KeyValuePair<string, int> kv in dem) tong += kv.Value;
            if (tong == 0) { ed.WriteMessage("\nBản vẽ không có đối tượng kết quả SN của lô " + lo + " đợt " + dot + "."); return; }
            if (hoi)
            {
                PromptKeywordOptions o = new PromptKeywordOptions("\nXóa " + tong + " đối tượng kết quả SN của lô " + lo + " đợt " + dot
                    + " khỏi bản vẽ này? (không đụng nguồn, không đụng lô khác) [Yes/No] <No>: ");
                o.Keywords.Add("Yes");
                o.Keywords.Add("No");
                o.Keywords.Default = "No";
                o.AllowNone = true;
                PromptResult r = ed.GetKeywords(o);
                if (r.Status != PromptStatus.OK || r.StringResult != "Yes") { ed.WriteMessage("\nĐã hủy — bản vẽ giữ nguyên."); return; }
            }
            System.Collections.Generic.List<XoaDef> mau = new System.Collections.Generic.List<XoaDef>();
            mau.Add(new XoaDef());
            KetQuaVe kq = DrawEngine.Xoa(doc, lo, dot, mau, false);
            ed.WriteMessage("\nSN_XOA_NET — đã xóa " + kq.TongXoa + " đối tượng của lô " + lo + " đợt " + dot + " trong " + kq.MsTong + " ms.");
            GhiKq("SN_XOA_NET", kq);
            try { ed.Regen(); } catch (Exception) { }
        }

        // ------------------------------------------------------------------ góc nhìn
        /// <summary>SW Isometric (hướng nhìn (−1,−1,1)), phóng vừa hộp bao mặt 3D (chừa lề 15 %), rồi lưu view "SN_TIN3D".
        /// Không ẩn layer nào — việc Hiện/Ẩn là của palette.</summary>
        static void XemIso(Document doc, Editor ed, double[] hop)
        {
            Point3d tam = new Point3d((hop[0] + hop[3]) / 2, (hop[1] + hop[4]) / 2, (hop[2] + hop[5]) / 2);
            Vector3d huong = new Vector3d(-1, -1, 1).GetNormal();
            Matrix3d dcsVeWcs = Matrix3d.Displacement(tam - Point3d.Origin) * Matrix3d.PlaneToWorld(huong);
            Matrix3d wcsVeDcs = dcsVeWcs.Inverse();
            double x0 = double.MaxValue, y0 = double.MaxValue, x1 = double.MinValue, y1 = double.MinValue;
            for (int i = 0; i < 8; i++)
            {
                Point3d p = new Point3d((i & 1) == 0 ? hop[0] : hop[3], (i & 2) == 0 ? hop[1] : hop[4], (i & 4) == 0 ? hop[2] : hop[5]).TransformBy(wcsVeDcs);
                if (p.X < x0) x0 = p.X; if (p.X > x1) x1 = p.X;
                if (p.Y < y0) y0 = p.Y; if (p.Y > y1) y1 = p.Y;
            }
            using (ViewTableRecord v = ed.GetCurrentView())
            {
                double w = Math.Max((x1 - x0) * 1.15, 5), h = Math.Max((y1 - y0) * 1.15, 5);
                double tl = v.Width / v.Height;
                if (w / h > tl) h = w / tl; else w = h * tl;
                v.ViewDirection = huong;
                v.Target = tam;
                v.ViewTwist = 0;
                v.CenterPoint = new Point2d((x0 + x1) / 2, (y0 + y1) / 2);
                v.Width = w;
                v.Height = h;
                ed.SetCurrentView(v);
            }
            Database db = doc.Database;
            using (DocumentLock khoa = doc.LockDocument())
            {
                using (Transaction tr = db.TransactionManager.StartTransaction())      // xóa view cũ cùng tên (giao dịch riêng)
                {
                    ViewTable vt = (ViewTable)tr.GetObject(db.ViewTableId, OpenMode.ForRead);
                    if (vt.Has(TenView)) ((DBObject)tr.GetObject(vt[TenView], OpenMode.ForWrite)).Erase();
                    tr.Commit();
                }
                using (Transaction tr = db.TransactionManager.StartTransaction())
                using (ViewTableRecord hienTai = ed.GetCurrentView())
                {
                    ViewTable vt = (ViewTable)tr.GetObject(db.ViewTableId, OpenMode.ForWrite);
                    ViewTableRecord nv = new ViewTableRecord();
                    nv.Name = TenView;
                    nv.CenterPoint = hienTai.CenterPoint;
                    nv.Height = hienTai.Height;
                    nv.Width = hienTai.Width;
                    nv.ViewDirection = hienTai.ViewDirection;
                    nv.Target = hienTai.Target;
                    nv.ViewTwist = hienTai.ViewTwist;
                    vt.Add(nv);
                    tr.AddNewlyCreatedDBObject(nv, true);
                    tr.Commit();
                }
            }
        }
    }
}
