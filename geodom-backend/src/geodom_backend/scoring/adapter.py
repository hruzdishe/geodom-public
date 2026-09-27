import asyncio
from decimal import Decimal
from typing import Any

from krasnoyarsk_ml.features import METHOD as FEATURES_METHOD
from krasnoyarsk_ml.features import VERSION as FEATURES_VERSION
from krasnoyarsk_ml.scoring import VERSION as SCORING_VERSION
from krasnoyarsk_ml.scoring import ScoringConfig, recommend

from geodom_backend.apartments.enums import ApartmentFeatureStatus
from geodom_backend.db.models import Apartment


class ApartmentScoringAdapter:
    model_version = "explainable_heuristic_v1"

    scoring_version = SCORING_VERSION
    feature_version = FEATURES_VERSION
    feature_method = FEATURES_METHOD

    async def recommend(self, *, apartments: list[Apartment], preferences: dict[str, Any], limit: int = 10) -> dict[str, Any]:
        apartment_rows = [
            self._map_apartment(apartment)
            for apartment in apartments
        ]

        feature_rows = []
        for apartment in apartments:
            feature = self._map_features(apartment)
            if feature is not None: feature_rows.append(feature)

        return await asyncio.to_thread(
            recommend,
            apartment_rows,
            feature_rows,
            preferences,
            limit,
            ScoringConfig(assumed_car_speed_kmh=30, enforce_max_commute=True, commute_tolerance_fraction=0)
        )

    @staticmethod
    def _map_apartment(apartment: Apartment) -> dict[str, Any]:
        return {
            "id": str(apartment.id),
            "title": apartment.title,
            "price": float(apartment.price),
            "currency": apartment.currency,
            "rooms": apartment.rooms,
            "area": float(apartment.area),
            "floor": apartment.floor,
            "floors_total": apartment.total_floors,
            "address": apartment.address,
            "offer_type": apartment.deal_type.value,
            "district_name": apartment.district.name,
            "lat": float(apartment.latitude),
            "lon": float(apartment.longitude),
            "source_url": apartment.source_url,
            "is_demo": apartment.is_demo,
        }

    def _map_features(self, apartment: Apartment) -> dict[str, Any] | None:
        features = apartment.features
        if features is None: return None

        if features.status != ApartmentFeatureStatus.READY: return None
        if features.feature_version != self.feature_version: return None

        return {
            "apartment_id": str(apartment.id),
            "feature_version": self.feature_version,
            "distance_method": self.feature_method,
            "school_observed_in_snapshot": (
                features.nearest_school_m
                is not None
            ),
            "school_nearest_distance_m": (
                self._number(
                    features.nearest_school_m
                )
            ),
            "school_nearest_poi_id": None,
            "kindergarten_observed_in_snapshot": (
                features.nearest_kindergarten_m
                is not None
            ),
            "kindergarten_nearest_distance_m": (
                self._number(
                    features.nearest_kindergarten_m
                )
            ),
            "kindergarten_nearest_poi_id": None,
            "park_observed_in_snapshot": (
                features.nearest_park_m
                is not None
            ),
            "park_nearest_distance_m": (
                self._number(
                    features.nearest_park_m
                )
            ),
            "park_nearest_poi_id": None,
            "public_transport_observed_in_snapshot": (
                features.nearest_transport_m
                is not None
            ),
            "public_transport_nearest_distance_m": (
                self._number(
                    features.nearest_transport_m
                )
            ),
            "public_transport_nearest_poi_id": None,
        }

    @staticmethod
    def _number(value: Decimal | None) -> float | None:
        if value is None: return None
        return float(value)
