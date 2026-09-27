import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from geodom_backend.imports.housing.schemas import (
    HousingApartmentRecord,
    HousingDatasetManifest,
    HousingMediaRecord
)

ModelT = TypeVar(
    "ModelT",
    bound=BaseModel
)

@dataclass(frozen=True, slots=True)
class HousingSnapshotPaths:
    root: Path

    @property
    def housing_dir(self) -> Path:
        return self.root / "processed" / "housing"

    @property
    def apartments(self) -> Path:
        return self.housing_dir / "apartments.jsonl"

    @property
    def media(self) -> Path:
        return self.housing_dir / "media.jsonl"

    @property
    def manifest(self) -> Path:
        return self.housing_dir / "dataset_manifest.json"

    def resolve_media_file(self, local_path: str) -> Path:
        return self.root / local_path

@dataclass(frozen=True, slots=True)
class HousingSnapshot:
    paths: HousingSnapshotPaths

    manifest: HousingDatasetManifest

    apartments: tuple[
        HousingApartmentRecord, ...
    ]

    media: tuple[
        HousingMediaRecord, ...
    ]

class HousingSnapshotReader:
    def __init__(self, root: Path):
        self._paths = HousingSnapshotPaths(root=root)

    def read(self) -> HousingSnapshot:
        manifest = self._read_json(self._paths.manifest, HousingDatasetManifest)
        apartments = tuple(self._read_jsonl(self._paths.apartments, HousingApartmentRecord))
        media = tuple(self._read_jsonl(self._paths.media, HousingMediaRecord))

        return HousingSnapshot(
            paths=self._paths,
            manifest=manifest,
            apartments=apartments,
            media=media
        )

    @staticmethod
    def _read_json(path: Path, model: type[ModelT]) -> ModelT:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file, parse_float=Decimal)

        return model.model_validate(data)

    @staticmethod
    def _read_jsonl(path: Path, model: type[ModelT]) -> list[ModelT]:
        records: list[ModelT] = []
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line: continue

                try:
                    data = json.loads(line, parse_float=Decimal)
                    record = model.model_validate(data)
                except Exception as e:
                    raise ValueError(f"Invalid record in {path} at line {line_number}") from e

                records.append(record)

        return records
