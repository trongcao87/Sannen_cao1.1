// Điều phối làm mới: số liệu từ Python (luồng nền) + quét bản vẽ (luồng giao diện). Có debounce, không vòng lặp:
// làm mới chỉ ĐỌC (thong-tin không ghi, quét bản vẽ không ghi), nên lệnh SN_* kết thúc → làm mới một lần rồi dừng.
using System;
using CauHinh = SanNen.Draw.CauHinh;
using System.Threading;
using System.Windows.Forms;
using Autodesk.AutoCAD.ApplicationServices;
using SanNen.Palette.Models;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace SanNen.Palette.Services
{
    public static class DieuPhoi
    {
        static Control _ui;
        static System.Windows.Forms.Timer _tm;
        static bool _canPython, _canQuet, _dangChay, _chayLai;
        static readonly object _khoa = new object();

        public static DuLieuPal Cuoi;          // lần đọc Python gần nhất (null: chưa có)
        public static QuetKQ Quet;             // lần quét bản vẽ gần nhất (null: chưa có)
        public static event Action<DuLieuPal> DuLieuDoi;
        public static event Action LopDoi;
        public static Func<bool> DangHien;     // palette đang hiện? (không làm mới khi ẩn)

        public static void Khoi(Control ui)
        {
            _ui = ui;
            IntPtr h = ui.Handle;                   // ép tạo handle trên luồng giao diện để BeginInvoke dùng được từ luồng nền
            _tm = new System.Windows.Forms.Timer();
            _tm.Interval = 600;
            _tm.Tick += delegate { _tm.Stop(); Chay(); };
            AcApp.DocumentManager.DocumentBecameCurrent += DocDoi;
            AcApp.DocumentManager.DocumentCreated += DocMoi;
            AcApp.DocumentManager.DocumentToBeDestroyed += DocHuy;
            foreach (Document d in AcApp.DocumentManager) d.CommandEnded += LenhXong;
        }

        public static void Dung()
        {
            try
            {
                AcApp.DocumentManager.DocumentBecameCurrent -= DocDoi;
                AcApp.DocumentManager.DocumentCreated -= DocMoi;
                AcApp.DocumentManager.DocumentToBeDestroyed -= DocHuy;
                foreach (Document d in AcApp.DocumentManager) d.CommandEnded -= LenhXong;
                if (_tm != null) { _tm.Stop(); _tm.Dispose(); _tm = null; }
            }
            catch (Exception) { }
        }

        // ---------------------------------------------------------------- sự kiện AutoCAD (bọc try/catch: không để văng AutoCAD)
        static void DocMoi(object s, DocumentCollectionEventArgs e)
        {
            try { e.Document.CommandEnded += LenhXong; } catch (Exception) { }
        }

        static void DocHuy(object s, DocumentCollectionEventArgs e)
        {
            try { e.Document.CommandEnded -= LenhXong; } catch (Exception) { }
        }

        static void DocDoi(object s, DocumentCollectionEventArgs e)
        {
            try { YeuCau(true, true); } catch (Exception) { }
        }

        static void LenhXong(object s, CommandEventArgs e)
        {
            try
            {
                string ten = (e.GlobalCommandName ?? "").ToUpperInvariant();
                if (ten.StartsWith("SN_PALETTE")) return;                       // chính palette: không tự làm mới
                if (ten.StartsWith("SN_")) YeuCau(true, true);
                else if (ten == "LAYER" || ten == "-LAYER" || ten == "ERASE" || ten == "U" || ten == "UNDO" || ten == "REDO" || ten == "MREDO")
                    YeuCau(false, true);
            }
            catch (Exception) { }
        }

        // ---------------------------------------------------------------- làm mới
        /// <summary>Đăng ký làm mới (debounce 0,6 giây). python: đọc lại lõi; banVe: quét lại layer/đối tượng.</summary>
        public static void YeuCau(bool python, bool banVe)
        {
            if (_ui == null || _ui.IsDisposed) return;
            if (python) _canPython = true;
            if (banVe) _canQuet = true;
            if (_tm != null) { _tm.Stop(); _tm.Start(); }
        }

        /// <summary>Làm mới NGAY (nút ↻ và sau khi bật/tắt layer).</summary>
        public static void YeuCauNgay(bool python, bool banVe)
        {
            if (python) _canPython = true;
            if (banVe) _canQuet = true;
            if (_tm != null) _tm.Stop();
            Chay();
        }

        static void Chay()
        {
            if (DangHien != null && !DangHien()) return;       // ẩn thì thôi; mở lại palette sẽ làm mới
            try
            {
                if (_canQuet)
                {
                    _canQuet = false;
                    Quet = CadLop.Quet(CadLop.DocHienHanh());
                    if (LopDoi != null) LopDoi();
                }
                if (_canPython)
                {
                    _canPython = false;
                    lock (_khoa)
                    {
                        if (_dangChay) { _chayLai = true; return; }
                        _dangChay = true;
                    }
                    ThreadPool.QueueUserWorkItem(delegate { NenPython(); });
                }
            }
            catch (Exception ex) { Noi("Palette SAN NỀN: lỗi làm mới — " + ex.Message); }
        }

        static void NenPython()
        {
            DuLieuPal r;
            try { r = PythonBridge.ThongTin(); }
            catch (Exception ex) { r = new DuLieuPal(); r.Luc = DateTime.Now; r.Loi = "Lỗi không rõ: " + ex.Message; }
            try
            {
                _ui.BeginInvoke(new Action(delegate
                {
                    try
                    {
                        Cuoi = r;
                        bool lai;
                        lock (_khoa) { _dangChay = false; lai = _chayLai; _chayLai = false; }
                        if (DuLieuDoi != null) DuLieuDoi(r);
                        // mã lô/đợt vừa biết → đếm lại đối tượng cho đúng lô
                        Quet = CadLop.Quet(CadLop.DocHienHanh());
                        if (LopDoi != null) LopDoi();
                        if (lai) { _canPython = true; Chay(); }
                    }
                    catch (Exception ex) { Noi("Palette SAN NỀN: lỗi cập nhật — " + ex.Message); }
                }));
            }
            catch (Exception) { lock (_khoa) { _dangChay = false; } }
        }

        // ---------------------------------------------------------------- mã lô / đợt hiện tại
        /// <summary>Mã lô + đợt: ưu tiên số liệu lõi; lỗi Python thì đọc lot.yaml (để Hiện/Ẩn vẫn đúng lô).</summary>
        public static void LoDot(out string ma, out int dot)
        {
            if (Cuoi != null && Cuoi.Ok && Cuoi.MaLo.Length > 0) { ma = Cuoi.MaLo; dot = Cuoi.Dot; return; }
            CauHinh.Doc().MaLoDot(out ma, out dot);
        }

        public static void Noi(string s)
        {
            try
            {
                Document d = CadLop.DocHienHanh();
                if (d != null) d.Editor.WriteMessage("\n" + s);
            }
            catch (Exception) { }
        }
    }
}
