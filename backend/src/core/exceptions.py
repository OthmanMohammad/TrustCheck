class TrustCheckError(Exception):
    """Base exception for all TrustCheck errors."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class ValidationError(TrustCheckError):
    """Raised when input data validation fails."""
    pass

class ScrapingError(TrustCheckError):
    """Raised when web scraping operations fail."""
    pass

class DatabaseError(TrustCheckError):
    """Raised when database operations fail."""
    pass

class AuthenticationError(TrustCheckError):
    """Raised when authentication fails."""
    pass

class RateLimitError(TrustCheckError):
    """Raised when API rate limits are exceeded."""
    pass

class ExternalAPIError(TrustCheckError):
    """Raised when external API calls fail."""
    pass

class EntityNotFoundError(TrustCheckError):
    """Raised when requested entity is not found."""
    pass