import os
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import polars as pl

from chart_observatory.domain.enums import RightsOperation
from chart_observatory.rights.gate import RightsGate


class AtomicDatasetWriter:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def write(self, frame: pl.DataFrame, dataset_name: str, format: str) -> Path:
        if format not in {"csv", "parquet"}:
            raise ValueError("format must be csv or parquet")
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / f"{dataset_name}.{format}"
        temporary = self.root / f".{dataset_name}.{uuid4().hex}.tmp"
        try:
            if format == "csv":
                frame.write_csv(temporary)
            else:
                frame.write_parquet(temporary)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return destination


class AuthorizedDatasetWriter:
    def __init__(self, writer: AtomicDatasetWriter, gate: RightsGate) -> None:
        self.writer = writer
        self.gate = gate

    def write(
        self,
        frame: pl.DataFrame,
        dataset_name: str,
        format: str,
        source_ids: list[UUID],
        occurred_at: datetime,
    ) -> Path:
        export_operation = (
            RightsOperation.EXPORT_AGGREGATE
            if dataset_name != "chart_observations"
            else RightsOperation.REDISTRIBUTE_ROWS
        )
        for source_id in source_ids:
            self.gate.require(source_id, RightsOperation.ANALYZE, occurred_at)
            self.gate.require(source_id, export_operation, occurred_at)
        return self.writer.write(frame, dataset_name, format)
