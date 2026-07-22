from pydantic import BaseModel, Field, ConfigDict
from typing import NamedTuple

class BBOX(NamedTuple):
    """A class to store the coordinates of various content in an extracted page"""
    min_x: float
    min_y: float
    max_x: float
    max_y: float


class BaseClass(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        )

class SpanContent(BaseClass):
    size: float = Field(..., description="Font size of the text span")
    font: str = Field(..., description="Font of the text span")
    color: int = Field(..., description="Color of the text span")
    alpha: int = Field(..., description="Alpha value of the text span")
    text: str = Field(..., description="Text content of the span")


class LineContent(BaseClass):
    spans: list[SpanContent] = Field(..., description="List of text spans in the line")
    bbox: BBOX = Field(..., description="Bounding box coordinates of the text span")


class BlockContent(BaseClass):
    type: int = Field(..., description="Type of the block content. It's either a text represented with 0 or an image represented with 1")
    number: int = Field(..., description="Block content number on the page in order of appearance")
    bbox: BBOX = Field(..., description="Overall bounding box coordinates of the block content")
    lines: list[LineContent] = Field(..., description="List of lines in the block")

class PageContent(BaseClass):
    page_number: int = Field(..., description="Page number in the PDF document")
    width: float = Field(..., description="Width of the page")
    height: float = Field(..., description="Height of the page")
    blocks: list[BlockContent] = Field(..., description="Block content on the page")

class PDFContent(BaseClass):
    job_id : str = Field(..., description="Unique identifier for the PDF processing job")
    total_pages: int = Field(..., description="Total number of pages in the PDF document")
    pages: list[PageContent] = Field(..., description="List of page contents in the PDF document")