class ApartmentError(Exception):
    pass

class ApartmentNotFoundError(ApartmentError):
    pass

class ApartmentPermissionError(ApartmentError):
    pass

class InvalidApartmentDataError(ApartmentError):
    pass
