"""Đọc điểm đo từ Excel / CSV khi khảo sát giao bảng số thay vì bản vẽ (giai đoạn 1).

Ba việc khó của file khảo sát thật, đều xử lý ở đây:
  1. Nhiều dòng tiêu đề phía trên, hàng tiêu đề thật nằm giữa trang  -> tự dò.
  2. Mỗi dòng xếp NHIỀU KHỐI điểm cạnh nhau (cột 1-5 và 6-10)       -> tách khối.
  3. Số viết kiểu Việt Nam: "103,5" hoặc "1.113.045,123"            -> đọc đúng.

Ánh xạ cột (tiêu đề -> id/northing/easting/z/code) KHÔNG đoán âm thầm (RULES 7):
  - lot.yaml khai sẵn                      -> dùng luôn.
  - đã từng được người xác nhận           -> nhớ trong `anh_xa_cot.yaml` của lô,
    khóa theo "dấu vân tay" hàng tiêu đề: giao đợt mới cùng khuôn thì khỏi hỏi lại,
    khảo sát đổi khuôn thì tự dừng hỏi lại.
  - chưa có gì                             -> đề xuất từ tiêu đề rồi DỪNG chờ người xác nhận.

Dòng hỏng bị bỏ qua nhưng LUÔN ghi lại số dòng (RULES 2): không âm thầm làm mất điểm.
"""
from __future__ import annotations
import csv
import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from .dxfio import Diem
from .paths import Lot
from .qc import _phat_hien

TRUONG = ("id", "northing", "easting", "z", "code")
BAT_BUOC = ("northing", "easting", "z")
QUET_TOI_DA = 40          # chỉ dò hàng tiêu đề trong 40 hàng đầu
TOI_DA_LIET_KE = 20       # liệt kê tối đa 20 dòng hỏng; còn lại gộp một dòng tổng
TY_LE_HONG_CHAN = 0.05    # quá 5 % dòng hỏng thì gần như chắc chắn ánh xạ cột sai
FILE_NHO = "anh_xa_cot.yaml"

# Đã chuẩn hóa (bỏ dấu, chữ thường, chỉ giữ chữ-số). "Tọa độ X(m)" -> "toadoxm".
# Quy ước trắc địa Việt Nam: X là NORTHING, Y là EASTING (xem lot.yaml).
DONG_NGHIA: dict[str, set[str]] = {
    "id": {"tendiem", "diem", "sohieu", "tenmoc", "point", "pointid", "id", "name", "ten"},
    "northing": {"x", "xm", "toadox", "toadoxm", "northing", "n"},
    "easting": {"y", "ym", "toadoy", "toadoym", "easting", "e"},
    "z": {"h", "hm", "z", "zm", "caodo", "caodoh", "caodohm", "caodoz", "caodozm",
          "cao", "elevation"},
    "code": {"ghichu", "code", "ma", "mota", "description", "desc"},
}


class LoiNguon(Exception):
    """File nguồn không đọc được hoặc khai báo sai. DỪNG, không vá (RULES 7)."""


class CanXacNhan(Exception):
    """Có đề xuất ánh xạ cột nhưng chưa người nào xác nhận. Agent phải HỎI người."""


# --------------------------------------------------------------------------- tiện ích
def chuan_hoa(s) -> str:
    s = unicodedata.normalize("NFD", str(s).replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.lower())


_RE_SO = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)")


