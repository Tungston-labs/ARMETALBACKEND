# import pytz
# from datetime import datetime, time
# from django.utils import timezone
# import logging

# logger = logging.getLogger(__name__)

# COUNTRY_TIMEZONE_MAPPING = {
#     "IN": "Asia/Kolkata",
#     "AE": "Asia/Dubai",
#     "US": "America/New_York",
#     # Add other countries as needed
# }
# def convert_to_company_timezone(dt, employee):
#     """Convert a datetime to the employee's company timezone."""
#     if dt is None:
#         return None
#     try:
#         tz = get_company_timezone(employee)
#         dt = ensure_timezone(dt, pytz.UTC)
#         return dt.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')  # Optional: format string
#     except Exception as e:
#         logger.error(f"Failed to convert to company timezone: {e}")
#         return dt  # fallback as UTC


# def safe_parse_datetime(dt_str):
#     """Safely parse datetime string with multiple format support"""
#     if isinstance(dt_str, datetime):
#         return dt_str  # Already parsed

#     if not isinstance(dt_str, str):
#         raise ValueError("Input must be string or datetime")

#     try:
#         if dt_str.endswith('Z'):
#             dt_str = dt_str[:-1] + '+00:00'
#         return datetime.fromisoformat(dt_str)
#     except ValueError:
#         try:
#             return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
#         except ValueError:
#             return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")


# def get_company_timezone(employee):
#     """Get timezone with comprehensive error handling"""
#     try:
#         country = None
#         if (hasattr(employee, 'department') and 
#             employee.department and 
#             hasattr(employee.department, 'company') and 
#             employee.department.company):
#             country = employee.department.company.country
        
#         tz_name = COUNTRY_TIMEZONE_MAPPING.get(country, "Asia/Kolkata")
#         return pytz.timezone(tz_name)
#     except Exception as e:
#         logger.error(f"Timezone detection failed: {e}")
#         return pytz.timezone("Asia/Kolkata")

# def ensure_timezone(dt, tz=None):
#     """Ensure datetime has timezone, converting if needed"""
#     if dt is None:
#         return None
        
#     if isinstance(dt, time):
#         raise ValueError("Time objects not supported - use datetime")
    
#     if timezone.is_naive(dt):
#         dt = timezone.make_aware(dt, timezone=tz or pytz.UTC)
#     return dt

import pytz
from datetime import datetime, time
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

COUNTRY_TIMEZONE_MAPPING = {
    "IN": "Asia/Kolkata",
    "AE": "Asia/Dubai",
    "US": "America/New_York",
    "GB": "Europe/London",
    "CA": "America/Toronto",
    "AU": "Australia/Sydney",
    # Add other countries as needed
}

def convert_to_company_timezone(dt, employee):
    """Convert a datetime to the employee's company timezone."""
    if dt is None:
        return None
    try:
        tz = get_company_timezone(employee)
        dt = ensure_timezone(dt, pytz.UTC)
        return dt.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"Failed to convert to company timezone: {e}")
        return dt  # fallback as UTC


def safe_parse_datetime(dt_str):
    """Safely parse datetime string with multiple format support"""
    if isinstance(dt_str, datetime):
        return dt_str  # Already parsed

    if not isinstance(dt_str, str):
        raise ValueError("Input must be string or datetime")

    # Common datetime formats to try
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z"
    ]

    try:
        # Handle ISO format with Z suffix
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
        
        # Try ISO format first
        return datetime.fromisoformat(dt_str)
    except ValueError:
        # Try other formats
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse datetime string: {dt_str}")


def get_company_timezone(employee):
    """Get timezone with comprehensive error handling"""
    try:
        country = None
        if (hasattr(employee, 'department') and 
            employee.department and 
            hasattr(employee.department, 'company') and 
            employee.department.company):
            country = employee.department.company.country
        
        tz_name = COUNTRY_TIMEZONE_MAPPING.get(country, "Asia/Kolkata")
        return pytz.timezone(tz_name)
    except Exception as e:
        logger.error(f"Timezone detection failed: {e}")
        return pytz.timezone("Asia/Kolkata")

def ensure_timezone(dt, tz=None):
    """Ensure datetime has timezone, converting if needed"""
    if dt is None:
        return None
        
    if isinstance(dt, time):
        raise ValueError("Time objects not supported - use datetime")
    
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone=tz or pytz.UTC)
    return dt

def get_current_time_in_company_tz(employee):
    """Get current time in employee's company timezone"""
    try:
        company_tz = get_company_timezone(employee)
        now_utc = timezone.now()
        return now_utc.astimezone(company_tz)
    except Exception as e:
        logger.error(f"Failed to get current time in company timezone: {e}")
        return timezone.now()

def validate_punch_times(time_in, time_out, company_tz):
    """Validate punch in and punch out times"""
    if not time_in or not time_out:
        return False, "Both punch in and punch out times are required"
    
    try:
        # Ensure both times are timezone-aware
        if timezone.is_naive(time_in):
            time_in = timezone.make_aware(time_in, timezone=company_tz)
        if timezone.is_naive(time_out):
            time_out = timezone.make_aware(time_out, timezone=company_tz)
        
        # Convert to company timezone for comparison
        time_in_tz = time_in.astimezone(company_tz)
        time_out_tz = time_out.astimezone(company_tz)
        
        if time_out_tz <= time_in_tz:
            return False, "Punch out time must be after punch in time"
        
        return True, "Valid punch times"
        
    except Exception as e:
        logger.error(f"Error validating punch times: {e}")
        return False, f"Error validating times: {str(e)}"

