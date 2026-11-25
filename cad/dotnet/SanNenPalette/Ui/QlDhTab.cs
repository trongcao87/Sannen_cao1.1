// Tab "QL ĐH" (quản lý địa hình): cây kiểu Civil 3D Toolspace. Hộp kiểm = Hiện/Ẩn layer (IsOff), kèm số đối tượng của ĐÚNG
// lô + đợt (layer + XDATA "SANNEN"). Chuột phải: Hiện/Ẩn · Chỉ hiện nhóm này · Zoom tới nhóm · Chọn đối tượng nhóm.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using SanNen.Palette.Models;
using SanNen.Palette.Services;

namespace SanNen.Palette.Ui
{
    public sealed class QlDhTab : TabCoSo
    {
        sealed class NutCay
        {
            public string Ten;
            public NhomDef Nhom;           // null: nút gộp (không có layer riêng)
            public string MatCat;          // tên mặt cắt (lọc theo XDATA ten=)
            public List<NutCay> Con = new List<NutCay>();
            public NutCay(string ten, NhomDef nhom) { Ten = ten; Nhom = nhom; }
            public NutCay Them(NutCay c) { Con.Add(c); return c; }
        }

        readonly TreeView _cay = new TreeView();
        readonly ContextMenuStrip _menu = new ContextMenuStrip();
        bool _dat;
        bool _daMoMacDinh;

        public override string TenTab { get { return "QL ĐH"; } }

        public QlDhTab()
        {
            _cay.Dock = DockStyle.Fill;
            _cay.CheckBoxes = true;
            _cay.HideSelection = false;
            _cay.ShowLines = true;
            _cay.ItemHeight = 24;
            _cay.BorderStyle = BorderStyle.FixedSingle;
            _cay.AfterCheck += SauTich;
            _cay.NodeMouseClick += ChuotCay;
            _cay.NodeMouseDoubleClick += delegate(object s, TreeNodeMouseClickEventArgs e) { Chay(delegate { Zoom(e.Node); }); };

            _menu.Items.Add("Hiện / Ẩn", null, delegate { Chay(delegate { DoiHienAn(_cay.SelectedNode); }); });
            _menu.Items.Add("Chỉ hiện nhóm này", null, delegate { Chay(delegate { ChiHien(_cay.SelectedNode); }); });
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add("Zoom tới nhóm", null, delegate { Chay(delegate { Zoom(_cay.SelectedNode); }); });
            _menu.Items.Add("Chọn đối tượng nhóm", null, delegate { Chay(delegate { Chon(_cay.SelectedNode); }); });

            FlowLayoutPanel hang = HangNut(
                Nut("Tạo/cập nhật MH (DD_DH)…", delegate { Bao(CadLenh.TaoMat() ?? "Mở hộp thoại Quản lý & khởi tạo mô hình địa hình (SN_TAOMAT)."); }),
                Nut("Chọn Breakline…", delegate { Bao(CadLenh.ChonDutGay() ?? "Chọn đường Breakline trên bản vẽ (SN_CHONDUTGAY)."); }),
                Nut("Chọn biên lô…", delegate { Bao(CadLenh.ChonBien() ?? "Chọn biên lô trên bản vẽ (SN_CHONBIEN)."); }),
                Nut("Hiện tất cả SAN NỀN", delegate { HienTatCa(true); }),
                Nut("Ẩn tất cả", delegate { HienTatCa(false); }),
                Nut("Xem 3D", delegate { Bao(CadLenh.Xem3D() ?? "Xem 3D bằng C# (SN_TIN3D_NET) — chọn bề mặt trên dòng lệnh AutoCAD."); }));
            Than.Controls.Add(_cay);
            Than.Controls.Add(hang);
            DungXong();
        }

