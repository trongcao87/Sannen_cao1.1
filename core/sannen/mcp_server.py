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
        from . import luoi_sua, dxfio
        tu_dxf = args.get("tu_file_dxf")
        cot_arg = args.get("cot")
        hang_arg = args.get("hang")
        if tu_dxf or cot_arg or hang_arg:
            st_cu = luoi_sua.trang_thai(lot) if (lot.process_dir / "grid.json").exists() else {
                "kich_thuoc_o_m": float(args.get("o") or 20.0),
                "goc_xoay_do": 0.0, "goc_luoi": [0.0, 0.0], "cot_m": [20.0], "hang_m": [20.0],
                "ngoai_suy_m": float(args.get("ngoai_suy") or 0.0), "ngoai_suy_kieu": "gan_nhat"
            }
            if tu_dxf:
                kq_dxf = dxfio.doc_luoi_dxf(Path(tu_dxf), args.get("layer_luoi"))
                st_moi = {**st_cu, "kich_thuoc_o_m": float(args.get("o") or kq_dxf["kich_thuoc_o_m"]),
                          "goc_xoay_do": float(args.get("goc") if args.get("goc") is not None else kq_dxf["goc_xoay_do"]),
                          "goc_luoi": [float(x) for x in args["goc_luoi"].split(",")] if args.get("goc_luoi") else kq_dxf["goc_luoi"],
                          "cot_m": luoi_sua.phan_tich(cot_arg) if cot_arg else kq_dxf["cot_m"],
                          "hang_m": luoi_sua.phan_tich(hang_arg) if hang_arg else kq_dxf["hang_m"]}
            else:
                kw_dat: dict = {}
                if cot_arg:
                    kw_dat["cot"] = cot_arg
                if hang_arg:
                    kw_dat["hang"] = hang_arg
                if args.get("o") is not None:
                    kw_dat["o"] = float(args["o"])
                if args.get("goc") is not None and str(args["goc"]) != "auto":
                    kw_dat["goc_do"] = float(args["goc"])
                if args.get("goc_luoi"):
                    kw_dat["goc_luoi"] = [float(x) for x in str(args["goc_luoi"]).split(",")]
                if args.get("ngoai_suy") is not None:
                    kw_dat["ngoai_suy_m"] = float(args["ngoai_suy"])
                st_moi = luoi_sua.ap_dung(st_cu, "dat", **kw_dat)
            if not preview:
                luoi_sua.ghi_tuy_chinh(lot, st_moi, args.get("ly_do") or "Đặt/Import lưới từ cửa sổ Chat qua MCP")
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
    import yaml
    lot = _lot(args)
    if not args.get("ma_viec") or not args.get("lua_chon"):
        return "Cần ma_viec (vd V-01) và lua_chon (vd a).", True
    ma_viec = str(args["ma_viec"]).strip()
    lua_chon = str(args["lua_chon"]).strip().lower()
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · {ma_viec} → {lua_chon}"
                f"{' — ' + args['ghi_chu'] if args.get('ghi_chu') else ''}\n")
    # Nếu là việc V-.. (qc_input.json) và người chọn (b) loại bỏ điểm nghi vấn → ghi mã điểm vào nguon_tuy_chinh.yaml:bo_diem
    them_tb = ""
    qi_p = lot.process_dir / "qc_input.json"
    if lua_chon == "b" and ma_viec.upper().startswith("V-") and qi_p.is_file():
        qi = io_out.doc_json(qi_p)
        for ph in qi.get("phat_hien", []):
            if str(ph.get("ma", "")).upper() == ma_viec.upper():
                import re
                ids = re.findall(r"\b(?:MOC|DO)-\d+\b", str(ph.get("mo_ta", "")))
                if ids:
                    from .config import doc_lot
                    cfg = doc_lot(lot.lot_yaml)
                    bo_ds = [str(x) for x in (cfg.get("bo_diem") or [])]
                    moi = [i for i in ids if i not in bo_ds]
                    if moi:
                        bo_ds.extend(moi)
                        ntc_p = lot.root / "nguon_tuy_chinh.yaml"
                        ntc = (yaml.safe_load(ntc_p.read_text(encoding="utf-8")) or {}) if ntc_p.exists() else {}
                        ntc["bo_diem"] = bo_ds
                        ntc_p.write_text("# Nguồn dữ liệu & quyết định lọc điểm từ Agent MCP / CAD — ghi đè lot.yaml.\n"
                                         + yaml.safe_dump(ntc, allow_unicode=True, sort_keys=False), encoding="utf-8")
                        them_tb = f" (đã đưa {', '.join(moi)} vào danh sách bo_diem)"
    return f"Đã ghi quyết định {ma_viec} → {lua_chon}{them_tb}.", False


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
           "be_mat_da_khoi_tao": bool(buoc["mat"]),
           "san_sang_agent_ra_soat": bool(buoc["mat"] and buoc["lo"]),
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


