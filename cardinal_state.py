from enum import Enum, auto

class CardinalState(Enum):
    MENU = auto()
    BOOK_PROMPT = auto()
    READING = auto()
    WAITING_FOR_NUMBER = auto()