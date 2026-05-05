"""
Natural language time parsing for automation scheduling.
Converts user input like "at noon" or "every Monday at 9am" to system format.
"""
import re
from datetime import datetime, time
from typing import Optional


# Time keywords to minutes mapping
TIME_KEYWORDS = {
    "midnight": "00:00",
    "noon": "12:00",
    "morning": "06:00",
    "afternoon": "12:00",
    "evening": "18:00",
    "night": "21:00",
}

# Day names to day-of-week mapping (0=Monday, 6=Sunday)
DAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_time_value(text: str) -> Optional[str]:
    """
    Parse natural language time expressions to HH:MM format.
    
    Examples:
        "at noon" -> "12:00"
        "at 3:30pm" -> "15:30"
        "at 15:30" -> "15:30"
        "at 3 pm" -> "15:00"
    
    Returns:
        Time string in HH:MM format, or None if parsing fails.
    """
    text = text.lower().strip()
    
    # Check for keyword times
    for keyword, time_value in TIME_KEYWORDS.items():
        if keyword in text:
            return time_value
    
    # Pattern: "3:30pm", "3:30 pm", "15:30", "3pm", "3 pm"
    # Handle 12-hour format with am/pm
    pattern_12h = r'(\d{1,2}):?(\d{2})?\s*(am|pm|a\.m\.|p\.m\.)'
    match = re.search(pattern_12h, text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3).replace(".", "").lower()
        
        # Convert 12-hour to 24-hour
        if period.startswith('p') and hour != 12:
            hour += 12
        elif period.startswith('a') and hour == 12:
            hour = 0
        
        return f"{hour:02d}:{minute:02d}"
    
    # Handle 24-hour format: "15:30", "15", "3:30"
    pattern_24h = r'(\d{1,2}):?(\d{2})?'
    match = re.search(pattern_24h, text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    
    return None


def parse_execution_day(text: str) -> Optional[int]:
    """
    Parse day of week from natural language.
    
    Examples:
        "every monday" -> 0
        "on friday" -> 4
        "daily" -> None (not specific to one day)
    
    Returns:
        Day number (0=Monday, 6=Sunday), or None if not a specific day.
    """
    text = text.lower().strip()
    
    for day_name, day_num in DAY_NAMES.items():
        if day_name in text:
            return day_num
    
    return None


def parse_automation_schedule(text: str) -> dict[str, Optional[str | int]]:
    """
    Parse complete automation schedule from user text.
    
    Examples:
        "every monday at 9am" -> {"trigger_value": "09:00", "execution_day": 0}
        "daily at noon" -> {"trigger_value": "12:00", "execution_day": None}
        "at 3:30pm" -> {"trigger_value": "15:30", "execution_day": None}
    
    Returns:
        Dict with "trigger_value" (HH:MM) and "execution_day" (0-6 or None).
    """
    time_value = parse_time_value(text)
    day_value = parse_execution_day(text)
    
    return {
        "trigger_value": time_value,
        "execution_day": day_value,
    }
