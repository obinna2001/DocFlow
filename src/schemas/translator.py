from pydantic import BaseModel, Field
from enum import Enum

class LanguageCode(str, Enum):
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


class TranslationRequest(BaseModel):
    """A model to validate user translation language field"""
    source_language: LanguageCode | None = Field(
        default=None,
        description="Source language. If None, language will be auto-detected"
    )

    target_language: LanguageCode