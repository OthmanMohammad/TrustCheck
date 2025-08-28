"""
Custom validators for API request/response validation.

Provides reusable validators for common patterns and business rules.
"""

from typing import Any, Optional, List, Dict, Union
from datetime import datetime, timedelta
from pydantic import field_validator, model_validator
import re

# ======================== STRING VALIDATORS ========================

class StringValidators:
    """Common string validation patterns."""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 500) -> str:
        """Sanitize and validate string input."""
        if not isinstance(value, str):
            raise ValueError("Value must be a string")
        
        # Strip whitespace
        value = value.strip()
        
        # Check empty
        if not value:
            raise ValueError("String cannot be empty")
        
        # Check length
        if len(value) > max_length:
            raise ValueError(f"String exceeds maximum length of {max_length}")
        
        # Remove control characters
        value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
        
        return value
    
    @staticmethod
    def validate_uid(value: str) -> str:
        """Validate entity UID format."""
        if not re.match(r'^[a-zA-Z0-9_\-]+$', value):
            raise ValueError("UID must contain only alphanumeric characters, hyphens, and underscores")
        
        if len(value) < 3:
            raise ValueError("UID must be at least 3 characters long")
        
        if len(value) > 100:
            raise ValueError("UID cannot exceed 100 characters")
        
        return value
    
    @staticmethod
    def validate_name(value: str) -> str:
        """Validate entity name."""
        value = StringValidators.sanitize_string(value, max_length=500)
        
        # Check for minimum meaningful length
        if len(value) < 2:
            raise ValueError("Name must be at least 2 characters long")
        
        # Check for suspicious patterns
        if re.match(r'^[0-9]+$', value):
            raise ValueError("Name cannot be purely numeric")
        
        return value
    
    @staticmethod
    def validate_program_name(value: str) -> str:
        """Validate sanctions program name."""
        value = value.strip().upper()
        
        if not re.match(r'^[A-Z0-9_\-\s]+$', value):
            raise ValueError("Program name must contain only uppercase letters, numbers, underscores, hyphens, and spaces")
        
        return value

# ======================== DATE VALIDATORS ========================

class DateValidators:
    """Date and time validation."""
    
    @staticmethod
    def validate_date_range(start_date: datetime, end_date: datetime) -> tuple:
        """Validate date range."""
        if end_date < start_date:
            raise ValueError("End date must be after start date")
        
        # Check reasonable range (e.g., max 1 year)
        if (end_date - start_date).days > 365:
            raise ValueError("Date range cannot exceed 365 days")
        
        # Check not in future
        if end_date > datetime.utcnow():
            raise ValueError("End date cannot be in the future")
        
        return start_date, end_date
    
    @staticmethod
    def validate_lookback_period(days: int) -> int:
        """Validate lookback period in days."""
        if days < 1:
            raise ValueError("Lookback period must be at least 1 day")
        
        if days > 365:
            raise ValueError("Lookback period cannot exceed 365 days")
        
        return days

# ======================== LIST VALIDATORS ========================

class ListValidators:
    """List and collection validation."""
    
    @staticmethod
    def validate_unique_list(values: List[Any]) -> List[Any]:
        """Ensure list contains unique values."""
        seen = set()
        unique_values = []
        
        for value in values:
            if value not in seen:
                seen.add(value)
                unique_values.append(value)
        
        return unique_values
    
    @staticmethod
    def validate_list_size(values: List[Any], min_size: int = None, max_size: int = None) -> List[Any]:
        """Validate list size constraints."""
        if min_size is not None and len(values) < min_size:
            raise ValueError(f"List must contain at least {min_size} items")
        
        if max_size is not None and len(values) > max_size:
            raise ValueError(f"List cannot exceed {max_size} items")
        
        return values
    
    @staticmethod
    def validate_non_empty_list(values: List[Any]) -> List[Any]:
        """Ensure list is not empty and contains non-null values."""
        if not values:
            raise ValueError("List cannot be empty")
        
        # Filter out None/empty values
        filtered = [v for v in values if v]
        
        if not filtered:
            raise ValueError("List must contain at least one non-empty value")
        
        return filtered

# ======================== BUSINESS RULE VALIDATORS ========================

class BusinessRuleValidators:
    """Validators for business rules and constraints."""
    
    @staticmethod
    def validate_risk_level_consistency(changes: List[Dict], risk_level: str) -> List[Dict]:
        """Ensure change risk levels are consistent with change types."""
        for change in changes:
            change_type = change.get('change_type')
            assigned_risk = change.get('risk_level')
            
            # Removals should always be critical
            if change_type == 'REMOVED' and assigned_risk != 'CRITICAL':
                raise ValueError(f"Removed entities must have CRITICAL risk level")
            
            # Additions should be at least MEDIUM
            if change_type == 'ADDED' and assigned_risk == 'LOW':
                raise ValueError(f"Added entities must have at least MEDIUM risk level")
        
        return changes
    
    @staticmethod
    def validate_entity_type_consistency(entity_type: str, personal_info: Optional[Dict]) -> str:
        """Ensure entity type is consistent with provided data."""
        if personal_info and entity_type != 'PERSON':
            raise ValueError("Personal information can only be provided for PERSON entities")
        
        if entity_type == 'PERSON' and not personal_info:
            # This is a warning, not an error
            pass  # Could log warning here
        
        return entity_type
    
    @staticmethod
    def validate_pagination_params(limit: int, offset: int) -> tuple:
        """Validate pagination parameters."""
        if limit < 1:
            raise ValueError("Limit must be at least 1")
        
        if limit > 1000:
            raise ValueError("Limit cannot exceed 1000")
        
        if offset < 0:
            raise ValueError("Offset cannot be negative")
        
        # Prevent deep pagination for performance
        if offset > 10000:
            raise ValueError("Offset too large. Use cursor-based pagination for large datasets")
        
        return limit, offset

