from enum import Enum, auto

class CardinalState(Enum):
    INTRO_PAGE = auto()
    MAIN_MENU = auto()
    WAITING_FOR_BOOK = auto()
    WAITING_FOR_PATH = auto()
    OPTIONS_MENU = auto()
    WAITING_FOR_OPTION = auto()
    VOICE_OPTION = auto()
    READING = auto()
    WAITING_FOR_NUMBER = auto()
    PATH_LISTING = auto()
    LOADING = auto()