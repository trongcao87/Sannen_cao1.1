"""MCP server của lõi (giai đoạn 7) — bọc CLI, cưỡng chế BA CỔNG duyệt.

    python -m sannen.mcp_server        (hoặc lệnh `sannen-mcp`)

Agent KHÔNG tính số: mỗi công cụ chỉ gọi đúng một verb của CLI rồi trả văn bản kèm mã thoát.
Server làm thêm đúng một việc mà một agent hay quên: **không cho lệnh ghi chạy khi người
chưa duyệt cổng tương ứng**, hoặc khi dữ liệu đã đổi kể từ lúc duyệt.

    Cổng 1 (dữ liệu)  sau nhap          → mở khóa  mat, lo
    Cổng 2 (bề mặt)   sau mat + lo      → mở khóa  luoi, hieuchinh, tinh
    Cổng 3 (số liệu)  sau tinh          → mở khóa  xuat

Chế độ xem trước (preview) luôn được chạy — RULES 4. Duyệt cổng ghi vào 90_log/cong.json
kèm "dấu vân tay" kết quả đã duyệt; kết quả đổi thì phê duyệt tự mất hiệu lực.
"""
from __future__ import annotations
import contextlib
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path

from . import __version__, cli, io_out
from .mcp_stdio import CongCu, chay_may_chu, schema
from .paths import Lot

# Logic cổng sống ở `cong.py` (CLI chặn ở đó). Tên cũ giữ lại ở đây cho mã đã import từ mcp_server.
from .cong import (CONG_CAN, DAU_VAN_TAY, QC_CONG, TEN_CONG, cong_da_duyet, dau_van_tay,  # noqa: F401,E402
                   doc_cong, duyet_cong, kiem_cong, thong_bao_tu_choi, viec_chan)
from .cong import lot_tu_args as _lot  # noqa: E402


def _chay_cli(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            ma = cli.main(argv)
        except SystemExit as e:                              # argparse báo lỗi tham số
            ma = int(e.code or 2)
    return ma, buf.getvalue()


def _tra(ma: int, ra: str, them: str = "") -> tuple[str, bool]:
    y = {0: "xong", 1: "xong, CÒN VIỆC CHẶN — đọc viec_can_lam", 2: "DỪNG — khai báo/đầu vào sai hoặc cần người xác nhận",
         3: "verb chưa cài"}.get(ma, "")
    return f"[mã thoát {ma}: {y}]\n{ra}{them}", ma >= 2


def goi_verb(verb: str, args: dict) -> tuple[str, bool]:
    lot = _lot(args)
    preview = args.get("preview", True)                     # RULES 4: mặc định xem trước
    ok, ly_do = kiem_cong(lot, verb, preview)          # từ chối sớm cho nhanh; CLI cũng chặn ở cùng chỗ (cong.py)
    if not ok:
        return thong_bao_tu_choi(verb, ly_do), True
    argv = [verb, "--lot", str(lot.root)]
    if preview:
        argv.append("--preview")
    if verb == "nhap" and args.get("xac_nhan_anh_xa"):
        argv.append("--xac-nhan-anh-xa")
    if verb == "mat" and args.get("be_mat"):
        argv += ["--be-mat", args["be_mat"]]
    if verb == "luoi":
        for k, c in (("o", "--o"), ("goc", "--goc"), ("goc_luoi", "--goc-luoi"), ("ngoai_suy", "--ngoai-suy")):
            if args.get(k) is not None:
                argv += [c, str(args[k])]
    if verb == "hieuchinh":
        if args.get("bo"):
            argv += ["--bo", args["bo"]]
        else:
            argv += ["--dinh", args["dinh"], "--z", str(args["z"]), "--be-mat-hc", args.get("be_mat", "do")]
            if args.get("ly_do"):
                argv += ["--ly-do", args["ly_do"]]
    if verb == "tinh" and args.get("sweep"):
        argv.append("--sweep")
    ma, ra = _chay_cli(argv)
    nhac = ""
    if not preview and ma in (0, 1):
        nhac = {"nhap": "\n→ Trình viec_can_lam.md cho người. Chờ người duyệt CỔNG 1 trước khi chạy mat/lo.",
                "lo": "\n→ Khi cả mat và lo xong: trình viec_can_lam.md, chờ người duyệt CỔNG 2.",
                "mat": "\n→ Khi cả mat và lo xong: trình viec_can_lam.md, chờ người duyệt CỔNG 2.",
                "tinh": "\n→ Trình kết quả và viec_can_lam.md, chờ người duyệt CỔNG 3 trước khi xuat."}.get(verb, "")
    return _tra(ma, ra, nhac)


def ghi_quyet_dinh(args: dict) -> tuple[str, bool]:
    lot = _lot(args)
    if not args.get("ma_viec") or not args.get("lua_chon"):
        return "Cần ma_viec (vd V-01) và lua_chon (vd a).", True
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · {args['ma_viec']} → {args['lua_chon']}"
                f"{' — ' + args['ghi_chu'] if args.get('ghi_chu') else ''}\n")
    return f"Đã ghi quyết định {args['ma_viec']} → {args['lua_chon']}.", False


