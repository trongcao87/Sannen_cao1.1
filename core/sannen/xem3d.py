"""xem3d — trình xem 3D hai bề mặt TIN (Mốc / Đo) thành MỘT file HTML tự chứa.

Để QS kiểm tra trực quan trước khi duyệt cổng: xoay, phóng đại Z, tô đào/đắp, bật/tắt biên lô,
ranh đào–đắp, lưới ô. Không đụng 00_input; không dùng thư viện ngoài, mở offline được.

Đọc từ 10_process/: surface_moc.json, surface_do.json (bắt buộc) · lo.json, grid.json,
volume.json (có thì vẽ thêm biên lô, lưới ô, ranh đào–đắp). Toạ độ được dời về trọng tâm
trước khi nhúng (RULES/CLAUDE.md: số nhỏ, không mất chữ số có nghĩa).

Deterministic: cùng đầu vào cho cùng byte HTML — không nhúng thời gian.
"""
from __future__ import annotations
import html
import json
import os
from pathlib import Path

from . import io_out
from .paths import Lot
from .tin import Tin
from .xem3d_mau import MAU_HTML

TEN_FILE = "tin3d_view.html"


class ThieuBeMat(Exception):
    """Chưa có bề mặt TIN để xem — phải chạy `mat` trước."""


def _r(v: float, d: int = 3) -> float:
    r = round(v, d)
    return 0.0 if r == 0 else r          # tránh "-0.0"


def _doc_be_mat(lot: Lot, ten: str, nhan: str) -> dict:
    p = lot.process_dir / ten
    if not p.exists():
        raise ThieuBeMat(
            f"Chưa có {ten} trong 10_process/ (bề mặt {nhan}). Chạy `mat` trước:\n"
            f"  python -m sannen.cli mat --lot {lot.root} --be-mat ca-hai")
    return io_out.doc_json(p)


def _doc_tuy_chon(lot: Lot, ten: str) -> dict | None:
    p = lot.process_dir / ten
    return io_out.doc_json(p) if p.exists() else None


def _vong(v) -> list:
    """Một vòng biên: chấp nhận {'vong': [[e,n],...]} hoặc danh sách điểm trần."""
    if isinstance(v, dict):
        v = v.get("vong") or v.get("dinh") or []
    return [p for p in v if len(p) >= 2]


