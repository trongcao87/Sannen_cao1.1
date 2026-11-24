// DTO: kết quả `thong-tin --json` của cầu nối Python, bọc lại để các tab đọc có kiểu.
// KHÔNG tính toán gì ở đây (RULES 1): chỉ lấy ra số/chữ do lõi Python đã tính và định dạng.
using System;
using System.Collections.Generic;

namespace SanNen.Palette.Models
{
    public sealed class MatCatDto
    {
        public string Ten;
        public double? ChieuDai, DaoM2, DapM2, ThieuM;
        public double[] A, B;           // toạ độ VN-2000 hai đầu (E,N) — có thể null với kết quả cũ
    }

    public sealed class CanhBaoDto
    {
        public string Muc, Ma, Loai, MoTa, Nguon;
        public double? E, N;
    }

    public sealed class DuLieuPal
    {
        public bool Ok;
        public string Loi;               // tiếng Việt, chỉ rõ sannen.cfg khi lỗi cấu hình
        public DateTime Luc;
        public object Goc;               // đối tượng "du_lieu" của JSON (null khi lỗi)

        public string MaLo { get { return J.S(J.Get(Goc, "lo", "ma_lo")); } }
        public int Dot { get { return J.I(J.Get(Goc, "lo", "dot"), 1); } }
        public string ThuMuc { get { return J.S(J.Get(Goc, "lo", "thu_muc")); } }

        public object Get(params string[] khoa) { return J.Get(Goc, khoa); }

        /// <summary>Các dòng [nhãn, giá trị] đã định dạng sẵn cho một nhóm ("nhom" của lõi) hoặc "bien_dong".</summary>
        public List<string[]> Dong(string khoaNhom)
        {
            object o = khoaNhom == "bien_dong" ? J.Get(Goc, "bien_dong") : J.Get(Goc, "nhom", khoaNhom);
            List<string[]> ra = new List<string[]>();
            foreach (object r in J.L(o))
            {
                List<object> p = J.L(r);
                if (p.Count >= 2) ra.Add(new string[] { J.S(p[0]), J.S(p[1]) });
            }
            return ra;
        }

        public List<MatCatDto> MatCat()
        {
            List<MatCatDto> ra = new List<MatCatDto>();
            foreach (object m in J.L(J.Get(Goc, "so_lieu", "matcat", "ds")))
            {
                MatCatDto d = new MatCatDto();
                d.Ten = J.S(J.Get(m, "ten"));
                d.ChieuDai = J.D(J.Get(m, "chieu_dai_m"));
                d.DaoM2 = J.D(J.Get(m, "dao_m2"));
                d.DapM2 = J.D(J.Get(m, "dap_m2"));
                d.ThieuM = J.D(J.Get(m, "thieu_m"));
                d.A = Diem(J.Get(m, "a"));
                d.B = Diem(J.Get(m, "b"));
                ra.Add(d);
            }
            return ra;
        }

        public List<CanhBaoDto> CanhBao()
        {
            List<CanhBaoDto> ra = new List<CanhBaoDto>();
            foreach (object c in J.L(J.Get(Goc, "canh_bao")))
            {
                CanhBaoDto d = new CanhBaoDto();
                d.Muc = J.S(J.Get(c, "muc")); d.Ma = J.S(J.Get(c, "ma")); d.Loai = J.S(J.Get(c, "loai"));
                d.MoTa = J.S(J.Get(c, "mo_ta")); d.Nguon = J.S(J.Get(c, "nguon"));
                d.E = J.D(J.Get(c, "e")); d.N = J.D(J.Get(c, "n"));
                ra.Add(d);
            }
            return ra;
        }

        /// <summary>Cổng n (1..3): đã duyệt? còn bao nhiêu việc CHẶN?</summary>
        public string ChuCong(int n)
        {
            object c = J.Get(Goc, "cong", n.ToString());
            if (c == null) return "Cổng " + n + ": chưa rõ";
            bool da = J.B(J.Get(c, "da_duyet"));
            int chan = J.I(J.Get(c, "viec_chan"), 0);
            return "Cổng " + n + ": " + (da ? "ĐÃ duyệt" : "chưa duyệt" + (chan > 0 ? " (còn " + chan + " việc CHẶN)" : ""));
        }

        public List<string> CanhBaoCu()
        {
            List<string> ra = new List<string>();
            foreach (object s in J.L(J.Get(Goc, "canh_bao_cu"))) ra.Add(J.S(s));
            return ra;
        }

        public static double[] Diem(object o)
        {
            List<object> p = J.L(o);
            if (p.Count < 2) return null;
            double? e = J.D(p[0]), n = J.D(p[1]);
            if (!e.HasValue || !n.HasValue) return null;
            return new double[] { e.Value, n.Value };
        }
    }
}
