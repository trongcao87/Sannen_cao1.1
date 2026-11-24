// Tab "Lưới": thông số lưới hiện tại + ô nhập Cột / Hàng / Bù dữ liệu. Các nút GHI chỉ gọi lệnh LISP có sẵn
// (SN_LUOIAPDUNG, SN_DICHLUOI, SN_XOAYLUOI, SN_LUOI, SN_VE) để vẫn xin xác nhận (RULES 4); palette KHÔNG tự ghi file lô.
// Kích thước ô / gốc / góc / cách bù thiếu là QUYẾT ĐỊNH của người (RULES 9) — palette chỉ chuyển giá trị người gõ.
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Windows.Forms;
using SanNen.Palette.Models;
using SanNen.Palette.Services;

namespace SanNen.Palette.Ui
{
    public sealed class LuoiTab : TabCoSo
    {
        readonly ListView _bang = TaoBang(new string[] { "Thông số", "Giá trị" }, new int[] { 190, 140 });
        readonly Label _canhBao = new Label();
        readonly TextBox _cot = new TextBox(), _hang = new TextBox(), _bu = new TextBox();
        bool _daSua;

        // mẫu "Số×KT, ..." (vd 10x20,5x15.5); chỉ chữ x thường/hoa
        // mỗi phần tử: "Số x KT" hoặc chỉ "KT" (như luoi_sua.phan_tich của lõi); kiểm chặt hơn ở lõi khi áp dụng
        static readonly Regex MauSoKt = new Regex("^\\s*(\\d+\\s*[xX]\\s*)?\\d+(\\.\\d+)?(\\s*,\\s*(\\d+\\s*[xX]\\s*)?\\d+(\\.\\d+)?)*\\s*$");

        public override string TenTab { get { return "Lưới"; } }

        public LuoiTab()
        {
            _canhBao.Dock = DockStyle.Top;
            _canhBao.AutoSize = true;
            _canhBao.Tag = "canhbao";
            _canhBao.Padding = new Padding(6, 2, 6, 2);
            _bang.Dock = DockStyle.Fill;

            TableLayoutPanel nhap = new TableLayoutPanel();
            nhap.Dock = DockStyle.Bottom;
            nhap.AutoSize = true;
            nhap.ColumnCount = 2;
            nhap.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));
            nhap.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            Dong(nhap, "Cột (Số×KT,…)", _cot);
            Dong(nhap, "Hàng (Số×KT,…)", _hang);
            Dong(nhap, "Bù dữ liệu (m)", _bu);
            _cot.TextChanged += delegate { _daSua = true; };
            _hang.TextChanged += delegate { _daSua = true; };
            _bu.TextChanged += delegate { _daSua = true; };

            Than.Controls.Add(_bang);
            Than.Controls.Add(nhap);
            Than.Controls.Add(HangNut(
                Nut("Áp dụng", ApDung),
                Nut("Di chuyển…", delegate { GuiLenh("SN_DICHLUOI ", "Di chuyển lưới"); }),
                Nut("Xoay…", delegate { GuiLenh("SN_XOAYLUOI ", "Xoay lưới"); }),
                Nut("Vẽ lại lưới", delegate { Bao(CadLenh.VeLai() ?? "Vẽ lại kết quả bằng C# (SN_VE_NET) — xem dòng lệnh AutoCAD."); }),
                Nut("Hộp thoại lưới…", delegate { GuiLenh("SN_LUOI ", "Mở hộp thoại lưới"); })));
            Than.Controls.Add(_canhBao);
            DungXong();
        }

        static void Dong(TableLayoutPanel t, string nhan, TextBox o)
        {
            Label l = new Label();
            l.Text = nhan;
            l.AutoSize = true;
            l.Anchor = AnchorStyles.Left;
            l.Margin = new Padding(6, 6, 3, 6);
            o.Dock = DockStyle.Fill;
            o.Margin = new Padding(3);
            t.Controls.Add(l);
            t.Controls.Add(o);
        }

        protected override void CapNhat(DuLieuPal d)
        {
            if (!d.Ok) { DoDong(_bang, new List<string[]>()); _canhBao.Visible = false; return; }
            DoDong(_bang, d.Dong("luoi"));
            List<string> cu = d.CanhBaoCu();
            _canhBao.Visible = cu.Count > 0;
            _canhBao.Text = cu.Count > 0 ? "KẾT QUẢ CŨ: " + string.Join("  •  ", cu.ToArray()) : "";
            if (!_daSua)                                   // không ghi đè khi người đang gõ dở
            {
                bool dang = _daSua;
                _cot.Text = J.S(d.Get("so_lieu", "luoi", "cot"));
                _hang.Text = J.S(d.Get("so_lieu", "luoi", "hang"));
                _bu.Text = J.S(d.Get("so_lieu", "luoi", "ngoai_suy_m"), "0");
                _daSua = dang;
            }
        }

        void ApDung()
        {
            string cot = _cot.Text.Replace('×', 'x').Replace(';', ',').Trim(), hang = _hang.Text.Replace('×', 'x').Replace(';', ',').Trim(), bu = _bu.Text.Trim().Replace(',', '.');
            double ns;
            if (cot.Length > 0 && !MauSoKt.IsMatch(cot)) { Bao("Cột phải dạng Số×KT, ví dụ 10x20,5x15 (chữ x)."); return; }
            if (hang.Length > 0 && !MauSoKt.IsMatch(hang)) { Bao("Hàng phải dạng Số×KT, ví dụ 10x20,5x15 (chữ x)."); return; }
            if (!double.TryParse(bu, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out ns) || ns < 0)
            { Bao("Bù dữ liệu phải là số ≥ 0 (mét)."); return; }
            // giá trị chỉ gồm chữ số, x, dấu chấm, dấu phẩy, khoảng trắng → an toàn khi nhúng vào biểu thức LISP
            string s = "(setq *sn-pal-luoi* (list \"" + cot + "\" \"" + hang + "\" \"" + ns.ToString(System.Globalization.CultureInfo.InvariantCulture) + "\")) SN_LUOIAPDUNG ";
            GuiLenh(s, "Áp dụng lưới (lệnh SN_LUOIAPDUNG sẽ hỏi xác nhận)");
            _daSua = false;
        }
    }
}
