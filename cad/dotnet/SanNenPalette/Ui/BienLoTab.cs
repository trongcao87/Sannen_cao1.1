// Tab "Biên lô": thông tin biên đã chuẩn hóa (số đỉnh, chu vi, diện tích, vùng loại trừ) + Hiện/Ẩn, Zoom, Nhập lại biên.
using System;
using System.Collections.Generic;
using System.Windows.Forms;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using SanNen.Palette.Models;
using SanNen.Palette.Services;

namespace SanNen.Palette.Ui
{
    public sealed class BienLoTab : TabCoSo
    {
        readonly ListView _bang = TaoBang(new string[] { "Mục", "Giá trị" }, new int[] { 190, 140 });
        readonly Label _ghiChu = new Label();

        public override string TenTab { get { return "Biên lô"; } }

        public BienLoTab()
        {
            _ghiChu.Dock = DockStyle.Bottom;
            _ghiChu.AutoSize = true;
            _ghiChu.Tag = "mo";
            _ghiChu.Padding = new Padding(6);
            _ghiChu.Text = "Biên lô là QUYẾT ĐỊNH của người (lot.yaml). «Nhập lại biên» và «Chuẩn hóa» chạy lệnh có xác nhận trên dòng lệnh.";
            _bang.Dock = DockStyle.Fill;
            Than.Controls.Add(_bang);
            Than.Controls.Add(_ghiChu);
            Than.Controls.Add(HangNut(
                Nut("Chọn biên lô trên CAD…", delegate { Bao(CadLenh.ChonBien() ?? "Chọn đa tuyến biên lô trên bản vẽ (SN_CHONBIEN)."); }),
                Nut("Hiện/Ẩn biên", HienAnBien),
                Nut("Zoom", ZoomBien),
                Nut("Nhập lại biên (SN_NHAP)", delegate { GuiLenh("SN_NHAP ", "Nhập lại dữ liệu và biên lô"); }),
                Nut("Chuẩn hóa biên (SN_LO)", delegate { GuiLenh("SN_LO ", "Chuẩn hóa biên lô"); })));
            DungXong();
        }

        protected override void CapNhat(DuLieuPal d)
        {
            DoDong(_bang, d.Ok ? d.Dong("bien_dong") : new List<string[]>());
        }

        List<string> LopBien(QuetKQ q, int dot)
        {
            List<string> r = CadLop.LopCua(q, BangNhom.NguonBienLo, dot);
            foreach (string l in CadLop.LopCua(q, BangNhom.NguonLoaiTru, dot)) if (!r.Contains(l)) r.Add(l);
            foreach (string l in CadLop.LopCua(q, BangNhom.Tim("ranh"), dot)) if (!r.Contains(l)) r.Add(l);
            if (r.Count == 0 && q != null)
            {
                foreach (string l in q.TrangThaiLop.Keys)
                    if (l.IndexOf("BIEN", StringComparison.OrdinalIgnoreCase) >= 0 || l.IndexOf("RANH", StringComparison.OrdinalIgnoreCase) >= 0)
                        r.Add(l);
            }
            return r;
        }

        void HienAnBien()
        {
            Document doc = CadLop.DocHienHanh();
            QuetKQ q = DieuPhoi.Quet;
            string lo; int dot;
            DieuPhoi.LoDot(out lo, out dot);
            if (doc == null || q == null) { Bao("Chưa đọc được bản vẽ hiện hành."); return; }
            List<string> lop = LopBien(q, dot);
            if (lop.Count == 0) { Bao("Bản vẽ chưa có layer biên lô (SN-BIENLO / SN-RANH-DAODAP). Bấm «Chọn biên lô trên CAD…» trước."); return; }
            bool bat = CadLop.TrangThai(q, lop) != "hien";
            List<string> gc = new List<string>();
            int k = CadLop.DatLop(doc, lop, bat, gc);
            Bao((bat ? "Đã hiện " : "Đã ẩn ") + k + " layer biên lô (" + string.Join(", ", lop.ToArray()) + ")" + (gc.Count > 0 ? " · " + string.Join("; ", gc.ToArray()) : ""));
            BeginInvoke(new Action(delegate { try { DieuPhoi.YeuCauNgay(false, true); } catch (Exception ex) { BaoLoi(ex); } }));
        }

        void ZoomBien()
        {
            Document doc = CadLop.DocHienHanh();
            if (doc == null) { Bao("Chưa mở bản vẽ nào."); return; }
            QuetKQ q = DieuPhoi.Quet;
            string lo; int dot;
            DieuPhoi.LoDot(out lo, out dot);
            if (q != null)
            {
                List<ObjectId> ids = new List<ObjectId>();
                foreach (Muc m in CadLop.CuaNhom(q, BangNhom.NguonBienLo, lo, dot)) ids.Add(m.Id);
                if (CadLop.Zoom(doc, ids)) { Bao("Đã zoom tới biên lô trong bản vẽ."); return; }
            }
            // chưa có layer biên trong bản vẽ: zoom theo hộp bao của lõi (lo.json qua thong-tin)
            DuLieuPal d = DieuPhoi.Cuoi;
            List<object> hb = d != null && d.Ok ? J.L(d.Get("so_lieu", "bien", "hop_bao")) : new List<object>();
            if (hb.Count >= 4)
            {
                double a = J.D(hb[0]).GetValueOrDefault(), b = J.D(hb[1]).GetValueOrDefault(), c = J.D(hb[2]).GetValueOrDefault(), e = J.D(hb[3]).GetValueOrDefault();
                CadLop.ZoomCuaSo(doc, new Point3d(a, b, 0), new Point3d(c, e, 0));
                Bao("Đã zoom theo hộp bao biên lô (lõi).");
            }
            else Bao("Chưa có biên lô để zoom — chạy bước nhập và chuẩn hóa biên.");
        }
    }
}