def thong_tin_mcp(args: dict) -> tuple[str, bool]:
    """Đọc toàn bộ số liệu có cấu trúc của lô (chỉ ĐỌC, không tính, không ghi)."""
    from . import thong_tin as _tt
    lot = _lot(args)
    tt = _tt.thong_tin(lot)
    return json.dumps({**tt, "nhom": _tt.dong_hien_thi(tt), "bien_dong": _tt.dong_bien(tt)},
                      ensure_ascii=False, indent=1), False


def canh_bao_mcp(args: dict) -> tuple[str, bool]:
    """Gom phát hiện QC (qc_*.json) và cảnh báo kết quả cũ theo mức độ (chặn → cảnh báo → thông tin)."""
    from . import thong_tin as _tt
    lot = _lot(args)
    thu_tu = {"chan": 0, "canh_bao": 1, "thong_tin": 2}
    ds = []
    for ten in ("qc_input.json", "qc_surface.json", "qc_lo.json", "qc_luoi.json", "qc_volume.json"):
        p = lot.process_dir / ten
        if not p.exists():
            continue
        for f in io_out.doc_json(p).get("phat_hien", []):
            vt = f.get("vi_tri") or [None, None]
            ds.append({"ma": f.get("ma"), "muc": f.get("muc"), "loai": f.get("loai"),
                       "mo_ta": f.get("mo_ta"), "e": vt[0], "n": vt[1], "nguon": ten})
    ds.sort(key=lambda x: thu_tu.get(x["muc"], 3))
    tt = _tt.thong_tin(lot)
    return json.dumps({"lot": lot.root.name, "canh_bao_cu": tt["canh_bao_cu"], "phat_hien": ds},
                      ensure_ascii=False, indent=1), False


