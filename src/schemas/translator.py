from enum import Enum

class SupportedLanguages(str, Enum):
    """A class to store all DocFlow supported languages and their codes"""
    ENGLISH = "en"
    GERMAN = "de"
    FRENCH = "fr"
    SPANISH = "es"
    PORTUGUESE = "pt"
    ITALIAN = "it"
    DUTCH = "nl"
    CHINESE = "zh"
    JAPANESE = "ja"
    ARABIC = "ar"
    YORUBA = "yo"
    HAUSA = "ha"
    IGBO = "ig"
    DEFAULT = None