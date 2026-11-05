from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class AudioHyperlink(BaseModel):
    id: str = Field(..., description="Unique hyperlink identifier (e.g., 'link_1')")
    term: str = Field(..., description="The key term being explained")
    explanation: str = Field(..., description="Explanation of the term")
    audio_file: str = Field(..., description="Relative path to the audio file for this hyperlink")


class ContentBlock(BaseModel):
    id: str = Field(..., description="Unique block identifier (e.g., 'block_1')")
    type: Literal["heading", "subheading", "paragraph", "sidebar", "activity",
                  "diagram", "graph", "equation"] = Field(..., description="Type of content")
    text: str = Field(..., description="Teacher-style explanation of the content")
    audio_file: str = Field(..., description="Relative path to the main audio file")
    audio_hyperlinks: Optional[List[AudioHyperlink]] = Field(
        default=None,
        description="Audio hyperlinks for key terms in this block"
    )
    context_title: Optional[str] = Field(
        default=None,
        description="Title for sidebars or special content boxes"
    )


class PageData(BaseModel):
    page_number: int = Field(
        ...,
        description="Printed textbook page number, not the PDF page position",
    )
    reading_flow: List[ContentBlock] = Field(..., description="Ordered list of content blocks")


class ProcessingProgress(BaseModel):
    book_id: str
    total_pages: int
    completed_pages: List[int] = Field(default_factory=list)
    failed_pages: List[int] = Field(default_factory=list)
    current_page: Optional[int] = None
    status: Literal["not_started", "in_progress", "paused", "completed", "failed"] = "not_started"
    last_updated: Optional[str] = None
    page_errors: dict[str, str] = Field(default_factory=dict)
    prompt_hash: Optional[str] = None