def trang_thai(args: dict) -> tuple[str, bool]:
    lot = _lot(args)
    ps = lot.process_dir
    co = lambda *ten: all((ps / t).exists() for t in ten)
    buoc = {"nhap": co("points_moc.csv", "qc_input.json"), "mat": co("surface_moc.json", "surface_do.json"),
            "lo": co("lo.json"), "luoi": co("grid.json"), "tinh": co("volume.json"),
            "xuat": (lot.output_dir / "phieu_truy_vet.json").exists()}
    cong = {}
    for n in (1, 2, 3):
        ok, ly = cong_da_duyet(lot, n)
        cong[str(n)] = {"da_duyet": ok, "ly_do_chua": "" if ok else ly, "viec_chan": len(viec_chan(lot, n))}
    tiep = next((v for v in ("nhap", "mat", "lo", "luoi", "tinh", "xuat") if not buoc[v]), None)
    out = {"lot": lot.root.name, "buoc_da_chay": buoc, "cong": cong, "buoc_ke_tiep": tiep,
           "so_hieu_chinh": len(json.loads((ps / "grid_adjusted.json").read_text(encoding="utf-8"))["ghi_de"])
           if (ps / "grid_adjusted.json").exists() else 0}
    if buoc["tinh"]:
        v = io_out.doc_json(ps / "volume.json")
        out["so_nop"] = {k: v["so_nop"][k] for k in ("dao_m3", "dap_m3", "rong_m3")}
        out["so_kiem"] = {k: v["so_kiem"][k] for k in ("dao_m3", "dap_m3", "rong_m3")}
    return json.dumps(out, ensure_ascii=False, indent=1), False


def doc_viec(args: dict) -> tuple[str, bool]:
    lot = _lot(args)
    p = lot.process_dir / "viec_can_lam.md"
    return (p.read_text(encoding="utf-8"), False) if p.exists() else ("Chưa có viec_can_lam.md.", False)


def _p(mo_ta, kieu="string", **kw):
    return {"type": kieu, "description": mo_ta, **kw}


LOT = _p("Đường dẫn thư mục lô (có lot.yaml)")
PREVIEW = _p("true (mặc định) = chỉ xem trước, không ghi. false = ghi thật; cần cổng đã duyệt.", "boolean")


