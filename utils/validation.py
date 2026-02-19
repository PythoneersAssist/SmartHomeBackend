import re

def validate_email(email: str) -> bool:
    """
    Validates an email using a complex regex.
    """
    # Regex explanation:
    # ^[a-zA-Z0-9_.+-]+ : Start with alphanumeric, dot, underscore, plus, or hyphen.
    # @                 : Literal @ symbol.
    # [a-zA-Z0-9-]+     : Domain name part (alphanumeric, hyphen).
    # \.                : Literal dot.
    # [a-zA-Z0-9-.]+$   : TLD part (alphanumeric, hyphen, dot).
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(email_regex, email) is not None

def validate_password(password: str) -> bool:
    """
    Validates a password based on:
    - Minimum length of 8 characters
    - At least one uppercase letter
    - At least one number
    - At least one symbol
    """
    if len(password) < 8:
        return False
    
    if len(password) > 72:
        return False
    
    if not re.search(r"[a-z]", password):
        return False
        
    if not re.search(r"[A-Z]", password):
        return False
        
    if not re.search(r"\d", password):
        return False
        
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
        
    return True
