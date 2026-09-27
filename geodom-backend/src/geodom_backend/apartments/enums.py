from enum import StrEnum


class ApartmentOrigin(StrEnum):
    SEED = "seed"
    USER = "user"

class ApartmentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    HIDDEN = "hidden"
    DELETED = "deleted"

class ApartmentDealType(StrEnum):
    SALE = "sale"
    RENT = "rent"

class RentPeriod(StrEnum):
    DAY = "day"
    MONTH = "month"

class ApartmentFeatureStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
