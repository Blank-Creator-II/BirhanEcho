from enum import Enum, auto

class CardinalState(Enum):
    INTRO_PAGE = auto()
    MAIN_MENU = auto()
    WAITING_FOR_BOOK = auto()
    OPTIONS_MENU = auto()
    WAITING_FOR_OPTION = auto()
    READING = auto()
    WAITING_FOR_NUMBER = auto()