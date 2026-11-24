"""MCP server CAD — phơi đúng 13 công cụ của SPEC mục 9.

    python -m sannen_cad.mcp_cad_server --backend dxf --vao ban_ve.dxf --ra ket_qua.dxf

Công cụ ghi mặc định `xem_truoc=true` (RULES 4): chỉ báo sẽ làm gì. Agent đặt `xem_truoc=false`
SAU KHI người duyệt. Không có công cụ nào ghi đè DXF đầu vào (RULES 3).
"""
from __future__ import annotations
import argparse
import json

from sannen import __version__
from sannen.mcp_stdio import CongCu, chay_may_chu, schema

from .backend import CONG_CU_GHI, TEN_CONG_CU, Backend

_P = lambda mo_ta, kieu="string", **kw: {"type": kieu, "description": mo_ta, **kw}
_LO = {"ma_lo": _P("mã lô, vd 01-CGP"), "dot": _P("đợt nghiệm thu", "integer"),
       "hash_tv": _P("hash truy vết của bộ đầu vào (volume.json.hash_dau_vao)")}
_XT = {"xem_truoc": _P("true (mặc định) = chỉ báo sẽ làm gì; false = ghi thật, sau khi người duyệt", "boolean")}
_MO_TA = {
    "cad_doc_info": ("Thông tin bản vẽ: layer, số đối tượng, các lô đã vẽ.", {}, []),
    "cad_read_points": ("Đọc các POINT trên một layer → [[E,N,Z]].", {"layer": _P("tên layer")}, ["layer"]),
    "cad_read_polylines": ("Đọc polyline trên một layer.", {"layer": _P("tên layer")}, ["layer"]),
    "cad_export_dxf": ("Xuất bản vẽ ra DXF (đường dẫn KHÁC file đầu vào).", {"duong_dan": _P("đường dẫn .dxf")}, ["duong_dan"]),
    "cad_read_grid_z": ("Đọc ngược cao độ đỉnh từ NHÃN trong bản vẽ (người có thể đã sửa tay) — dùng cho luoi --resync.",
                        {"ma_lo": _P("mã lô"), "dot": _P("đợt", "integer")}, ["ma_lo"]),
    "cad_purge_sn": ("Xóa sạch đối tượng kết quả CŨ của đúng lô này (RULES 5). Gọi trước mọi lần vẽ lại.",
                     {"ma_lo": _P("mã lô"), "dot": _P("đợt (bỏ trống = mọi đợt)", "integer"), **_XT}, ["ma_lo"]),
    "cad_draw_grid": ("Vẽ lưới ô vuông lên SN-LUOI từ grid.json.tham_so.",
                      {**_LO, "luoi": _P("grid.json.tham_so: goc_luoi, goc_xoay_do, cot_m, hang_m", "object"), **_XT},
                      ["ma_lo", "dot", "hash_tv", "luoi"]),
    "cad_set_vertex_z": ("Đặt/cập nhật nhãn cao độ mốc, đo, chênh cao tại các đỉnh (SN-LUOI-NHAN).",
                         {**_LO, "nut": _P("[{ma,e,n,z_moc,z_do}]", "array"), **_XT}, ["ma_lo", "dot", "hash_tv", "nut"]),
    "cad_label_cells": ("Ghi khối lượng đào/đắp từng ô (SN-LUOI-O).",
                        {**_LO, "o": _P("[{ma,e,n,kl_dao_m3,kl_dap_m3,thieu_du_lieu}]", "array"), **_XT},
                        ["ma_lo", "dot", "hash_tv", "o"]),
    "cad_draw_cutfill_line": ("Vẽ ranh giới đào–đắp (SN-RANH-DAODAP).",
                              {**_LO, "doan": _P("[[[E,N],[E,N]],...]", "array"), **_XT}, ["ma_lo", "dot", "hash_tv", "doan"]),
    "cad_draw_3dface": ("Vẽ mặt 3D (SN-3DF-MOC/DO; loai=qc thì lên SN-QC). dang=polyface: MỘT đối tượng polyface mỗi "
                        "bề mặt (≤ 30000 đỉnh/khối, vượt thì chia khối liên tiếp); dang=3dface (mặc định): 3DFACE rời.",
                        {**_LO, "be_mat": _P("moc | do", enum=["moc", "do"]), "tam_giac": _P("[[[E,N,Z]*3],...]", "array"),
                         "loai": _P("mat | qc", enum=["mat", "qc"]),
                         "dang": _P("polyface | 3dface (mặc định)", enum=["polyface", "3dface"]), **_XT},
                        ["ma_lo", "dot", "hash_tv", "be_mat", "tam_giac"]),
    "cad_draw_table": ("Vẽ bảng in khối lượng (SN-BANG) từ 20_output/bang_in_cad.json.",
                       {**_LO, "bang": _P("nội dung bang_in_cad.json", "object"), "goc_ve": _P("[E,N] góc trên-trái", "array"),
                        "chieu_cao_chu": _P("chiều cao chữ (đơn vị bản vẽ)", "number"), **_XT},
                       ["ma_lo", "dot", "hash_tv", "bang", "goc_ve"]),
    "cad_zoom_to": ("Phóng tới một vị trí VN-2000 (soi điểm cảnh báo).",
                    {"e": _P("E", "number"), "n": _P("N", "number"), "kich_thuoc": _P("chiều cao khung nhìn", "number")},
                    ["e", "n"]),
}


def tao_cong_cu(be: Backend) -> list[CongCu]:
    ra = []
    for ten in TEN_CONG_CU:
        mo_ta, tp, bb = _MO_TA[ten]

        def ham(args: dict, ten=ten):
            a = dict(args)
            if ten in CONG_CU_GHI:
                a.setdefault("xem_truoc", True)               # RULES 4
            return json.dumps(getattr(be, ten)(**a), ensure_ascii=False, indent=1), False
        ra.append(CongCu(ten, mo_ta + (" [GHI — cần duyệt]" if ten in CONG_CU_GHI else ""), schema(tp, bb), ham))
    return ra


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="sannen_cad.mcp_cad_server")
    ap.add_argument("--backend", choices=("dxf", "com"), default="dxf")
    ap.add_argument("--vao", help="DXF bản vẽ nhà thầu (chỉ đọc)")
    ap.add_argument("--ra", help="DXF kết quả")
    a = ap.parse_args(argv)
    if a.backend == "com":
        from .backend_com import BackendCOM
        BackendCOM()                                            # báo rõ chưa cài
    from .backend_dxf import BackendDXF
    if not a.vao or not a.ra:
        ap.error("backend dxf cần --vao và --ra")
    chay_may_chu("sannen-cad", __version__, tao_cong_cu(BackendDXF(a.vao, a.ra)))


if __name__ == "__main__":
    main()
