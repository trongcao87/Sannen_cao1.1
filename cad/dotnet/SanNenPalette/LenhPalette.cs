// Cửa vào của add-in: lệnh SN_PALETTE (bật/tắt bảng dọc dock được "SAN NỀN"), SN_PALETTE_MO (tên không trùng với lệnh LISP
// c:SN_PALETTE — LISP dùng tên này để gọi vào đây) và SN_PALETTE_DONG. Mọi handler bọc try/catch: lỗi báo ra dòng lệnh, không làm AutoCAD văng.
using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Text;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Windows;
using SanNen.Palette.Services;
using CauHinh = SanNen.Draw.CauHinh;
using SanNen.Palette.Ui;
using Rt = Autodesk.AutoCAD.Runtime;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: Rt.ExtensionApplication(typeof(SanNen.Palette.KhoiDong))]
[assembly: Rt.CommandClass(typeof(SanNen.Palette.LenhPalette))]

namespace SanNen.Palette
{
    public sealed class KhoiDong : Rt.IExtensionApplication
    {
        public void Initialize()
        {
            try
            {
                AppDomain.CurrentDomain.AssemblyResolve += TimAssembly;
                bool daThay = LenhPalette.ThayThePaletteCu();
                try
                {
                    string diag = Path.Combine(Path.GetTempPath(), "sn_net_init.txt");
                    File.WriteAllText(diag, "Loaded=" + typeof(KhoiDong).Assembly.FullName + " @ " + typeof(KhoiDong).Assembly.Location + "\nReplaced=" + daThay);
                }
                catch (Exception) { }
                Document d = AcApp.DocumentManager.MdiActiveDocument;
                if (d != null) d.Editor.WriteMessage(daThay
                    ? "\nSAN NỀN palette: đã xóa giao diện cũ và cập nhật giao diện mới!"
                    : "\nSAN NỀN palette đã nạp — gõ SN_PALETTE để mở/tắt bảng dọc.");
            }
            catch (Exception) { }
        }

        public void Terminate()
        {
            try
            {
                AppDomain.CurrentDomain.AssemblyResolve -= TimAssembly;
                PythonBridge.XoaDuLieuCu();
                LenhPalette.Huy();
            }
            catch (Exception) { }
        }

        static Assembly TimAssembly(object sender, ResolveEventArgs args)
        {
            try
            {
                string ten = (args.Name ?? "").Split(',')[0].Trim();
                if (!ten.StartsWith("SanNenDraw", StringComparison.OrdinalIgnoreCase)) return null;
                foreach (Assembly a in AppDomain.CurrentDomain.GetAssemblies())
                    if (a.GetName().Name.StartsWith("SanNenDraw", StringComparison.OrdinalIgnoreCase)) return a;
                string dir = Path.GetDirectoryName(typeof(KhoiDong).Assembly.Location);
                string p = Path.Combine(dir, "SanNenDraw.dll");
                if (File.Exists(p)) return Assembly.LoadFrom(p);
            }
            catch (Exception) { }
            return null;
        }
    }

    public sealed class LenhPalette
    {
        static readonly Guid MaPalette = new Guid("5A7E6D2C-3B1F-4E8A-9C44-7D1B0E52A6F3");
        static PaletteSet _ps;
        static TabCoSo[] _tab;
        static System.Windows.Forms.Control _ui;

        // Hai tên: SN_PALETTE (nhóm SANNEN_NET để không đè c:SN_PALETTE của LISP) và SN_PALETTE_MO (tên duy nhất, LISP gọi tên này).
        [Rt.CommandMethod("SANNEN_NET", "SN_PALETTE", Rt.CommandFlags.Modal)]
        public void BatTat() { Chay(true); }

        [Rt.CommandMethod("SN_PALETTE_MO", Rt.CommandFlags.Modal)]
        public void Mo() { Chay(true); }

        [Rt.CommandMethod("SN_PALETTE_DONG", Rt.CommandFlags.Modal)]
        public void Dong()
        {
            try { if (_ps != null) _ps.Visible = false; }
            catch (Exception ex) { Bao(ex); }
        }

        static void Chay(bool batTat)
        {
            try
            {
                if (_ps == null) Tao();
                if (batTat && _ps.Visible) { _ps.Visible = false; GhiTrangThai(false); return; }
                _ps.Visible = true;
                GhiTrangThai(true);
                DieuPhoi.YeuCauNgay(true, true);
                foreach (TabCoSo t in _tab) t.ApMau();
            }
            catch (Exception ex) { Bao(ex); }
        }

        [Rt.CommandMethod("SN_PALETTE_CAPNHAT_UI", Rt.CommandFlags.Modal)]
        public void CapNhatUi()
        {
            try
            {
                Huy();
                Tao();
                DieuPhoi.YeuCauNgay(true, true);
                foreach (TabCoSo t in _tab) t.ApMau();
            }
            catch (Exception ex) { Bao(ex); }
        }

