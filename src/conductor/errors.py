"""Custom exception classes for Conductor."""

class ConductorError(Exception):
    """Base class for Conductor errors."""
    pass

class ConsensusTimeoutError(ConductorError):
    """Consensus round failed to complete within timeout."""
    pass

class InsufficientValidatorsError(ConductorError):
    """Not enough validators online for quorum."""
    pass

class InvalidSignatureError(ConductorError):
    """Signature verification failed."""
    pass

class NetworkPartitionError(ConductorError):
    """Network partition detected."""
    pass

class VDFComputationError(ConductorError):
    """VDF computation failed."""
    pass

class StorageError(ConductorError):
    """Storage operation failed."""
    pass

class ConfigurationError(ConductorError):
    """Configuration error."""
    pass

class AuthenticationError(ConductorError):
    """Authentication failed."""
    pass

class RateLimitError(ConductorError):
    """Rate limit exceeded."""
    pass