        // ---------------------------------------------------------------- dựng cây
        NutCay DungCay(string lo, int dot, QuetKQ q)
        {
            NutCay goc = new NutCay("Lô " + (lo.Length > 0 ? lo : "?") + " · đợt " + dot, null);
            NutCay mh = goc.Them(new NutCay("Mô hình địa hình", null));
            NutCay mhtn = mh.Them(new NutCay("MHTN (mặt mốc)", null));
            mhtn.Them(new NutCay("Hồ địa hình 3D", BangNhom.Tim("moc")));
            mhtn.Them(new NutCay("Điểm mốc", BangNhom.NguonDiemMoc));
            NutCay mhtk = mh.Them(new NutCay("MHTK (mặt đo / sau san lấp)", null));
            mhtk.Them(new NutCay("Hồ địa hình 3D", BangNhom.Tim("do")));
            mhtk.Them(new NutCay("Điểm đo", BangNhom.NguonDiemDo));
            mh.Them(new NutCay("Tam giác thiếu dữ liệu", BangNhom.Tim("qc")));
            mh.Them(new NutCay("Đứt gãy địa hình", BangNhom.NguonDutGay));
            mh.Them(new NutCay("Đường đồng mức địa hình", BangNhom.NguonDongMuc));
            mh.Them(new NutCay("Đường bao địa hình (biên lô)", BangNhom.NguonBienLo));
            mh.Them(new NutCay("Vùng loại trừ", BangNhom.NguonLoaiTru));
            NutCay luoi = goc.Them(new NutCay("Lưới ô", null));
            luoi.Them(new NutCay("Đường lưới", BangNhom.Tim("luoi")));
            luoi.Them(new NutCay("Nhãn đỉnh lưới", BangNhom.Tim("nhan")));
            luoi.Them(new NutCay("Nhãn ô (khối lượng)", BangNhom.Tim("o")));
            goc.Them(new NutCay("Ranh đào–đắp", BangNhom.Tim("ranh")));
            NutCay mc = goc.Them(new NutCay("Mặt cắt", BangNhom.Tim("matcat")));
            SortedDictionary<string, bool> ten = new SortedDictionary<string, bool>(StringComparer.OrdinalIgnoreCase);
            if (DieuPhoi.Cuoi != null && DieuPhoi.Cuoi.Ok) foreach (MatCatDto m in DieuPhoi.Cuoi.MatCat()) ten[m.Ten] = true;
            if (q != null) foreach (Muc m in q.Muc) if (m.Loai == "mat_cat" && m.Ten.Length > 0 && m.Lo == lo) ten[m.Ten] = true;
            foreach (string t in ten.Keys) { NutCay c = mc.Them(new NutCay(t, BangNhom.Tim("matcat"))); c.MatCat = t; }
            goc.Them(new NutCay("Bảng in", BangNhom.Tim("bang")));
            return goc;
        }

        static List<string> LopCua(NutCay n, QuetKQ q, int dot)
        {
            HashSet<string> r = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (n.Nhom != null) foreach (string l in CadLop.LopCua(q, n.Nhom, dot)) r.Add(l);
            else foreach (NutCay c in n.Con) foreach (string l in LopCua(c, q, dot)) r.Add(l);
            return new List<string>(r);
        }

        static List<Muc> MucCua(NutCay n, QuetKQ q, string lo, int dot)
        {
            List<Muc> r = new List<Muc>();
            if (n.Nhom != null)
            {
                foreach (Muc m in CadLop.CuaNhom(q, n.Nhom, lo, dot))
                    if (n.MatCat == null || string.Equals(m.Ten, n.MatCat, StringComparison.OrdinalIgnoreCase)) r.Add(m);
                return r;
            }
            HashSet<ObjectId> thay = new HashSet<ObjectId>();
            foreach (NutCay c in n.Con) foreach (Muc m in MucCua(c, q, lo, dot)) if (thay.Add(m.Id)) r.Add(m);
            return r;
        }

