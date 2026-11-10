from sqlalchemy.exc import DBAPIError


class PersistenceError(Exception):
    """Safe domain error: never includes SQL, parameters or credentials."""


class DuplicateRecord(PersistenceError):
    pass


class IntegrityViolation(PersistenceError):
    pass


class StaleRevision(PersistenceError):
    pass


class RecordNotFound(PersistenceError):
    pass


class ForbiddenOperation(PersistenceError):
    pass


def translate_database_error(error: DBAPIError) -> PersistenceError:
    code = getattr(error.orig, "sqlstate", None)
    if code == "23505":
        return DuplicateRecord("A record with this identity already exists.")
    if code in {"23503", "23514", "23502"}:
        return IntegrityViolation("Data violates a persistence constraint.")
    if code in {"42501", "55000"}:
        return ForbiddenOperation("This persistence operation is not permitted.")
    return PersistenceError("Database operation failed.")
