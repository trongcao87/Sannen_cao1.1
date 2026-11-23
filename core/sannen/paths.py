"""Cấu trúc thư mục một lô. Một lô = một thư mục (SPEC mục 2)."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Lot:
    root: Path

    @property
    def lot_yaml(self) -> Path:
        return self.root / "lot.yaml"

    @property
    def input_dir(self) -> Path:
        """CHỈ ĐỌC. Agent không bao giờ ghi vào đây (RULES 3)."""
        return self.root / "00_input"

    @property
    def process_dir(self) -> Path:
        return self.root / "10_process"

    @property
    def output_dir(self) -> Path:
        return self.root / "20_output"

    @property
    def log_dir(self) -> Path:
        return self.root / "90_log"

    def ensure(self) -> None:
        for d in (self.input_dir, self.process_dir, self.output_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)

    def guard_write(self, target: Path) -> None:
        """Chặn mọi lần ghi vào 00_input/ ngay trong lõi, không đợi agent nhớ."""
        try:
            target.resolve().relative_to(self.input_dir.resolve())
        except ValueError:
            return
        raise PermissionError(
            f"RULES 3: 00_input/ chỉ đọc. Không được ghi {target}"
        )
