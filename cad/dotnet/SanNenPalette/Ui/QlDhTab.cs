// Tab "QL ĐH" (quản lý địa hình): cây quy trình MHTN (mặt gốc) & MHTK (mặt thiết kế) + nhánh Đồng bộ từ AI Agent (MCP).
// Mỗi bề mặt gồm đủ: Tọa độ (lấy trên CAD / import từ Excel) · Đường đứt gãy · Đường biên lô · Tạo TIN · Tạo 3D Mesh & HTML View ·
// Hiệu chỉnh (Xóa điểm, Thêm điểm, Lật cạnh, Thêm Breakline, Xóa tam giác).
// Hộp kiểm = Hiện/Ẩn layer (IsOff); Click đúp vào nút hành động = chạy lệnh ngay; Bảng dưới hiển thị báo cáo thông số TIN & QC.
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
            public NhomDef Nhom;           // null: nút gộp hoặc nút hành động không gắn layer riêng
            public string MatCat;          // tên mặt cắt (lọc theo XDATA ten=)
            public string LenhCad;         // lệnh CAD chạy khi click đúp / bấm nút thực hiện
            public string MoTaLenh;
            public string KhoaBang;        // khoá nhóm thông số để hiển thị ở bảng dưới ("moc", "do", "qc", "nguon", "bien_dong", ...)
            public List<NutCay> Con = new List<NutCay>();

            public NutCay(string ten, NhomDef nhom)
            {
                Ten = ten; Nhom = nhom;
            }

            public NutCay(string ten, NhomDef nhom, string lenhCad, string moTaLenh, string khoaBang)
            {
                Ten = ten; Nhom = nhom; LenhCad = lenhCad; MoTaLenh = moTaLenh; KhoaBang = khoaBang;
            }

            public NutCay Them(NutCay c) { Con.Add(c); return c; }
        }

        readonly TreeView _cay = new TreeView();
        readonly ListView _bang = TaoBang(new string[] { "Chỉ tiêu / Báo cáo QC", "Giá trị" }, new int[] { 175, 130 });
        readonly ContextMenuStrip _menu = new ContextMenuStrip();
        readonly ToolStripMenuItem _mnuChay = new ToolStripMenuItem("▶ Thực hiện chức năng này");
        bool _dat;
        bool _daMoMacDinh;
        string _khoaBangHienTai = "moc";

        public override string TenTab { get { return "QL ĐH"; } }

        public QlDhTab()
        {
            _cay.Dock = DockStyle.Fill;
            _cay.CheckBoxes = true;
            _cay.HideSelection = false;
            _cay.ShowLines = true;
            _cay.ItemHeight = 23;
            _cay.BorderStyle = BorderStyle.FixedSingle;
            _cay.AfterCheck += SauTich;
            _cay.AfterSelect += SauChon;
            _cay.NodeMouseClick += ChuotCay;
            _cay.NodeMouseDoubleClick += delegate(object s, TreeNodeMouseClickEventArgs e) { Chay(delegate { KichDup(e.Node); }); };

            _mnuChay.Click += delegate { Chay(delegate { ThucHienNut(_cay.SelectedNode); }); };
            _menu.Items.Add(_mnuChay);
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add("Hiện / Ẩn layer", null, delegate { Chay(delegate { DoiHienAn(_cay.SelectedNode); }); });
            _menu.Items.Add("Chỉ hiện nhóm này", null, delegate { Chay(delegate { ChiHien(_cay.SelectedNode); }); });
            _menu.Items.Add("Hiện tất cả layer SAN NỀN", null, delegate { Chay(delegate { HienTatCa(true); }); });
            _menu.Items.Add("Ẩn tất cả layer SAN NỀN", null, delegate { Chay(delegate { HienTatCa(false); }); });
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add("Zoom tới nhóm", null, delegate { Chay(delegate { Zoom(_cay.SelectedNode); }); });
            _menu.Items.Add("Chọn đối tượng nhóm", null, delegate { Chay(delegate { Chon(_cay.SelectedNode); }); });

            _bang.Dock = DockStyle.Bottom;
            _bang.Height = 185;

            Than.Controls.Add(_cay);
            Than.Controls.Add(_bang);
            DungXong();
        }

        // ---------------------------------------------------------------- dựng cây MHTN & MHTK
        void ThemNhanhBeMat(NutCay cha, string maBm, string tenBm, NhomDef nhomMesh, NhomDef nhomDiem)
        {
            string hauTo = maBm == "moc" ? "MOC" : "DO";
            NutCay bm = cha.Them(new NutCay(tenBm, nhomMesh, null, null, maBm));

            // 1. Tọa độ điểm (lấy tọa độ trên CAD hoặc import từ Excel / CSV / DXF và chèn lên CAD)
            NutCay td = bm.Them(new NutCay("1. Tọa độ điểm", nhomDiem, "SN_LAYDIEM_" + hauTo + " ",
                "Quét chọn đối tượng trên CAD để lấy tọa độ điểm cho " + tenBm, maBm));
            td.Them(new NutCay("▶ 1.1 Lấy tọa độ trên CAD (Point/Block/Text/Line/Pline)…", null, "SN_LAYDIEM_" + hauTo + " ",
                "Chọn đối tượng trên bản vẽ CAD để trích tọa độ cho " + tenBm, maBm));
            td.Them(new NutCay("▶ 1.2 Import tọa độ từ Excel / CSV / DXF (chèn lên CAD)…", null, "SN_EXCEL_" + hauTo + " ",
                "Chọn file Excel / CSV / DXF để nhập tọa độ và chèn hiển thị trực quan lên bản vẽ CAD cho " + tenBm, maBm));

            // 2. Đường đứt gãy (Breakline - tùy chọn có hoặc không)
            NutCay dg = bm.Them(new NutCay("2. Đường đứt gãy (Breakline — tùy chọn)", BangNhom.NguonDutGay, "SN_CHONDUTGAY ",
                "Chọn các đường thẳng / đa tuyến 2D-3D làm đường đứt gãy (có thể bỏ qua nếu không có)", maBm));
            dg.Them(new NutCay("▶ Chọn / Gán đường đứt gãy trên CAD (tùy chọn)…", null, "SN_CHONDUTGAY ",
                "Chọn đường Breakline trên bản vẽ CAD", maBm));

            // 3. Phạm vi đường bao (Biên giới hạn tạo lưới tam giác TIN)
            NutCay bl = bm.Them(new NutCay("3. Phạm vi đường bao (Biên lô)", BangNhom.NguonBienLo, "SN_CHONBIEN ",
                "Chọn đa tuyến làm đường bao để lưới tam giác TIN chỉ tạo trong phạm vi đường bao", "bien_dong"));
            bl.Them(new NutCay("▶ Chọn đường bao (biên giới hạn TIN) trên CAD…", null, "SN_CHONBIEN ",
                "Chọn đa tuyến làm đường bao để lưới tam giác TIN chỉ tạo trong phạm vi đường bao", "bien_dong"));

            // 4. Tạo TIN & Báo cáo QC
            NutCay tin = bm.Them(new NutCay("4. Tạo TIN & Báo cáo QC", BangNhom.Tim("qc"), "SN_TAOTIN_" + hauTo + " ",
                "Dựng lưới tam giác TIN (cắt theo phạm vi đường bao) và kiểm tra điểm bất thường, tam giác dẹt cho " + tenBm, maBm));
            tin.Them(new NutCay("▶ 4.1 Tạo / Tạo lại lưới TIN (" + hauTo + ")", null, "SN_TAOTIN_" + hauTo + " ",
                "Chạy thuật toán Delaunay dựng lưới TIN trong phạm vi đường bao cho " + tenBm, maBm));
            tin.Them(new NutCay("▶ 4.2 Báo cáo điểm bất thường & tam giác dẹt (QC)…", BangNhom.Tim("qc"), "SN_CANHBAO ",
                "Mở bảng báo cáo QC: điểm cao độ bất thường, tam giác dẹt, thiếu dữ liệu", "qc"));

            // 5. Tạo 3D Mesh & HTML View
            NutCay m3d = bm.Them(new NutCay("5. Tạo 3D Mesh & HTML View", nhomMesh, "SN_MESH_" + hauTo + " ",
                "Tạo và hiển thị lưới 3D PolyfaceMesh trên AutoCAD cho " + tenBm, maBm));
            m3d.Them(new NutCay("▶ 5.1 Tạo & Xem 3D Mesh (tô bóng)", nhomMesh, "SN_MESH_" + hauTo + " ",
                "Vẽ 3D PolyfaceMesh lên bản vẽ CAD và chuyển góc nhìn 3D tô bóng", maBm));
            m3d.Them(new NutCay("▶ 5.2 Bật / Tắt 3D Mesh (chỉ hiển thị lưới tam giác)", null, "SN_TOGGLE_MESH_" + hauTo + " ",
                "Chuyển đổi giữa chế độ tô bóng 3D Mesh và chế độ khung dây 2D chỉ hiển thị lưới tam giác", maBm));
            m3d.Them(new NutCay("▶ 5.3 Hộp thoại Xem 3D (MHTN / MHTK / Cả hai)…", null, "SN_TIN3D ",
                "Xem 3D Mesh tùy chọn bề mặt (CadLenh.Xem3D / SN_TIN3D)", maBm));
            m3d.Them(new NutCay("▶ 5.4 Tạo & Mở trình xem 3D trên Web HTML", null, "SN_XEM3D ",
                "Tạo và mở trình xem 3D tương tác (tin3d_view.html) trên trình duyệt Web", maBm));

            // 6. Hiệu chỉnh lưới TIN
            NutCay hc = bm.Them(new NutCay("6. Hiệu chỉnh lưới TIN", null, null, null, maBm));
            hc.Them(new NutCay("▶ 6.1 Xóa điểm (bỏ điểm gai nhọn / bất thường)…", null, "SN_XOADIEM_" + hauTo + " ",
                "Pick điểm bất thường trên bản vẽ CAD để loại bỏ và tạo lại lưới TIN", maBm));
            hc.Them(new NutCay("▶ 6.2 Thêm điểm vào lưới TIN…", null, "SN_THEMDIEM_" + hauTo + " ",
                "Pick vị trí và nhập cao độ Z để chèn thêm điểm vào lưới TIN", maBm));
            hc.Them(new NutCay("▶ 6.3 Lật cạnh tam giác (Flip Edge)…", null, "SN_LATCANH_" + hauTo + " ",
                "Pick cạnh chung của 2 tam giác trên CAD để đổi đường chéo", maBm));
            hc.Them(new NutCay("▶ 6.4 Thêm đường Breakline cưỡng bức…", null, "SN_CHONDUTGAY ",
                "Chọn bổ sung đường đứt gãy trên CAD và ép lại cạnh TIN", maBm));
            hc.Them(new NutCay("▶ 6.5 Xóa tam giác thừa (quét chọn nhiều / pick)…", null, "SN_XOATG_" + hauTo + " ",
                "Quét cửa sổ chọn nhiều tam giác thừa hoặc vẽ đường cắt / pick điểm để xóa khỏi bề mặt TIN", maBm));
            hc.Them(new NutCay("▶ 6.6 Tạo lại lưới TIN", null, "SN_TAOTIN_" + hauTo + " ",
                "Dựng lại lưới tam giác TIN sau khi hiệu chỉnh", maBm));
        }

        NutCay DungCay(string lo, int dot, QuetKQ q)
        {
            NutCay goc = new NutCay("Lô " + (lo.Length > 0 ? lo : "?") + " · đợt " + dot, null, null, null, "nguon");

            // Nhánh dành riêng cho AI Agent (Claude Desktop / ChatGPT Desktop / Antigravity)
            NutCay ag = goc.Them(new NutCay("AI Agent & MCP (Claude / ChatGPT / Antigravity)", null, "SN_NAP_TU_MCP ",
                "Đồng bộ dữ liệu đầu vào đã được AI Agent kiểm soát qua MCP vào bản vẽ CAD đang mở", "nguon"));
            ag.Them(new NutCay("▶ 1. Nhận dữ liệu từ Agent (MCP) & Tạo TIN trên CAD", null, "SN_NAP_TU_MCP ",
                "Đẩy dữ liệu điểm/Breakline đã duyệt từ Agent vào CAD, dựng TIN, 3D Mesh & HTML View", "nguon"));
            ag.Them(new NutCay("▶ 2. Hộp thoại khởi tạo tổng hợp (DD_DH)…", null, "SN_TAOMAT ",
                "Mở hộp thoại Quản lý & khởi tạo mô hình địa hình tổng hợp (SN_TAOMAT)", "nguon"));
            ag.Them(new NutCay("▶ 3. Xem báo cáo kiểm soát dữ liệu đầu vào (QC)…", null, "SN_CANHBAO ",
                "Xem danh sách điểm nghi vấn (V-01..V-n) và tam giác cảnh báo (M-01..M-n)", "qc"));
            ag.Them(new NutCay("▶ 4. Duyệt cổng dữ liệu & bề mặt (Cổng 1 & 2)…", null, "SN_DUYET ",
                "Mở hộp thoại xác nhận duyệt Cổng 1 (Dữ liệu) và Cổng 2 (Bề mặt)", "nguon"));
            ag.Them(new NutCay("▶ 5. Khởi tạo lô mới (xóa sạch dữ liệu cũ)…", null, "SN_LAMMOI ",
                "Xóa sạch kết quả và dữ liệu xử lý cũ của lô để khởi tạo lại từ đầu (SN_LAMMOI)", "nguon"));

            // Nhánh MHTN (mặt gốc) & MHTK (mặt thiết kế) theo đúng cấu trúc người dùng yêu cầu
            ThemNhanhBeMat(goc, "moc", "MHTN (Mặt gốc / Tự nhiên)", BangNhom.Tim("moc"), BangNhom.NguonDiemMoc);
            ThemNhanhBeMat(goc, "do", "MHTK (Mặt thiết kế / Sau san lấp)", BangNhom.Tim("do"), BangNhom.NguonDiemDo);

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
            string dangChon = _cay.SelectedNode != null ? _cay.SelectedNode.Name : null;
            _dat = true;
            _cay.BeginUpdate();
            try
            {
                _cay.Nodes.Clear();
                TaoNode(_cay.Nodes, DungCay(lo, dot, q), "", q, lo, dot);
                bool macDinh = !_daMoMacDinh;
                RestoreMo(_cay.Nodes, mo, macDinh, 0, dangChon);
                _daMoMacDinh = true;
            }
            finally { _cay.EndUpdate(); _dat = false; }
            CapNhatBang(DieuPhoi.Cuoi);
        }

        static void GhiMo(TreeNodeCollection ds, HashSet<string> mo)
        {
            foreach (TreeNode n in ds) { if (n.IsExpanded) mo.Add(n.Name); GhiMo(n.Nodes, mo); }
        }

        void RestoreMo(TreeNodeCollection ds, HashSet<string> mo, bool macDinh, int sau, string dangChon)
        {
            foreach (TreeNode n in ds)
            {
                if (mo.Contains(n.Name) || (macDinh && sau < 2)) n.Expand();
                if (dangChon != null && n.Name == dangChon) _cay.SelectedNode = n;
                RestoreMo(n.Nodes, mo, macDinh, sau + 1, dangChon);
            }
        }

        void TaoNode(TreeNodeCollection ds, NutCay n, string cha, QuetKQ q, string lo, int dot)
        {
            TreeNode t = new TreeNode();
            t.Name = cha + "/" + n.Ten;
            t.Tag = n;
            if (n.LenhCad != null && n.Nhom == null && n.Con.Count == 0)
            {
                // Nút lệnh hành động trực tiếp trên cây (Lấy tọa độ, Import Excel, Tạo TIN, Lật cạnh, Xóa điểm...):
                // क्लिक một lần hoặc click vào ô kiểm hay click đúp đều chạy lệnh ngay
                t.Text = n.Ten;
                t.Checked = false;
                t.ForeColor = Mau.Chu;
            }
            else if (q == null || q.Loi != null)
            {
                t.Text = n.Ten;
                t.ForeColor = Mau.Chu;
            }
            else
            {
                List<string> lop = LopCua(n, q, dot);
                if (lop.Count == 0)
                {
                    t.Text = n.Ten;
                    t.ForeColor = n.LenhCad != null ? Mau.Chu : Mau.ChuMo;
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

        protected override void CapNhat(DuLieuPal d)
        {
            Xay();
            CapNhatBang(d);
        }

        protected override void CapNhatBanVe() { Xay(); }

        // ---------------------------------------------------------------- bảng thông số
        void SauChon(object s, TreeViewEventArgs e)
        {
            if (_dat || e.Node == null) return;
            NutCay n = e.Node.Tag as NutCay;
            if (n != null && !string.IsNullOrEmpty(n.KhoaBang)) _khoaBangHienTai = n.KhoaBang;
            CapNhatBang(DieuPhoi.Cuoi);
        }

        void CapNhatBang(DuLieuPal d)
        {
            if (d == null || !d.Ok)
            {
                DoDong(_bang, new List<string[]>());
                return;
            }
            List<string[]> dong = new List<string[]>();
            dong.Add(new string[] { "Cổng 1 (Dữ liệu đầu vào)", d.ChuCong(1) });
            dong.Add(new string[] { "Cổng 2 (Bề mặt TIN & Biên lô)", d.ChuCong(2) });
            string khoa = string.IsNullOrEmpty(_khoaBangHienTai) ? "moc" : _khoaBangHienTai;
            foreach (string[] r in d.Dong(khoa)) dong.Add(r);
            DoDong(_bang, dong);
        }

        // ---------------------------------------------------------------- thao tác trên cây
        void KichDup(TreeNode tn)
        {
            if (tn == null) return;
            NutCay n = tn.Tag as NutCay;
            if (n != null && !string.IsNullOrEmpty(n.LenhCad))
            {
                GuiLenh(n.LenhCad, n.MoTaLenh ?? n.Ten);
                return;
            }
            Zoom(tn);
        }

        void ThucHienNut(TreeNode tn)
        {
            if (tn == null) { Bao("Chọn một mục trên cây trước."); return; }
            NutCay n = tn.Tag as NutCay;
            if (n != null && !string.IsNullOrEmpty(n.LenhCad))
            {
                if (n.LenhCad.Trim() == "SN_TIN3D") { Bao(CadLenh.Xem3D() ?? "Xem mặt 3D trên AutoCAD (SN_TIN3D)."); return; }
                GuiLenh(n.LenhCad, n.MoTaLenh ?? n.Ten);
            }
            else
                Zoom(tn);
        }

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
            NutCay n = e.Node != null ? e.Node.Tag as NutCay : null;
            if (n != null && n.LenhCad != null && n.Nhom == null && n.Con.Count == 0)
            {
                _dat = true;
                try { e.Node.Checked = false; } finally { _dat = false; }
                Chay(delegate { GuiLenh(n.LenhCad, n.MoTaLenh ?? n.Ten); });
                return;
            }
            Chay(delegate { DatHienAn(e.Node, e.Node.Checked); });
        }

        void ChuotCay(object s, TreeNodeMouseClickEventArgs e)
        {
            if (e.Button == MouseButtons.Left && e.Node != null)
            {
                NutCay na = e.Node.Tag as NutCay;
                TreeViewHitTestInfo hit = _cay.HitTest(e.Location);
                // Click chuột trái vào nhãn của nút lệnh lá (▶ ...) → chạy lệnh luôn cho thuận tiện
                if (na != null && na.LenhCad != null && na.Nhom == null && na.Con.Count == 0 &&
                    (hit.Location == TreeViewHitTestLocations.Label || hit.Location == TreeViewHitTestLocations.RightOfLabel))
                {
                    _cay.SelectedNode = e.Node;
                    Chay(delegate { GuiLenh(na.LenhCad, na.MoTaLenh ?? na.Ten); });
                    return;
                }
            }
            if (e.Button != MouseButtons.Right) return;
            _cay.SelectedNode = e.Node;
            NutCay n = e.Node != null ? e.Node.Tag as NutCay : null;
            if (n != null && !string.IsNullOrEmpty(n.LenhCad))
            {
                _mnuChay.Text = "▶ Thực hiện: " + n.Ten.Replace("▶ ", "");
                _mnuChay.Visible = true;
            }
            else
            {
                _mnuChay.Visible = false;
            }
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

        void LamMoiBanVe()
        {
            BeginInvoke(new Action(delegate { try { DieuPhoi.YeuCauNgay(false, true); } catch (Exception ex) { BaoLoi(ex); } }));
        }
    }
}
