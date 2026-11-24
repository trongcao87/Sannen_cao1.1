// Màu và phông giao diện theo chủ đề màu hệ thống AutoCAD (biến COLORTHEME: 0 = tối, 1 = sáng). Chỉ ĐỌC biến hệ thống.
using System;
using System.Drawing;
using System.Windows.Forms;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace SanNen.Palette.Ui
{
    public static class Mau
    {
        public static bool Toi = true;
        public static Color Nen, NenPhu, Chu, ChuMo, Do, Cam, Xanh, Vien;
        public static readonly Font Font = new Font("Segoe UI", 9.5f);
        public static readonly Font FontDam = new Font("Segoe UI", 9.5f, FontStyle.Bold);

        static Mau() { Cap(); }

        public static void Cap()
        {
            try { Toi = Convert.ToInt32(AcApp.GetSystemVariable("COLORTHEME")) == 0; }
            catch (Exception) { Toi = true; }
            if (Toi)
            {
                Nen = Color.FromArgb(46, 52, 64); NenPhu = Color.FromArgb(59, 66, 82); Chu = Color.FromArgb(232, 234, 240);
                ChuMo = Color.FromArgb(150, 156, 170); Do = Color.FromArgb(255, 110, 110); Cam = Color.FromArgb(255, 190, 90);
                Xanh = Color.FromArgb(120, 190, 255); Vien = Color.FromArgb(90, 98, 115);
            }
            else
            {
                Nen = Color.FromArgb(240, 240, 240); NenPhu = Color.White; Chu = Color.FromArgb(30, 30, 30);
                ChuMo = Color.FromArgb(120, 120, 120); Do = Color.FromArgb(190, 20, 20); Cam = Color.FromArgb(170, 100, 0);
                Xanh = Color.FromArgb(0, 90, 180); Vien = Color.FromArgb(180, 180, 180);
            }
        }

        /// <summary>Áp màu + phông cho điều khiển và mọi điều khiển con.</summary>
        public static void Ap(Control c)
        {
            c.Font = Font;
            if (c is Button)
            {
                Button b = (Button)c;
                b.FlatStyle = FlatStyle.Flat;
                b.FlatAppearance.BorderColor = Vien;
                b.BackColor = NenPhu;
                b.ForeColor = Chu;
                b.UseVisualStyleBackColor = false;
            }
            else if (c is TextBox || c is ListView || c is TreeView)
            {
                c.BackColor = NenPhu;
                c.ForeColor = Chu;
            }
            else if (c is Label)
            {
                string vai = c.Tag as string;                      // "loi" → đỏ, "canhbao" → cam, "mo" → xám
                c.ForeColor = vai == "loi" ? Do : (vai == "canhbao" ? Cam : (vai == "mo" ? ChuMo : Chu));
                c.BackColor = Color.Transparent;
            }
            else
            {
                c.BackColor = Nen;
                c.ForeColor = Chu;
            }
            foreach (Control con in c.Controls) Ap(con);
        }
    }
}
