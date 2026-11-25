// Tab "Khối lượng": số nộp (lưới) / số kiểm (lăng trụ) / chênh lệch / ô lệch lớn / ba cổng duyệt — TẤT CẢ do lõi tính và định dạng.
// Palette chỉ HIỂN THỊ trạng thái cổng và gọi SN_DUYET (người bấm duyệt tại chỗ); chốt chặn ba cổng nằm ở core/sannen/cong.py.
// Các nút gọi lệnh LISP có sẵn; chuyển sang C# ở bước 3 lộ trình (_agent/KIEN-TRUC-TOI-UU.md).
using System;
using System.Collections.Generic;
using System.Windows.Forms;
using SanNen.Palette.Models;
using SanNen.Palette.Services;

namespace SanNen.Palette.Ui
{
    public sealed class KhoiLuongTab : TabCoSo
    {
        readonly ListView _bang = TaoBang(new string[] { "Chỉ tiêu", "Giá trị" }, new int[] { 200, 130 });
        readonly Label _cong = new Label();
        readonly Label _cu = new Label();

        public override string TenTab { get { return "Khối lượng"; } }

        public KhoiLuongTab()
        {
            _cu.Dock = DockStyle.Top;
            _cu.AutoSize = true;
            _cu.Tag = "canhbao";
            _cu.Padding = new Padding(6, 2, 6, 2);
            _cu.Visible = false;
            _cong.Dock = DockStyle.Top;
            _cong.AutoSize = true;
            _cong.Padding = new Padding(6, 4, 6, 4);
            _cong.Font = Mau.FontDam;
            _bang.Dock = DockStyle.Fill;
            Than.Controls.Add(_bang);
            Than.Controls.Add(HangNut(
                Nut("Tính đào đắp lưới (SN_TINH)", delegate { GuiLenh("SN_TINH ", "Tính toán đào đắp lưới và vẽ khối lượng từng ô / ranh đào đắp"); }),
                Nut("Cộng ô (DD_MC)", delegate { GuiLenh("SN_CONGO ", "Cộng khối lượng hai ô lưới cạnh nhau trên bản vẽ"); }),
                Nut("Bảng biểu", delegate { Bao(CadLenh.Bang() ?? "Chèn bảng khối lượng — xem dòng lệnh AutoCAD."); }),
                Nut("Excel (SN_EXCEL)", delegate { GuiLenh("SN_EXCEL ", "Xuất Excel + hồ sơ"); }),
                Nut("Trình xem 3D HTML", delegate { GuiLenh("SN_XEM3D ", "Mở trình xem 3D"); }),
                Nut("Duyệt cổng…", delegate { Bao(CadLenh.Duyet() ?? "Duyệt cổng — xem dòng lệnh AutoCAD."); })));
            Than.Controls.Add(_cu);
            Than.Controls.Add(_cong);
            DungXong();
        }

        protected override void CapNhat(DuLieuPal d)
        {
            if (!d.Ok)
            {
                DoDong(_bang, new List<string[]>());
                _cong.Text = "Cổng 1: chưa rõ  |  Cổng 2: chưa rõ  |  Cổng 3: chưa rõ";
                _cu.Visible = false;
                return;
            }
            DoDong(_bang, d.Dong("khoiluong"));
            _cong.Text = d.ChuCong(1) + "\r\n" + d.ChuCong(2) + "\r\n" + d.ChuCong(3);
            List<string> cu = d.CanhBaoCu();
            _cu.Visible = cu.Count > 0;
            _cu.Text = cu.Count > 0 ? "KẾT QUẢ CŨ: " + string.Join("  •  ", cu.ToArray()) : "";
            Mau.Ap(_cu);
        }
    }
}
