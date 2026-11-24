// Ánh xạ NHÓM đối tượng → LAYER của SAN NỀN. Lớp THUẦN (không dùng API AutoCAD) để biên dịch và kiểm tĩnh được.
// Bảng này phải KHỚP với *sn-ql-nhom* trong cad/lisp/sannen.lsp và LAYER_KET_QUA trong cad/sannen_cad/backend.py
// (core/tests/test_gd16_palette.py so sánh bằng regex — sửa một nơi phải sửa cả hai).
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace SanNen.Palette.Models
{
    /// <summary>Một nhóm đối tượng. Kieu: "dot" (layer gốc, đợt n≥2 thêm -Dnn) | "co-dinh" (luôn đúng tên gốc) | "mau" (mẫu * nhiều layer nhà thầu) | null (không có layer).</summary>
    public sealed class NhomDef
    {
        public readonly string Khoa;
        public readonly string Ten;
        public readonly string Kieu;
        public readonly string Goc;
        public readonly bool CoXdata;

        public NhomDef(string khoa, string ten, string kieu, string goc, bool coXdata)
        {
            Khoa = khoa; Ten = ten; Kieu = kieu; Goc = goc; CoXdata = coXdata;
        }

        public bool CoLop { get { return Goc != null; } }
    }

    public static class BangNhom
    {
        // (khoá, tên có dấu, kiểu layer, gốc layer, có XDATA SANNEN?) — đúng thứ tự và nội dung của LISP.
        public static readonly NhomDef[] Tat = new NhomDef[]
        {
            new NhomDef("moc", "TIN mốc", "dot", "SN-3DF-MOC", true),
            new NhomDef("do", "TIN đo", "dot", "SN-3DF-DO", true),
            new NhomDef("qc", "Tam giác thiếu dữ liệu", "dot", "SN-QC", true),
            new NhomDef("luoi", "Lưới ô", "dot", "SN-LUOI", true),
            new NhomDef("nhan", "Nhãn đỉnh lưới", "dot", "SN-LUOI-NHAN", true),
            new NhomDef("o", "Nhãn ô (khối lượng)", "dot", "SN-LUOI-O", true),
            new NhomDef("ranh", "Ranh đào–đắp", "dot", "SN-RANH-DAODAP", true),
            new NhomDef("matcat", "Mặt cắt", "co-dinh", "SN-MATCAT", true),
            new NhomDef("bang", "Bảng in", "co-dinh", "SN-BANG", true),
            new NhomDef("khoiluong", "Khối lượng (số liệu)", null, null, false),
            new NhomDef("nguon", "Dữ liệu nguồn (nhà thầu)", "mau", "SN-DIEM-MOC*,SN-DIEM-DO*,SN-DUTGAY*,SN-DONGMUC*,SN-BIENLO*,SN-LOAITRU*", false)
        };

        // Tách nhóm "nguon" thành từng loại để hiện từng nút trên cây (hợp của các mẫu này = mẫu của nhóm "nguon").
        public static readonly NhomDef NguonDiemMoc = new NhomDef("nguon_diem_moc", "Điểm mốc", "mau", "SN-DIEM-MOC*", false);
        public static readonly NhomDef NguonDiemDo = new NhomDef("nguon_diem_do", "Điểm đo", "mau", "SN-DIEM-DO*", false);
        public static readonly NhomDef NguonDutGay = new NhomDef("nguon_dutgay", "Đứt gãy địa hình", "mau", "SN-DUTGAY*", false);
        public static readonly NhomDef NguonDongMuc = new NhomDef("nguon_dongmuc", "Đường đồng mức", "mau", "SN-DONGMUC*", false);
        public static readonly NhomDef NguonBienLo = new NhomDef("nguon_bienlo", "Đường bao / Biên lô", "mau", "SN-BIENLO*", false);
        public static readonly NhomDef NguonLoaiTru = new NhomDef("nguon_loaitru", "Vùng loại trừ", "mau", "SN-LOAITRU*", false);

        public static NhomDef Tim(string khoa)
        {
            foreach (NhomDef g in Tat) if (g.Khoa == khoa) return g;
            return null;
        }

        /// <summary>Như backend.ten_layer: đợt 1 → gốc; đợt n → gốc-Dnn.</summary>
        public static string TenLop(string goc, int dot)
        {
            return dot <= 1 ? goc : goc + "-D" + dot.ToString("00");
        }

        /// <summary>Layer của SAN NỀN mà palette được phép bật/tắt: chỉ "SN-*", không phải layer xref (có dấu |).</summary>
        public static bool LaLopSanNen(string ten)
        {
            return ten != null && ten.StartsWith("SN-", StringComparison.OrdinalIgnoreCase) && ten.IndexOf('|') < 0;
        }

        /// <summary>So khớp không phân biệt hoa thường với mẫu có dấu * (nhiều mẫu cách nhau bởi dấu phẩy).</summary>
        public static bool KhopMau(string ten, string mau)
        {
            foreach (string m in mau.Split(','))
            {
                string p = m.Trim();
                if (p.Length == 0) continue;
                string re = "^" + Regex.Escape(p).Replace("\\*", ".*") + "$";
                if (Regex.IsMatch(ten, re, RegexOptions.IgnoreCase)) return true;
            }
            return false;
        }

        /// <summary>Các layer THỰC CÓ trong bản vẽ thuộc nhóm g (đợt dot).</summary>
        public static List<string> LopThucCo(NhomDef g, IEnumerable<string> tatCaLop, int dot)
        {
            List<string> ra = new List<string>();
            if (g == null || !g.CoLop) return ra;
            foreach (string ten in tatCaLop)
            {
                if (!LaLopSanNen(ten)) continue;
                bool khop;
                if (g.Kieu == "dot") khop = string.Equals(ten, TenLop(g.Goc, dot), StringComparison.OrdinalIgnoreCase);
                else if (g.Kieu == "co-dinh") khop = string.Equals(ten, g.Goc, StringComparison.OrdinalIgnoreCase);
                else khop = KhopMau(ten, g.Goc);
                if (khop) ra.Add(ten);
            }
            return ra;
        }
    }
}
