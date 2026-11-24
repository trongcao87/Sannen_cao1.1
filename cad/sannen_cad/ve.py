"""Bộ điều phối: vẽ kết quả của một lô vào bản vẽ qua giao diện 13 công cụ.

    python -m sannen_cad.ve --lot <thư mục lô> --vao <dxf nhà thầu> --ra <dxf kết quả> [--preview] [--lop luoi,nhan,...]

Luôn theo thứ tự: purge kết quả cũ CỦA CHÍNH LÔ NÀY, đúng nhóm sắp vẽ (RULES 5) → lưới → nhãn đỉnh → nhãn ô →
ranh đào–đắp → mặt 3D hai bề mặt → bảng in. Chạy hai lần cho số đối tượng y hệt nhau.
`lop` cho vẽ lại TỪNG PHẦN (menu CAD): tập con của luoi, nhan, o, ranh, 3d, bang. Mặt cắt (mat_cat) không bao giờ bị
vẽ lại toàn bộ xóa mất — chúng chỉ bị xóa bởi lệnh mặt cắt cùng tên.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import yaml

from .backend import NHOM_LOP, Backend

TAT_CA = ("luoi", "nhan", "o", "ranh", "3d", "bang")


def _doc(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def ngu_canh(lot_root: str | Path) -> dict:
    """Mã lô, đợt, hash truy vết và các file kết quả cần cho việc vẽ."""
    from sannen.paths import Lot
    lot = Lot(Path(lot_root).resolve())
    ps = lot.process_dir
    for ten in ("grid.json", "volume.json"):
        if not (ps / ten).exists():
            raise FileNotFoundError(f"Chưa có {ten} — chạy luoi và tinh trước")
    cfg = yaml.safe_load(lot.lot_yaml.read_text(encoding="utf-8"))
    vol = _doc(ps / "volume.json")
    return {"lot": lot, "ps": ps, "ma_lo": str(cfg["ma_lo"]), "dot": int(cfg["dot"]),
            "grid": _doc(ps / "grid.json"), "vol": vol, "hash_tv": str(vol["hash_dau_vao"])[:16]}


def ve_mat_3d(be: Backend, nc: dict, nhan_list: list[str], xem_truoc: bool = False, dang: str = "3dface") -> dict:
    """Vẽ mặt 3D (SN-3DF-MOC/DO) và tam giác thiếu dữ liệu (SN-QC) của các bề mặt chọn.
    `dang="polyface"`: mỗi bề mặt MỘT polyface (menu CAD); `"3dface"`: 3DFACE rời (lối cũ, mặc định ở lõi)."""
    kq: dict[str, dict] = {}
    for nhan in nhan_list:
        s = _doc(nc["ps"] / f"surface_{nhan}.json")
        d, loai = s["diem"], s.get("loai_tam_giac") or [0] * len(s["tam_giac"])
        tot = [[d[a], d[b], d[c]] for (a, b, c), l in zip(s["tam_giac"], loai) if l == 0]
        xau = [[d[a], d[b], d[c]] for (a, b, c), l in zip(s["tam_giac"], loai) if l != 0]
        kq[f"mat_{nhan}"] = be.cad_draw_3dface(nc["ma_lo"], nc["dot"], nc["hash_tv"], nhan, tot, "mat", xem_truoc=xem_truoc, dang=dang)
        if xau:
            kq[f"qc_{nhan}"] = be.cad_draw_3dface(nc["ma_lo"], nc["dot"], nc["hash_tv"], nhan, xau, "qc", xem_truoc=xem_truoc, dang=dang)
    return kq


def ve_ket_qua(be: Backend, lot_root: str | Path, *, xem_truoc: bool = False, ve_3d: bool = True,
               lop: list[str] | tuple[str, ...] | None = None, dang: str = "3dface") -> dict:
    from sannen.luoi import doc_hieu_chinh, nut_hieu_luc
    chon = list(TAT_CA) if lop is None else list(lop)
    xau = set(chon) - set(TAT_CA)
    if xau:
        raise ValueError(f"Nhóm vẽ lạ: {', '.join(sorted(xau))} (có: {', '.join(TAT_CA)})")
    if lop is None and not ve_3d:
        chon.remove("3d")
    nc = ngu_canh(lot_root)
    lot, ps, ma_lo, dot, grid, vol, hash_tv = (nc[k] for k in ("lot", "ps", "ma_lo", "dot", "grid", "vol", "hash_tv"))
    kq: dict[str, dict] = {}

    loai = tuple(x for g in chon for x in NHOM_LOP[g])
    kq["purge"] = be.cad_purge_sn(ma_lo, dot, xem_truoc=xem_truoc, loai=loai)
    if "luoi" in chon:
        kq["luoi"] = be.cad_draw_grid(ma_lo, dot, hash_tv, grid["tham_so"], xem_truoc=xem_truoc)
    if "nhan" in chon:
        hieu_luc = nut_hieu_luc(grid, doc_hieu_chinh(lot))        # cao độ đỉnh = grid_adjusted, KHÔNG phải nhãn cũ
        nut = [{"ma": m, "e": n["e"], "n": n["n"], "z_moc": hieu_luc[m]["z_moc"], "z_do": hieu_luc[m]["z_do"]}
               for m, n in grid["nut"].items() if hieu_luc[m]["z_moc"] is not None and hieu_luc[m]["z_do"] is not None]
        kq["nhan_dinh"] = be.cad_set_vertex_z(ma_lo, dot, hash_tv, nut, xem_truoc=xem_truoc)
    if "o" in chon:
        vo = {o["ma"]: o for o in vol["o"]}
        o_list = []
        for o in grid["o"]:
            ns = [grid["nut"][m] for m in o["nut"]]
            v = vo[o["ma"]]
            o_list.append({"ma": o["ma"], "e": sum(n["e"] for n in ns) / 4, "n": sum(n["n"] for n in ns) / 4,
                           "kl_dao_m3": v["kl_dao_m3"], "kl_dap_m3": v["kl_dap_m3"],
                           "thieu_du_lieu": v["thieu_du_lieu"]})
        kq["nhan_o"] = be.cad_label_cells(ma_lo, dot, hash_tv, o_list, xem_truoc=xem_truoc)
    if "ranh" in chon:
        kq["ranh"] = be.cad_draw_cutfill_line(ma_lo, dot, hash_tv, vol.get("ranh_dao_dap", []), xem_truoc=xem_truoc)
    if "3d" in chon:
        kq.update(ve_mat_3d(be, nc, ["moc", "do"], xem_truoc, dang))
    if "bang" in chon:
        bang_p = lot.output_dir / "bang_in_cad.json"
        if bang_p.exists():
            hb = _doc(ps / "lo.json")["hop_bao"]
            kq["bang"] = be.cad_draw_table(ma_lo, dot, hash_tv, _doc(bang_p), [hb[0], hb[1] - 20.0], xem_truoc=xem_truoc)
        else:
            kq["bang"] = {"bo_qua": "chưa có 20_output/bang_in_cad.json — chạy `xuat` trước"}
    return kq


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sannen_cad.ve")
    ap.add_argument("--lot", required=True, type=Path)
    ap.add_argument("--vao", required=True, type=Path, help="DXF bản vẽ nhà thầu (chỉ đọc)")
    ap.add_argument("--ra", required=True, type=Path, help="DXF kết quả (khác --vao)")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--khong-3d", action="store_true")
    ap.add_argument("--lop", help="vẽ lại riêng các nhóm: " + ",".join(TAT_CA))
    ap.add_argument("--dang", choices=("polyface", "3dface"), default="3dface", help="dạng mặt 3D (mặc định 3dface rời)")
    a = ap.parse_args(argv)
    from .backend_dxf import BackendDXF
    be = BackendDXF(a.vao, a.ra)
    kq = ve_ket_qua(be, a.lot, xem_truoc=a.preview, ve_3d=not a.khong_3d,
                    lop=[x.strip() for x in a.lop.split(",") if x.strip()] if a.lop else None, dang=a.dang)
    for k, v in kq.items():
        so = {x: y for x, y in v.items() if x.startswith("so_")}
        print(f"{k:10s} {so or v}")
    print("XEM TRƯỚC — chưa ghi gì." if a.preview else f"Đã ghi {a.ra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