        void Xay()
        {
            QuetKQ q = DieuPhoi.Quet;
            string lo; int dot;
            DieuPhoi.LoDot(out lo, out dot);
            if (q != null && q.Loi != null) Bao(q.Loi);
            HashSet<string> mo = new HashSet<string>();
            GhiMo(_cay.Nodes, mo);
            _dat = true;
            _cay.BeginUpdate();
            try
            {
                _cay.Nodes.Clear();
                TaoNode(_cay.Nodes, DungCay(lo, dot, q), "", q, lo, dot);
                bool macDinh = !_daMoMacDinh;
                RestoreMo(_cay.Nodes, mo, macDinh, 0);
                _daMoMacDinh = true;
            }
            finally { _cay.EndUpdate(); _dat = false; }
        }

        static void GhiMo(TreeNodeCollection ds, HashSet<string> mo)
        {
            foreach (TreeNode n in ds) { if (n.IsExpanded) mo.Add(n.Name); GhiMo(n.Nodes, mo); }
        }

        static void RestoreMo(TreeNodeCollection ds, HashSet<string> mo, bool macDinh, int sau)
        {
            foreach (TreeNode n in ds)
            {
                if (mo.Contains(n.Name) || (macDinh && sau < 2)) n.Expand();
                RestoreMo(n.Nodes, mo, macDinh, sau + 1);
            }
        }

        void TaoNode(TreeNodeCollection ds, NutCay n, string cha, QuetKQ q, string lo, int dot)
        {
            TreeNode t = new TreeNode();
            t.Name = cha + "/" + n.Ten;
            t.Tag = n;
            if (q == null || q.Loi != null)
            {
                t.Text = n.Ten + "  (chưa đọc được bản vẽ)";
                t.ForeColor = Mau.ChuMo;
            }
            else
            {
                List<string> lop = LopCua(n, q, dot);
                if (lop.Count == 0)
                {
                    t.Text = n.Ten + "  — chưa có lớp";
                    t.ForeColor = Mau.ChuMo;
                }
                else
                {
                    string tt = CadLop.TrangThai(q, lop);
                    int dem = MucCua(n, q, lo, dot).Count;
                    t.Text = n.Ten + "  ·  " + dem + (tt == "mot-phan" ? "  (một phần)" : (tt == "dong-bang" ? "  (đóng băng)" : ""));
                    t.Checked = tt == "hien";
                    t.ForeColor = Mau.Chu;
                }
            }
            ds.Add(t);
            foreach (NutCay c in n.Con) TaoNode(t.Nodes, c, t.Name, q, lo, dot);
        }

        protected override void CapNhat(DuLieuPal d) { Xay(); }

        protected override void CapNhatBanVe() { Xay(); }

        // ---------------------------------------------------------------- thao tác
        bool BoiCanh(TreeNode tn, out NutCay n, out QuetKQ q, out Document doc, out string lo, out int dot)
        {
            n = tn == null ? null : tn.Tag as NutCay;
            q = DieuPhoi.Quet;
            doc = CadLop.DocHienHanh();
            DieuPhoi.LoDot(out lo, out dot);
            if (n == null) { Bao("Chọn một nút trên cây trước."); return false; }
            if (doc == null || q == null || q.Loi != null) { Bao("Chưa đọc được bản vẽ hiện hành."); return false; }
            return true;
        }

        void SauTich(object s, TreeViewEventArgs e)
        {
            if (_dat || e.Action == TreeViewAction.Unknown) return;
            Chay(delegate { DatHienAn(e.Node, e.Node.Checked); });
        }

        void ChuotCay(object s, TreeNodeMouseClickEventArgs e)
        {
            if (e.Button != MouseButtons.Right) return;
            _cay.SelectedNode = e.Node;
            _menu.Show(_cay, e.Location);
        }

        void DoiHienAn(TreeNode tn)
        {
            if (tn == null) { Bao("Chọn một nút trên cây trước."); return; }
            DatHienAn(tn, !tn.Checked);
        }

