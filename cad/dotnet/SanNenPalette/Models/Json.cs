// Đọc JSON tối giản (System.Web.Extensions của .NET 4 — không thêm thư viện). Lớp THUẦN, không dùng API AutoCAD.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Web.Script.Serialization;

namespace SanNen.Palette.Models
{
    public static class J
    {
        public static object Parse(string s)
        {
            JavaScriptSerializer js = new JavaScriptSerializer();
            js.MaxJsonLength = int.MaxValue;
            js.RecursionLimit = 200;
            return js.DeserializeObject(s);
        }

        /// <summary>Đi theo chuỗi khoá từ gốc; thiếu khoá → null.</summary>
        public static object Get(object o, params string[] khoa)
        {
            foreach (string k in khoa)
            {
                IDictionary<string, object> d = o as IDictionary<string, object>;
                if (d == null || !d.ContainsKey(k)) return null;
                o = d[k];
            }
            return o;
        }

        public static string S(object o, string macDinh)
        {
            if (o == null) return macDinh;
            if (o is bool) return ((bool)o) ? "true" : "false";
            if (o is IConvertible) return Convert.ToString(o, CultureInfo.InvariantCulture);
            return macDinh;
        }

        public static string S(object o) { return S(o, ""); }

        public static double? D(object o)
        {
            if (o == null || o is string || o is bool || !(o is IConvertible)) return null;
            try { return Convert.ToDouble(o, CultureInfo.InvariantCulture); }
            catch (Exception) { return null; }
        }

        public static int I(object o, int macDinh)
        {
            double? d = D(o);
            return d.HasValue ? (int)Math.Round(d.Value) : macDinh;
        }

        public static bool B(object o)
        {
            return o is bool && (bool)o;
        }

        public static List<object> L(object o)
        {
            List<object> ra = new List<object>();
            IEnumerable e = o as IEnumerable;
            if (e == null || o is string || o is IDictionary<string, object>) return ra;
            foreach (object x in e) ra.Add(x);
            return ra;
        }
    }
}
