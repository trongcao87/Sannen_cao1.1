// Tab "Cảnh báo": phát hiện QC (qc_*.json), việc cần làm (viec_can_lam.md), cảnh báo "kết quả cũ" — tất cả do lõi gom (JSON).
// Bấm đúp dòng có toạ độ → zoom tới điểm đó (như SN_CANHBAO). Palette không tự xử lý việc: quyết định là của người.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Windows.Forms;
using SanNen.Palette.Models;
using SanNen.Palette.Services;

namespace SanNen.Palette.Ui
{
    public sealed class CanhBaoTab : TabCoSo
    {
        readonly ListView _ds = TaoBang(new string[] { "Mức", "Mã", "Mô tả", "Vị trí (E, N)" }, new int[] { 80, 60, 260, 150 });

        public override string TenTab { get { return "Cảnh báo"; } }

        public CanhBaoTab()
        {
            _ds.Dock = DockStyle.Fill;
            _ds.DoubleClick += delegate { Chay(ZoomDong); };
            Than.Controls.Add(_ds);
            Than.Controls.Add(HangNut(
                Nut("Zoom tới điểm", ZoomDong),
                Nut("Cảnh báo / QC… (SN_CANHBAO)", delegate { GuiLenh("SN_CANHBAO ", "Mở hộp cảnh báo QC"); })));
            DungXong();
        }

        static string TenMuc(string m)
        {
            if (m == "chan") return "CHẶN";
            if (m == "canh_bao") return "Cảnh báo";
            if (m == "thong_tin") return "Thông tin";
            return m;
        }

        protected override void CapNhat(DuLieuPal d)
        {
            _ds.BeginUpdate();
            _ds.Items.Clear();
            if (d.Ok)
            {
                foreach (string c in d.CanhBaoCu())
                    Them("Kết quả cũ", "", c, null, Mau.Cam);
                List<CanhBaoDto> cb = d.CanhBao();
                foreach (CanhBaoDto c in cb)
                {
                    double[] vt = c.E.HasValue && c.N.HasValue ? new double[] { c.E.Value, c.N.Value } : null;
                    Them(TenMuc(c.Muc), c.Ma, c.MoTa, vt, c.Muc == "chan" ? Mau.Do : (c.Muc == "canh_bao" ? Mau.Cam : Mau.Chu));
                }
                foreach (object v in J.L(d.Get("viec_can_lam")))
                    Them("Việc " + J.S(J.Get(v, "muc")), J.S(J.Get(v, "ma")), J.S(J.Get(v, "mo_ta")), null, Mau.Chu);
            }
            _ds.EndUpdate();
        }

        void Them(string muc, string ma, string mota, double[] vt, System.Drawing.Color mau)
        {
            string vitri = vt == null ? "—" : vt[0].ToString("F2", CultureInfo.InvariantCulture) + ", " + vt[1].ToString("F2", CultureInfo.InvariantCulture);
            ListViewItem it = new ListViewItem(new string[] { muc, ma, mota, vitri });
            it.Tag = vt;
            it.ForeColor = mau;
            it.ToolTipText = mota;
            _ds.Items.Add(it);
        }

        void ZoomDong()
        {
            if (_ds.SelectedItems.Count == 0) { Bao("Chọn một dòng cảnh báo trước."); return; }
            double[] vt = _ds.SelectedItems[0].Tag as double[];
            Autodesk.AutoCAD.ApplicationServices.Document doc = CadLop.DocHienHanh();
            if (vt == null) { Bao("Dòng này không có toạ độ để zoom."); return; }
            if (doc == null) { Bao("Chưa mở bản vẽ nào."); return; }
            CadLop.ZoomDiem(doc, vt[0], vt[1], 40.0);
            Bao("Đã zoom tới " + vt[0].ToString("F2", CultureInfo.InvariantCulture) + ", " + vt[1].ToString("F2", CultureInfo.InvariantCulture) + ".");
        }
    }
}
