class GeoError(Exception):
    pass

class AddressNotFoundError(GeoError):
    pass

class AddressOutsideCityError(GeoError):
    pass

class DistrictNotResolvedError(GeoError):
    pass

class GeocodingUnavailableError(GeoError):
    pass
