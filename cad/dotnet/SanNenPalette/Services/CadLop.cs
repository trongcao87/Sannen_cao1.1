// Thao tác với bản vẽ AutoCAD (lớp mỏng): quét đối tượng SAN NỀN, bật/tắt layer, zoom, chọn.
// Không có phép tính nghiệp vụ. Bật/tắt layer CHỈ đặt IsOff (không đóng băng, không xoá, không đổi layer hiện hành).
// Khi cần vẽ/purge hàng loạt (bước 2 của lộ trình trong _agent/KIEN-TRUC-TOI-UU.md) sẽ thêm Drawing/DrawEngine.
using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using SanNen.Palette.Models;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace SanNen.Palette.Services
{
    /// <summary>Một đối tượng SAN NỀN trong ModelSpace (đọc từ layer SN-* và XDATA appid "SANNEN":
    /// 1000 mã lô, 1000 đợt, 1000 hash, 1000 loại, 1000 "k=v"...).</summary>
    public sealed class Muc
    {
        public ObjectId Id;
        public string Lop;
        public string Lo = "";
        public int Dot;
        public string Loai = "";
        public string Ten = "";          // "ten=MC1" của mặt cắt
        public bool CoXd;
    }

    public sealed class QuetKQ
    {
        public string Loi;
        public Dictionary<string, string> TrangThaiLop = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);   // hien | an | dong-bang
        public List<Muc> Muc = new List<Muc>();
        public string LopHienHanh = "";
    }

    public static class CadLop
    {
        public const string AppId = "SANNEN";

        public static Document DocHienHanh()
        {
            return AcApp.DocumentManager.MdiActiveDocument;
        }

        /// <summary>Một lượt quét: trạng thái mọi layer + các đối tượng nằm trên layer SN-* trong ModelSpace. Chỉ ĐỌC.</summary>
        public static QuetKQ Quet(Document doc)
        {
            QuetKQ q = new QuetKQ();
            if (doc == null) { q.Loi = "Chưa mở bản vẽ nào."; return q; }
            try
            {
                Database db = doc.Database;
                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
                    foreach (ObjectId id in lt)
                    {
                        LayerTableRecord r = (LayerTableRecord)tr.GetObject(id, OpenMode.ForRead);
                        q.TrangThaiLop[r.Name] = r.IsFrozen ? "dong-bang" : (r.IsOff ? "an" : "hien");
                    }
                    LayerTableRecord cur = (LayerTableRecord)tr.GetObject(db.Clayer, OpenMode.ForRead);
                    q.LopHienHanh = cur.Name;

                    BlockTableRecord ms = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForRead);
                    foreach (ObjectId id in ms)
                    {
                        Entity e = tr.GetObject(id, OpenMode.ForRead, false) as Entity;
                        if (e == null || !BangNhom.LaLopSanNen(e.Layer)) continue;
                        Muc m = new Muc();
                        m.Id = id;
                        m.Lop = e.Layer;
                        using (ResultBuffer rb = e.GetXDataForApplication(AppId))
                        {
                            if (rb != null)
                            {
                                List<string> s = new List<string>();
                                foreach (TypedValue tv in rb)
                                    if (tv.TypeCode == (short)DxfCode.ExtendedDataAsciiString) s.Add(Convert.ToString(tv.Value));
                                if (s.Count >= 4)
                                {
                                    m.CoXd = true;
                                    m.Lo = s[0];
                                    int dot; if (int.TryParse(s[1], out dot)) m.Dot = dot;
                                    m.Loai = s[3];
                                    for (int i = 4; i < s.Count; i++) if (s[i].StartsWith("ten=")) m.Ten = s[i].Substring(4);
                                }
                            }
                        }
                        q.Muc.Add(m);
                    }
                    tr.Commit();
                }
            }
            catch (Exception ex)
            {
                q.Loi = "Không đọc được bản vẽ: " + ex.Message;
            }
            return q;
        }

        public static List<string> LopCua(QuetKQ q, NhomDef g, int dot)
        {
            return BangNhom.LopThucCo(g, q.TrangThaiLop.Keys, dot);
        }

        /// <summary>Đối tượng của đúng lô + đợt trong nhóm (nhóm có XDATA: lọc theo XDATA; nhóm nguồn: mọi đối tượng trên layer).</summary>
        public static List<Muc> CuaNhom(QuetKQ q, NhomDef g, string lo, int dot)
        {
            List<Muc> ra = new List<Muc>();
            HashSet<string> lop = new HashSet<string>(LopCua(q, g, dot), StringComparer.OrdinalIgnoreCase);
            if (lop.Count == 0) return ra;
            foreach (Muc m in q.Muc)
            {
                if (!lop.Contains(m.Lop)) continue;
                if (g.CoXdata && !(m.CoXd && m.Lo == lo && m.Dot == dot)) continue;
                ra.Add(m);
            }
            return ra;
        }

        /// <summary>"hien" | "an" | "mot-phan" | "dong-bang" | "khong" (chưa có layer).</summary>
        public static string TrangThai(QuetKQ q, IEnumerable<string> lop)
        {
            int hien = 0, an = 0, dong = 0, tong = 0;
            foreach (string l in lop)
            {
                string t;
                if (!q.TrangThaiLop.TryGetValue(l, out t)) continue;
                tong++;
                if (t == "hien") hien++; else if (t == "an") an++; else dong++;
            }
            if (tong == 0) return "khong";
            if (dong > 0) return "dong-bang";
            if (hien == tong) return "hien";
            if (an == tong) return "an";
            return "mot-phan";
        }

        /// <summary>Bật (bat=true) / tắt các layer SN-*. Trả số layer đổi; ghiChu nhận lý do bỏ qua (đóng băng, layer hiện hành).</summary>
        public static int DatLop(Document doc, IEnumerable<string> ten, bool bat, List<string> ghiChu)
        {
            int n = 0;
            Database db = doc.Database;
            using (DocumentLock khoa = doc.LockDocument())
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
                string cur = ((LayerTableRecord)tr.GetObject(db.Clayer, OpenMode.ForRead)).Name;
                foreach (string t in ten)
                {
                    if (!BangNhom.LaLopSanNen(t) || !lt.Has(t)) continue;
                    LayerTableRecord r = (LayerTableRecord)tr.GetObject(lt[t], OpenMode.ForRead);
                    if (r.IsFrozen) { ghiChu.Add(t + ": đang đóng băng, không đổi"); continue; }
                    if (r.IsOff == !bat) continue;
                    if (!bat && string.Equals(t, cur, StringComparison.OrdinalIgnoreCase))
                    {
                        ghiChu.Add(t + ": là layer hiện hành, không tắt");
                        continue;
                    }
                    r.UpgradeOpen();
                    r.IsOff = !bat;
                    n++;
                }
                tr.Commit();
            }
            if (n > 0) { try { doc.Editor.Regen(); } catch (Exception) { } }
            return n;
        }

        /// <summary>Chỉ hiện các layer trong giu; tắt mọi layer SN-* còn lại (trừ layer hiện hành). Layer của nhà thầu không đụng.</summary>
        public static int ChiHien(Document doc, QuetKQ q, IEnumerable<string> giu, List<string> ghiChu)
        {
            HashSet<string> g = new HashSet<string>(giu, StringComparer.OrdinalIgnoreCase);
            List<string> tat = new List<string>();
            foreach (string l in q.TrangThaiLop.Keys)
                if (BangNhom.LaLopSanNen(l) && !g.Contains(l)) tat.Add(l);
            int n = DatLop(doc, g, true, ghiChu);
            return n + DatLop(doc, tat, false, ghiChu);
        }

        // ------------------------------------------------------------------ zoom / chọn
        public static bool Zoom(Document doc, IEnumerable<ObjectId> ids)
        {
            bool co = false;
            Point3d mn = Point3d.Origin, mx = Point3d.Origin;
            using (Transaction tr = doc.Database.TransactionManager.StartTransaction())
            {
                foreach (ObjectId id in ids)
                {
                    try
                    {
                        Entity e = tr.GetObject(id, OpenMode.ForRead, false) as Entity;
                        if (e == null) continue;
                        Extents3d x = e.GeometricExtents;
                        if (!co) { mn = x.MinPoint; mx = x.MaxPoint; co = true; }
                        else
                        {
                            mn = new Point3d(Math.Min(mn.X, x.MinPoint.X), Math.Min(mn.Y, x.MinPoint.Y), Math.Min(mn.Z, x.MinPoint.Z));
                            mx = new Point3d(Math.Max(mx.X, x.MaxPoint.X), Math.Max(mx.Y, x.MaxPoint.Y), Math.Max(mx.Z, x.MaxPoint.Z));
                        }
                    }
                    catch (Exception) { }          // đối tượng không có hộp bao: bỏ qua
                }
                tr.Commit();
            }
            if (!co) return false;
            ZoomCuaSo(doc, mn, mx);
            return true;
        }

        /// <summary>Zoom vừa hộp bao (toạ độ WCS), chừa lề 15 %, giữ tỉ lệ khung nhìn hiện tại.</summary>
        public static void ZoomCuaSo(Document doc, Point3d mn, Point3d mx)
        {
            Editor ed = doc.Editor;
            using (ViewTableRecord v = ed.GetCurrentView())
            {
                Matrix3d w2d = Matrix3d.PlaneToWorld(v.ViewDirection);
                w2d = Matrix3d.Displacement(v.Target - Point3d.Origin) * w2d;
                w2d = Matrix3d.Rotation(-v.ViewTwist, v.ViewDirection, v.Target) * w2d;
                w2d = w2d.Inverse();
                Extents3d e = new Extents3d(mn, mx);
                e.TransformBy(w2d);
                double w = (e.MaxPoint.X - e.MinPoint.X) * 1.15, h = (e.MaxPoint.Y - e.MinPoint.Y) * 1.15;
                if (w < 5) w = 5;
                if (h < 5) h = 5;
                double tl = v.Width / v.Height;
                if (w / h > tl) h = w / tl; else w = h * tl;
                v.CenterPoint = new Point2d((e.MaxPoint.X + e.MinPoint.X) / 2.0, (e.MaxPoint.Y + e.MinPoint.Y) / 2.0);
                v.Width = w;
                v.Height = h;
                ed.SetCurrentView(v);
            }
        }

        public static void ZoomDiem(Document doc, double e, double n, double canh)
        {
            ZoomCuaSo(doc, new Point3d(e - canh / 2, n - canh / 2, 0), new Point3d(e + canh / 2, n + canh / 2, 0));
        }

        public static bool Chon(Document doc, IEnumerable<ObjectId> ids)
        {
            List<ObjectId> ds = new List<ObjectId>(ids);
            if (ds.Count == 0) return false;
            doc.Editor.SetImpliedSelection(ds.ToArray());
            return true;
        }
    }
}
