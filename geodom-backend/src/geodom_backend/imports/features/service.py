from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.apartments.feature_data import (
    CalculatedApartmentFeatures,
)
from geodom_backend.db.repositories import (
    ApartmentFeaturesRepository,
    ApartmentRepository,
)

from .reader import (
    ApartmentFeatureSnapshot,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ApartmentFeatureImportReport:
    feature_version: str

    rows_read: int
    rows_imported: int


class ApartmentFeatureImportService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        apartments: ApartmentRepository,
        features: ApartmentFeaturesRepository,
    ) -> None:
        self._session = session
        self._apartments = apartments
        self._features = features

    async def import_snapshot(
        self,
        snapshot: ApartmentFeatureSnapshot,
    ) -> ApartmentFeatureImportReport:
        dataset_ids = {
            row["apartment_id"]
            for row in snapshot.rows
        }

        apartment_ids = (
            await self._apartments
            .get_ids_by_dataset_ids(
                dataset_ids
            )
        )

        missing_dataset_ids = (
            dataset_ids
            - set(apartment_ids)
        )

        if missing_dataset_ids:
            examples = sorted(
                missing_dataset_ids
            )[:10]

            raise ValueError(
                "Some apartments from feature "
                "snapshot do not exist in "
                "PostgreSQL. "
                f"Missing count: "
                f"{len(missing_dataset_ids)}. "
                f"Examples: {examples}"
            )

        try:
            for row in snapshot.rows:
                dataset_id = row[
                    "apartment_id"
                ]

                db_apartment_id = (
                    apartment_ids[
                        dataset_id
                    ]
                )

                data = self._map_row(
                    row
                )

                await (
                    self._features
                    .save_calculated(
                        apartment_id=(
                            db_apartment_id
                        ),
                        data=data,
                    )
                )

            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise

        return ApartmentFeatureImportReport(
            feature_version=(
                snapshot.feature_version
            ),
            rows_read=len(
                snapshot.rows
            ),
            rows_imported=len(
                snapshot.rows
            ),
        )

    @classmethod
    def _map_row(
        cls,
        row: dict[str, Any],
    ) -> CalculatedApartmentFeatures:
        return CalculatedApartmentFeatures(
            schools_1km=cls._int(
                row[
                    "school_count_1000m"
                ]
            ),

            kindergartens_1km=cls._int(
                row[
                    "kindergarten_count_1000m"
                ]
            ),

            parks_1km=cls._int(
                row[
                    "park_count_1000m"
                ]
            ),

            shops_1km=(
                cls._int(
                    row[
                        "supermarket_count_1000m"
                    ]
                )
                + cls._int(
                    row[
                        "mall_count_1000m"
                    ]
                )
            ),

            transport_stops_1km=cls._int(
                row[
                    "public_transport_count_1000m"
                ]
            ),

            nearest_school_m=(
                cls._decimal_or_none(
                    row[
                        "school_nearest_distance_m"
                    ]
                )
            ),

            nearest_kindergarten_m=(
                cls._decimal_or_none(
                    row[
                        "kindergarten_nearest_distance_m"
                    ]
                )
            ),

            nearest_park_m=(
                cls._decimal_or_none(
                    row[
                        "park_nearest_distance_m"
                    ]
                )
            ),

            nearest_transport_m=(
                cls._decimal_or_none(
                    row[
                        "public_transport_nearest_distance_m"
                    ]
                )
            ),

            feature_version=(
                row["feature_version"]
            ),

            computed_at=(
                cls._datetime_or_none(
                    row.get(
                        "computed_at"
                    )
                )
            ),
        )

    @staticmethod
    def _int(
        value: Any,
    ) -> int:
        if value is None:
            return 0

        return int(value)

    @staticmethod
    def _decimal_or_none(
        value: Any,
    ) -> Decimal | None:
        if value is None:
            return None

        return Decimal(
            str(value)
        )

    @staticmethod
    def _datetime_or_none(
        value: Any,
    ) -> datetime | None:
        if value is None:
            return None

        if isinstance(
            value,
            datetime,
        ):
            return value

        if isinstance(
            value,
            str,
        ):
            return datetime.fromisoformat(
                value
            )

        raise TypeError(
            "Unsupported computed_at type: "
            f"{type(value)!r}"
        )
