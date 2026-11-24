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

# verb ghi -> cổng phải được duyệt trước
CONG_CAN = {"mat": 1, "lo": 1, "luoi": 2, "hieuchinh": 2, "tinh": 2, "xuat": 3}
TEN_CONG = {1: "Cổng 1 — dữ liệu (sau nhap)", 2: "Cổng 2 — bề mặt (sau mat + lo)",
            3: "Cổng 3 — số liệu (sau tinh)"}
# file kết quả làm "dấu vân tay" của từng cổng, và file QC phải sạch việc chặn
DAU_VAN_TAY = {1: ["qc_input.json", "points_moc.csv", "points_do.csv", "boundary.geojson"],
               2: ["surface_moc.json", "surface_do.json", "lo.json"],
               3: ["volume.json"]}
QC_CONG = {1: ["qc_input.json"], 2: ["qc_surface.json", "qc_lo.json"], 3: ["qc_luoi.json", "qc_volume.json"]}


def _lot(args: dict) -> Lot:
    p = Path(args["lot"]).expanduser().resolve()
    if not (p / "lot.yaml").is_file():
        raise ValueError(f"{p} không phải thư mục lô (thiếu lot.yaml)")
    return Lot(p)


def dau_van_tay(lot: Lot, cong: int) -> str | None:
    h = hashlib.sha256()
    for ten in DAU_VAN_TAY[cong]:
        p = lot.process_dir / ten
        if not p.exists():
            return None
        h.update(ten.encode()); h.update(p.read_bytes())
    if cong == 3 and (lot.process_dir / "grid_adjusted.json").exists():
        h.update((lot.process_dir / "grid_adjusted.json").read_bytes())
    return h.hexdigest()


def doc_cong(lot: Lot) -> dict:
    p = lot.log_dir / "cong.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def viec_chan(lot: Lot, cong: int) -> list[str]:
    ra = []
    for ten in QC_CONG[cong]:
        p = lot.process_dir / ten
        if p.exists():
            ra += [f"{f.get('ma')}: {f.get('mo_ta')}" for f in io_out.doc_json(p).get("phat_hien", [])
                   if f.get("muc") == "chan"]
    return ra


def cong_da_duyet(lot: Lot, cong: int) -> tuple[bool, str]:
    d = doc_cong(lot).get(str(cong))
    if not d or not d.get("duyet"):
        return False, f"{TEN_CONG[cong]} CHƯA được người duyệt"
    if d.get("dau_van_tay") != dau_van_tay(lot, cong):
        return False, (f"{TEN_CONG[cong]} đã duyệt lúc {d['luc']} nhưng kết quả đã thay đổi kể từ đó "
                       "— phê duyệt mất hiệu lực, cần người duyệt lại")
    return True, ""


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
    cong = CONG_CAN.get(verb)
    if cong and not preview:
        ok, ly_do = cong_da_duyet(lot, cong)
        if not ok:
            return (f"TỪ CHỐI ghi `{verb}`: {ly_do}.\nQuy trình: chạy verb với preview, trình "
                    f"viec_can_lam.md cho người, chờ người nói rõ duyệt, rồi gọi sannen_duyet_cong({cong}).\n"
                    "Bạn có thể chạy `preview=true` để xem trước mà không cần duyệt."), True
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


def duyet_cong(args: dict) -> tuple[str, bool]:
    lot = _lot(args)
    cong = int(args["cong"])
    if cong not in (1, 2, 3):
        return "cong phải là 1, 2 hoặc 3", True
    if not args.get("nguoi_duyet") or not args.get("bang_chung"):
        return ("Phải ghi `nguoi_duyet` và `bang_chung` (trích NGUYÊN VĂN câu người nói đồng ý). "
                "Agent không được tự duyệt cổng thay người."), True
    vt = dau_van_tay(lot, cong)
    if vt is None:
        return f"{TEN_CONG[cong]}: chưa có kết quả để duyệt — chạy verb tương ứng trước.", True
    chan = viec_chan(lot, cong)
    if chan:
        return (f"Không thể duyệt {TEN_CONG[cong]} khi còn {len(chan)} việc CHẶN:\n  - "
                + "\n  - ".join(chan[:10])), True
    d = doc_cong(lot)
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    d[str(cong)] = {"duyet": True, "luc": luc, "nguoi_duyet": args["nguoi_duyet"],
                    "bang_chung": args["bang_chung"], "dau_van_tay": vt,
                    "ghi_chu": args.get("ghi_chu", "")}
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    (lot.log_dir / "cong.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · {TEN_CONG[cong]} · {args['nguoi_duyet']} duyệt: «{args['bang_chung']}»\n")
    return f"Đã ghi duyệt {TEN_CONG[cong]} lúc {luc}. Mở khóa: " + ", ".join(
        v for v, c in CONG_CAN.items() if c == cong) + ".", False


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