def _du_lieu(lot: Lot, cfg: dict | None, phong_dai_z: float, cho_phep_mot_mat: bool = False) -> dict:
    p_moc = lot.process_dir / "surface_moc.json"
    p_do = lot.process_dir / "surface_do.json"
    if not p_moc.exists() and not p_do.exists():
        raise ThieuBeMat(
            "Chưa có surface_moc.json / surface_do.json trong 10_process/. Chạy `mat` trước:\n"
            f"  python -m sannen.cli mat --lot {lot.root} --be-mat ca-hai")
    if not cho_phep_mot_mat:
        d_moc = _doc_be_mat(lot, "surface_moc.json", "mốc")
        d_do = _doc_be_mat(lot, "surface_do.json", "đo")
    else:
        d_moc = io_out.doc_json(p_moc) if p_moc.exists() else {"goc": [0.0, 0.0], "diem": [], "tam_giac": [], "loai_tam_giac": []}
        d_do = io_out.doc_json(p_do) if p_do.exists() else {"goc": d_moc["goc"], "diem": [], "tam_giac": [], "loai_tam_giac": []}
        if not p_moc.exists():
            d_moc["goc"] = d_do["goc"]
    moc = Tin.from_dict(d_moc) if d_moc["diem"] else None
    do = Tin.from_dict(d_do) if d_do["diem"] else None

    pts = list(d_moc["diem"]) + list(d_do["diem"])
    if not pts:
        raise ThieuBeMat("Bề mặt không có điểm nào — xem lại `mat`.")
    e0 = _r(sum(p[0] for p in pts) / len(pts))
    n0 = _r(sum(p[1] for p in pts) / len(pts))

    def be_mat(d: dict, dz: list | None = None) -> dict:
        out = {"p": [[_r(e - e0), _r(n - n0), _r(z)] for e, n, z in d["diem"]],
               "t": [list(t) for t in d["tam_giac"]],
               "l": list(d.get("loai_tam_giac") or [0] * len(d["tam_giac"]))}
        if dz is not None:
            out["dz"] = dz
        return out

    # Δz tại từng đỉnh bề mặt Đo = z_đo − z_mốc nội suy (null nếu đỉnh ngoài TIN mốc)
    dz = []
    for e, n, z in d_do["diem"]:
        zm = moc.z_tai(e, n) if moc else None
        dz.append(None if zm is None else _r(z - zm, 4))

    def diem_phu(e: float, n: float) -> list:
        zm = moc.z_tai(e, n) if moc else None
        zd = do.z_tai(e, n) if do else None
        return [_r(e - e0), _r(n - n0), None if zm is None else _r(zm), None if zd is None else _r(zd)]

    bien, loai_tru = [], []
    lo = _doc_tuy_chon(lot, "lo.json")
    if lo:
        for v in lo.get("bien_lo", []):
            ring = _vong(v)
            if len(ring) >= 3:
                bien.append([diem_phu(*p[:2]) for p in ring] )
        for v in lo.get("loai_tru", []):
            ring = _vong(v)
            if len(ring) >= 3:
                loai_tru.append([diem_phu(*p[:2]) for p in ring])

    luoi = []
    gr = _doc_tuy_chon(lot, "grid.json")
    if gr:
        nut = gr.get("nut", {})
        da = set()
        for o in gr.get("o", []):
            ids = o.get("nut", [])
            for a, b in zip(ids, ids[1:] + ids[:1]):
                k = tuple(sorted((a, b)))
                if a in nut and b in nut and k not in da:
                    da.add(k)
                    luoi.append([diem_phu(nut[a]["e"], nut[a]["n"]), diem_phu(nut[b]["e"], nut[b]["n"])])

    ranh = []
    vol = _doc_tuy_chon(lot, "volume.json")
    if vol:
        for seg in vol.get("ranh_dao_dap", []):
            if len(seg) >= 2:
                ranh.append([diem_phu(*seg[0][:2]), diem_phu(*seg[1][:2])])

    sinh = (d_moc.get("sinh_tu") or {}).get("hash_dau_vao") or ""
    return {
        "ma_lo": str((cfg or {}).get("ma_lo", lot.root.name)),
        "dot": (cfg or {}).get("dot", ""),
        "hash": sinh[:8],
        "phong_dai_z": float(phong_dai_z),
        "goc": [e0, n0],
        "moc": be_mat(d_moc),
        "do": be_mat(d_do, dz),
        "bien": bien, "loai_tru": loai_tru, "ranh": ranh, "luoi": luoi,
    }


def tao_html(lot_root, ra=None, phong_dai_z: float = 2.0, cfg: dict | None = None,
             cho_phep_mot_mat: bool = False) -> Path:
    """Sinh trình xem 3D. Mặc định ghi `20_output/tin3d_view.html` của lô; trả về đường dẫn file."""
    lot = Lot(Path(lot_root).expanduser().resolve())
    if cfg is None:
        try:
            from .config import doc_lot
            cfg = doc_lot(lot.lot_yaml)
        except Exception:                # lot.yaml thiếu/lỗi không cản việc xem
            cfg = None
    du_lieu = _du_lieu(lot, cfg, max(1.0, min(10.0, float(phong_dai_z))), cho_phep_mot_mat=cho_phep_mot_mat)
    js = json.dumps(du_lieu, ensure_ascii=False, separators=(",", ":"))
    js = js.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    noi_dung = (MAU_HTML.replace("__TIEU_DE__", html.escape(du_lieu["ma_lo"]))
                .replace("__DU_LIEU__", js))

    dich = Path(ra).expanduser() if ra else lot.output_dir / TEN_FILE
    dich = dich if dich.is_absolute() else Path.cwd() / dich
    lot.guard_write(dich)
    dich.parent.mkdir(parents=True, exist_ok=True)
    tam = dich.with_name(dich.name + ".tmp")
    tam.write_bytes(noi_dung.encode("utf-8"))      # ghi byte: không phụ thuộc kiểu xuống dòng của máy
    os.replace(tam, dich)
    return dich


def chay(lot: Lot, cfg: dict, ra: Path | None, phong_dai_z: float, mo: bool) -> int:
    """Verb CLI `xem3d`."""
    p = tao_html(lot.root, ra, phong_dai_z, cfg, cho_phep_mot_mat=mo)
    print(f"Đã tạo trình xem 3D: {p}")
    if mo:
        try:
            os.startfile(str(p))                      # type: ignore[attr-defined]
        except AttributeError:
            import webbrowser
            webbrowser.open(p.as_uri())
    return 0
