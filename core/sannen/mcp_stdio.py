"""MCP qua stdio, viết bằng thư viện chuẩn — không phụ thuộc gói `mcp`.

Giao thức: JSON-RPC 2.0, mỗi thông điệp một dòng JSON UTF-8. Chỉ cài phần cần cho công cụ:
initialize · ping · tools/list · tools/call (+ bỏ qua các thông báo notifications/*).
Dùng chung cho MCP lõi (mcp_server.py) và MCP CAD (cad/mcp_cad_server.py).
"""
from __future__ import annotations
import json
import sys
from typing import Callable

PHIEN_BAN_HO_TRO = ("2025-06-18", "2025-03-26", "2024-11-05")


class CongCu:
    """Một công cụ: tên, mô tả, JSON-schema của tham số, hàm xử lý(args) -> (văn bản, có_lỗi)."""

    def __init__(self, ten: str, mo_ta: str, tham_so: dict, ham: Callable[[dict], tuple[str, bool]]):
        self.ten, self.mo_ta, self.tham_so, self.ham = ten, mo_ta, tham_so, ham

    def mo_ta_json(self) -> dict:
        return {"name": self.ten, "description": self.mo_ta, "inputSchema": self.tham_so}


def schema(thuoc_tinh: dict, bat_buoc: list[str] | None = None) -> dict:
    return {"type": "object", "properties": thuoc_tinh, "required": bat_buoc or [],
            "additionalProperties": False}


def xu_ly(msg: dict, ten_may: str, phien_ban: str, cong_cu: dict[str, CongCu]) -> dict | None:
    """Xử lý MỘT thông điệp. Trả None với thông báo (không có id)."""
    method, id_ = msg.get("method"), msg.get("id")
    if id_ is None:
        return None                                        # notifications/initialized, ... không đáp
    ok = lambda kq: {"jsonrpc": "2.0", "id": id_, "result": kq}
    loi = lambda ma, tn: {"jsonrpc": "2.0", "id": id_, "error": {"code": ma, "message": tn}}
    if method == "initialize":
        yc = (msg.get("params") or {}).get("protocolVersion")
        return ok({"protocolVersion": yc if yc in PHIEN_BAN_HO_TRO else PHIEN_BAN_HO_TRO[0],
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": ten_may, "version": phien_ban}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": [c.mo_ta_json() for c in cong_cu.values()]})
    if method == "tools/call":
        p = msg.get("params") or {}
        c = cong_cu.get(p.get("name"))
        if c is None:
            return loi(-32602, f"Không có công cụ {p.get('name')!r}")
        try:
            van_ban, co_loi = c.ham(p.get("arguments") or {})
        except Exception as e:                              # lỗi công cụ báo cho agent, không sập máy chủ
            van_ban, co_loi = f"{type(e).__name__}: {e}", True
        return ok({"content": [{"type": "text", "text": van_ban}], "isError": bool(co_loi)})
    return loi(-32601, f"Phương thức không hỗ trợ: {method}")


def chay_may_chu(ten_may: str, phien_ban: str, cong_cu: list[CongCu]) -> None:
    """Vòng lặp stdio. stdout CHỈ chứa JSON-RPC; mọi log ra stderr."""
    for s in (sys.stdin, sys.stdout):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:                                   # pragma: no cover
            pass
    bang = {c.ten: c for c in cong_cu}
    for dong in sys.stdin:
        dong = dong.strip()
        if not dong:
            continue
        try:
            msg = json.loads(dong)
        except json.JSONDecodeError as e:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                         "error": {"code": -32700, "message": f"JSON hỏng: {e}"}}) + "\n")
            sys.stdout.flush()
            continue
        kq = xu_ly(msg, ten_may, phien_ban, bang)
        if kq is not None:
            sys.stdout.write(json.dumps(kq, ensure_ascii=False) + "\n")
            sys.stdout.flush()
