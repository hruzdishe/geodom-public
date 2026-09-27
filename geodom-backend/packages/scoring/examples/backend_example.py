"""Offline integration example. All records are synthetic, not parser output."""

import json

from krasnoyarsk_ml.districts import rank_districts
from krasnoyarsk_ml.features import METHOD, VERSION
from krasnoyarsk_ml.scoring import Preferences, ScoringConfig, recommend


def main():
    preferences = Preferences.model_validate(
        {"price_max": 10_000_000, "rooms": [2], "priorities": {"schools": 5}}
    )
    config = ScoringConfig()
    apartments = [
        {
            "id": "synthetic-home",
            "price": 8_000_000,
            "rooms": 2,
            "currency": "RUB",
            "offer_type": "sale",
            "district_name": "Synthetic district",
            "lat": 56.0,
            "lon": 93.0,
            "is_demo": True,
        }
    ]
    infrastructure = {
        "feature_version": VERSION,
        "distance_method": METHOD,
        "school_observed_in_snapshot": True,
        "school_nearest_distance_m": 500.0,
        "school_nearest_poi_id": "synthetic-school",
    }
    apartment_result = recommend(
        apartments,
        [{"apartment_id": "synthetic-home", **infrastructure}],
        preferences,
        limit=max(1, len(apartments)),
        config=config,
    )
    district_result = rank_districts(
        [{"district_id": "synthetic-district", "district_name": "Synthetic district"}],
        [{"id": "synthetic-point", "district_id": "synthetic-district",
          "lat": 56.0, "lon": 93.0, "weight_m2": 100.0}],
        [{"point_id": "synthetic-point", **infrastructure}],
        preferences,
        config,
        apartment_result=apartment_result,
    )
    assert apartment_result["results"][0]["score"] == 50.0
    assert district_result["results"][0]["score"] == 50.0
    assert district_result["results"][0]["matching_listing_count"] == 1
    print(json.dumps({"synthetic": True, "apartments": apartment_result,
                      "districts": district_result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