def ra_soat_phuong_an_mcp(args: dict) -> tuple[str, bool]:
    """Agent chỉ chạy bước rà soát, chuẩn hóa, và tạo nhiều phương án (--sweep) KHI người dùng đã khởi tạo bề mặt thành công."""
    lot = _lot(args)
    ps = lot.process_dir
    preview = args.get("preview", True)
    if not ((ps / "surface_moc.json").exists() and (ps / "surface_do.json").exists()):
        return ("TỪ CHỐI: Người dùng CHƯA khởi tạo xong hai bề mặt (surface_moc.json, surface_do.json). "
                "Theo quy trình thủ công: người dùng phải tự chọn dữ liệu từ Excel hoặc AutoCAD, chọn đường Breakline, "
                "chọn biên lô bằng nút lệnh trong AutoCAD (SN_TAOMAT / DD_DH) để khởi tạo bề mặt thành công trước; "
                "sau đó Agent mới chạy rà soát, chuẩn hóa và tạo nhiều phương án."), True
    if not (ps / "boundary.geojson").exists():
        return ("TỪ CHỐI: Chưa có biên lô (boundary.geojson). Người dùng cần chọn biên lô bằng nút lệnh bên AutoCAD "
                "(SN_TAOMAT hoặc SN_CHONBIEN) trước khi Agent chạy rà soát và tạo phương án."), True

    log_buoc: list[str] = []
    # 1. Chuẩn hóa biên lô nếu chưa có lo.json
    if not (ps / "lo.json").exists():
        ma_lo, ra_lo = _chay_cli(["lo", "--lot", str(lot.root)] + (["--preview"] if preview else []))
        log_buoc.append(f"── CHUẨN HÓA BIÊN LÔ (mã {ma_lo}) ──\n{ra_lo.strip()}")
        if ma_lo >= 2:
            return "\n\n".join(log_buoc), True
    else:
        lo_d = io_out.doc_json(ps / "lo.json")
        log_buoc.append(f"── BIÊN LÔ ĐÃ CHUẨN HÓA ──\nDiện tích hiệu dụng: {lo_d.get('tong', {}).get('dt_hieu_dung_m2', 0):,.3f} m²")

    # 2. Rà soát QC bề mặt + dữ liệu + biên lô
    phat_hien = []
    for ten in ("qc_input.json", "qc_surface.json", "qc_lo.json"):
        p = ps / ten
        if p.exists():
            for f in io_out.doc_json(p).get("phat_hien", []):
                if f.get("muc") != "thong_tin":
                    phat_hien.append(f"[{f.get('muc')}] {f.get('ma')}: {f.get('mo_ta')}")
    log_buoc.append("── RÀ SOÁT CHẤT LƯỢNG BỀ MẶT & BIÊN LÔ ──\n" +
                    ("\n".join(phat_hien) if phat_hien else "Không có cảnh báo hay việc chặn ở bề mặt và biên lô."))

    # 3. Đặt lưới (nếu chưa có grid.json hoặc đang chạy chính thức sau khi cổng 2 đã duyệt)
    if not preview:
        ok_c2, ly_c2 = kiem_cong(lot, "tinh", False)
        if not ok_c2:
            return "\n\n".join(log_buoc) + "\n\n" + thong_bao_tu_choi("tinh", ly_c2), True
        if not (ps / "grid.json").exists():
            ma_lu, ra_lu = _chay_cli(["luoi", "--lot", str(lot.root)])
            log_buoc.append(f"── ĐẶT LƯỚI Ô VUÔNG (mã {ma_lu}) ──\n{ra_lu.strip()}")
            if ma_lu >= 2:
                return "\n\n".join(log_buoc), True
        ma_ti, ra_ti = _chay_cli(["tinh", "--lot", str(lot.root), "--sweep"])
        log_buoc.append(f"── TÍNH & QUÉT NHIỀU PHƯƠNG ÁN (--sweep, mã {ma_ti}) ──\n{ra_ti.strip()}")
        return "\n\n".join(log_buoc), ma_ti >= 2

    # Chế độ preview: nếu chưa có grid.json thì báo trạng thái rà soát bề mặt/biên lô để người dùng tạo lưới hoặc duyệt cổng 2
    if (ps / "grid.json").exists():
        ma_ti, ra_ti = _chay_cli(["tinh", "--lot", str(lot.root), "--sweep", "--preview"])
        log_buoc.append(f"── XEM TRƯỚC TÍNH & QUÉT NHIỀU PHƯƠNG ÁN (--sweep, mã {ma_ti}) ──\n{ra_ti.strip()}")
    else:
        log_buoc.append("── LƯỚI Ô VUÔNG ──\nChưa có grid.json — người dùng có thể mở hộp thoại Tạo lưới (SN_LUOI / DD_TAOLUOI) "
                        "chọn biên lô để tự tính số cột/hàng, hoặc duyệt Cổng 2 để chạy bước đặt lưới và quét ma trận phương án (--sweep).")
    return "\n\n".join(log_buoc), False


