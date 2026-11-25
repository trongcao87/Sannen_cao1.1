// Lớp nền của mọi tab: thanh đầu (↻ Làm mới + giờ cập nhật), dòng lỗi đỏ, vùng thân; nhận sự kiện làm mới của DieuPhoi;
// bọc try/catch mọi handler để lỗi không làm AutoCAD văng.
using System;
using System.Drawing;
using System.Windows.Forms;
using SanNen.Palette.Models;
using SanNen.Palette.Services;

namespace SanNen.Palette.Ui
{
    public abstract class TabCoSo : UserControl
    {
        readonly Panel _dau = new Panel();
        readonly Label _tt = new Label();
        readonly Label _loi = new Label();
        readonly Button _lamMoi = new Button();
        protected readonly Panel Than = new Panel();

        public abstract string TenTab { get; }

        /// <summary>Có số liệu mới từ lõi Python (kể cả khi lỗi: d.Ok = false).</summary>
        protected abstract void CapNhat(DuLieuPal d);

        /// <summary>Bản vẽ vừa được quét lại (layer/đối tượng đổi).</summary>
        protected virtual void CapNhatBanVe() { }

        protected TabCoSo()
        {
            Dock = DockStyle.Fill;
            Than.Dock = DockStyle.Fill;
            _loi.Dock = DockStyle.Top;
            _loi.AutoSize = true;
            _loi.Tag = "loi";
            _loi.Padding = new Padding(6, 4, 6, 4);
            _loi.Visible = false;
            _dau.Dock = DockStyle.Top;
            _dau.Height = 34;
            _lamMoi.Text = "↻ Làm mới";
            _lamMoi.Dock = DockStyle.Right;
            _lamMoi.Width = 100;
            _lamMoi.Click += delegate
            {
                Chay(delegate
                {
                    Bao("Đang làm mới trạng thái lô và bản vẽ…");
                    DieuPhoi.YeuCauNgay(true, true);
                });
            };
            _tt.Dock = DockStyle.Fill;
            _tt.TextAlign = ContentAlignment.MiddleLeft;
            _tt.Tag = "mo";
            _tt.Text = "Đang đọc số liệu…";
            _dau.Controls.Add(_tt);
            _dau.Controls.Add(_lamMoi);
            Controls.Add(Than);
            Controls.Add(_loi);
            Controls.Add(_dau);
            Resize += delegate { _loi.MaximumSize = new Size(Math.Max(100, Width - 8), 0); };
            DieuPhoi.DuLieuDoi += NhanDuLieu;
            DieuPhoi.LopDoi += NhanLop;
            Disposed += delegate { DieuPhoi.DuLieuDoi -= NhanDuLieu; DieuPhoi.LopDoi -= NhanLop; };
        }

        /// <summary>Gọi sau khi dựng xong các điều khiển con của tab.</summary>
        protected void DungXong()
        {
            Mau.Ap(this);
            if (DieuPhoi.Cuoi != null) NhanDuLieu(DieuPhoi.Cuoi);
        }

        public void ApMau()
        {
            Mau.Ap(this);
            if (DieuPhoi.Cuoi != null) NhanDuLieu(DieuPhoi.Cuoi);
        }

        void NhanDuLieu(DuLieuPal d)
        {
            try
            {
                _tt.Text = (d.Ok ? "Cập nhật " : "Lỗi lúc ") + d.Luc.ToString("HH:mm:ss") + (d.Ok ? "  ·  lô " + d.MaLo + ", đợt " + d.Dot : "");
                _loi.Visible = !d.Ok;
                if (!d.Ok)
                {
                    _loi.Text = d.Loi + "  Hiện/Ẩn layer vẫn dùng được.";
                    _loi.ForeColor = Mau.Do;
                }
                CapNhat(d);
            }
            catch (Exception ex) { BaoLoi(ex); }
        }

        void NhanLop()
        {
            try { CapNhatBanVe(); }
            catch (Exception ex) { BaoLoi(ex); }
        }

        // ---------------------------------------------------------------- tiện ích cho tab con
        protected void BaoLoi(Exception ex)
        {
            DieuPhoi.Noi("Palette SAN NỀN — lỗi: " + ex.Message);
            _tt.Text = "Lỗi: " + ex.Message;
        }

        protected void Bao(string s)
        {
            _tt.Text = s;
        }

        /// <summary>Chạy hành động, bắt mọi ngoại lệ.</summary>
        protected void Chay(Action a)
        {
            try { a(); }
            catch (Exception ex) { BaoLoi(ex); }
        }

        /// <summary>Gửi lệnh LISP (có xác nhận trên dòng lệnh) và báo kết quả gửi.</summary>
        protected void GuiLenh(string chuoi, string moTa)
        {
            string loi = CadLenh.Gui(chuoi);
            Bao(loi ?? (moTa + " — xem dòng lệnh AutoCAD."));
        }

        protected Button Nut(string chu, Action hanhDong)
        {
            Button b = new Button();
            b.Text = chu;
            b.AutoSize = true;
            b.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            b.Margin = new Padding(3);
            b.MinimumSize = new Size(0, 28);
            b.Click += delegate { Chay(hanhDong); };
            return b;
        }

        protected static ListView TaoBang(string[] cot, int[] rong)
        {
            ListView lv = new ListView();
            lv.View = View.Details;
            lv.FullRowSelect = true;
            lv.GridLines = true;
            lv.HideSelection = false;
            lv.HeaderStyle = ColumnHeaderStyle.Nonclickable;
            lv.BorderStyle = BorderStyle.FixedSingle;
            for (int i = 0; i < cot.Length; i++) lv.Columns.Add(cot[i], rong[i]);
            lv.Resize += delegate                                         // cột cuối lấp đầy bề ngang còn lại
            {
                int n = lv.Columns.Count, s = 0;
                for (int i = 0; i < n - 1; i++) s += lv.Columns[i].Width;
                int w = lv.ClientSize.Width - s;
                if (n > 0 && w > 60) lv.Columns[n - 1].Width = w;
            };
            return lv;
        }

        protected FlowLayoutPanel HangNut(params Button[] nut)
        {
            FlowLayoutPanel f = new FlowLayoutPanel();
            f.Dock = DockStyle.Top;
            f.AutoSize = true;
            f.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            f.WrapContents = true;
            f.Padding = new Padding(3);
            foreach (Button b in nut) f.Controls.Add(b);
            return f;
        }

        protected static void DoDong(ListView lv, System.Collections.Generic.List<string[]> dong)
        {
            lv.BeginUpdate();
            lv.Items.Clear();
            foreach (string[] r in dong) lv.Items.Add(new ListViewItem(r));
            lv.EndUpdate();
        }
    }
}
