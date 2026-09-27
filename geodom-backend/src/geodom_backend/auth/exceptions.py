class AuthError(Exception):
    pass

class LoginAlreadyExistsError(AuthError):
    pass

class InvalidCredentialsError(AuthError):
    pass

class InvalidSessionError(AuthError):
    pass
