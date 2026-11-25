"""Nạp lot.yaml, project.yaml và ngưỡng QC, theo đúng thứ tự ưu tiên."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml

# Mặc định đồng bộ với _agent/kb/nguong-qc.md. lot.yaml ghi đè được từng khóa.
NGUONG_MAC_DINH: dict[str, float] = {
    "trung_mat_bang_mm": 1.0,
    "mad_he_so": 3.0,
    # Sàn cho MAD: trên bề mặt gần phẳng (sau san lấp) MAD tiến về 0 và mọi điểm
    # trông như bất thường. Sàn = sai số đo cao độ cho phép của khảo sát.
    "mad_san_m": 0.02,
    "giao_dutgay_cm": 1.0,
    "goc_tam_giac_det_do": 5.0,
    "tam_giac_lon_boi": 3.0,
    "cung_tron_sai_so_mm": 5.0,
    "area_lech_pct": 0.01,
    "civil3d_lech_pct": 0.1,
    # CHƯA CHỐT — đề xuất, chờ người duyệt (SPEC mục 8)
    "o_lech_lon_pct": 5.0,
    "o_lech_lon_m3": 10.0,
}

TRUONG_BAT_BUOC = (
    "ma_lo", "dot", "he_toa_do", "phuong_phap_chinh_thuc",
    "be_mat_moc", "be_mat_do", "luoi",
)


class ThieuKhaiBao(Exception):
    """lot.yaml thiếu trường bắt buộc. Hỏi đúng trường đó, không đoán (RULES 7)."""


def doc_lot(lot_yaml: Path) -> dict[str, Any]:
    if not lot_yaml.exists():
        raise ThieuKhaiBao(f"Không thấy {lot_yaml}. Mỗi lô phải có lot.yaml.")
    cfg = yaml.safe_load(lot_yaml.read_text(encoding="utf-8")) or {}
    # Người chỉnh lưới trong CAD (menu SAN NỀN) → luoi_tuy_chinh.yaml ở thư mục lô; GHI ĐÈ mục `luoi` của lot.yaml
    # mà không sửa lot.yaml (giữ nguyên chú thích của người). Xóa file đó là quay về lot.yaml.
    tc = lot_yaml.parent / "luoi_tuy_chinh.yaml"
    if tc.exists():
        cfg["luoi"] = {**(cfg.get("luoi") or {}), **((yaml.safe_load(tc.read_text(encoding="utf-8")) or {}).get("luoi") or {})}
    # Người chọn dữ liệu khởi tạo bề mặt / breakline / biên lô thủ công từ CAD/Excel → nguon_tuy_chinh.yaml
    ntc = lot_yaml.parent / "nguon_tuy_chinh.yaml"
    if ntc.exists():
        nd = yaml.safe_load(ntc.read_text(encoding="utf-8")) or {}
        for k in ("be_mat_moc", "be_mat_do", "bien_lo", "loai_tru", "dut_gay", "dut_gay_ap_dung", "anh_xa_cot_excel", "bo_diem", "them_diem"):
            if k in nd and nd[k] is not None:
                cfg[k] = nd[k]
    thieu = [t for t in TRUONG_BAT_BUOC if t not in cfg]
    if thieu:
        raise ThieuKhaiBao("lot.yaml thiếu trường bắt buộc: " + ", ".join(thieu))
    if cfg.get("luoi", {}).get("kich_thuoc_o_m") in (None, 0):
        raise ThieuKhaiBao("lot.yaml: luoi.kich_thuoc_o_m chưa khai.")
    return cfg


def nguong(cfg: dict[str, Any]) -> dict[str, float]:
    ket_qua = dict(NGUONG_MAC_DINH)
    ket_qua.update(cfg.get("nguong") or {})
    return ket_qua
