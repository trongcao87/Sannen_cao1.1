"""Ba cổng duyệt — MỘT chốt chặn cho mọi lối vào (CLI, MCP, menu AutoCAD).

    Cổng 1 (dữ liệu)  sau nhap          → mở khóa  mat, lo
    Cổng 2 (bề mặt)   sau mat + lo      → mở khóa  luoi, hieuchinh, tinh
    Cổng 3 (số liệu)  sau tinh          → mở khóa  xuat

Verb ghi (không `--preview`) chỉ chạy khi cổng tương ứng đã được NGƯỜI duyệt và kết quả không đổi từ lúc duyệt.
Chế độ xem trước luôn được chạy — RULES 4. Duyệt cổng ghi vào 90_log/cong.json kèm "dấu vân tay" các file kết quả
đã duyệt; kết quả đổi thì phê duyệt tự mất hiệu lực.

Chốt chặn đặt trong `cli.main` — mọi lối vào đều đi qua đó (MCP gọi `cli.main`, cầu nối CAD gọi `cli.main`,
dòng lệnh `sannen` là `cli.main`), nên một chỗ kiểm là đủ. Module này KHÔNG import cli/mcp_server để lõi không phụ thuộc
lớp giao thức.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime
from pathlib import Path

from . import io_out
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


def lot_tu_args(args: dict) -> Lot:
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
    try:
        d = doc_cong(lot).get(str(cong))
    except (OSError, ValueError):                  # cong.json hỏng → coi như CHƯA duyệt, không bao giờ coi là đã duyệt
        return False, f"{TEN_CONG[cong]} CHƯA được người duyệt (cong.json không đọc được)"
    if not d or not d.get("duyet"):
        return False, f"{TEN_CONG[cong]} CHƯA được người duyệt"
    if d.get("dau_van_tay") != dau_van_tay(lot, cong):
        return False, (f"{TEN_CONG[cong]} đã duyệt lúc {d['luc']} nhưng kết quả đã thay đổi kể từ đó "
                       "— phê duyệt mất hiệu lực, cần người duyệt lại")
    return True, ""


def kiem_cong(lot: Lot, verb: str, preview: bool) -> tuple[bool, str]:
    """Chốt chặn duy nhất. Xem trước, hoặc verb không cần cổng → luôn cho qua. Ngược lại phải có cổng đã duyệt."""
    cong = CONG_CAN.get(verb)
    if cong is None or preview:
        return True, ""
    return cong_da_duyet(lot, cong)


def thong_bao_tu_choi(verb: str, ly_do: str) -> str:
    cong = CONG_CAN[verb]
    return (f"TỪ CHỐI ghi `{verb}`: {ly_do}.\n"
            f"Quy trình: chạy verb với --preview, trình viec_can_lam.md cho người, chờ người nói rõ duyệt, "
            f"rồi ghi duyệt {TEN_CONG[cong]} (sannen_duyet_cong / SN_DUYET).\n"
            "Có thể chạy --preview để xem trước mà không cần duyệt.")


def duyet_cong(args: dict) -> tuple[str, bool]:
    """Ghi NGƯỜI đã duyệt một cổng. Trả (văn bản, có_lỗi)."""
    lot = lot_tu_args(args)
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