def day_tin_cad_mcp(args: dict) -> tuple[str, bool]:
    """Sau khi Agent đọc & kiểm soát dữ liệu đầu vào và người dùng duyệt Cổng 1:
    dựng lưới tam giác TIN, xuất trình xem 3D Web HTML, sinh kế hoạch vẽ 3D Mesh và đẩy vào AutoCAD đang mở."""
    import sys
    lot = _lot(args)
    preview = args.get("preview", True)
    be_mat = args.get("be_mat") or "ca-hai"
    ok, ly_do = kiem_cong(lot, "mat", preview)
    if not ok:
        return thong_bao_tu_choi("mat", ly_do), True
    ma_mat, ra_mat = _chay_cli(["mat", "--lot", str(lot.root), "--be-mat", be_mat] + (["--preview"] if preview else []))
    if ma_mat >= 2:
        return _tra(ma_mat, ra_mat)
    ra_lo = ""
    if (lot.process_dir / "boundary.geojson").exists():
        _, ra_lo = _chay_cli(["lo", "--lot", str(lot.root)] + (["--preview"] if preview else []))
    if preview:
        return _tra(ma_mat, ra_mat + "\n" + ra_lo,
                    "\n→ Xem trước dựng TIN xong. Gọi lại với preview=false (sau khi Cổng 1 đã duyệt) để tạo TIN, 3D Mesh, HTML 3D View và đẩy vào AutoCAD đang mở.")
    _, ra_html = _chay_cli(["xem3d", "--lot", str(lot.root)])
    cad_dir = Path(__file__).resolve().parents[2] / "cad"
    if str(cad_dir) not in sys.path and cad_dir.is_dir():
        sys.path.insert(0, str(cad_dir))
    from sannen_cad import ke_hoach as _kh
    kh = _kh.tao_ke_hoach_tin3d(lot.root, be_mat, "polyface")
    dest = lot.output_dir / "ke_hoach_tin3d.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_kh.ghi_json(kh))
    # Thử kích hoạt lệnh SN_NAP_TU_MCP trên AutoCAD đang mở qua COM (nếu AutoCAD đang chạy trên cùng máy)
    da_day_cad = False
    tb_cad = "Người dùng có thể bấm nút «Nhận & Tạo TIN từ Agent (MCP)» trên tab QL ĐH (hoặc gõ SN_NAP_TU_MCP trong AutoCAD) để hiển thị ngay."
    try:
        import subprocess
        ps_cmd = (
            "try { $acad = [Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application'); "
            "if ($acad -and $acad.ActiveDocument) { $acad.ActiveDocument.SendCommand('SN_NAP_TU_MCP '); Write-Output 'OK_CAD' } } catch {}"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=4)
        if "OK_CAD" in (r.stdout or ""):
            da_day_cad = True
            tb_cad = "Đã tự động đẩy lệnh SN_NAP_TU_MCP vào cửa sổ AutoCAD đang mở để dựng TIN & vẽ 3D Mesh!"
    except Exception:
        pass
    out = {
        "be_mat": be_mat,
        "da_day_vao_autocad": da_day_cad,
        "thong_bao_cad": tb_cad,
        "html_3d": str(lot.output_dir / "tin3d_view.html"),
        "ke_hoach_3d_mesh": str(dest),
        "tom_tat_3d": kh["tom_tat"],
        "ket_qua_mat": ra_mat.strip(),
    }
    return json.dumps(out, ensure_ascii=False, indent=1), False