def danh_sach_cong_cu() -> list[CongCu]:
    verb = lambda v, mo_ta, them=None, bb=None: CongCu(
        f"sannen_{v}", mo_ta, schema({"lot": LOT, "preview": PREVIEW, **(them or {})}, ["lot"] + (bb or [])),
        lambda a, v=v: goi_verb(v, a))
    return [
        CongCu("sannen_trang_thai", "Tình trạng một lô: bước đã chạy, ba cổng đã duyệt chưa, bước kế tiếp, "
               "số nộp/số kiểm nếu có. Gọi ĐẦU TIÊN mỗi phiên.", schema({"lot": LOT}, ["lot"]), trang_thai),
        CongCu("sannen_doc_viec", "Đọc 10_process/viec_can_lam.md — các việc người phải quyết ở cổng hiện tại.",
               schema({"lot": LOT}, ["lot"]), doc_viec),
        verb("nhap", "Đọc DXF/Excel/CSV, chuẩn hóa điểm, chạy các phép kiểm dữ liệu. File Excel mới: lõi đề xuất ánh xạ "
             "cột rồi DỪNG (mã 2) — đưa đề xuất cho người xem rồi mới dùng xac_nhan_anh_xa=true.",
             {"xac_nhan_anh_xa": _p("CHỈ khi NGƯỜI đã xem và đồng ý ánh xạ cột đề xuất", "boolean")}),
        verb("mat", "Dựng TIN có ràng buộc đứt gãy cho hai bề mặt, QC tam giác. Cần cổng 1.",
             {"be_mat": _p("moc | do | ca-hai", enum=["moc", "do", "ca-hai"])}),
        verb("lo", "Chuẩn hóa biên lô và vùng loại trừ, đối chiếu AREA. Cần cổng 1."),
        verb("luoi", "Đặt lưới ô vuông, nội suy cao độ đỉnh. Cần cổng 2. Kích thước ô/góc/gốc theo hồ sơ, KHÔNG tự chọn.",
             {"o": _p("kích thước ô (m)", "number"), "goc": _p("góc xoay độ hoặc 'auto'"),
              "goc_luoi": _p("gốc lưới 'E,N' VN-2000"),
              "ngoai_suy": _p("CHỈ khi NGƯỜI đã chấp nhận: ngoại suy cao độ đỉnh ngoài vùng đo ≤ M mét (mặc định 0 = cấm, RULES 8)", "number")}),
        verb("hieuchinh", "Áp cao độ một đỉnh lưới do NGƯỜI chỉ định (tự tính lại chênh cao). Cần cổng 2.",
             {"dinh": _p("mã đỉnh, vd D03-05"), "z": _p("cao độ mới (m)", "number"),
              "be_mat": _p("moc | do (mặc định do)", enum=["moc", "do"]),
              "ly_do": _p("lý do (ghi vào decisions.md)"), "bo": _p("mã đỉnh cần bỏ hiệu chỉnh")}),
        verb("tinh", "Tính khối lượng theo lưới (số nộp) và lăng trụ (số kiểm); sweep=true quét ma trận phương án. "
             "Cần cổng 2.", {"sweep": _p("quét ma trận phương án A/B", "boolean")}),
        verb("xuat", "Xuất workbook 7 sheet, bảng in CAD, phiếu truy vết, thuyết minh. Cần cổng 3."),
        CongCu("sannen_duyet_cong",
               "GHI NHẬN NGƯỜI đã duyệt một cổng. CHỈ gọi sau khi người nói rõ đồng ý; bang_chung phải là "
               "nguyên văn câu của người. Agent không được tự duyệt.",
               schema({"lot": LOT, "cong": _p("1, 2 hoặc 3", "integer", enum=[1, 2, 3]),
                       "nguoi_duyet": _p("tên người duyệt"), "bang_chung": _p("trích nguyên văn câu người đồng ý"),
                       "ghi_chu": _p("tuỳ chọn")}, ["lot", "cong", "nguoi_duyet", "bang_chung"]), duyet_cong),
        CongCu("sannen_ghi_quyet_dinh", "Ghi câu trả lời của người cho một việc (vd V-01 → a) vào 90_log/decisions.md.",
               schema({"lot": LOT, "ma_viec": _p("vd V-01"), "lua_chon": _p("vd a"), "ghi_chu": _p("tuỳ chọn")},
                      ["lot", "ma_viec", "lua_chon"]), ghi_quyet_dinh),
    ]


def main() -> None:
    chay_may_chu("sannen-core", __version__, danh_sach_cong_cu())


if __name__ == "__main__":
    main()
