// DrawEngine — THỰC THI kế hoạch vẽ bằng API AutoCAD: một DocumentLock + một Transaction, ModelSpace mở MỘT lần.
// Không tính toán nghiệp vụ: vẽ đúng những gì kế hoạch ghi. Mỗi đối tượng mang XDATA appid "SANNEN" đúng cấu trúc của sannen.lsp:
//     (1001 "SANNEN") (1000 mã_lô) (1000 đợt) (1000 hash) (1000 loại) (1000 "k=v")...
// nên lệnh đếm/purge/SN_QL/palette đang có (LISP và C#) nhận ra đối tượng do DrawEngine vẽ y hệt đối tượng do file .lsp vẽ.
// Chỉ tham chiếu accoremgd.dll + acdbmgd.dll (không acmgd, không WinForms/WPF) để chạy được cả trong accoreconsole.exe.
// Vẽ lại: Purge nhóm sắp vẽ TRƯỚC (RULES 5) → hai lần vẽ không nhân đôi. Purge chỉ xóa đối tượng có XDATA khớp lô (và đợt).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using System.Web.Script.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Colors;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;

namespace SanNen.Draw
{
    public sealed class KetQuaVe
    {
        public Dictionary<string, int> Ve = new Dictionary<string, int>();     // loại → số đối tượng đã vẽ
        public Dictionary<string, int> Xoa = new Dictionary<string, int>();    // loại → số đối tượng đã xóa (hoặc SẼ xóa nếu chỉ đếm)
        public List<string> GhiChu = new List<string>();
        public long MsXoa, MsVe, MsTong;
        public bool Co3D;
        public double[] Hop3D = new double[6];                                  // minX,minY,minZ,maxX,maxY,maxZ của mặt 3D vừa vẽ

        public int TongVe { get { return Tong(Ve); } }
        public int TongXoa { get { return Tong(Xoa); } }

        static int Tong(Dictionary<string, int> d)
        {
            int n = 0;
            foreach (KeyValuePair<string, int> kv in d) n += kv.Value;
            return n;
        }

        static string Dem(Dictionary<string, int> d)
        {
            if (d.Count == 0) return "không có";
            List<string> t = new List<string>();
            foreach (KeyValuePair<string, int> kv in d) t.Add(kv.Key + " " + kv.Value);
            return string.Join(", ", t.ToArray());
        }

        public string TomTat()
        {
            return "Đã xóa " + TongXoa + " đối tượng cũ (" + Dem(Xoa) + "); đã vẽ " + TongVe + " đối tượng (" + Dem(Ve) + ") trong "
                + MsTong + " ms.";
        }

        public string ToJson()
        {
            Dictionary<string, object> g = new Dictionary<string, object>();
            g["ve"] = Ve;
            g["xoa"] = Xoa;
            g["tong_ve"] = TongVe;
            g["tong_xoa"] = TongXoa;
            g["ms_xoa"] = MsXoa;
            g["ms_ve"] = MsVe;
            g["ms_tong"] = MsTong;
            g["ghi_chu"] = GhiChu;
            JavaScriptSerializer js = new JavaScriptSerializer();
            return js.Serialize(g);
        }
    }

    public static class DrawEngine
    {
        public const string AppId = "SANNEN";

        // ------------------------------------------------------------------ vẽ
        /// <summary>Thực thi kế hoạch trong MỘT transaction: đăng ký appid → purge (các mục `xoa`) → tạo layer → vẽ → bật/tắt layer.
        /// Lỗi ở bất cứ bước nào: transaction bị hủy, bản vẽ không đổi gì.</summary>
        public static KetQuaVe Ve(Document doc, KeHoach kh)
        {
            KetQuaVe kq = new KetQuaVe();
            Stopwatch tong = Stopwatch.StartNew();
            Database db = doc.Database;
            using (DocumentLock khoa = doc.LockDocument())
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                DangKyAppId(db, tr);
                BlockTableRecord ms = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForWrite);

