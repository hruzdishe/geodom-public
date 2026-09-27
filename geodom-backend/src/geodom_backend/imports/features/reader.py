import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from krasnoyarsk_ml.features import (
    METHOD as EXPECTED_DISTANCE_METHOD,
)
from krasnoyarsk_ml.features import (
    VERSION as EXPECTED_FEATURE_VERSION,
)


REQUIRED_COLUMNS = {
    "apartment_id",
    "feature_version",
    "computed_at",
    "distance_method",

    "school_count_1000m",
    "kindergarten_count_1000m",
    "park_count_1000m",
    "supermarket_count_1000m",
    "mall_count_1000m",
    "public_transport_count_1000m",

    "school_nearest_distance_m",
    "kindergarten_nearest_distance_m",
    "park_nearest_distance_m",
    "public_transport_nearest_distance_m",
}


@dataclass(
    frozen=True,
    slots=True,
)
class ApartmentFeatureSnapshot:
    rows: tuple[dict[str, Any], ...]

    feature_version: str
    distance_method: str


class ApartmentFeatureReader:
    def __init__(
        self,
        *,
        parquet_path: Path,
        report_path: Path,
    ) -> None:
        self._parquet_path = parquet_path
        self._report_path = report_path

    def read(self) -> ApartmentFeatureSnapshot:
        self._validate_files_exist()

        report = self._read_report()

        self._validate_report(report)
        self._validate_parquet_hash(report)

        table = pq.read_table(
            self._parquet_path
        )

        self._validate_columns(
            set(table.column_names)
        )

        rows = tuple(
            table.to_pylist()
        )

        self._validate_rows(rows)

        return ApartmentFeatureSnapshot(
            rows=rows,
            feature_version=(
                EXPECTED_FEATURE_VERSION
            ),
            distance_method=(
                EXPECTED_DISTANCE_METHOD
            ),
        )

    def _validate_files_exist(self) -> None:
        if not self._parquet_path.is_file():
            raise FileNotFoundError(
                f"Feature parquet not found: "
                f"{self._parquet_path}"
            )

        if not self._report_path.is_file():
            raise FileNotFoundError(
                f"Feature report not found: "
                f"{self._report_path}"
            )

    def _read_report(
        self,
    ) -> dict[str, Any]:
        with self._report_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    @staticmethod
    def _validate_report(
        report: dict[str, Any],
    ) -> None:
        if report.get("status") != "complete":
            raise ValueError(
                "Feature report status "
                f"is {report.get('status')!r}, "
                "expected 'complete'"
            )

        if (
            report.get("feature_version")
            != EXPECTED_FEATURE_VERSION
        ):
            raise ValueError(
                "Unsupported feature version: "
                f"{report.get('feature_version')!r}"
            )

        if (
            report.get("distance_method")
            != EXPECTED_DISTANCE_METHOD
        ):
            raise ValueError(
                "Unsupported distance method: "
                f"{report.get('distance_method')!r}"
            )

    def _validate_parquet_hash(
        self,
        report: dict[str, Any],
    ) -> None:
        outputs = report.get(
            "outputs",
            {}
        )

        parquet_info = outputs.get(
            "apartment_features.parquet"
        )

        if parquet_info is None:
            raise ValueError(
                "feature_report.json does not "
                "contain apartment_features.parquet"
            )

        expected_sha256 = parquet_info.get(
            "sha256"
        )

        if not expected_sha256:
            raise ValueError(
                "feature_report.json does not "
                "contain parquet SHA-256"
            )

        actual_sha256 = self._sha256(
            self._parquet_path
        )

        if actual_sha256 != expected_sha256:
            raise ValueError(
                "apartment_features.parquet "
                "SHA-256 does not match "
                "feature_report.json"
            )

    @staticmethod
    def _validate_columns(
        columns: set[str],
    ) -> None:
        missing = (
            REQUIRED_COLUMNS
            - columns
        )

        if missing:
            raise ValueError(
                "Feature parquet is missing "
                f"columns: {sorted(missing)}"
            )

    @staticmethod
    def _validate_rows(
        rows: tuple[
            dict[str, Any],
            ...,
        ],
    ) -> None:
        if not rows:
            raise ValueError(
                "Feature parquet is empty"
            )

        seen_apartment_ids: set[str] = set()

        for index, row in enumerate(
            rows,
            start=1,
        ):
            apartment_id = row.get(
                "apartment_id"
            )

            if (
                not isinstance(
                    apartment_id,
                    str,
                )
                or not apartment_id
            ):
                raise ValueError(
                    "Invalid apartment_id "
                    f"in feature row {index}"
                )

            if (
                apartment_id
                in seen_apartment_ids
            ):
                raise ValueError(
                    "Duplicate feature "
                    f"apartment_id: "
                    f"{apartment_id}"
                )

            seen_apartment_ids.add(
                apartment_id
            )

            if (
                row.get("feature_version")
                != EXPECTED_FEATURE_VERSION
            ):
                raise ValueError(
                    "Unsupported feature_version "
                    f"for apartment "
                    f"{apartment_id}: "
                    f"{row.get('feature_version')!r}"
                )

            if (
                row.get("distance_method")
                != EXPECTED_DISTANCE_METHOD
            ):
                raise ValueError(
                    "Unsupported distance_method "
                    f"for apartment "
                    f"{apartment_id}: "
                    f"{row.get('distance_method')!r}"
                )

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(
                lambda: file.read(
                    1024 * 1024
                ),
                b"",
            ):
                digest.update(chunk)

        return digest.hexdigest()
