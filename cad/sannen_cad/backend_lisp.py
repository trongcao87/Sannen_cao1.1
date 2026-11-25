"""Backend LISP — SINH một file .lsp (entmake) để NẠP vào bản vẽ đang mở trong AutoCAD (menu SAN NỀN).

Không cần COM, không cần ghi file DXF: người dùng `(load "ve.lsp")` là các đối tượng kết quả xuất hiện
ngay trong bản vẽ đang làm việc. Mọi đối tượng mang XDATA appid "SANNEN" gồm
    (1000 . mã_lô) (1000 . đợt) (1000 . hash_truy_vết) (1000 . loại) (1000 . "k=v") ...
cùng thứ tự với `BackendDXF.doc_nhan`, nên file DXF lưu từ bản vẽ đó vẫn được backend DXF nhận ra
và `cad_purge_sn` xóa sạch đúng phần của lô này (RULES 5).

`xem_truoc=True` (RULES 4): KHÔNG thêm dòng nào vào script. File .lsp bản thân đã là "đề xuất vẽ":
bản vẽ chỉ đổi khi người nạp nó.
Các công cụ ĐỌC bản vẽ không làm được từ một file sinh ra — đọc là việc của lệnh chạy TRONG CAD.
"""
from __future__ import annotations
import csv
from pathlib import Path

from .backend import MAU_LAYER, TOI_DA_DINH_POLYFACE, Backend, chia_polyface, kiem_dang_3d, ten_layer

MAU = MAU_LAYER

