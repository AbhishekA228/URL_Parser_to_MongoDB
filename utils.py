from langdetect import detect

def is_english(text):
    """
    Check if the given text is in English using langdetect.
    """
    try:
        return detect(text) == 'en'
    except Exception:
        return False
