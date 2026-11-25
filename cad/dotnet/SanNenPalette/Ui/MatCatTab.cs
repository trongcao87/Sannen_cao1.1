// Tab "Mặt cắt": danh sách mặt cắt đã tạo (số liệu từ lõi qua thong-tin --json), tạo mới / zoom / xoá.
// Tạo và xoá chạy lệnh LISP có sẵn (SN_MATCAT, SN_XOAMATCAT) — có xác nhận trên dòng lệnh. Chuyển sang C# ở bước 3 lộ trình.
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Windows.Forms;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using SanNen.Palette.Models;
using SanNen.Palette.Services;

namespace SanNen.Palette.Ui
{
    public sealed class MatCatTab : TabCoSo
    {
        readonly ListView _ds = TaoBang(new string[] { "Tên", "Dài (m)", "Đào (m²)", "Đắp (m²)", "Thiếu (m)" }, new int[] { 70, 70, 80, 80, 80 });
        readonly Label _trong = new Label();

        public override string TenTab { get { return "Mặt cắt"; } }

        public MatCatTab()
        {
            _ds.Dock = DockStyle.Fill;
            _ds.MultiSelect = false;
            _ds.DoubleClick += delegate { Chay(ZoomBieuDo); };
            _trong.Dock = DockStyle.Bottom;
            _trong.AutoSize = true;
            _trong.Tag = "mo";
            _trong.Padding = new Padding(6);
            _trong.Text = "Số liệu đào/đắp trên mặt cắt do lõi tính (matcat_*.json). Bấm đúp một dòng để zoom tới biểu đồ.";
            Than.Controls.Add(_ds);
            Than.Controls.Add(_trong);
            Than.Controls.Add(HangNut(
                Nut("Tạo mặt cắt mới…", delegate { Bao(CadLenh.MatCat() ?? "Tạo mặt cắt (chọn hai điểm A, B) — xem dòng lệnh AutoCAD."); }),
                Nut("Zoom tới", ZoomBieuDo),
                Nut("Zoom tuyến A–B", ZoomTuyen),
                Nut("Xoá mặt cắt này", Xoa)));
            DungXong();
        }

        static string So(double? v, string dang)
        {
            return v.HasValue ? v.Value.ToString(dang, System.Globalization.CultureInfo.CurrentCulture) : "—";
        }

        protected override void CapNhat(DuLieuPal d)
        {
            _ds.BeginUpdate();
            _ds.Items.Clear();
            if (d.Ok)
            {
                foreach (MatCatDto m in d.MatCat())
                {
                    ListViewItem it = new ListViewItem(new string[] { m.Ten, So(m.ChieuDai, "N2"), So(m.DaoM2, "N2"), So(m.DapM2, "N2"), So(m.ThieuM, "N2") });
                    it.Tag = m;
                    _ds.Items.Add(it);
                }
            }
            _ds.EndUpdate();
            _trong.Text = _ds.Items.Count == 0 && d.Ok ? "Chưa tạo mặt cắt nào — bấm «Tạo mặt cắt mới…»." : "Số liệu đào/đắp trên mặt cắt do lõi tính (matcat_*.json). Bấm đúp một dòng để zoom tới biểu đồ.";
        }

        MatCatDto Chon()
        {
            if (_ds.SelectedItems.Count == 0) { Bao("Chọn một mặt cắt trong danh sách trước."); return null; }
            return _ds.SelectedItems[0].Tag as MatCatDto;
        }

        void ZoomBieuDo()
        {
            MatCatDto m = Chon();
            Document doc = CadLop.DocHienHanh();
            if (m == null || doc == null) return;
            QuetKQ q = DieuPhoi.Quet;
            string lo; int dot;
            DieuPhoi.LoDot(out lo, out dot);
            List<ObjectId> ids = new List<ObjectId>();
            if (q != null)
                foreach (Muc x in CadLop.CuaNhom(q, BangNhom.Tim("matcat"), lo, dot))
                    if (string.Equals(x.Ten, m.Ten, StringComparison.OrdinalIgnoreCase)) ids.Add(x.Id);
            if (CadLop.Zoom(doc, ids)) Bao("Đã zoom tới biểu đồ mặt cắt " + m.Ten + ".");
            else Bao("Mặt cắt " + m.Ten + " chưa được vẽ trong bản vẽ này — dùng «Zoom tuyến A–B» hoặc SN_MATCAT.");
        }

        void ZoomTuyen()
        {
            MatCatDto m = Chon();
            Document doc = CadLop.DocHienHanh();
            if (m == null || doc == null) return;
            if (m.A == null || m.B == null) { Bao("Mặt cắt " + m.Ten + " chưa có toạ độ A, B (kết quả cũ) — tạo lại bằng SN_MATCAT."); return; }
            double d = Math.Max(Math.Abs(m.A[0] - m.B[0]), Math.Abs(m.A[1] - m.B[1]));
            CadLop.ZoomCuaSo(doc, new Point3d(Math.Min(m.A[0], m.B[0]) - d * 0.05, Math.Min(m.A[1], m.B[1]) - d * 0.05, 0),
                                  new Point3d(Math.Max(m.A[0], m.B[0]) + d * 0.05, Math.Max(m.A[1], m.B[1]) + d * 0.05, 0));
            Bao("Đã zoom tới tuyến " + m.Ten + ".");
        }

        void Xoa()
        {
            MatCatDto m = Chon();
            if (m == null) return;
            if (!Regex.IsMatch(m.Ten, "^[A-Za-z0-9_\\-]+$"))
            {
                Bao("Tên mặt cắt có ký tự đặc biệt — gõ SN_XOAMATCAT trên dòng lệnh để xoá.");
                return;
            }
            // Xoá đối tượng VẼ của mặt cắt trong bản vẽ (file số liệu giữ nguyên) và HỎI Yes/No trên dòng lệnh.
            Bao(CadLenh.XoaMatCat(m.Ten) ?? "Xoá mặt cắt " + m.Ten + " khỏi bản vẽ (cần xác nhận trên dòng lệnh).");
        }
    }
}