# Hàm trợ giúp tiền tố `snv:` — định nghĩa lại mỗi lần nạp nên file .lsp tự đủ, không phụ thuộc menu.
DAU_FILE = r""";; Sinh tự động bởi sannen_cad.backend_lisp — KHÔNG sửa tay. Nạp bằng (load) trong AutoCAD.
(regapp "SANNEN")
(setq *snv-xd* nil)
;; tạo layer nếu chưa có (PHẢI tạo trước khi vẽ); tat = T thì tắt layer khi tạo (màu âm)
(defun snv:lop (ten mau tat)
  (if (not (tblsearch "LAYER" ten))
    (entmake (list '(0 . "LAYER") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbLayerTableRecord")
                   (cons 2 ten) '(70 . 0) (cons 62 (if tat (- mau) mau)))))
  ten)
;; bật/tắt layer đã có (màu âm = tắt)
(defun snv:bat (ten bat / r c)
  (if (and (tblsearch "LAYER" ten) (setq r (entget (tblobjname "LAYER" ten))))
    (progn
      (setq c (abs (cdr (assoc 62 r))))
      (entmod (subst (cons 62 (if bat c (- c))) (assoc 62 r) r))))
  ten)
;; dấu truy vết cho các đối tượng vẽ tiếp theo: lô, đợt, hash, loại, danh sách "k=v"
(defun snv:dat (lo dot hs loai ex)
  (setq *snv-xd*
         (list -3 (cons "SANNEN" (mapcar '(lambda (s) (cons 1000 s)) (append (list lo dot hs loai) ex))))))
(defun snv:pl (pts dong ly mau)
  (entmake (append (list '(0 . "LWPOLYLINE") '(100 . "AcDbEntity") (cons 8 ly) (cons 62 mau)
                         '(100 . "AcDbPolyline") (cons 90 (length pts)) (cons 70 (if dong 1 0)))
                   (mapcar '(lambda (p) (cons 10 p)) pts)
                   (list *snv-xd*))))
(defun snv:t (x y h s ly mau)
  (entmake (list '(0 . "TEXT") (cons 8 ly) (cons 62 mau) (cons 10 (list x y 0.0)) (cons 40 h) (cons 1 s) *snv-xd*)))
(defun snv:t3 (x y z h s ly mau)
  (entmake (list '(0 . "TEXT") (cons 8 ly) (cons 62 mau) (cons 10 (list x y z)) (cons 40 h) (cons 1 s) *snv-xd*)))
(defun snv:pt (x y z ly mau)
  (entmake (list '(0 . "POINT") '(100 . "AcDbEntity") (cons 8 ly) (cons 62 mau) '(100 . "AcDbPoint") (cons 10 (list x y z)) *snv-xd*)))
(defun snv:m (x y h s ly mau)
  (entmake (list '(0 . "MTEXT") '(100 . "AcDbEntity") (cons 8 ly) (cons 62 mau) '(100 . "AcDbMText")
                 (cons 10 (list x y 0.0)) (cons 40 h) (cons 71 5) (cons 1 s) *snv-xd*)))
(defun snv:f (p1 p2 p3 ly)
  (entmake (list '(0 . "3DFACE") '(100 . "AcDbEntity") (cons 8 ly) '(100 . "AcDbFace")
                 (cons 10 p1) (cons 11 p2) (cons 12 p3) (cons 13 p3) *snv-xd*)))
;; đặt lại MÀU layer đã có (giữ nguyên trạng thái bật/tắt: màu âm = tắt) — layer 3D cũ có thể còn màu cũ
(defun snv:mau (ten mau / r c)
  (if (and (tblsearch "LAYER" ten) (setq r (entget (tblobjname "LAYER" ten))))
    (progn
      (setq c (cdr (assoc 62 r)))
      (entmod (subst (cons 62 (if (< c 0) (- mau) mau)) (assoc 62 r) r))))
  ten)
;; POLYFACE MESH: snv:pf mở (71 = số đỉnh, 72 = số mặt), snv:pd từng đỉnh, snv:pm từng mặt tam giác (chỉ số 1..n),
;; snv:pk đóng (SEQEND). Cả khối là MỘT đối tượng POLYLINE mang XDATA "SANNEN" (chọn/ẩn/xóa một lần).
(defun snv:pf (nd nm ly)
  (setq *snv-ly* ly)
  (entmake (list '(0 . "POLYLINE") '(100 . "AcDbEntity") (cons 8 ly) '(100 . "AcDbPolyFaceMesh")
                 '(66 . 1) '(10 0.0 0.0 0.0) '(70 . 64) (cons 71 nd) (cons 72 nm) *snv-xd*)))
(defun snv:pd (x y z)
  (entmake (list '(0 . "VERTEX") '(100 . "AcDbEntity") (cons 8 *snv-ly*) '(100 . "AcDbVertex")
                 '(100 . "AcDbPolyFaceMeshVertex") (list 10 x y z) '(70 . 192))))
(defun snv:pm (a b c)
  (entmake (list '(0 . "VERTEX") '(100 . "AcDbEntity") (cons 8 *snv-ly*) '(100 . "AcDbFaceRecord")
                 '(10 0.0 0.0 0.0) '(70 . 128) (cons 71 a) (cons 72 b) (cons 73 c) '(74 . 0))))
(defun snv:pk () (entmake (list '(0 . "SEQEND") (cons 8 *snv-ly*))))
;; xóa đối tượng kết quả CŨ của đúng lô này. dot = nil: mọi đợt; loais = nil: mọi loại;
;; ex = danh sách "k=v" mà đối tượng phải có đủ. Trả số đối tượng đã xóa. Không đụng nguồn, không đụng lô khác.
(defun snv:xoa (lo dot loais ex / ss i e d n)
  (setq n 0)
  (if (setq ss (ssget "X" '((-3 ("SANNEN")))))
    (repeat (setq i (sslength ss))
      (setq e (ssname ss (setq i (1- i))))
      (setq d (mapcar 'cdr (cdr (cadr (assoc -3 (entget e '("SANNEN")))))))
      (if (and (>= (length d) 4)
               (= (nth 0 d) lo)
               (or (null dot) (= (nth 1 d) dot))
               (or (null loais) (member (nth 3 d) loais))
               (or (null ex) (null (vl-remove-if '(lambda (x) (member x (cddddr d))) ex))))
        (progn (entdel e) (setq n (1+ n))))))
  n)
;; xóa nhãn đỉnh (loại nhan_dinh) của các mã đỉnh cho trước: mas = ("ma=D01-01" ...) — cập nhật tại chỗ
(defun snv:xoa-nhan (lo dot mas / ss i e d n)
  (setq n 0)
  (if (setq ss (ssget "X" '((-3 ("SANNEN")))))
    (repeat (setq i (sslength ss))
      (setq e (ssname ss (setq i (1- i))))
      (setq d (mapcar 'cdr (cdr (cadr (assoc -3 (entget e '("SANNEN")))))))
      (if (and (>= (length d) 4)
               (= (nth 0 d) lo)
               (or (null dot) (= (nth 1 d) dot))
               (= (nth 3 d) "nhan_dinh")
               (vl-some '(lambda (x) (member x mas)) (cddddr d)))
        (progn (entdel e) (setq n (1+ n))))))
  n)
"""


