// Lệnh tương tác CAD bằng C# (.NET): SN_LUOI_NET, SN_DICHLUOI_NET, SN_XOAYLUOI_NET, SN_LUOI_BO_NET,
// SN_SUADINH_NET, SN_DONGBO_NET, SN_DUYET_NET.
// Không chứa logic tính toán nghiệp vụ — mọi phép tính và chốt chặn cổng nằm ở lõi Python qua cau_noi.py.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Rt = Autodesk.AutoCAD.Runtime;

[assembly: Rt.CommandClass(typeof(SanNen.Draw.LenhTuongTac))]

namespace SanNen.Draw
{
    public sealed class LenhTuongTac
    {
        static string F4(double v) { return v.ToString("F4", CultureInfo.InvariantCulture); }

        static void VeLaiNhom(Document doc, Editor ed, string lenh, string lop)
        {
            KeHoach kh = LenhDraw.DungKeHoach("ve", "--lop " + lop + " --dang polyface");
            LenhDraw.VeVaBao(doc, ed, lenh, kh);
        }

        // ------------------------------------------------------------------ lưới
        [Rt.CommandMethod("SANNEN_DRAW", "SN_LUOI_NET", Rt.CommandFlags.Modal)]
        public void Luoi()
        {
            LenhDraw.Chay("SN_LUOI_NET", delegate(Document doc, Editor ed)
            {
                string tmp = CauNoiPython.ThuMucTam();
                string tam = Path.Combine(tmp, "sn_luoi_tam.txt");
                string cot = "", hang = "", bu = "", gocXoay = "", gocLuoi = "";
                if (File.Exists(tam))
                {
                    string[] d = File.ReadAllLines(tam, new UTF8Encoding(false));
                    try { File.Delete(tam); } catch (Exception) { }
                    if (d.Length >= 3) { cot = d[0].Trim(); hang = d[1].Trim(); bu = d[2].Trim(); }
                }
                else
                {
                    PromptKeywordOptions k = new PromptKeywordOptions("\nThao tác lưới [Dat/ChonVung/ImportDxf/LayMcp/Dich/Xoay/QuayVeLot] <Dat>: ");
                    k.Keywords.Add("Dat"); k.Keywords.Add("ChonVung"); k.Keywords.Add("ImportDxf"); k.Keywords.Add("LayMcp");
                    k.Keywords.Add("Dich"); k.Keywords.Add("Xoay"); k.Keywords.Add("QuayVeLot");
                    k.Keywords.Default = "Dat"; k.AllowNone = true;
                    PromptResult rk = ed.GetKeywords(k);
                    if (rk.Status != PromptStatus.OK && rk.Status != PromptStatus.None) return;
                    string chon = rk.Status == PromptStatus.OK ? rk.StringResult : "Dat";
                    if (chon == "Dich") { DichLuoi(); return; }
                    if (chon == "Xoay") { XoayLuoi(); return; }
                    if (chon == "QuayVeLot") { QuayVeLot(); return; }
                    if (chon == "LayMcp")
                    {
                        CauHinh cm = CauHinh.Doc();
                        string ram = Path.Combine(tmp, "sn_luoi_mcp_ra.json");
                        object gocm = CauNoiPython.ChayArgs(cm, "luoi-doc", new string[] { "--cho-phep-chua-co" }, ram);
                        object dl = J.Get(gocm, "du_lieu");
                        ed.WriteMessage("\nĐã lấy cấu hình lưới từ cửa sổ Chat / MCP: cột=" + J.S(J.Get(dl, "cot")) + ", hàng=" + J.S(J.Get(dl, "hang")));
                        VeLaiNhom(doc, ed, "SN_LUOI_NET", "luoi,nhan,o,ranh");
                        return;
                    }
                    if (chon == "ImportDxf")
                    {
                        PromptKeywordOptions ki = new PromptKeywordOptions("\nImport lưới từ [FileDxf/ChonTrenCad] <FileDxf>: ");
                        ki.Keywords.Add("FileDxf"); ki.Keywords.Add("ChonTrenCad"); ki.Keywords.Default = "FileDxf"; ki.AllowNone = true;
                        PromptResult rki = ed.GetKeywords(ki);
                        if (rki.Status != PromptStatus.OK && rki.Status != PromptStatus.None) return;
                        string nguonImp = (rki.Status == PromptStatus.OK && rki.StringResult == "ChonTrenCad") ? "ChonTrenCad" : "FileDxf";
                        string fileImp = "";
                        if (nguonImp == "FileDxf")
                        {
                            fileImp = LenhDraw.HoiChuoi(ed, "\nĐường dẫn file .dxf chứa lưới ô vuông: ");
                            if (string.IsNullOrEmpty(fileImp)) return;
                        }
                        else
                        {
                            PromptSelectionOptions pso = new PromptSelectionOptions();
                            pso.MessageForAdding = "\nChọn các đường lưới (LINE, LWPOLYLINE) trên bản vẽ: ";
                            TypedValue[] tv = new TypedValue[] { new TypedValue((int)DxfCode.Start, "LINE,LWPOLYLINE") };
                            PromptSelectionResult psr = ed.GetSelection(pso, new SelectionFilter(tv));
                            if (psr.Status != PromptStatus.OK) return;
                            StringBuilder sb = new StringBuilder();
                            sb.Append("{\"doan\":[");
                            bool dau = true;
                            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
                            {
                                foreach (SelectedObject so in psr.Value)
                                {
                                    if (so == null) continue;
                                    Entity ent = tr.GetObject(so.ObjectId, OpenMode.ForRead) as Entity;
                                    Line ln = ent as Line;
                                    if (ln != null)
                                    {
                                        if (!dau) sb.Append(",");
                                        sb.Append("[" + F4(ln.StartPoint.X) + "," + F4(ln.StartPoint.Y) + "," + F4(ln.EndPoint.X) + "," + F4(ln.EndPoint.Y) + "]");
                                        dau = false;
                                    }
                                    Polyline pl = ent as Polyline;
                                    if (pl != null && pl.NumberOfVertices >= 2)
                                    {
                                        int nv = pl.NumberOfVertices;
                                        for (int i = 0; i < nv - 1; i++)
                                        {
                                            Point2d a = pl.GetPoint2dAt(i), b = pl.GetPoint2dAt(i + 1);
                                            if (!dau) sb.Append(",");
                                            sb.Append("[" + F4(a.X) + "," + F4(a.Y) + "," + F4(b.X) + "," + F4(b.Y) + "]");
                                            dau = false;
                                        }
                                        if (pl.Closed && nv >= 3)
                                        {
                                            Point2d a = pl.GetPoint2dAt(nv - 1), b = pl.GetPoint2dAt(0);
                                            if (!dau) sb.Append(",");
                                            sb.Append("[" + F4(a.X) + "," + F4(a.Y) + "," + F4(b.X) + "," + F4(b.Y) + "]");
                                            dau = false;
                                        }
                                    }
                                }
                                tr.Commit();
                            }
                            sb.Append("]}");
                            fileImp = Path.Combine(tmp, "sn_cad_luoi_doan.json");
                            File.WriteAllText(fileImp, sb.ToString(), new UTF8Encoding(false));
                        }
                        if (!LenhDraw.HoiYesNo(ed, "\nImport lưới từ " + Path.GetFileName(fileImp) + ", tính lại và vẽ lại lưới?", true))
                        { ed.WriteMessage("\nĐã hủy."); return; }
                        CauHinh ci = CauHinh.Doc();
                        string rai = Path.Combine(tmp, "sn_luoi_imp_ra.json");
                        object goci = CauNoiPython.ChayArgs(ci, "luoi-import-dxf", new string[] { "--tu-file", fileImp }, rai);
                        ed.WriteMessage("\n" + J.S(J.Get(goci, "thong_bao"), "Đã import lưới."));
                        VeLaiNhom(doc, ed, "SN_LUOI_NET", "luoi,nhan,o,ranh");
                        return;
                    }
                    if (chon == "ChonVung")
                    {
                        PromptEntityOptions peo = new PromptEntityOptions("\nChọn đa tuyến biên lô (ranh đào đắp) hoặc Enter để chọn 2 điểm góc: ");
                        peo.AllowNone = true;
                        PromptEntityResult per = ed.GetEntity(peo);
                        double minX = 0, minY = 0, maxX = 0, maxY = 0;
                        bool coVung = false;
                        if (per.Status == PromptStatus.OK)
                        {
                            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
                            {
                                Entity ent = tr.GetObject(per.ObjectId, OpenMode.ForRead) as Entity;
                                if (ent != null)
                                {
                                    Extents3d ex = ent.GeometricExtents;
                                    minX = ex.MinPoint.X; minY = ex.MinPoint.Y;
                                    maxX = ex.MaxPoint.X; maxY = ex.MaxPoint.Y;
                                    coVung = true;
                                }
                                tr.Commit();
                            }
                        }
                        else if (per.Status == PromptStatus.None)
                        {
                            Point3d p1, p2;
                            if (!LenhDraw.ChonDiemKhongOsnap(ed, "\nGóc thứ nhất vùng lưới: ", null, false, out p1)) return;
                            if (!LenhDraw.ChonDiemKhongOsnap(ed, "\nGóc đối diện vùng lưới: ", p1, false, out p2)) return;
                            minX = Math.Min(p1.X, p2.X); minY = Math.Min(p1.Y, p2.Y);
                            maxX = Math.Max(p1.X, p2.X); maxY = Math.Max(p1.Y, p2.Y);
                            coVung = true;
                        }
                        if (!coVung) return;
                        double w = maxX - minX, h = maxY - minY;
                        ed.WriteMessage("\nKích thước vùng đào đắp (rộng × cao): " + w.ToString("F2", CultureInfo.InvariantCulture) + " × " + h.ToString("F2", CultureInfo.InvariantCulture) + " m");
                        string kt = LenhDraw.HoiChuoi(ed, "\nKích thước ô (m) <20>: ");
                        if (kt == null) return;
                        double o = 20.0;
                        if (kt.Length > 0 && !double.TryParse(kt.Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out o))
                        { ed.WriteMessage("\nKích thước ô phải là số dương."); return; }
                        int nc = Math.Max(1, (int)Math.Ceiling(w / o - 1e-9));
                        int nh = Math.Max(1, (int)Math.Ceiling(h / o - 1e-9));
                        cot = nc + "x" + o.ToString("G", CultureInfo.InvariantCulture);
                        hang = nh + "x" + o.ToString("G", CultureInfo.InvariantCulture);
                        gocLuoi = F4(minX) + "," + F4(minY);
                        ed.WriteMessage("\n  → Tự động tính: " + nc + " cột (" + cot + ") × " + nh + " hàng (" + hang + ").");
                    }
                    else
                    {
                        cot = LenhDraw.HoiChuoi(ed, "\nCột (vd 7x20 hoặc Enter giữ nguyên): "); if (cot == null) return;
                        hang = LenhDraw.HoiChuoi(ed, "\nHàng (vd 5x20 hoặc Enter giữ nguyên): "); if (hang == null) return;
                        bu = LenhDraw.HoiChuoi(ed, "\nBù dữ liệu ngoài vùng đo (m, Enter giữ nguyên): "); if (bu == null) return;
                        gocXoay = LenhDraw.HoiChuoi(ed, "\nGóc xoay độ (Enter giữ nguyên): "); if (gocXoay == null) return;
                    }
                }

                if (!LenhDraw.HoiYesNo(ed, "\nÁp dụng thay đổi lưới, tính lại khối lượng và vẽ lại lưới/nhãn?", true))
                { ed.WriteMessage("\nĐã hủy."); return; }

                List<string> args = new List<string>();
                args.Add("--lenh"); args.Add("dat");
                if (cot.Length > 0) { args.Add("--cot"); args.Add(cot); }
                if (hang.Length > 0) { args.Add("--hang"); args.Add(hang); }
                if (bu.Length > 0) { args.Add("--ngoai-suy"); args.Add(bu.Replace(',', '.')); }
                if (gocXoay.Length > 0) { args.Add("--goc"); args.Add(gocXoay.Replace(',', '.')); }
                if (gocLuoi.Length > 0) { args.Add("--goc-luoi"); args.Add(gocLuoi); }

                CauHinh c = CauHinh.Doc();
                string ra = Path.Combine(tmp, "sn_luoi_sua_ra.json");
                object goc = CauNoiPython.ChayArgs(c, "luoi-sua", args.ToArray(), ra);
                ed.WriteMessage("\n" + J.S(J.Get(goc, "thong_bao"), "Đã áp dụng lưới."));
                VeLaiNhom(doc, ed, "SN_LUOI_NET", "luoi,nhan,o,ranh");
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_DICHLUOI_NET", Rt.CommandFlags.Modal)]
        public void DichLuoi()
        {
            LenhDraw.Chay("SN_DICHLUOI_NET", delegate(Document doc, Editor ed)
            {
                Point3d p1, p2;
                if (!LenhDraw.ChonDiemKhongOsnap(ed, "\nĐiểm gốc hiện tại (hay điểm chuẩn): ", null, false, out p1)) return;
                if (!LenhDraw.ChonDiemKhongOsnap(ed, "\nĐiểm mới muốn dịch tới: ", p1, false, out p2)) return;
                double dx = p2.X - p1.X, dy = p2.Y - p1.Y;
                if (!LenhDraw.HoiYesNo(ed, "\nDịch lưới (dx=" + F4(dx) + " m, dy=" + F4(dy) + " m) và tính lại?", true))
                { ed.WriteMessage("\nĐã hủy."); return; }
                CauHinh c = CauHinh.Doc();
                string ra = Path.Combine(CauNoiPython.ThuMucTam(), "sn_dich_ra.json");
                CauNoiPython.ChayArgs(c, "luoi-sua", new string[] { "--lenh", "dich", "--dx", F4(dx), "--dy", F4(dy) }, ra);
                VeLaiNhom(doc, ed, "SN_DICHLUOI_NET", "luoi,nhan,o,ranh");
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_XOAYLUOI_NET", Rt.CommandFlags.Modal)]
        public void XoayLuoi()
        {
            LenhDraw.Chay("SN_XOAYLUOI_NET", delegate(Document doc, Editor ed)
            {
                string s = LenhDraw.HoiChuoi(ed, "\nGóc xoay lưới quanh tâm (độ): ");
                if (string.IsNullOrEmpty(s)) return;
                double goc;
                if (!double.TryParse(s.Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out goc))
                { ed.WriteMessage("\nGóc xoay phải là số (độ)."); return; }
                if (!LenhDraw.HoiYesNo(ed, "\nXoay lưới " + goc.ToString("G", CultureInfo.InvariantCulture) + "° và tính lại?", true))
                { ed.WriteMessage("\nĐã hủy."); return; }
                CauHinh c = CauHinh.Doc();
                string ra = Path.Combine(CauNoiPython.ThuMucTam(), "sn_xoay_ra.json");
                CauNoiPython.ChayArgs(c, "luoi-sua", new string[] { "--lenh", "xoay", "--goc", goc.ToString("G", CultureInfo.InvariantCulture) }, ra);
                VeLaiNhom(doc, ed, "SN_XOAYLUOI_NET", "luoi,nhan,o,ranh");
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_LUOI_BO_NET", Rt.CommandFlags.Modal)]
        public void QuayVeLot()
        {
            LenhDraw.Chay("SN_LUOI_BO_NET", delegate(Document doc, Editor ed)
            {
                if (!LenhDraw.HoiYesNo(ed, "\nBỏ lưới tùy chỉnh, quay về thông số gốc trong lot.yaml và tính lại?", false))
                { ed.WriteMessage("\nĐã hủy."); return; }
                CauHinh c = CauHinh.Doc();
                string ra = Path.Combine(CauNoiPython.ThuMucTam(), "sn_luoi_bo_ra.json");
                CauNoiPython.ChayArgs(c, "luoi-ve-lai-lot-yaml", new string[0], ra);
                VeLaiNhom(doc, ed, "SN_LUOI_BO_NET", "luoi,nhan,o,ranh");
            });
        }

        // ------------------------------------------------------------------ sửa đỉnh & đồng bộ nhãn
        sealed class NhanDinh
        {
            public string Ma;
            public double E, N;
            public string NoiDung;
        }

        static List<NhanDinh> DocNhanDinh(Document doc, string lo, int dot)
        {
            List<NhanDinh> ds = new List<NhanDinh>();
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTableRecord ms = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForRead);
                foreach (ObjectId id in ms)
                {
                    DBText t = tr.GetObject(id, OpenMode.ForRead, false, true) as DBText;
                    if (t == null) continue;
                    List<string> xd = DrawEngine.DocXd(t);
                    if (xd == null || xd[0] != lo || xd[1] != dot.ToString() || xd[3] != "nhan_dinh") continue;
                    string ma = "";
                    for (int i = 4; i < xd.Count; i++)
                        if (xd[i].StartsWith("ma=")) { ma = xd[i].Substring(3); break; }
                    if (ma.Length == 0) continue;
                    NhanDinh nd = new NhanDinh();
                    nd.Ma = ma; nd.E = t.Position.X; nd.N = t.Position.Y; nd.NoiDung = t.TextString ?? "";
                    ds.Add(nd);
                }
                tr.Commit();
            }
            return ds;
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_SUADINH_NET", Rt.CommandFlags.Modal)]
        public void SuaDinh()
        {
            LenhDraw.Chay("SN_SUADINH_NET", delegate(Document doc, Editor ed)
            {
                CauHinh c = CauHinh.Doc();
                string lo; int dot;
                c.MaLoDot(out lo, out dot);
                string ma = "";
                Point3d pt;
                if (LenhDraw.ChonDiemKhongOsnap(ed, "\nChọn điểm gần đỉnh lưới trên bản vẽ (Enter để tự gõ mã đỉnh): ", null, true, out pt))
                {
                    List<NhanDinh> ds = DocNhanDinh(doc, lo, dot);
                    double totNhat = double.MaxValue;
                    foreach (NhanDinh nd in ds)
                    {
                        double d2 = (nd.E - pt.X) * (nd.E - pt.X) + (nd.N - pt.Y) * (nd.N - pt.Y);
                        if (d2 < totNhat) { totNhat = d2; ma = nd.Ma; }
                    }
                    if (ma.Length > 0) ed.WriteMessage("\n  → Đỉnh gần nhất: " + ma);
                }
                if (ma.Length == 0)
                {
                    ma = LenhDraw.HoiChuoi(ed, "\nMã đỉnh cần sửa (vd D03-05): ");
                    if (string.IsNullOrEmpty(ma)) return;
                }

                PromptKeywordOptions bm = new PromptKeywordOptions("\nBề mặt sửa cao độ [Do/Moc] <Do>: ");
                bm.Keywords.Add("Do"); bm.Keywords.Add("Moc"); bm.Keywords.Default = "Do"; bm.AllowNone = true;
                PromptResult rbm = ed.GetKeywords(bm);
                if (rbm.Status != PromptStatus.OK && rbm.Status != PromptStatus.None) return;
                string beMat = (rbm.Status == PromptStatus.OK && rbm.StringResult == "Moc") ? "moc" : "do";

                string zs = LenhDraw.HoiChuoi(ed, "\nCao độ mới (m) cho đỉnh " + ma + " (" + beMat + "): ");
                if (string.IsNullOrEmpty(zs)) return;
                double z;
                if (!double.TryParse(zs.Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out z))
                { ed.WriteMessage("\nCao độ phải là số."); return; }

                string lyDo = LenhDraw.HoiChuoi(ed, "\nLý do sửa (Enter để bỏ trống): ");
                if (lyDo == null) return;

                if (!LenhDraw.HoiYesNo(ed, "\nĐặt đỉnh " + ma + " (" + beMat + ") = " + z.ToString("F3", CultureInfo.InvariantCulture) + " m và tính lại?", true))
                { ed.WriteMessage("\nĐã hủy."); return; }

                string tmp = CauNoiPython.ThuMucTam();
                string csv = Path.Combine(tmp, "sn_suadinh.csv");
                string dong = ma + "," + z.ToString("F4", CultureInfo.InvariantCulture) + "," + beMat + "," + lyDo.Replace(",", ";");
                File.WriteAllText(csv, "ma,z,be_mat,ly_do\n" + dong + "\n", new UTF8Encoding(false));

                string ra = Path.Combine(tmp, "sn_suadinh_ra.json");
                List<string> args = new List<string>();
                args.Add("--tu-file"); args.Add(csv);
                if (lyDo.Length > 0) { args.Add("--ly-do"); args.Add(lyDo); }
                CauNoiPython.ChayArgs(c, "hieuchinh-nhieu", args.ToArray(), ra);
                VeLaiNhom(doc, ed, "SN_SUADINH_NET", "nhan,o,ranh");
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_DONGBO_NET", Rt.CommandFlags.Modal)]
        public void DongBo()
        {
            LenhDraw.Chay("SN_DONGBO_NET", delegate(Document doc, Editor ed)
            {
                CauHinh c = CauHinh.Doc();
                string lo; int dot;
                c.MaLoDot(out lo, out dot);
                if (lo.Length == 0) { ed.WriteMessage("\nChưa chọn lô — gõ SN_LOT."); return; }
                List<NhanDinh> ds = DocNhanDinh(doc, lo, dot);
                if (ds.Count == 0) { ed.WriteMessage("\nBản vẽ chưa có nhãn đỉnh nào của lô " + lo + " đợt " + dot + "."); return; }

                // Nhãn đỉnh trong bản vẽ gồm 3 dòng trên cùng vị trí hoặc text chứa giá trị số (Mốc / Đo / Chênh):
                // gom theo mã đỉnh, phân biệt bằng tiền tố "M:" / "D:" hoặc khớp số thực.
                Dictionary<string, double[]> gop = new Dictionary<string, double[]>();
                foreach (NhanDinh nd in ds)
                {
                    double[] v;
                    if (!gop.TryGetValue(nd.Ma, out v)) { v = new double[] { double.NaN, double.NaN }; gop[nd.Ma] = v; }
                    string s = nd.NoiDung.Trim();
                    Match m = Regex.Match(s, "[-+]?\\d+(?:[.,]\\d+)?");
                    if (!m.Success) continue;
                    double so;
                    if (!double.TryParse(m.Value.Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out so)) continue;
                    if (s.StartsWith("M", StringComparison.OrdinalIgnoreCase)) v[0] = so;
                    else if (s.StartsWith("D", StringComparison.OrdinalIgnoreCase) || s.Contains("Đ")) v[1] = so;
                }

                string tmp = CauNoiPython.ThuMucTam();
                string csv = Path.Combine(tmp, "sn_dongbo.csv");
                StringBuilder sb = new StringBuilder();
                sb.AppendLine("ma,z_moc,z_do");
                foreach (KeyValuePair<string, double[]> kv in gop)
                {
                    string zm = double.IsNaN(kv.Value[0]) ? "" : F4(kv.Value[0]);
                    string zd = double.IsNaN(kv.Value[1]) ? "" : F4(kv.Value[1]);
                    if (zm.Length > 0 || zd.Length > 0) sb.AppendLine(kv.Key + "," + zm + "," + zd);
                }
                File.WriteAllText(csv, sb.ToString(), new UTF8Encoding(false));

                string ra = Path.Combine(tmp, "sn_dongbo_ra.json");
                object kq = CauNoiPython.ChayArgs(c, "dong-bo", new string[] { "--tu-file", csv }, ra);
                ed.WriteMessage("\n" + J.S(J.Get(kq, "du_lieu", "van_ban"), J.S(J.Get(kq, "thong_bao"))));
                if (!LenhDraw.HoiYesNo(ed, "\nChấp nhận các chênh lệch trên vào lưới?", false))
                { ed.WriteMessage("\nĐã hủy — chưa thay đổi lưới."); return; }

                CauNoiPython.ChayArgs(c, "dong-bo", new string[] { "--tu-file", csv, "--chap-nhan" }, ra);
                VeLaiNhom(doc, ed, "SN_DONGBO_NET", "nhan,o,ranh");
            });
        }

        // ------------------------------------------------------------------ duyệt cổng
        [Rt.CommandMethod("SANNEN_DRAW", "SN_DUYET_NET", Rt.CommandFlags.Modal)]
        public void Duyet()
        {
            LenhDraw.Chay("SN_DUYET_NET", delegate(Document doc, Editor ed)
            {
                PromptKeywordOptions o = new PromptKeywordOptions("\nChọn cổng cần duyệt [1/2/3] (1=Dữ liệu, 2=Bề mặt, 3=Số liệu): ");
                o.Keywords.Add("1"); o.Keywords.Add("2"); o.Keywords.Add("3");
                PromptResult r = ed.GetKeywords(o);
                if (r.Status != PromptStatus.OK) return;
                int cong;
                if (!int.TryParse(r.StringResult, out cong)) return;

                string macDinhNguoi = Environment.UserName + " (QS)";
                string nguoi = LenhDraw.HoiChuoi(ed, "\nNgười duyệt <" + macDinhNguoi + ">: ");
                if (nguoi == null) return;
                if (nguoi.Length == 0) nguoi = macDinhNguoi;

                string bangChung = LenhDraw.HoiChuoi(ed, "\nNhập nguyên văn câu đồng ý duyệt cổng " + cong + " (bắt buộc): ");
                if (string.IsNullOrEmpty(bangChung))
                {
                    ed.WriteMessage("\nKhông có nguyên văn câu đồng ý — chưa duyệt (RULES 4).");
                    return;
                }

                CauHinh c = CauHinh.Doc();
                string ra = Path.Combine(CauNoiPython.ThuMucTam(), "sn_duyet_ra.json");
                object kq = CauNoiPython.ChayArgs(c, "duyet", new string[] {
                    "--cong", cong.ToString(CultureInfo.InvariantCulture),
                    "--nguoi", nguoi,
                    "--bang-chung", bangChung
                }, ra);
                ed.WriteMessage("\n" + J.S(J.Get(kq, "thong_bao"), "Đã duyệt cổng " + cong + "."));
            });
        }

        // ------------------------------------------------------------------ chọn biên lô / breakline / khởi tạo bề mặt
        static string TrichVong2DJson(Document doc, SelectionSet ss)
        {
            List<string> vongs = new List<string>();
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (SelectedObject so in ss)
                {
                    if (so == null) continue;
                    Entity ent = tr.GetObject(so.ObjectId, OpenMode.ForRead) as Entity;
                    Polyline pl = ent as Polyline;
                    if (pl != null && pl.NumberOfVertices >= 3)
                    {
                        List<string> pts = new List<string>();
                        for (int i = 0; i < pl.NumberOfVertices; i++)
                        {
                            Point2d p = pl.GetPoint2dAt(i);
                            double b = pl.GetBulgeAt(i);
                            pts.Add("[" + F4(p.X) + "," + F4(p.Y) + "," + b.ToString("F6", CultureInfo.InvariantCulture) + "]");
                        }
                        bool khep = pl.Closed || (pl.GetPoint2dAt(0).GetDistanceTo(pl.GetPoint2dAt(pl.NumberOfVertices - 1)) < 1e-4);
                        vongs.Add("{\"khep_kin\":" + (khep ? "true" : "false") + ",\"dinh\":[" + string.Join(",", pts.ToArray()) + "]}");
                    }
                    else
                    {
                        Polyline2d p2 = ent as Polyline2d;
                        if (p2 != null)
                        {
                            List<string> pts = new List<string>();
                            foreach (ObjectId vid in p2)
                            {
                                Vertex2d v = tr.GetObject(vid, OpenMode.ForRead) as Vertex2d;
                                if (v != null) pts.Add("[" + F4(v.Position.X) + "," + F4(v.Position.Y) + "," + v.Bulge.ToString("F6", CultureInfo.InvariantCulture) + "]");
                            }
                            if (pts.Count >= 3)
                                vongs.Add("{\"khep_kin\":" + (p2.Closed ? "true" : "false") + ",\"dinh\":[" + string.Join(",", pts.ToArray()) + "]}");
                        }
                    }
                }
                tr.Commit();
            }
            if (vongs.Count == 0) return null;
            return "{\"vong\":[" + string.Join(",", vongs.ToArray()) + "]}";
        }

        static string TrichDutGay3DJson(Document doc, SelectionSet ss)
        {
            List<string> duongs = new List<string>();
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (SelectedObject so in ss)
                {
                    if (so == null) continue;
                    Entity ent = tr.GetObject(so.ObjectId, OpenMode.ForRead) as Entity;
                    Line ln = ent as Line;
                    if (ln != null)
                    {
                        duongs.Add("[[" + F4(ln.StartPoint.X) + "," + F4(ln.StartPoint.Y) + "," + F4(ln.StartPoint.Z) + "],["
                                 + F4(ln.EndPoint.X) + "," + F4(ln.EndPoint.Y) + "," + F4(ln.EndPoint.Z) + "]]");
                        continue;
                    }
                    Polyline pl = ent as Polyline;
                    if (pl != null && pl.NumberOfVertices >= 2)
                    {
                        List<string> pts = new List<string>();
                        double elev = pl.Elevation;
                        for (int i = 0; i < pl.NumberOfVertices; i++)
                        {
                            Point2d p = pl.GetPoint2dAt(i);
                            pts.Add("[" + F4(p.X) + "," + F4(p.Y) + "," + F4(elev) + "]");
                        }
                        duongs.Add("[" + string.Join(",", pts.ToArray()) + "]");
                        continue;
                    }
                    Polyline3d p3 = ent as Polyline3d;
                    if (p3 != null)
                    {
                        List<string> pts = new List<string>();
                        foreach (ObjectId vid in p3)
                        {
                            PolylineVertex3d v = tr.GetObject(vid, OpenMode.ForRead) as PolylineVertex3d;
                            if (v != null) pts.Add("[" + F4(v.Position.X) + "," + F4(v.Position.Y) + "," + F4(v.Position.Z) + "]");
                        }
                        if (pts.Count >= 2) duongs.Add("[" + string.Join(",", pts.ToArray()) + "]");
                    }
                }
                tr.Commit();
            }
            if (duongs.Count == 0) return null;
            return "{\"dut_gay\":[" + string.Join(",", duongs.ToArray()) + "]}";
        }

        static string TrichDiemCadCsv(Document doc, SelectionSet ss, string prefix, out int soDiem)
        {
            soDiem = 0;
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("id,northing,easting,z,code");
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (SelectedObject so in ss)
                {
                    if (so == null) continue;
                    Entity ent = tr.GetObject(so.ObjectId, OpenMode.ForRead) as Entity;
                    DBPoint pt = ent as DBPoint;
                    if (pt != null)
                    {
                        soDiem++;
                        sb.AppendLine(prefix + "-" + soDiem + "," + F4(pt.Position.Y) + "," + F4(pt.Position.X) + "," + F4(pt.Position.Z) + ",point");
                        continue;
                    }
                    BlockReference br = ent as BlockReference;
                    if (br != null)
                    {
                        soDiem++;
                        sb.AppendLine(prefix + "-" + soDiem + "," + F4(br.Position.Y) + "," + F4(br.Position.X) + "," + F4(br.Position.Z) + ",block");
                        continue;
                    }
                    DBText tx = ent as DBText;
                    if (tx != null)
                    {
                        double z;
                        if (double.TryParse((tx.TextString ?? "").Trim().Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out z))
                        {
                            soDiem++;
                            sb.AppendLine(prefix + "-" + soDiem + "," + F4(tx.Position.Y) + "," + F4(tx.Position.X) + "," + F4(z) + ",text");
                        }
                        continue;
                    }
                    Line ln = ent as Line;
                    if (ln != null)
                    {
                        soDiem++; sb.AppendLine(prefix + "-" + soDiem + "," + F4(ln.StartPoint.Y) + "," + F4(ln.StartPoint.X) + "," + F4(ln.StartPoint.Z) + ",line");
                        soDiem++; sb.AppendLine(prefix + "-" + soDiem + "," + F4(ln.EndPoint.Y) + "," + F4(ln.EndPoint.X) + "," + F4(ln.EndPoint.Z) + ",line");
                        continue;
                    }
                    Polyline pl = ent as Polyline;
                    if (pl != null)
                    {
                        double elev = pl.Elevation;
                        for (int i = 0; i < pl.NumberOfVertices; i++)
                        {
                            Point2d p = pl.GetPoint2dAt(i);
                            soDiem++; sb.AppendLine(prefix + "-" + soDiem + "," + F4(p.Y) + "," + F4(p.X) + "," + F4(elev) + ",pline2d");
                        }
                        continue;
                    }
                    Polyline3d p3 = ent as Polyline3d;
                    if (p3 != null)
                    {
                        foreach (ObjectId vid in p3)
                        {
                            PolylineVertex3d v = tr.GetObject(vid, OpenMode.ForRead) as PolylineVertex3d;
                            if (v != null)
                            {
                                soDiem++; sb.AppendLine(prefix + "-" + soDiem + "," + F4(v.Position.Y) + "," + F4(v.Position.X) + "," + F4(v.Position.Z) + ",pline3d");
                            }
                        }
                    }
                }
                tr.Commit();
            }
            return soDiem > 0 ? sb.ToString() : null;
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_CHONBIEN_NET", Rt.CommandFlags.Modal)]
        public void ChonBien()
        {
            LenhDraw.Chay("SN_CHONBIEN_NET", delegate(Document doc, Editor ed)
            {
                PromptSelectionOptions pso = new PromptSelectionOptions();
                pso.MessageForAdding = "\nChọn đa tuyến khép kín làm biên lô (ranh giới đào đắp): ";
                PromptSelectionResult psr = ed.GetSelection(pso);
                if (psr.Status != PromptStatus.OK) return;
                string js = TrichVong2DJson(doc, psr.Value);
                if (js == null) { ed.WriteMessage("\nChưa chọn được đa tuyến hợp lệ (cần ≥ 3 đỉnh)."); return; }
                string tmp = CauNoiPython.ThuMucTam();
                string p = Path.Combine(tmp, "sn_cad_bien_lo.json"), ra = Path.Combine(tmp, "sn_chonbien_ra.json");
                File.WriteAllText(p, js, new UTF8Encoding(false));
                object kq = CauNoiPython.ChayArgs(CauHinh.Doc(), "khoi-tao-be-mat", new string[] { "--file-bien-lo", p, "--chi-nhap" }, ra);
                ed.WriteMessage("\n" + J.S(J.Get(kq, "thong_bao"), "Đã cập nhật biên lô."));
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_CHONDUTGAY_NET", Rt.CommandFlags.Modal)]
        public void ChonDutGay()
        {
            LenhDraw.Chay("SN_CHONDUTGAY_NET", delegate(Document doc, Editor ed)
            {
                PromptSelectionOptions pso = new PromptSelectionOptions();
                pso.MessageForAdding = "\nChọn các đường đứt gãy địa hình (Breakline: Line, 2D/3D Polyline): ";
                PromptSelectionResult psr = ed.GetSelection(pso);
                if (psr.Status != PromptStatus.OK) return;
                string js = TrichDutGay3DJson(doc, psr.Value);
                if (js == null) { ed.WriteMessage("\nKhông có đường đứt gãy hợp lệ (cần ≥ 2 đỉnh)."); return; }
                string tmp = CauNoiPython.ThuMucTam();
                string p = Path.Combine(tmp, "sn_cad_dut_gay.json"), ra = Path.Combine(tmp, "sn_chondg_ra.json");
                File.WriteAllText(p, js, new UTF8Encoding(false));
                object kq = CauNoiPython.ChayArgs(CauHinh.Doc(), "khoi-tao-be-mat", new string[] { "--file-dut-gay", p, "--chi-nhap" }, ra);
                ed.WriteMessage("\n" + J.S(J.Get(kq, "thong_bao"), "Đã cập nhật đường đứt gãy (Breakline)."));
            });
        }

        [Rt.CommandMethod("SANNEN_DRAW", "SN_TAOMAT_NET", Rt.CommandFlags.Modal)]
        public void TaoMat()
        {
            LenhDraw.Chay("SN_TAOMAT_NET", delegate(Document doc, Editor ed)
            {
                string tmp = CauNoiPython.ThuMucTam();
                List<string> args = new List<string>();
                args.Add("--xac-nhan-anh-xa");

                PromptKeywordOptions kbm = new PromptKeywordOptions("\nChọn dữ liệu MHTN (mặt bằng gốc) từ đâu? [Cad/Excel/GiuNguyen] <GiuNguyen>: ");
                kbm.Keywords.Add("Cad"); kbm.Keywords.Add("Excel"); kbm.Keywords.Add("GiuNguyen");
                kbm.Keywords.Default = "GiuNguyen"; kbm.AllowNone = true;
                PromptResult r1 = ed.GetKeywords(kbm);
                if (r1.Status == PromptStatus.Cancel) return;
                string c1 = r1.Status == PromptStatus.OK ? r1.StringResult : "GiuNguyen";
                if (c1 == "Cad")
                {
                    PromptSelectionOptions pso = new PromptSelectionOptions();
                    pso.MessageForAdding = "\nChọn các đối tượng AutoCAD tạo MHTN (Point, Block, Text, Line, 2D/3D Polyline): ";
                    PromptSelectionResult psr = ed.GetSelection(pso);
                    if (psr.Status == PromptStatus.OK)
                    {
                        int nDiem;
                        string csv = TrichDiemCadCsv(doc, psr.Value, "MOC", out nDiem);
                        if (csv != null)
                        {
                            string f = Path.Combine(tmp, "sn_cad_chon_moc.csv");
                            File.WriteAllText(f, csv, new UTF8Encoding(false));
                            args.Add("--nguon-moc"); args.Add("cad_chon"); args.Add("--file-moc"); args.Add(f);
                            ed.WriteMessage("\n  → Đã trích " + nDiem + " điểm MHTN từ CAD.");
                        }
                    }
                }
                else if (c1 == "Excel")
                {
                    string f = LenhDraw.HoiChuoi(ed, "\nĐường dẫn file Excel/CSV cho MHTN: ");
                    if (!string.IsNullOrEmpty(f))
                    {
                        args.Add("--nguon-moc"); args.Add(f.EndsWith(".csv", StringComparison.OrdinalIgnoreCase) ? "csv" : "excel");
                        args.Add("--file-moc"); args.Add(f);
                    }
                }

                PromptKeywordOptions ktk = new PromptKeywordOptions("\nChọn dữ liệu MHTK (mặt tính toán) từ đâu? [Cad/Excel/GiuNguyen] <GiuNguyen>: ");
                ktk.Keywords.Add("Cad"); ktk.Keywords.Add("Excel"); ktk.Keywords.Add("GiuNguyen");
                ktk.Keywords.Default = "GiuNguyen"; ktk.AllowNone = true;
                PromptResult r2 = ed.GetKeywords(ktk);
                if (r2.Status == PromptStatus.Cancel) return;
                string c2 = r2.Status == PromptStatus.OK ? r2.StringResult : "GiuNguyen";
                if (c2 == "Cad")
                {
                    PromptSelectionOptions pso = new PromptSelectionOptions();
                    pso.MessageForAdding = "\nChọn các đối tượng AutoCAD tạo MHTK (Point, Block, Text, Line, 2D/3D Polyline): ";
                    PromptSelectionResult psr = ed.GetSelection(pso);
                    if (psr.Status == PromptStatus.OK)
                    {
                        int nDiem;
                        string csv = TrichDiemCadCsv(doc, psr.Value, "DO", out nDiem);
                        if (csv != null)
                        {
                            string f = Path.Combine(tmp, "sn_cad_chon_do.csv");
                            File.WriteAllText(f, csv, new UTF8Encoding(false));
                            args.Add("--nguon-do"); args.Add("cad_chon"); args.Add("--file-do"); args.Add(f);
                            ed.WriteMessage("\n  → Đã trích " + nDiem + " điểm MHTK từ CAD.");
                        }
                    }
                }
                else if (c2 == "Excel")
                {
                    string f = LenhDraw.HoiChuoi(ed, "\nĐường dẫn file Excel/CSV cho MHTK: ");
                    if (!string.IsNullOrEmpty(f))
                    {
                        args.Add("--nguon-do"); args.Add(f.EndsWith(".csv", StringComparison.OrdinalIgnoreCase) ? "csv" : "excel");
                        args.Add("--file-do"); args.Add(f);
                    }
                }

                if (LenhDraw.HoiYesNo(ed, "\nChọn thêm đường đứt gãy (Breakline) trên bản vẽ?", false))
                {
                    PromptSelectionOptions pso = new PromptSelectionOptions();
                    pso.MessageForAdding = "\nChọn các đường Breakline (Line, 2D/3D Polyline): ";
                    PromptSelectionResult psr = ed.GetSelection(pso);
                    if (psr.Status == PromptStatus.OK)
                    {
                        string js = TrichDutGay3DJson(doc, psr.Value);
                        if (js != null)
                        {
                            string p = Path.Combine(tmp, "sn_cad_dut_gay.json");
                            File.WriteAllText(p, js, new UTF8Encoding(false));
                            args.Add("--file-dut-gay"); args.Add(p);
                        }
                    }
                }

                if (LenhDraw.HoiYesNo(ed, "\nChọn biên lô (ranh giới đào đắp) trên bản vẽ?", false))
                {
                    PromptSelectionOptions pso = new PromptSelectionOptions();
                    pso.MessageForAdding = "\nChọn đa tuyến khép kín làm biên lô: ";
                    PromptSelectionResult psr = ed.GetSelection(pso);
                    if (psr.Status == PromptStatus.OK)
                    {
                        string js = TrichVong2DJson(doc, psr.Value);
                        if (js != null)
                        {
                            string p = Path.Combine(tmp, "sn_cad_bien_lo.json");
                            File.WriteAllText(p, js, new UTF8Encoding(false));
                            args.Add("--file-bien-lo"); args.Add(p);
                        }
                    }
                }

                if (!LenhDraw.HoiYesNo(ed, "\nKhởi tạo mô hình địa hình TIN (MHTN + MHTK) và chuẩn hóa biên lô?", true))
                { ed.WriteMessage("\nĐã hủy."); return; }

                string ra = Path.Combine(tmp, "sn_taomat_ra.json");
                object kq = CauNoiPython.ChayArgs(CauHinh.Doc(), "khoi-tao-be-mat", args.ToArray(), ra);
                ed.WriteMessage("\n" + J.S(J.Get(kq, "du_lieu", "van_ban")));
                ed.WriteMessage("\n" + J.S(J.Get(kq, "thong_bao"), "Đã khởi tạo mô hình địa hình thành công."));
                VeLaiNhom(doc, ed, "SN_TAOMAT_NET", "3d");
            });
        }
    }
}
