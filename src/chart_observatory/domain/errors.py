class DomainError(Exception):
    """Base class for domain failures."""


class DomainValidationError(DomainError, ValueError):
    """Raised when a value would violate a scientific-domain invariant."""


class RightsDenied(DomainError):
    """Raised when a source-specific rights profile denies an operation."""


class SourceDisabled(DomainError):
    """Raised before contacting a provider whose adapter is disabled."""


class TemporalAlignmentRequired(DomainError):
    """Raised when unlike native periods lack an explicit alignment policy."""