def ve_mcp(args: dict) -> tuple[str, bool]:
    """Dựng kế hoạch vẽ JSON theo ý định (ve | tin3d | mat-cat | bang). Mặc định preview=true không ghi file."""
    import sys
    lot = _lot(args)
    preview = args.get("preview", True)
    che_do = args.get("che_do") or "ve"
    cad_dir = Path(__file__).resolve().parents[2] / "cad"
    if str(cad_dir) not in sys.path and cad_dir.is_dir():
        sys.path.insert(0, str(cad_dir))
    from sannen_cad import ke_hoach as _kh
    try:
        if che_do == "ve":
            lop = args.get("lop")
            if isinstance(lop, str):
                lop = [x.strip() for x in lop.split(",") if x.strip()]
            kh = _kh.tao_ke_hoach(lot.root, lop, args.get("dang") or "polyface")
        elif che_do == "tin3d":
            kh = _kh.tao_ke_hoach_tin3d(lot.root, args.get("be_mat") or "ca-hai", args.get("dang") or "polyface")
        elif che_do == "mat-cat":
            ten = args.get("ten") or "MC1"
            kh = _kh.tao_ke_hoach_mat_cat(lot.root, ten, ty_le=float(args.get("ty_le_dung") or 5.0))
        elif che_do == "bang":
            gv = args.get("goc_ve") or [0.0, 0.0]
            kh = _kh.tao_ke_hoach_bang(lot.root, args.get("loai") or "o", (float(gv[0]), float(gv[1])))
        else:
            return f"che_do phải là ve, tin3d, mat-cat hoặc bang (nhận '{che_do}').", True
    except (FileNotFoundError, ValueError) as e:
        return str(e), True
    out = {"che_do": che_do, "preview": preview, "tom_tat": kh["tom_tat"],
           "lop": [l["ten"] for l in kh["lop"]], "xoa": kh["xoa"]}
    if not preview:
        dest = Path(args["ke_hoach"]) if args.get("ke_hoach") else (lot.output_dir / "ke_hoach_ve.json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_kh.ghi_json(kh))
        out["ke_hoach"] = str(dest)
    return json.dumps(out, ensure_ascii=False, indent=1), False


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
        verb("luoi", "Đặt lưới ô vuông, nội suy cao độ đỉnh (hoặc import lưới từ file CAD/DXF, đẩy cấu hình cột/hàng từ Chat sang AutoCAD). "
             "Cần cổng 2. Kích thước ô/góc/gốc theo hồ sơ, KHÔNG tự chọn.",
             {"o": _p("kích thước ô (m)", "number"), "goc": _p("góc xoay độ hoặc 'auto'"),
              "goc_luoi": _p("gốc lưới 'E,N' VN-2000"),
              "cot": _p("chiều rộng các cột dạng Số×KT (vd '7x20,2x15') đẩy từ Chat sang CAD"),
              "hang": _p("chiều cao các hàng dạng Số×KT (vd '5x20') đẩy từ Chat sang CAD"),
              "tu_file_dxf": _p("đường dẫn file .dxf hoặc .json để import lưới ô vuông vào lô"),
              "layer_luoi": _p("tên layer chứa lưới trong file DXF (tuỳ chọn)"),
              "ly_do": _p("lý do đặt/import lưới từ Chat (ghi vào decisions.md)"),
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
        CongCu("sannen_thong_tin", "Đọc toàn bộ số liệu có cấu trúc của lô (TIN, biên, lưới, khối lượng, mặt cắt). Chỉ ĐỌC.",
               schema({"lot": LOT}, ["lot"]), thong_tin_mcp),
        CongCu("sannen_canh_bao", "Gom tất cả phát hiện QC (qc_*.json) theo mức độ (chặn → cảnh báo → thông tin) và cảnh báo kết quả cũ.",
               schema({"lot": LOT}, ["lot"]), canh_bao_mcp),
        CongCu("sannen_ra_soat_phuong_an",
               "Agent chạy bước rà soát QC, chuẩn hóa biên lô và quét ma trận nhiều phương án (--sweep) SAU KHI người dùng "
               "đã khởi tạo bề mặt (MHTN + MHTK) thành công từ AutoCAD/Excel. Nếu bề mặt chưa khởi tạo sẽ từ chối.",
               schema({"lot": LOT, "preview": PREVIEW}, ["lot"]), ra_soat_phuong_an_mcp),
        CongCu("sannen_ve", "Dựng kế hoạch vẽ JSON theo ý định (ve | tin3d | mat-cat | bang) cho AutoCAD DrawEngine. Mặc định preview=true.",
               schema({"lot": LOT, "preview": PREVIEW,
                       "che_do": _p("ve (mặc định) | tin3d | mat-cat | bang", enum=["ve", "tin3d", "mat-cat", "bang"]),
                       "lop": _p("danh sách nhóm cần vẽ: luoi,nhan,o,ranh,3d,bang", "array"),
                       "be_mat": _p("moc | do | ca-hai (cho tin3d)", enum=["moc", "do", "ca-hai"]),
                       "ten": _p("tên mặt cắt (cho mat-cat)"),
                       "loai": _p("tong | tong-hop | o (cho bang)", enum=["tong", "tong-hop", "o"]),
                       "ke_hoach": _p("đường dẫn file JSON đầu ra khi preview=false")}, ["lot"]), ve_mcp),
        CongCu("sannen_day_tin_cad",
               "Sau khi Agent đọc & kiểm soát dữ liệu đầu vào (sannen_nhap) và người dùng duyệt Cổng 1: "
               "dựng lưới tam giác TIN, tạo 3D Mesh (SN-3DF-MOC/DO), xuất trình xem 3D Web HTML (tin3d_view.html) "
               "và đẩy trực tiếp vào bản vẽ AutoCAD đang mở thông qua lệnh SN_NAP_TU_MCP.",
               schema({"lot": LOT, "preview": PREVIEW,
                       "be_mat": _p("moc | do | ca-hai (mặc định ca-hai)", enum=["moc", "do", "ca-hai"])}, ["lot"]), day_tin_cad_mcp),
    ]


def main() -> None:
    chay_may_chu("sannen-core", __version__, danh_sach_cong_cu())


if __name__ == "__main__":
    main()