# ======================== SECURITY VALIDATORS ========================

class SecurityValidators:
    """Security-focused validators."""
    
    @staticmethod
    def validate_no_injection(value: str) -> str:
        """Check for potential injection attacks."""
        # SQL injection patterns
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
            r"(--|#|/\*|\*/)",
            r"(\bOR\b.*=.*)",
            r"(\bAND\b.*=.*)",
            r"(;.*\b(SELECT|INSERT|UPDATE|DELETE)\b)"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValueError("Input contains potentially dangerous patterns")
        
        # XSS patterns
        if re.search(r'<script[^>]*>.*?</script>', value, re.IGNORECASE | re.DOTALL):
            raise ValueError("Input contains potentially dangerous script tags")
        
        # Command injection patterns
        if re.search(r'[;&|`$]', value):
            raise ValueError("Input contains potentially dangerous shell characters")
        
        return value
    
    @staticmethod
    def validate_safe_filename(filename: str) -> str:
        """Validate filename for safety."""
        # Remove path traversal attempts
        filename = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Allow only safe characters
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
            raise ValueError("Filename contains invalid characters")
        
        # Check extension
        allowed_extensions = ['.json', '.xml', '.csv', '.txt']
        if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError(f"File extension not allowed. Must be one of: {allowed_extensions}")
        
        return filename

# ======================== COMPOSITE VALIDATORS ========================

class CompositeValidators:
    """Validators that combine multiple validation rules."""
    
    @staticmethod
    def validate_search_query(query: str) -> str:
        """Validate search query with multiple rules."""
        # Basic string validation
        query = StringValidators.sanitize_string(query, max_length=200)
        
        # Security validation
        query = SecurityValidators.validate_no_injection(query)
        
        # Minimum length for meaningful search
        if len(query) < 2:
            raise ValueError("Search query must be at least 2 characters")
        
        # Check for too many wildcards
        wildcard_count = query.count('*') + query.count('?') + query.count('%')
        if wildcard_count > 3:
            raise ValueError("Too many wildcard characters in search query")
        
        return query
    
    @staticmethod
    def validate_bulk_operation(entity_uids: List[str], operation: str) -> tuple:
        """Validate bulk operation request."""
        # Validate UIDs
        validated_uids = []
        for uid in entity_uids:
            validated_uids.append(StringValidators.validate_uid(uid))
        
        # Validate unique
        validated_uids = ListValidators.validate_unique_list(validated_uids)
        
        # Validate size
        validated_uids = ListValidators.validate_list_size(
            validated_uids,
            min_size=1,
            max_size=1000
        )
        
        # Validate operation
        allowed_operations = ['activate', 'deactivate', 'delete', 'export']
        if operation not in allowed_operations:
            raise ValueError(f"Invalid operation. Must be one of: {allowed_operations}")
        
        return validated_uids, operation

# ======================== CUSTOM FIELD VALIDATORS ========================

def create_field_validator(field_name: str, validator_func):
    """Factory to create Pydantic field validators."""
    @field_validator(field_name)
    def validator(cls, v):
        return validator_func(v)
    return validator

def create_model_validator(validator_func):
    """Factory to create Pydantic model validators."""
    @model_validator(mode='after')
    def validator(cls, values):
        return validator_func(values)
    return validator

# ======================== VALIDATION DECORATORS ========================

def validate_request(schema_class):
    """Decorator to validate request against a schema."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request data
            request_data = kwargs.get('request_data', {})
            
            # Validate against schema
            try:
                validated_data = schema_class(**request_data)
                kwargs['validated_data'] = validated_data
            except ValueError as e:
                raise ValueError(f"Request validation failed: {e}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def validate_response(schema_class):
    """Decorator to validate response against a schema."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Validate response
            try:
                if not isinstance(result, schema_class):
                    result = schema_class(**result)
            except ValueError as e:
                raise ValueError(f"Response validation failed: {e}")
            
            return result
        return wrapper
    return decorator

# ======================== VALIDATION ERROR MESSAGES ========================

class ValidationMessages:
    """Standard validation error messages."""
    
    REQUIRED_FIELD = "This field is required"
    INVALID_FORMAT = "Invalid format for {field}"
    OUT_OF_RANGE = "{field} must be between {min} and {max}"
    TOO_SHORT = "{field} must be at least {min} characters"
    TOO_LONG = "{field} cannot exceed {max} characters"
    INVALID_ENUM = "{field} must be one of: {choices}"
    DUPLICATE_VALUE = "Duplicate value not allowed: {value}"
    FUTURE_DATE = "Date cannot be in the future"
    PAST_DATE = "Date cannot be more than {days} days in the past"
    INVALID_EMAIL = "Invalid email address format"
    INVALID_URL = "Invalid URL format"
    INVALID_UUID = "Invalid UUID format"
    
    @staticmethod
    def format_message(template: str, **kwargs) -> str:
        """Format error message with context."""
        return template.format(**kwargs)

# ======================== EXPORTS ========================

__all__ = [
    # Validator classes
    'StringValidators',
    'DateValidators',
    'ListValidators',
    'BusinessRuleValidators',
    'SecurityValidators',
    'CompositeValidators',
    
    # Helper functions
    'create_field_validator',
    'create_model_validator',
    
    # Decorators
    'validate_request',
    'validate_response',
    
    # Error messages
    'ValidationMessages'
]