        void DatHienAn(TreeNode tn, bool bat)
        {
            NutCay n; QuetKQ q; Document doc; string lo; int dot;
            if (!BoiCanh(tn, out n, out q, out doc, out lo, out dot)) { LamMoiBanVe(); return; }
            List<string> lop = LopCua(n, q, dot);
            if (lop.Count == 0) { Bao("«" + n.Ten + "» chưa có layer trong bản vẽ này."); LamMoiBanVe(); return; }
            List<string> gc = new List<string>();
            int k = CadLop.DatLop(doc, lop, bat, gc);
            Bao((bat ? "Đã hiện " : "Đã ẩn ") + k + " layer của «" + n.Ten + "»" + (gc.Count > 0 ? " · " + string.Join("; ", gc.ToArray()) : ""));
            LamMoiBanVe();
        }

        void ChiHien(TreeNode tn)
        {
            NutCay n; QuetKQ q; Document doc; string lo; int dot;
            if (!BoiCanh(tn, out n, out q, out doc, out lo, out dot)) return;
            List<string> lop = LopCua(n, q, dot);
            if (lop.Count == 0) { Bao("«" + n.Ten + "» chưa có layer trong bản vẽ này."); return; }
            List<string> gc = new List<string>();
            CadLop.ChiHien(doc, q, lop, gc);
            Bao("Chỉ hiện «" + n.Ten + "»; các layer SAN NỀN khác đã tắt (layer nhà thầu không đụng)" + (gc.Count > 0 ? " · " + string.Join("; ", gc.ToArray()) : ""));
            LamMoiBanVe();
        }

        void HienTatCa(bool bat)
        {
            Document doc = CadLop.DocHienHanh();
            QuetKQ q = DieuPhoi.Quet;
            if (doc == null || q == null) { Bao("Chưa đọc được bản vẽ hiện hành."); return; }
            List<string> tat = new List<string>();
            foreach (string l in q.TrangThaiLop.Keys) if (BangNhom.LaLopSanNen(l)) tat.Add(l);
            List<string> gc = new List<string>();
            int k = CadLop.DatLop(doc, tat, bat, gc);
            Bao((bat ? "Đã hiện " : "Đã ẩn ") + k + " layer SAN NỀN" + (gc.Count > 0 ? " · " + string.Join("; ", gc.ToArray()) : ""));
            LamMoiBanVe();
        }

        void Zoom(TreeNode tn)
        {
            NutCay n; QuetKQ q; Document doc; string lo; int dot;
            if (!BoiCanh(tn, out n, out q, out doc, out lo, out dot)) return;
            List<ObjectId> ids = new List<ObjectId>();
            foreach (Muc m in MucCua(n, q, lo, dot)) ids.Add(m.Id);
            Bao(CadLop.Zoom(doc, ids) ? "Đã zoom tới «" + n.Ten + "» (" + ids.Count + " đối tượng)." : "«" + n.Ten + "» chưa có đối tượng của lô/đợt này để zoom.");
        }

        void Chon(TreeNode tn)
        {
            NutCay n; QuetKQ q; Document doc; string lo; int dot;
            if (!BoiCanh(tn, out n, out q, out doc, out lo, out dot)) return;
            List<ObjectId> ids = new List<ObjectId>();
            foreach (Muc m in MucCua(n, q, lo, dot)) ids.Add(m.Id);
            Bao(CadLop.Chon(doc, ids) ? "Đã chọn " + ids.Count + " đối tượng của «" + n.Ten + "» (đối tượng trên layer đang ẩn không chọn được)." : "«" + n.Ten + "» chưa có đối tượng để chọn.");
        }

        // quét lại bản vẽ SAU khi thoát khỏi sự kiện của cây (tránh sửa cây trong lúc đang xử lý hộp kiểm)
        void LamMoiBanVe()
        {
            BeginInvoke(new Action(delegate { try { DieuPhoi.YeuCauNgay(false, true); } catch (Exception ex) { BaoLoi(ex); } }));
        }
    }
}