def doc_so(v) -> float | None:
    """None nếu ô rỗng. ValueError nếu có nội dung mà không phải số.

    Dấu phẩy đơn là dấu thập phân (kiểu Việt Nam): "103,5" = 103.5.
    Nhiều dấu cùng loại là dấu nghìn: "1.113.045" = 1113045. Có cả hai: dấu nằm
    sau cùng là dấu thập phân.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        raise ValueError("giá trị logic")
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            raise ValueError("không hữu hạn")
        return float(v)
    s = str(v).replace("\u00a0", "").replace(" ", "").strip()
    if s == "":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") \
            else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    if not _RE_SO.fullmatch(s):
        raise ValueError(f"«{v}» không phải số")
    return float(s)


def _rong(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _id_chuoi(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def bam_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for khoi in iter(lambda: f.read(1 << 20), b""):
            h.update(khoi)
    return h.hexdigest()


# --------------------------------------------------------------------------- đọc bảng thô
@dataclass
class _Bang:
    ten: str
    hang: list[list]


def _cac_bang(path: Path, sheet: str | None) -> list[_Bang]:
    suf = path.suffix.lower()
    if suf in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError as e:                       # pragma: no cover
            raise LoiNguon("Thiếu thư viện openpyxl: pip install openpyxl") from e
        try:
            wb = load_workbook(path, read_only=False, data_only=True)
        except Exception as e:
            raise LoiNguon(f"Không mở được {path.name}: {e}") from e
        try:
            if sheet and sheet not in wb.sheetnames:
                raise LoiNguon(f"Không thấy sheet «{sheet}» trong {path.name}. "
                               f"Có: {', '.join(wb.sheetnames)}")
            ten = [sheet] if sheet else wb.sheetnames
            return [_Bang(n, [list(r) for r in wb[n].iter_rows(values_only=True)])
                    for n in ten]
        finally:
            wb.close()
    if suf == ".xls":                                   # Excel 97-2003: khảo sát vẫn hay giao định dạng này
        try:
            import xlrd
        except ImportError as e:                       # pragma: no cover
            raise LoiNguon("File .xls cần thư viện xlrd: pip install xlrd (hoặc lưu lại thành .xlsx)") from e
        try:
            wb = xlrd.open_workbook(str(path))
        except Exception as e:
            raise LoiNguon(f"Không mở được {path.name}: {e}") from e
        ten = [sheet] if sheet else [s.name for s in wb.sheets() if s.nrows]
        if sheet and sheet not in wb.sheet_names():
            raise LoiNguon(f"Không thấy sheet «{sheet}» trong {path.name}. Có: {', '.join(wb.sheet_names())}")
        return [_Bang(n, [list(wb.sheet_by_name(n).row_values(r)) for r in range(wb.sheet_by_name(n).nrows)])
                for n in ten]
    if suf in (".csv", ".txt"):
        for enc in ("utf-8-sig", "cp1258", "cp1252"):
            try:
                txt = path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:                                           # pragma: no cover
            raise LoiNguon(f"Không đoán được bảng mã của {path.name}")
        try:
            dau = csv.Sniffer().sniff(txt[:4096], delimiters=",;\t|").delimiter
        except csv.Error:
            dau = ","
        return [_Bang(path.stem, [list(r) for r in csv.reader(txt.splitlines(), delimiter=dau)])]
    raise LoiNguon(f"Định dạng {suf} chưa hỗ trợ (có: .xlsx .xls .csv). Lưu lại thành .xlsx hoặc .csv.")


# --------------------------------------------------------------------------- hàng tiêu đề
@dataclass
class _Hit:
    bang: _Bang
    r: int                          # chỉ số hàng tiêu đề, đếm từ 0
    cols: dict[str, list[int]]      # trường -> các cột, mỗi khối điểm một cột


def _tim_trong(bang: _Bang, ten_cot: dict[str, set[str]]) -> _Hit | None:
    for r, hang in enumerate(bang.hang[:QUET_TOI_DA]):
        cols: dict[str, list[int]] = {}
        for c, o in enumerate(hang):
            if _rong(o):
                continue
            n = chuan_hoa(o)
            for t, tap in ten_cot.items():
                if n in tap:
                    cols.setdefault(t, []).append(c)
                    break
        if all(t in cols for t in BAT_BUOC):
            return _Hit(bang, r, cols)
    return None


def _tim(cac_bang: list[_Bang], ten_cot: dict[str, set[str]]) -> _Hit | None:
    thay = [h for b in cac_bang if (h := _tim_trong(b, ten_cot))]
    if len(thay) > 1:
        raise LoiNguon("Nhiều sheet cùng có hàng tiêu đề điểm đo ("
                       + ", ".join(h.bang.ten for h in thay)
                       + "). Khai `sheet:` trong lot.yaml để chỉ rõ.")
    return thay[0] if thay else None


def dau_van_tay(h: _Hit) -> str:
    """Băm hàng tiêu đề — cùng khuôn bảng thì cùng dấu vân tay, bất kể bao nhiêu điểm."""
    chuoi = "|".join(chuan_hoa(o) for o in h.bang.hang[h.r] if not _rong(o))
    return hashlib.sha1(chuoi.encode("utf-8")).hexdigest()[:12]


def _tieu_de_thay(cac_bang: list[_Bang]) -> str:
    d = []
    for b in cac_bang:
        for r, hang in enumerate(b.hang[:QUET_TOI_DA]):
            o = [str(x) for x in hang if not _rong(x)]
            if len(o) >= 3:
                d.append(f"  {b.ten}!hàng {r + 1}: " + " | ".join(o[:10]))
                break
    return "Tiêu đề tìm thấy:\n" + "\n".join(d) if d else "Không thấy hàng nào giống tiêu đề."


def _chu_goc(h: _Hit) -> dict[str, str]:
    """Chữ tiêu đề đúng như viết trong file (lấy cột đầu của mỗi trường)."""
    return {t: str(h.bang.hang[h.r][cs[0]]).strip() for t, cs in h.cols.items()}


# --------------------------------------------------------------------------- bộ nhớ ánh xạ
def _nho_doc(lot: Lot) -> list[dict]:
    p = lot.root / FILE_NHO
    if not p.exists():
        return []
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("anh_xa", [])


def luu_anh_xa(lot: Lot, h: _Hit, tu_file: str) -> None:
    """Ghi nhớ ánh xạ người đã xác nhận + một dòng vào decisions.md (SPEC mục 5)."""
    p = lot.root / FILE_NHO
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    cot = _chu_goc(h)
    vt = dau_van_tay(h)
    ds = [e for e in _nho_doc(lot) if e.get("dau_van_tay") != vt]
    ds.append({"dau_van_tay": vt, "tu_file": tu_file, "sheet": h.bang.ten,
               "hang_tieu_de": h.r + 1, "xac_nhan_luc": luc, "cot": cot})
    p.write_text("# Ánh xạ cột đã được người xác nhận. Xóa mục nào thì lần sau hỏi lại mục đó.\n"
                 + yaml.safe_dump({"anh_xa": ds}, allow_unicode=True, sort_keys=False),
                 encoding="utf-8")
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · nhap · Xác nhận ánh xạ cột `{tu_file}` "
                f"(sheet {h.bang.ten}, hàng tiêu đề {h.r + 1}): "
                + ", ".join(f"{t}=«{v}»" for t, v in cot.items()) + "\n")


# --------------------------------------------------------------------------- kết quả
@dataclass
class KetQuaBang:
    file: Path
    hash_sha256: str
    sheet: str
    hang_tieu_de: int
    so_khoi: int
    anh_xa: dict[str, str]
    nguon_anh_xa: str
    dau_van_tay: str
    diem: list[Diem] = field(default_factory=list)
    phat_hien: list[dict] = field(default_factory=list)
    so_hang_khong_phai_du_lieu: int = 0
    so_dong_hong: int = 0


def _mau(h: _Hit, khoi: list[dict[str, int]]) -> str:
    """Một dòng dữ liệu mẫu để người soát X/Y có bị đảo không."""
    for hang in h.bang.hang[h.r + 1:]:
        c = khoi[0]
        try:
            return ", ".join(f"{t}={hang[c[t]]}" for t in BAT_BUOC if c[t] < len(hang))
        except IndexError:
            continue
    return "(không có dữ liệu)"


def _chia_khoi(h: _Hit) -> tuple[list[dict[str, int]], list[str]]:
    """Khối thứ k = cột thứ k của mỗi trường. Số cột phải đều nhau, không đoán."""
    n = len(h.cols["northing"])
    ghi_chu: list[str] = []
    cols = {t: cs for t, cs in h.cols.items()}
    for t in BAT_BUOC:
        if len(cols[t]) != n:
            raise LoiNguon(
                f"Số cột không đều giữa các khối điểm: "
                + ", ".join(f"{t2}×{len(cols[t2])}" for t2 in BAT_BUOC)
                + ". Sửa tiêu đề trong file hoặc khai ánh xạ rõ trong lot.yaml.")
    if "id" in cols and len(cols["id"]) != n:
        raise LoiNguon(f"Cột tên điểm xuất hiện {len(cols['id'])} lần nhưng có {n} khối điểm.")
    if "code" in cols and len(cols["code"]) != n:
        ghi_chu.append("cột ghi chú không đều giữa các khối — bỏ qua cột ghi chú")
        del cols["code"]
    return [{t: cs[k] for t, cs in cols.items()} for k in range(n)], ghi_chu


def _trich(h: _Hit, nhan: str, kq: KetQuaBang) -> None:
    khoi, ghi_chu = _chia_khoi(h)
    kq.so_khoi = len(khoi)
    for g in ghi_chu:
        kq.phat_hien.append(_phat_hien("", "cot_ghi_chu", "thong_tin", f"{nhan}: {g}"))

    hong: list[dict] = []
    chu: list[str] = []
    ids: dict[str, str] = {}
    id_trung: list[str] = []
    for r in range(h.r + 1, len(h.bang.hang)):
        hang = h.bang.hang[r]
        for k, c in enumerate(khoi):
            def o(t):
                i = c.get(t)
                return hang[i] if i is not None and i < len(hang) else None
            if all(_rong(o(t)) for t in BAT_BUOC):
                if any(not _rong(o(t)) for t in ("id", "code") if t in c):
                    kq.so_hang_khong_phai_du_lieu += 1      # dòng chữ: "Tổng", ghi chú...
                continue                                    # khối trống cuối bảng: bỏ qua im lặng
            vt = f"{h.bang.ten}!hàng {r + 1}" + (f" (khối {k + 1})" if len(khoi) > 1 else "")
            loi = []
            v: dict[str, float] = {}
            for t in BAT_BUOC:
                try:
                    x = doc_so(o(t))
                except ValueError as e:
                    loi.append(f"{t}: {e}")
                    continue
                if x is None:
                    loi.append(f"thiếu {t}")
                else:
                    v[t] = x
            if loi:
                if not v:
                    # Không ô nào là số: chú giải ("D = ĐỈNH TA LUY"), khối chữ ký...
                    # Không phải điểm đo hỏng. Vẫn liệt kê để người thấy lõi đã bỏ gì.
                    chu.append(vt)
                else:
                    hong.append({"vt": vt, "loi": "; ".join(loi)})
                continue
            ten = o("id")
            ten = _id_chuoi(ten) if not _rong(ten) else f"{nhan[:1].upper()}-H{r + 1}" + (
                f"-{k + 1}" if len(khoi) > 1 else "")
            if ten in ids:
                id_trung.append(f"{ten} ({ids[ten]} và {vt})")
            else:
                ids[ten] = vt
            code = o("code")
            kq.diem.append(Diem(ten, v["northing"], v["easting"], v["z"],
                                "" if _rong(code) else str(code).strip(), vt))

    kq.so_dong_hong = len(hong)
    kq.so_hang_khong_phai_du_lieu += len(chu)
    if chu:
        kq.phat_hien.append(_phat_hien(
            "", "dong_chu", "thong_tin",
            f"{nhan}: {len(chu)} dòng chỉ có chữ (chú giải, chữ ký) không phải điểm đo, "
            f"đã bỏ qua: {'; '.join(chu[:6])}{'…' if len(chu) > 6 else ''}"))
        if len(chu) / (len(kq.diem) + len(hong) + len(chu)) > TY_LE_HONG_CHAN:
            kq.phat_hien.append(_phat_hien(
                "", "dong_chu_nhieu", "chan",
                f"{nhan}: {len(chu)} dòng chữ — quá nhiều so với {len(kq.diem)} điểm, "
                "nhiều khả năng ánh xạ cột sai",
                lua_chon=["(a) soát lại ánh xạ cột", "(b) hỏi lại đơn vị khảo sát"],
                he_qua="phần lớn dòng dữ liệu bị bỏ qua"))
    tong = len(kq.diem) + len(hong)
    for x in hong[:TOI_DA_LIET_KE]:
        kq.phat_hien.append(_phat_hien(
            "", "dong_hong", "canh_bao",
            f"{nhan}: {x['vt']} — {x['loi']}. Đã bỏ qua dòng này.",
            lua_chon=["(a) đơn vị khảo sát sửa số liệu rồi nộp lại",
                      "(b) xác nhận bỏ điểm này"],
            he_qua="thiếu một đỉnh của TIN; vùng quanh điểm có thể thành vùng trống (RULES 8)"))
    if len(hong) > TOI_DA_LIET_KE:
        kq.phat_hien.append(_phat_hien(
            "", "dong_hong", "canh_bao",
            f"{nhan}: còn {len(hong) - TOI_DA_LIET_KE} dòng hỏng nữa chưa liệt kê "
            f"(tổng {len(hong)})."))
    if tong and len(hong) / tong > TY_LE_HONG_CHAN:
        kq.phat_hien.append(_phat_hien(
            "", "dong_hong_nhieu", "chan",
            f"{nhan}: {len(hong)}/{tong} dòng hỏng ({100 * len(hong) / tong:.1f} %) — "
            "nhiều khả năng ánh xạ cột sai hoặc file khác khuôn",
            lua_chon=["(a) soát lại ánh xạ cột", "(b) hỏi lại đơn vị khảo sát"],
            he_qua="phần lớn điểm bị bỏ, mọi số khối lượng sau đó vô nghĩa"))
    if id_trung:
        kq.phat_hien.append(_phat_hien(
            "", "id_trung", "canh_bao",
            f"{nhan}: {len(id_trung)} tên điểm bị lặp, vd {'; '.join(id_trung[:5])}",
            lua_chon=["(a) giữ cả hai — chỉ là đặt tên trùng",
                      "(b) hỏi lại đơn vị khảo sát"],
            he_qua="tra ngược điểm theo tên có thể ra nhầm điểm"))


# --------------------------------------------------------------------------- cổng vào
def doc_bang(lot: Lot, cau_hinh: dict, cfg: dict, nhan: str, *,
             xac_nhan: bool = False, ghi: bool = True) -> KetQuaBang:
    """Đọc một bề mặt từ Excel/CSV. `ghi=False` (xem trước): không lưu ánh xạ."""
    ten_file = cau_hinh.get("file")
    if not ten_file:
        raise LoiNguon(f"lot.yaml: be_mat_{nhan} dùng nguon={cau_hinh.get('nguon')} "
                       "nhưng chưa khai `file` (tên file trong 00_input/).")
    path = Path(ten_file) if Path(ten_file).is_absolute() else (
        (lot.input_dir / ten_file) if (lot.input_dir / ten_file).is_file() else (lot.root / ten_file).resolve()
    )
    if not path.is_file():
        raise LoiNguon(f"Không thấy {path}. Đặt file khảo sát vào 00_input/.")

    cac_bang = _cac_bang(path, cau_hinh.get("sheet"))
    khai = cau_hinh.get("anh_xa_cot") or cfg.get("anh_xa_cot_excel")
    moi = False

    if khai:                                            # 1) lot.yaml khai sẵn
        ten_cot = {t: {chuan_hoa(v)} for t, v in khai.items() if t in TRUONG and v}
        thieu = [t for t in BAT_BUOC if t not in ten_cot]
        if thieu:
            raise LoiNguon("lot.yaml: anh_xa_cot thiếu " + ", ".join(thieu))
        h = _tim(cac_bang, ten_cot)
        if h is None:
            raise LoiNguon(f"Không thấy tiêu đề khai trong lot.yaml "
                           f"({', '.join(f'{t}=«{v}»' for t, v in khai.items())}) "
                           f"trong {path.name}.\n" + _tieu_de_thay(cac_bang))
        nguon_ax = "lot.yaml"
    else:
        h, nguon_ax = None, ""
        for e in _nho_doc(lot):                         # 2) đã nhớ, khớp dấu vân tay
            cand = _tim(cac_bang, {t: {chuan_hoa(v)} for t, v in e["cot"].items()})
            if cand and dau_van_tay(cand) == e["dau_van_tay"]:
                h, nguon_ax = cand, f"{FILE_NHO} (đã xác nhận {e['xac_nhan_luc']})"
                break
        if h is None:                                   # 3) đề xuất rồi dừng
            h = _tim(cac_bang, DONG_NGHIA)
            if h is None:
                raise LoiNguon(f"Không nhận ra hàng tiêu đề điểm đo trong {path.name}. "
                               "Khai `anh_xa_cot` trong lot.yaml.\n" + _tieu_de_thay(cac_bang))
            if not xac_nhan:
                tc = _chu_goc(h)
                raise CanXacNhan(
                    f"Chưa có ánh xạ cột cho {path.name} (sheet {h.bang.ten}, "
                    f"hàng tiêu đề {h.r + 1}, {len(h.cols['northing'])} khối điểm/dòng).\n"
                    "Đề xuất từ tiêu đề:\n"
                    + "\n".join(f"  {t:9s} <- «{v}»" for t, v in tc.items())
                    + f"\nDòng mẫu: {_mau(h, _chia_khoi(h)[0])}\n"
                    "Soát kỹ northing/easting có bị đảo không (X là northing ~1.113.000).\n"
                    "Đúng thì chạy lại với --xac-nhan-anh-xa để ghi nhớ; "
                    "sai thì khai `anh_xa_cot` trong lot.yaml.")
            nguon_ax, moi = "đề xuất tự động, người xác nhận", True

    kq = KetQuaBang(file=path, hash_sha256=bam_sha256(path), sheet=h.bang.ten,
                    hang_tieu_de=h.r + 1, so_khoi=0, anh_xa=_chu_goc(h),
                    nguon_anh_xa=nguon_ax, dau_van_tay=dau_van_tay(h))
    _trich(h, nhan, kq)
    if moi and ghi:
        luu_anh_xa(lot, h, path.name)
    return kq
