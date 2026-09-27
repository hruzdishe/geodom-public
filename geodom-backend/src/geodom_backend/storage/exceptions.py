class ObjectStorageError(Exception):
    pass

class ObjectStorageUnavailableError(ObjectStorageError):
    pass

class ObjectNotFoundError(ObjectStorageError):
    pass
