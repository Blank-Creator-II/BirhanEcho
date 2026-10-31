from typing import List, Optional
from pydantic import BaseModel, Field

class AudioHyperlink(BaseModel):
    id: str
    term: str
    explanation: str
    audio_file: str

class Block(BaseModel):
    id: str
    type: str
    text: str
    audio_file: str
    # Handles empty lists automatically if "audio_hyperlinks": [] is passed
    audio_hyperlinks: List[AudioHyperlink] = Field(default_factory=list)
    
    # Optional field:
    context_title: Optional[str] = None

class PageData(BaseModel):
    page_number: int
    reading_flow: List[Block]

class TextID(BaseModel):
    page_number: int
    block_id: str
    # Optional field:
    link_id: Optional[str] = None