                Stopwatch sw = Stopwatch.StartNew();
                if (kh.Xoa.Count > 0) QuetVaXoa(tr, ms, kh.MaLo, kh.Dot, kh.Xoa, false, kq.Xoa);
                kq.MsXoa = sw.ElapsedMilliseconds;

                TaoLop(db, tr, kh);
                sw.Restart();
                string[] tienTo = new string[] { kh.MaLo, kh.Dot.ToString(), kh.Hash, null };
                foreach (DoiTuongVe d in kh.DoiTuong)
                {
                    Entity e = Tao(db, tr, ms, d, kq);
                    e.Layer = d.Lop;
                    if (d.Mau != 256) e.ColorIndex = (short)d.Mau;
                    tienTo[3] = d.Loai;
                    e.XData = TaoXd(tienTo, d.Ex);
                    if (e.Database == null)                      // polyface đã tự append trong Tao; còn lại append ở đây
                    {
                        ms.AppendEntity(e);
                        tr.AddNewlyCreatedDBObject(e, true);
                    }
                    int n;
                    kq.Ve.TryGetValue(d.Loai, out n);
                    kq.Ve[d.Loai] = n + 1;
                }
                kq.MsVe = sw.ElapsedMilliseconds;

                BatTatLop(db, tr, kh, kq);
                tr.Commit();
            }
            kq.MsTong = tong.ElapsedMilliseconds;
            return kq;
        }

        static void DangKyAppId(Database db, Transaction tr)
        {
            RegAppTable rat = (RegAppTable)tr.GetObject(db.RegAppTableId, OpenMode.ForRead);
            if (rat.Has(AppId)) return;
            rat.UpgradeOpen();
            RegAppTableRecord r = new RegAppTableRecord();
            r.Name = AppId;
            rat.Add(r);
            tr.AddNewlyCreatedDBObject(r, true);
        }

        static ResultBuffer TaoXd(string[] tienTo, string[] ex)
        {
            int n = 1 + tienTo.Length + (ex == null ? 0 : ex.Length);
            TypedValue[] tv = new TypedValue[n];
            tv[0] = new TypedValue((int)DxfCode.ExtendedDataRegAppName, AppId);
            for (int i = 0; i < tienTo.Length; i++) tv[1 + i] = new TypedValue((int)DxfCode.ExtendedDataAsciiString, tienTo[i]);
            if (ex != null)
                for (int i = 0; i < ex.Length; i++) tv[1 + tienTo.Length + i] = new TypedValue((int)DxfCode.ExtendedDataAsciiString, ex[i]);
            return new ResultBuffer(tv);
        }

        static void TaoLop(Database db, Transaction tr, KeHoach kh)
        {
            LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            foreach (LopDef l in kh.Lop)
            {
                Color mau = Color.FromColorIndex(ColorMethod.ByAci, (short)l.Mau);
                if (!lt.Has(l.Ten))
                {
                    lt.UpgradeOpen();
                    LayerTableRecord r = new LayerTableRecord();
                    r.Name = l.Ten;
                    r.Color = mau;
                    r.IsOff = l.Tat;
                    lt.Add(r);
                    tr.AddNewlyCreatedDBObject(r, true);
                }
                else if (l.DatMau)
                {
                    LayerTableRecord r = (LayerTableRecord)tr.GetObject(lt[l.Ten], OpenMode.ForWrite);
                    r.Color = mau;
                }
            }
            foreach (DoiTuongVe d in kh.DoiTuong)
                if (!lt.Has(d.Lop)) throw new InvalidOperationException("Kế hoạch vẽ dùng layer «" + d.Lop + "» mà không khai trong `lop`.");
        }

        static void BatTatLop(Database db, Transaction tr, KeHoach kh, KetQuaVe kq)
        {
            if (kh.HienLop.Count == 0) return;
            LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            string hienHanh = ((LayerTableRecord)tr.GetObject(db.Clayer, OpenMode.ForRead)).Name;
            foreach (HienLopDef h in kh.HienLop)
            {
                if (!lt.Has(h.Ten)) continue;                     // layer chưa có (vd SN-QC khi không có tam giác thiếu dữ liệu)
                LayerTableRecord r = (LayerTableRecord)tr.GetObject(lt[h.Ten], OpenMode.ForRead);
                if (r.IsOff == !h.Bat) continue;
                if (!h.Bat && string.Equals(h.Ten, hienHanh, StringComparison.OrdinalIgnoreCase))
                {
                    kq.GhiChu.Add(h.Ten + ": là layer hiện hành, không tắt");
                    continue;
                }
                r.UpgradeOpen();
                r.IsOff = !h.Bat;
            }
        }

        static void MoRong(KetQuaVe kq, double x, double y, double z)
        {
            double[] h = kq.Hop3D;
            if (!kq.Co3D)
            {
                h[0] = h[3] = x; h[1] = h[4] = y; h[2] = h[5] = z;
                kq.Co3D = true;
                return;
            }
            if (x < h[0]) h[0] = x; if (y < h[1]) h[1] = y; if (z < h[2]) h[2] = z;
            if (x > h[3]) h[3] = x; if (y > h[4]) h[4] = y; if (z > h[5]) h[5] = z;
        }

        /// <summary>Tạo một thực thể. Trả thực thể CHƯA thuộc cơ sở dữ liệu (Database == null) để nơi gọi append — trừ polyface,
        /// vốn phải append trước khi thêm đỉnh nên đã thuộc ModelSpace khi trả về.</summary>
        static Entity Tao(Database db, Transaction tr, BlockTableRecord ms, DoiTuongVe d, KetQuaVe kq)
        {
            switch (d.Kieu)
            {
                case "polyline":
                {
                    Polyline pl = new Polyline();
                    int n = d.Diem.Length / 2;
                    for (int i = 0; i < n; i++) pl.AddVertexAt(i, new Point2d(d.Diem[2 * i], d.Diem[2 * i + 1]), 0, 0, 0);
                    pl.Closed = d.Dong;
                    return pl;
                }
                case "text":
                {
                    DBText t = new DBText();
                    t.SetDatabaseDefaults(db);
                    t.Position = new Point3d(d.Diem[0], d.Diem[1], 0);
                    t.Height = d.Cao;
                    t.TextString = d.NoiDung;
                    return t;
                }
                case "mtext":
                {
                    MText m = new MText();
                    m.SetDatabaseDefaults(db);
                    m.Location = new Point3d(d.Diem[0], d.Diem[1], 0);
                    m.TextHeight = d.Cao;
                    m.Attachment = AttachmentPoint.MiddleCenter;
                    m.Contents = d.NoiDung;
                    return m;
                }
                case "3dface":
                {
                    Point3d a = new Point3d(d.Dinh[0], d.Dinh[1], d.Dinh[2]), b = new Point3d(d.Dinh[3], d.Dinh[4], d.Dinh[5]),
                        c = new Point3d(d.Dinh[6], d.Dinh[7], d.Dinh[8]);
                    for (int i = 0; i < 9; i += 3) MoRong(kq, d.Dinh[i], d.Dinh[i + 1], d.Dinh[i + 2]);
                    return new Face(a, b, c, c, true, true, true, true);
                }
                case "polyface":
                {
                    PolyFaceMesh pf = new PolyFaceMesh();
                    pf.Layer = d.Lop;
                    ms.AppendEntity(pf);
                    tr.AddNewlyCreatedDBObject(pf, true);
                    int nv = d.Dinh.Length / 3;
                    for (int i = 0; i < nv; i++)
                    {
                        PolyFaceMeshVertex v = new PolyFaceMeshVertex(new Point3d(d.Dinh[3 * i], d.Dinh[3 * i + 1], d.Dinh[3 * i + 2]));
                        pf.AppendVertex(v);
                        tr.AddNewlyCreatedDBObject(v, true);
                        MoRong(kq, d.Dinh[3 * i], d.Dinh[3 * i + 1], d.Dinh[3 * i + 2]);
                    }
                    int nm = d.Mat.Length / 3;
                    for (int i = 0; i < nm; i++)
                    {
                        FaceRecord f = new FaceRecord((short)(d.Mat[3 * i] + 1), (short)(d.Mat[3 * i + 1] + 1), (short)(d.Mat[3 * i + 2] + 1), 0);
                        pf.AppendFaceRecord(f);
                        tr.AddNewlyCreatedDBObject(f, true);
                    }
                    return pf;
                }
            }
            throw new InvalidOperationException("Kiểu đối tượng lạ: " + d.Kieu);
        }

        // ------------------------------------------------------------------ xóa
        /// <summary>Xóa đối tượng kết quả CŨ của đúng lô (và đợt nếu có) khớp một trong các mục `mau`. Không đụng nguồn, không đụng lô khác.</summary>
        public static KetQuaVe Xoa(Document doc, string lo, int? dot, List<XoaDef> mau, bool chiDem)
        {
            KetQuaVe kq = new KetQuaVe();
            Stopwatch sw = Stopwatch.StartNew();
            Database db = doc.Database;
            using (DocumentLock khoa = doc.LockDocument())
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTableRecord ms = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForRead);
                QuetVaXoa(tr, ms, lo, dot, mau, chiDem, kq.Xoa);
                tr.Commit();
            }
            kq.MsXoa = kq.MsTong = sw.ElapsedMilliseconds;
            return kq;
        }

        /// <summary>Số đối tượng SN của lô (và đợt) theo loại — không xóa gì.</summary>
        public static Dictionary<string, int> Dem(Document doc, string lo, int? dot)
        {
            XoaDef tatCa = new XoaDef();
            return Xoa(doc, lo, dot, new List<XoaDef>(new XoaDef[] { tatCa }), true).Xoa;
        }

        /// <summary>Đọc XDATA "SANNEN" thành danh sách chuỗi; null nếu không có hoặc ít hơn 4 trường.</summary>
        internal static List<string> DocXd(Entity e)
        {
            using (ResultBuffer rb = e.GetXDataForApplication(AppId))
            {
                if (rb == null) return null;
                List<string> s = new List<string>();
                foreach (TypedValue tv in rb)
                    if (tv.TypeCode == (short)DxfCode.ExtendedDataAsciiString) s.Add(Convert.ToString(tv.Value));
                return s.Count >= 4 ? s : null;
            }
        }

        static bool Khop(List<string> s, string lo, int? dot, XoaDef x)
        {
            if (s[0] != lo) return false;
            if (dot.HasValue && s[1] != dot.Value.ToString()) return false;
            if (x.Loai != null && s[3] != x.Loai) return false;
            foreach (string k in x.Ex)
                if (!s.GetRange(4, s.Count - 4).Contains(k)) return false;
            if (x.ExMotTrong.Count > 0)
            {
                bool co = false;
                foreach (string k in x.ExMotTrong)
                    if (s.GetRange(4, s.Count - 4).Contains(k)) { co = true; break; }
                if (!co) return false;
            }
            return true;
        }

        static void QuetVaXoa(Transaction tr, BlockTableRecord ms, string lo, int? dot, List<XoaDef> mau, bool chiDem, Dictionary<string, int> dem)
        {
            List<ObjectId> bo = new List<ObjectId>();
            foreach (ObjectId id in ms)
            {
                Entity e = tr.GetObject(id, OpenMode.ForRead, false, true) as Entity;
                if (e == null || !CoXd(e)) continue;
                List<string> s = DocXd(e);
                if (s == null) continue;
                bool khop = false;
                foreach (XoaDef x in mau) if (Khop(s, lo, dot, x)) { khop = true; break; }
                if (!khop) continue;
                int n;
                dem.TryGetValue(s[3], out n);
                dem[s[3]] = n + 1;
                bo.Add(id);
            }
            if (chiDem) return;
            foreach (ObjectId id in bo)
            {
                Entity w = (Entity)tr.GetObject(id, OpenMode.ForWrite, false, true);      // true: kể cả layer đang khóa
                w.Erase();
            }
        }

        /// <summary>Có XDATA của appid SANNEN không (không dựng danh sách chuỗi nếu không cần).</summary>
        static bool CoXd(Entity e)
        {
            using (ResultBuffer rb = e.GetXDataForApplication(AppId)) return rb != null;
        }
    }
}