def ls(s) -> str:
    """Chuỗi LISP: thoát \\ và \" và xuống dòng. Chữ Việt giữ nguyên (file UTF-8 đã kiểm chứng)."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n") + '"'


def so(x) -> str:
    """Số thực LISP, luôn ở dạng thập phân (không dùng số mũ)."""
    return f"{round(float(x), 6):.6f}"


def _pt(p) -> str:
    return "'(" + " ".join(so(v) for v in p) + ")"


def _pts(ds) -> str:
    return "'(" + " ".join("(" + " ".join(so(v) for v in p) + ")" for p in ds) + ")"


def _ds(xau: list[str]) -> str:
    return "'(" + " ".join(ls(x) for x in xau) + ")" if xau else "nil"


class BackendLisp(Backend):
    toi_da_dinh = TOI_DA_DINH_POLYFACE          # số đỉnh tối đa của MỘT polyface (test hạ xuống để thử chia khối)

    def __init__(self, csv_nhan: str | Path | None = None):
        self.csv_nhan = Path(csv_nhan) if csv_nhan else None   # CSV (ma,be_mat,z) do CAD xuất — cho cad_read_grid_z
        self.dong: list[str] = []
        self._lop_da_khai: set[str] = set()

    # ---- tiện ích -------------------------------------------------------------------
    def noi_dung(self) -> str:
        return DAU_FILE + "\n".join(self.dong) + "\n(princ)\n"

    def luu(self, duong_dan: str | Path) -> Path:
        p = Path(duong_dan)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.noi_dung().encode("utf-8"))          # UTF-8 KHÔNG BOM (đã kiểm chứng với AutoCAD 2022)
        return p

    def _them(self, xem_truoc: bool, *dong: str) -> None:
        if not xem_truoc:
            self.dong.extend(dong)

    def _lop(self, goc: str, dot: int | None, tat: bool = False) -> tuple[str, str | None]:
        """Tên layer + dòng lệnh tạo layer (chỉ lần đầu trong script)."""
        ten = ten_layer(goc, dot)
        if ten in self._lop_da_khai:
            return ten, None
        self._lop_da_khai.add(ten)
        return ten, f"(snv:lop {ls(ten)} {MAU.get(goc, 7)} {'T' if tat else 'nil'})"

    def _dat(self, ma_lo, dot, hash_tv, loai, ex=()) -> str:
        return f"(snv:dat {ls(ma_lo)} {ls(dot)} {ls(hash_tv)} {ls(loai)} {_ds(list(ex))})"

    def _kq(self, ten: str, xem_truoc: bool, **kq) -> dict:
        return {"cong_cu": ten, "xem_truoc": xem_truoc, "da_ghi": not xem_truoc, **kq}

    # ---- đọc: KHÔNG làm được từ một file sinh ra --------------------------------------
    def cad_doc_info(self) -> dict:
        raise NotImplementedError("Backend LISP chỉ sinh lệnh vẽ; đọc thông tin bản vẽ: dùng lệnh SN_TRANGTHAI trong CAD")

    def cad_read_points(self, layer: str) -> list[list[float]]:
        raise NotImplementedError("Backend LISP không đọc bản vẽ; đầu vào của lõi là DXF (xuất từ CAD rồi chạy nhap)")

    def cad_read_polylines(self, layer: str) -> list[dict]:
        raise NotImplementedError("Backend LISP không đọc bản vẽ; đầu vào của lõi là DXF (xuất từ CAD rồi chạy nhap)")

    def cad_export_dxf(self, duong_dan: str) -> dict:
        raise NotImplementedError("Xuất DXF: dùng lệnh SAVEAS của AutoCAD (chọn DXF)")

    def cad_read_grid_z(self, ma_lo: str, dot: int | None = None) -> list[dict]:
        """Đọc ngược cao độ đỉnh từ CSV do CAD xuất (lệnh SN_DONGBO): cột ma, be_mat, z."""
        if self.csv_nhan is None:
            raise NotImplementedError("Chưa có CSV nhãn đỉnh — chạy lệnh SN_DONGBO trong CAD để xuất ra")
        txt = self.csv_nhan.read_text(encoding="utf-8-sig")
        dau = ";" if txt.splitlines() and txt.splitlines()[0].count(";") > txt.splitlines()[0].count(",") else ","
        ra = []
        for r in csv.reader(txt.splitlines(), delimiter=dau):
            if len(r) < 3 or r[0].strip().lower() == "ma":
                continue
            ra.append({"ma": r[0].strip(), "be_mat": r[1].strip(), "z": float(r[2].strip().replace(",", "."))})
        return sorted(ra, key=lambda x: (x["ma"], x["be_mat"]))

    # ---- ghi ------------------------------------------------------------------------
    def cad_purge_sn(self, ma_lo: str, dot: int | None = None, xem_truoc: bool = True,
                     loai: tuple[str, ...] | None = None, ex: list[str] | None = None) -> dict:
        """Xóa kết quả CŨ của đúng lô này. `ex` (mở rộng): chỉ xóa đối tượng có đủ các "k=v" đó (vd "ten=MC1")."""
        self._them(xem_truoc, f"(snv:xoa {ls(ma_lo)} {'nil' if dot is None else ls(dot)} "
                              f"{_ds(list(loai)) if loai else 'nil'} {_ds(ex or [])})")
        return self._kq("cad_purge_sn", xem_truoc, ma_lo=ma_lo, loai=list(loai) if loai else None)

    def cad_draw_grid(self, ma_lo, dot, hash_tv, luoi, xem_truoc=True) -> dict:
        import math
        ox, oy = luoi["goc_luoi"]
        th = math.radians(luoi["goc_xoay_do"])
        c, s = math.cos(th), math.sin(th)
        U, V = [0.0], [0.0]
        for w in luoi["cot_m"]:
            U.append(U[-1] + w)
        for h in luoi["hang_m"]:
            V.append(V[-1] + h)
        P = lambda u, v: (ox + u * c - v * s, oy + u * s + v * c)
        duong = [(P(u, V[0]), P(u, V[-1])) for u in U] + [(P(U[0], v), P(U[-1], v)) for v in V]
        ten, tao = self._lop("SN-LUOI", dot)
        if not xem_truoc:
            if tao:
                self.dong.append(tao)
            self.dong.append(self._dat(ma_lo, dot, hash_tv, "luoi"))
            self.dong += [f"(snv:pl {_pts([a, b])} nil {ls(ten)} 256)" for a, b in duong]
        return self._kq("cad_draw_grid", xem_truoc, so_duong=len(duong))

    def cad_set_vertex_z(self, ma_lo, dot, hash_tv, nut, xem_truoc=True) -> dict:
        """Tạo/cập nhật nhãn cao độ mốc, đo, chênh cao: xóa nhãn cũ cùng mã đỉnh rồi vẽ lại — không nhân đôi."""
        moi = 0
        if not xem_truoc and nut:
            ten, tao = self._lop("SN-LUOI-NHAN", dot)
            if tao:
                self.dong.append(tao)
            mas = ["ma=" + str(d["ma"]) for d in nut]
            self.dong.append(f"(snv:xoa-nhan {ls(ma_lo)} {ls(dot)} {_ds(mas)})")
            for d in nut:
                dz = None if d.get("z_do") is None or d.get("z_moc") is None else d["z_do"] - d["z_moc"]
                for be, z, dy in (("moc", d.get("z_moc"), 0.0), ("do", d.get("z_do"), -1.0), ("dz", dz, -2.0)):
                    if z is None:
                        continue
                    txt = f"{z:+.3f}" if be == "dz" else f"{z:.3f}"
                    self.dong.append(self._dat(ma_lo, dot, hash_tv, "nhan_dinh", ["ma=" + str(d["ma"]), "be_mat=" + be]))
                    self.dong.append(f"(snv:t {so(d['e'] + 0.3)} {so(d['n'] + 0.3 + dy * 0.7)} 0.5 {ls(txt)} {ls(ten)} 256)")
                    moi += 1
        return self._kq("cad_set_vertex_z", xem_truoc, so_nhan=moi)

    def cad_label_cells(self, ma_lo, dot, hash_tv, o, xem_truoc=True) -> dict:
        if not xem_truoc:
            ten, tao = self._lop("SN-LUOI-O", dot)
            if tao:
                self.dong.append(tao)
            for c in o:
                van_ban = f"{c['ma']}\\PĐào {c['kl_dao_m3']:,.1f}\\PĐắp {c['kl_dap_m3']:,.1f}"
                if c.get("thieu_du_lieu"):
                    van_ban = f"{c['ma']}\\PTHIẾU DỮ LIỆU"
                self.dong.append(self._dat(ma_lo, dot, hash_tv, "nhan_o", ["ma=" + str(c["ma"])]))
                self.dong.append(f"(snv:m {so(c['e'])} {so(c['n'])} 0.8 {ls(van_ban)} {ls(ten)} 256)")
        return self._kq("cad_label_cells", xem_truoc, so_nhan=len(o))

    def cad_draw_cutfill_line(self, ma_lo, dot, hash_tv, doan, xem_truoc=True) -> dict:
        if not xem_truoc and doan:
            ten, tao = self._lop("SN-RANH-DAODAP", dot)
            if tao:
                self.dong.append(tao)
            self.dong.append(self._dat(ma_lo, dot, hash_tv, "ranh_dao_dap"))
            self.dong += [f"(snv:pl {_pts([a, b])} nil {ls(ten)} 256)" for a, b in doan]
        return self._kq("cad_draw_cutfill_line", xem_truoc, so_doan=len(doan))

    def cad_draw_3dface(self, ma_lo, dot, hash_tv, be_mat, tam_giac, loai="mat", xem_truoc=True, dang="3dface") -> dict:
        kiem_dang_3d(dang)
        goc = "SN-QC" if loai == "qc" else ("SN-3DF-MOC" if be_mat == "moc" else "SN-3DF-DO")
        ten = ten_layer(goc, dot)
        loai_tv = "qc" if loai == "qc" else "mat_3d"
        kq: dict = {}
        khoi = chia_polyface(tam_giac, self.toi_da_dinh) if dang == "polyface" else []
        if dang == "polyface":
            kq = {"dang": "polyface", "so_polyface": len(khoi), "so_dinh": sum(len(d) for d, _ in khoi)}
            if len(khoi) > 1:
                kq["ghi_chu"] = (f"Bề mặt có {kq['so_dinh']} đỉnh — vượt giới hạn một polyface của AutoCAD, "
                                 f"đã chia thành {len(khoi)} khối liên tiếp (mỗi khối ≤ {self.toi_da_dinh} đỉnh)")
        if not xem_truoc and tam_giac:
            _, tao = self._lop(goc, dot, tat=goc.startswith("SN-3DF"))   # mặt 3D tắt mặc định (layer-convention)
            if tao:
                self.dong.append(tao)
            self.dong.append(f"(snv:mau {ls(ten)} {MAU.get(goc, 7)})")
            if dang == "polyface":
                for i, (dinh, mat) in enumerate(khoi, 1):
                    self.dong.append(self._dat(ma_lo, dot, hash_tv, loai_tv,
                                               [f"be_mat={be_mat}", f"so_mat={len(mat)}", f"khoi={i}/{len(khoi)}"]))
                    self.dong.append(f"(snv:pf {len(dinh)} {len(mat)} {ls(ten)})")
                    self.dong += [f"(snv:pd {so(p[0])} {so(p[1])} {so(p[2])})" for p in dinh]
                    self.dong += [f"(snv:pm {a + 1} {b + 1} {c + 1})" for a, b, c in mat]
                    self.dong.append("(snv:pk)")
            else:
                self.dong.append(self._dat(ma_lo, dot, hash_tv, loai_tv, [f"be_mat={be_mat}"]))
                self.dong += [f"(snv:f {_pt(t[0])} {_pt(t[1])} {_pt(t[2])} {ls(ten)})" for t in tam_giac]
        return self._kq("cad_draw_3dface", xem_truoc, layer=ten, so_mat=len(tam_giac), **kq)

    def cad_draw_table(self, ma_lo, dot, hash_tv, bang, goc_ve, chieu_cao_chu=1.25, xem_truoc=True) -> dict:
        from .bo_cuc import bang_ent
        kq = self.ve_ent(ma_lo, dot, hash_tv, "bang", "SN-BANG", bang_ent(bang, goc_ve, chieu_cao_chu), xem_truoc)
        return {**kq, "cong_cu": "cad_draw_table", "so_khoi": len(bang["khoi"])}

    def ve_ent(self, ma_lo, dot, hash_tv, loai, layer, ent, xem_truoc=True, **them) -> dict:
        """Vẽ danh sách đối tượng đơn giản của bo_cuc (chữ, khung, đoạn, đa tuyến). `them` → "k=v" trong dấu truy vết."""
        if not xem_truoc and ent:
            ten, tao = self._lop(layer, dot)
            if tao:
                self.dong.append(tao)
            self.dong.append(self._dat(ma_lo, dot, hash_tv, loai, [f"{k}={v}" for k, v in them.items()]))
            for x in ent:
                if x[0] == "text":
                    self.dong.append(f"(snv:t {so(x[2])} {so(x[3])} {so(x[4])} {ls(x[1])} {ls(ten)} {x[5] if len(x) > 5 else 256})")
                elif x[0] == "text3d":
                    self.dong.append(f"(snv:t3 {so(x[2])} {so(x[3])} {so(x[4])} {so(x[5])} {ls(x[1])} {ls(ten)} {x[6] if len(x) > 6 else 256})")
                elif x[0] == "point":
                    self.dong.append(f"(snv:pt {so(x[1])} {so(x[2])} {so(x[3])} {ls(ten)} {x[4] if len(x) > 4 else 256})")
                elif x[0] == "khung":
                    _, fx, fy, fw, fh = x
                    self.dong.append(f"(snv:pl {_pts([(fx, fy), (fx + fw, fy), (fx + fw, fy - fh), (fx, fy - fh)])} T {ls(ten)} 256)")
                elif x[0] == "doan":
                    self.dong.append(f"(snv:pl {_pts([(x[1], x[2]), (x[3], x[4])])} nil {ls(ten)} {x[5] if len(x) > 5 else 256})")
                elif x[0] == "pl":
                    self.dong.append(f"(snv:pl {_pts(x[1])} {'T' if x[2] else 'nil'} {ls(ten)} {x[3] if len(x) > 3 else 256})")
                else:
                    raise ValueError(f"Phần tử bố cục lạ: {x[0]}")
        return self._kq("ve_ent", xem_truoc, loai=loai, so_doi_tuong=len(ent))

    # ---- điều hướng -------------------------------------------------------------------
    def cad_zoom_to(self, e: float, n: float, kich_thuoc: float = 50.0) -> dict:
        self.dong.append(f"(command \"_.ZOOM\" \"_C\" (list {so(e)} {so(n)}) {so(kich_thuoc)})")
        return {"e": e, "n": n, "chieu_cao_khung_nhin": kich_thuoc}

    # ---- mở rộng cho menu: bật/tắt layer ------------------------------------------------
    def bat_lop(self, goc: str, dot: int | None, bat: bool) -> None:
        """Bật/tắt một layer kết quả (vd SN-3DF-MOC). Không làm gì nếu layer chưa tồn tại khi nạp."""
        self.dong.append(f"(snv:bat {ls(ten_layer(goc, dot))} {'T' if bat else 'nil'})")
