// Cầu nối tới lõi Python: ĐỌC cấu hình sannen.cfg và gọi `python -m sannen_cad.cau_noi <lệnh> --json` bằng tiến trình con.
// Hợp đồng duy nhất là JSON (không parse s-expression). Hàm Chay* chạy ĐỒNG BỘ — chỉ gọi từ luồng nền (xem DieuPhoi).
// C# không đọc 10_process/ trực tiếp và không tự tính.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using SanNen.Palette.Models;

namespace SanNen.Palette.Services
{
    public sealed class CauHinh
    {
        public string File, Python, Cad, Lot;

        public static string DuongDanFile()
        {
            string env = Environment.GetEnvironmentVariable("SANNEN_CFG");
            if (!string.IsNullOrEmpty(env)) return env;
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "SanNen", "sannen.cfg");
        }

        public static CauHinh Doc()
        {
            CauHinh c = new CauHinh();
            c.File = DuongDanFile();
            if (!System.IO.File.Exists(c.File)) return c;
            foreach (string d in System.IO.File.ReadAllLines(c.File, new UTF8Encoding(false)))
            {
                string s = d.Trim().TrimStart('﻿');
                int p = s.IndexOf('=');
                if (s.Length == 0 || s[0] == '#' || p <= 0) continue;
                string k = s.Substring(0, p).Trim().ToLowerInvariant(), v = s.Substring(p + 1).Trim();
                if (k == "python") c.Python = v; else if (k == "cad") c.Cad = v; else if (k == "lot") c.Lot = v;
            }
            return c;
        }

        /// <summary>Thông báo tiếng Việt nếu thiếu cấu hình; null nếu đủ python=, cad=, lot=.</summary>
        public string ThieuGi()
        {
            if (!System.IO.File.Exists(File))
                return "Chưa có file cấu hình " + File + " — chạy cad\\cai_dat_cad.ps1 và lệnh SN_LOT (cần python=, cad=, lot=).";
            List<string> t = new List<string>();
            if (string.IsNullOrEmpty(Python) || !System.IO.File.Exists(Python)) t.Add("python= (không thấy python.exe)");
            if (string.IsNullOrEmpty(Cad) || !Directory.Exists(Cad)) t.Add("cad= (không thấy thư mục cad)");
            if (string.IsNullOrEmpty(Lot) || !System.IO.File.Exists(Path.Combine(Lot, "lot.yaml"))) t.Add("lot= (chưa chọn lô có lot.yaml — gõ SN_LOT)");
            return t.Count == 0 ? null : "Cấu hình " + File + " chưa đúng: " + string.Join("; ", t.ToArray()) + ".";
        }

        /// <summary>Dự phòng khi Python lỗi: mã lô / đợt đọc thẳng từ lot.yaml (như LISP) — để Hiện/Ẩn layer vẫn đúng lô.</summary>
        public void MaLoDot(out string ma, out int dot)
        {
            ma = ""; dot = 1;
            try
            {
                if (string.IsNullOrEmpty(Lot)) return;
                string f = Path.Combine(Lot, "lot.yaml");
                if (!System.IO.File.Exists(f)) return;
                foreach (string d in System.IO.File.ReadAllLines(f, new UTF8Encoding(false)))
                {
                    Match m = Regex.Match(d, "^(ma_lo|dot):\\s*(.*?)\\s*(#.*)?$");
                    if (!m.Success) continue;
                    string v = m.Groups[2].Value.Trim('"', '\'');
                    if (m.Groups[1].Value == "ma_lo") ma = v;
                    else { int n; if (int.TryParse(v, out n)) dot = n; }
                }
            }
            catch (Exception) { }
        }
    }

    public static class PythonBridge
    {
        const int HetGio = 180000;

        /// <summary>Gọi `thong-tin --json` cho lô hiện tại. Không bao giờ ném ngoại lệ: lỗi nằm trong DuLieuPal.Loi.</summary>
        public static DuLieuPal ThongTin()
        {
            DuLieuPal r = new DuLieuPal();
            r.Luc = DateTime.Now;
            CauHinh c = CauHinh.Doc();
            string thieu = c.ThieuGi();
            if (thieu != null) { r.Loi = thieu; return r; }
            string ra = Path.Combine(Path.GetTempPath(), "sn_palette_" + Process.GetCurrentProcess().Id + ".json");
            try
            {
                if (File.Exists(ra)) File.Delete(ra);
                string args = "-X utf8 -m sannen_cad.cau_noi thong-tin --lot \"" + c.Lot + "\" --json --ra \"" + ra + "\"";
                string nhatKy;
                int ma = ChayPython(c, args, out nhatKy);
                if (!File.Exists(ra))
                {
                    r.Loi = "Python không trả kết quả (mã thoát " + ma + "). Kiểm tra python= trong " + c.File + " đã cài sannen-core chưa. " + Cat(nhatKy);
                    return r;
                }
                object goc = J.Parse(File.ReadAllText(ra, new UTF8Encoding(false)));
                if (!J.B(J.Get(goc, "ok")))
                {
                    r.Loi = "Lõi báo: " + J.S(J.Get(goc, "thong_bao"), "lỗi không rõ") + " (lot= trong " + c.File + ")";
                    return r;
                }
                r.Goc = J.Get(goc, "du_lieu");
                r.Ok = true;
            }
            catch (Exception ex)
            {
                r.Loi = "Không đọc được số liệu từ lõi: " + ex.Message + " — kiểm tra " + c.File + " (python=, cad=, lot=).";
            }
            finally
            {
                try { if (File.Exists(ra)) File.Delete(ra); } catch (Exception) { }
            }
            return r;
        }

        static string Cat(string s)
        {
            s = (s ?? "").Trim();
            string[] d = s.Split('\n');
            int tu = Math.Max(0, d.Length - 3);
            return string.Join(" ", d, tu, d.Length - tu).Trim();
        }

        static int ChayPython(CauHinh c, string args, out string nhatKy)
        {
            ProcessStartInfo psi = new ProcessStartInfo(c.Python, args);
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            psi.StandardErrorEncoding = Encoding.UTF8;
            psi.WorkingDirectory = c.Cad;
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            string cu = Environment.GetEnvironmentVariable("PYTHONPATH");
            psi.EnvironmentVariables["PYTHONPATH"] = string.IsNullOrEmpty(cu) ? c.Cad : c.Cad + ";" + cu;
            StringBuilder sb = new StringBuilder();
            object khoa = new object();
            using (Process p = new Process())
            {
                p.StartInfo = psi;
                p.OutputDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) lock (khoa) sb.AppendLine(e.Data); };
                p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e) { if (e.Data != null) lock (khoa) sb.AppendLine(e.Data); };
                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                if (!p.WaitForExit(HetGio))
                {
                    try { p.Kill(); } catch (Exception) { }
                    nhatKy = "Quá thời gian chờ (" + (HetGio / 1000) + " giây).";
                    return -1;
                }
                p.WaitForExit();
                lock (khoa) nhatKy = sb.ToString();
                return p.ExitCode;
            }
        }
    }
}
