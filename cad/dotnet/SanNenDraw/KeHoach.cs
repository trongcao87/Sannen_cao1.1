// KẾ HOẠCH VẼ do Python xuất (`cau_noi ve-ke-hoach`, lược đồ phien_ban = 1 — xem cad/sannen_cad/ke_hoach.py).
// Lớp THUẦN: chỉ đọc JSON thành đối tượng; không dùng API AutoCAD, không tính toán nghiệp vụ.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace SanNen.Draw
{
    public sealed class LopDef
    {
        public string Ten;
        public int Mau = 7;
        public bool Tat;        // tắt layer khi TẠO (mặt 3D tắt mặc định)
        public bool DatMau;     // layer đã có: đặt lại màu, giữ nguyên bật/tắt
    }

    public sealed class XoaDef
    {
        public string Loai;                                 // null = mọi loại
        public List<string> Ex = new List<string>();        // đối tượng phải có ĐỦ các "k=v" này
        public List<string> ExMotTrong = new List<string>(); // …và (nếu khác rỗng) có ÍT NHẤT MỘT "k=v" trong danh sách này
    }

    public sealed class HienLopDef
    {
        public string Ten;
        public bool Bat;
    }

    /// <summary>Một thực thể cần vẽ. Số liệu hình học để dạng mảng phẳng (đỡ bộ nhớ khi có hàng trăm nghìn đối tượng).</summary>
    public sealed class DoiTuongVe
    {
        public string Kieu, Loai, Lop, NoiDung;
        public int Mau = 256;                   // 256 = theo layer
        public string[] Ex;                     // các "k=v" phụ của XDATA (sau 4 trường đầu); null = không có
        public double Cao;
        public bool Dong;
        public double[] Diem;                   // polyline / text / mtext: x0,y0,x1,y1,...
        public double[] Dinh;                   // polyface: x,y,z,...   |   3dface: 9 số (3 điểm)
        public int[] Mat;                       // polyface: a,b,c,... (chỉ số đỉnh 0-based)
    }

    public sealed class KeHoach
    {
        public const int PhienBanHieu = 1;
        public int PhienBan;
        public string Lenh = "", MaLo = "", Hash = "";
        public int Dot = 1;
        public List<XoaDef> Xoa = new List<XoaDef>();
        public List<LopDef> Lop = new List<LopDef>();
        public List<HienLopDef> HienLop = new List<HienLopDef>();
        public List<DoiTuongVe> DoiTuong = new List<DoiTuongVe>();
        public int TomTatSo = -1;               // số đối tượng Python khai trong tom_tat (để đối chiếu)

        public static KeHoach DocFile(string duongDan)
        {
            return Doc(File.ReadAllText(duongDan, new UTF8Encoding(false)));
        }

        public static KeHoach Doc(string json)
        {
            object g = J.Parse(json);
            KeHoach k = new KeHoach();
            k.PhienBan = J.I(J.Get(g, "phien_ban"), 0);
            if (k.PhienBan != PhienBanHieu)
                throw new InvalidOperationException("Kế hoạch vẽ phiên bản " + k.PhienBan + " — add-in này chỉ hiểu phiên bản " + PhienBanHieu
                    + ". Cập nhật SanNenDraw.dll hoặc lõi Python cho cùng phiên bản.");
            k.Lenh = J.S(J.Get(g, "lenh"));
            k.MaLo = J.S(J.Get(g, "truy_vet", "ma_lo"));
            k.Dot = J.I(J.Get(g, "truy_vet", "dot"), 1);
            k.Hash = J.S(J.Get(g, "truy_vet", "hash_dau_vao"));
            if (k.MaLo.Length == 0) throw new InvalidOperationException("Kế hoạch vẽ thiếu truy_vet.ma_lo — không biết vẽ cho lô nào.");
            k.TomTatSo = J.I(J.Get(g, "tom_tat", "so_doi_tuong"), -1);

            foreach (object o in J.L(J.Get(g, "xoa")))
            {
                XoaDef x = new XoaDef();
                string l = J.S(J.Get(o, "loai"));
                x.Loai = l.Length == 0 ? null : l;
                foreach (object e in J.L(J.Get(o, "ex"))) x.Ex.Add(J.S(e));
                foreach (object e in J.L(J.Get(o, "ex_mot_trong"))) x.ExMotTrong.Add(J.S(e));
                k.Xoa.Add(x);
            }
            foreach (object o in J.L(J.Get(g, "lop")))
            {
                LopDef l = new LopDef();
                l.Ten = J.S(J.Get(o, "ten"));
                l.Mau = J.I(J.Get(o, "mau"), 7);
                l.Tat = J.B(J.Get(o, "tat"));
                l.DatMau = J.B(J.Get(o, "dat_mau"));
                if (l.Ten.Length == 0) throw new InvalidOperationException("Kế hoạch vẽ có layer không tên.");
                k.Lop.Add(l);
            }
            foreach (object o in J.L(J.Get(g, "hien_lop")))
            {
                HienLopDef h = new HienLopDef();
                h.Ten = J.S(J.Get(o, "ten"));
                h.Bat = J.B(J.Get(o, "bat"));
                k.HienLop.Add(h);
            }
            List<object> ds = J.L(J.Get(g, "doi_tuong"));
            k.DoiTuong.Capacity = ds.Count;
            foreach (object o in ds)
            {
                DoiTuongVe d = new DoiTuongVe();
                d.Kieu = J.S(J.Get(o, "kieu"));
                d.Loai = J.S(J.Get(o, "loai"));
                d.Lop = J.S(J.Get(o, "lop"));
                d.Mau = J.I(J.Get(o, "mau"), 256);
                List<object> ex = J.L(J.Get(o, "ex"));
                if (ex.Count > 0)
                {
                    d.Ex = new string[ex.Count];
                    for (int i = 0; i < ex.Count; i++) d.Ex[i] = J.S(ex[i]);
                }
                d.NoiDung = J.S(J.Get(o, "noi_dung"));
                d.Cao = J.D(J.Get(o, "cao")) ?? 0.0;
                d.Dong = J.B(J.Get(o, "dong"));
                switch (d.Kieu)
                {
                    case "polyline":
                        d.Diem = Phang(J.Get(o, "diem"), 2);
                        break;
                    case "text":
                    case "mtext":
                        List<object> xy = J.L(J.Get(o, "diem"));
                        double? px = xy.Count == 2 ? J.D(xy[0]) : null, py = xy.Count == 2 ? J.D(xy[1]) : null;
                        if (!px.HasValue || !py.HasValue) throw new InvalidOperationException("text/mtext cần diem = [x, y].");
                        d.Diem = new double[] { px.Value, py.Value };
                        break;
                    case "polyface":
                        d.Dinh = Phang(J.Get(o, "dinh"), 3);
                        d.Mat = PhangInt(J.Get(o, "mat"), 3);
                        break;
                    case "3dface":
                        d.Dinh = Phang(J.Get(o, "p"), 3);
                        if (d.Dinh.Length != 9) throw new InvalidOperationException("3dface phải có đúng 3 điểm.");
                        break;
                    default:
                        throw new InvalidOperationException("Kiểu đối tượng lạ trong kế hoạch vẽ: «" + d.Kieu + "».");
                }
                if (d.Lop.Length == 0 || d.Loai.Length == 0) throw new InvalidOperationException("Đối tượng thiếu lop/loai.");
                if ((d.Kieu == "text" || d.Kieu == "mtext") && d.Diem.Length != 2) throw new InvalidOperationException("text/mtext cần đúng một điểm.");
                if (d.Kieu == "polyline" && d.Diem.Length < 4) throw new InvalidOperationException("polyline cần ít nhất 2 điểm.");
                k.DoiTuong.Add(d);
            }
            if (k.TomTatSo >= 0 && k.TomTatSo != k.DoiTuong.Count)
                throw new InvalidOperationException("Kế hoạch vẽ hỏng: tom_tat khai " + k.TomTatSo + " đối tượng nhưng có " + k.DoiTuong.Count + ".");
            return k;
        }

        // mảng các bộ `n` số → mảng phẳng
        static double[] Phang(object o, int n)
        {
            List<object> ds = J.L(o);
            double[] r = new double[ds.Count * n];
            for (int i = 0; i < ds.Count; i++)
            {
                List<object> b = J.L(ds[i]);
                if (b.Count < n) throw new InvalidOperationException("Toạ độ thiếu số (cần " + n + ").");
                for (int k = 0; k < n; k++)
                {
                    double? v = J.D(b[k]);
                    if (!v.HasValue) throw new InvalidOperationException("Toạ độ không phải số.");
                    r[i * n + k] = v.Value;
                }
            }
            return r;
        }

        static int[] PhangInt(object o, int n)
        {
            double[] d = Phang(o, n);
            int[] r = new int[d.Length];
            for (int i = 0; i < d.Length; i++) r[i] = (int)Math.Round(d[i]);
            return r;
        }
    }
}
