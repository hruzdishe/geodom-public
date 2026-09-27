class ApartmentPhotoError(Exception):
    pass

class ApartmentPhotoNotFoundError(ApartmentPhotoError):
    pass

class InvalidApartmentPhotoError(ApartmentPhotoError):
    pass

class ApartmentPhotoLimitError(ApartmentPhotoError):
    pass

class InvalidPhotoOrderError(ApartmentPhotoError):
    pass