        static void Tao()
        {
            Mau.Cap();
            _ui = new System.Windows.Forms.Control();
            _ps = new PaletteSet("SAN NỀN", MaPalette);
            _ps.Style = PaletteSetStyles.ShowAutoHideButton | PaletteSetStyles.ShowCloseButton | PaletteSetStyles.ShowPropertiesMenu | PaletteSetStyles.Snappable;
            _ps.MinimumSize = new Size(300, 300);
            _ps.Size = new Size(340, 700);
            _ps.DockEnabled = DockSides.Left | DockSides.Right;      // dock trái/phải; kéo ra giữa màn hình = thả nổi (Float)
            _tab = new TabCoSo[] { new QlDhTab(), new BienLoTab(), new LuoiTab(), new MatCatTab(), new KhoiLuongTab(), new CanhBaoTab() };
            foreach (TabCoSo t in _tab) _ps.Add(t.TenTab, t);
            DieuPhoi.DangHien = delegate { return _ps != null && _ps.Visible; };
            DieuPhoi.Khoi(_ui);
            _ps.PaletteActivated += delegate(object s, PaletteActivatedEventArgs e)
            {
                try { GhiIni("tab", e.Activated.Name); } catch (Exception) { }
            };
            _ps.StateChanged += delegate(object s, PaletteSetStateEventArgs e)
            {
                try { if (e.NewState == StateEventIndex.Show) DieuPhoi.YeuCau(true, true); } catch (Exception) { }
            };
            _ps.Visible = true;
            _ps.Dock = DockSides.Left;                                // mặc định dock trái (lần đầu; sau đó AutoCAD nhớ vị trí theo GUID)
            string ten = DocIni("tab");
            if (ten != null)
                for (int i = 0; i < _tab.Length; i++) if (_tab[i].TenTab == ten) { _ps.Activate(i); break; }
        }

        public static bool ThayThePaletteCu()
        {
            // Nếu một bản SanNenPalette.dll cũ đã được nạp trước đó trong cùng phiên AutoCAD, đóng và hủy PaletteSet cũ rồi dựng lại bằng bản mới
            bool coCu = false;
            try
            {
                Assembly hienTai = typeof(LenhPalette).Assembly;
                foreach (Assembly a in AppDomain.CurrentDomain.GetAssemblies())
                {
                    if (a == hienTai) continue;
                    string n = a.GetName().Name ?? "";
                    if (!n.StartsWith("SanNenPalette", StringComparison.OrdinalIgnoreCase)) continue;
                    Type t = a.GetType("SanNen.Palette.LenhPalette");
                    if (t == null) continue;
                    coCu = true;
                    MethodInfo mHuy = t.GetMethod("Huy", BindingFlags.Public | BindingFlags.Static);
                    if (mHuy != null) { try { mHuy.Invoke(null, null); } catch (Exception) { } }
                    FieldInfo fPs = t.GetField("_ps", BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static);
                    if (fPs != null)
                    {
                        PaletteSet cu = fPs.GetValue(null) as PaletteSet;
                        if (cu != null)
                        {
                            try { cu.Visible = false; cu.Dispose(); } catch (Exception) { }
                            try { fPs.SetValue(null, null); } catch (Exception) { }
                        }
                    }
                }
                if (coCu)
                {
                    Huy();
                    Tao();
                    DieuPhoi.YeuCauNgay(true, true);
                    if (_tab != null) foreach (TabCoSo tb in _tab) tb.ApMau();
                }
            }
            catch (Exception) { }
            return coCu;
        }

        public static void Huy()
        {
            DieuPhoi.Dung();
            if (_ps != null) { _ps.Dispose(); _ps = null; }
            if (_ui != null) { _ui.Dispose(); _ui = null; }
        }

        static void Bao(Exception ex)
        {
            DieuPhoi.Noi("Palette SAN NỀN — lỗi: " + ex.Message);
        }

        // ---- nhớ trạng thái nhẹ: %APPDATA%\SanNen\palette.ini (tab đang mở, đang hiện hay không). Kích thước/dock do AutoCAD nhớ theo GUID.
        static string FileIni()
        {
            return Path.Combine(Path.GetDirectoryName(CauHinh.DuongDanFile()), "palette.ini");
        }

        static string DocIni(string khoa)
        {
            try
            {
                if (!File.Exists(FileIni())) return null;
                foreach (string d in File.ReadAllLines(FileIni(), new UTF8Encoding(false)))
                    if (d.StartsWith(khoa + "=")) return d.Substring(khoa.Length + 1).Trim();
            }
            catch (Exception) { }
            return null;
        }

        static void GhiIni(string khoa, string giaTri)
        {
            string tab = khoa == "tab" ? giaTri : DocIni("tab");
            string hien = khoa == "hien" ? giaTri : DocIni("hien");
            Directory.CreateDirectory(Path.GetDirectoryName(FileIni()));
            File.WriteAllText(FileIni(), "tab=" + (tab ?? "") + "\nhien=" + (hien ?? "") + "\n", new UTF8Encoding(false));
        }

        static void GhiTrangThai(bool hien)
        {
            try { GhiIni("hien", hien ? "1" : "0"); } catch (Exception) { }
        }
    }
}
