import shutil
import os
import json
import time
import logging
import threading
import webview
from webview import Window
from word2number import w2n
from singleton import SETTINGS
from cardinal_state import CardinalState
from Player.speech_manager import listen_for_commands
from Player.audio_manager import AudioController
from Player.audib_manager import *
from Player.audib_manifest_model import PageData, TextID
from Player.voice_manager import generate_voice, generate_cardinal_audio, generate_book_title_audio, generate_dynamic_audio
from Processor.processor import TextbookProcessor

logging.basicConfig(
    level=logging.DEBUG,  # Capture DEBUG level and above (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

class Cardinal:
    def __init__(self, window: Window):
        self.window = window
        self.root_dir: Path = Path(Path.home(), "Documents") 
        self.current_path: Path = self.root_dir
        self.state: CardinalState = CardinalState.INTRO_PAGE
        self.speech_listener_off_event = threading.Event()
        self.audio_controller = AudioController(self)
        self.manifest: dict[int, PageData]
        self.current_page_number: int
        self.audib: Path
        self.position: TextID
        self._repeat_lock = threading.Lock()
        self._repeat_cancel_event = threading.Event()
        self._repeat_replay_event = threading.Event()
        self._repeat_threads = set()

        condition_1 = not Path("Data", "Cardinal Audios", "system_prompts", "app_greet.wav").is_file()
        condition_2 = SETTINGS.cardinal_voice_character.strip().casefold() != SETTINGS.voice_character.strip().casefold()
        condition_3 = SETTINGS.cardinal_voice_speed != SETTINGS.voice_speed
        if condition_1 or condition_2  or condition_3:
            log.debug("Invalid Cardinal Audio detected. Regenerating audio.")
            if Path("Data", "Cardinal Audios").exists():
                shutil.rmtree(str(Path("Data", "Cardinal Audios")))
                
            generate_cardinal_audio()

    def initialize_app_greet(self):
        self.state = CardinalState.INTRO_PAGE
        audio_path = Path("Data", "Cardinal Audios", "system_prompts", "app_greet.wav")
        self._audio_repeater(
            repeat_command=self.initialize_app_greet,
            repeat_delay=15.0,
            audio_delay=1.0,
            audio_path=audio_path,
            is_wav=True
        )

    def initialize_speech_receiver(self):
        receiver = threading.Thread(daemon=False, target=listen_for_commands, args=(self, self.speech_listener_off_event))
        receiver.start()
        log.info("Speech receiver initialized.")

    def receive_command(self, text: str ):
        # map command keywords to their respective player actions
        commands = [
            # system &global commands
            ("command exit", lambda: self.shutdown()),
            ("command help", lambda: self.help_audio()),
            ("command repeat", lambda: self.audio_controller.replay()),
            ("command go back", lambda: self.go_back()),
            ("command main menu", lambda: self.main_menu()),

            # menu & configuration choices
            ("command list books", lambda: self.list_books()),
            ("command upload", lambda: self.upload_book()),
            ("command options", lambda: self.option_menu()),
            ("command change voice", lambda: self.change_voice()),
            ("command change speed", lambda: self.change_speed()),

            # book session flow
            ("command resume", lambda: self.resume_reading()),
            ("command start over", lambda: self.start_over_reading()),

            # playback controls
            ("command stop", lambda: self.audio_controller.pause()),
            ("command pause", lambda: self.audio_controller.pause()),
            ("command play", lambda: self.audio_controller.resume()),
            ("command continue", lambda: self.audio_controller.resume()),

            # reader navigation & context
            ("command explain more", lambda: self.start_audio_hyperlink()),
            ("command jump forward", lambda: self.next_audio()),
            ("command go forward", lambda: self.next_audio()),
            ("command jump backward", lambda: self.previous_audio()),
            ("command go backward", lambda: self.previous_audio()),
            ("command move page", lambda: self.move_page()),

            ("change grace", lambda: self._change_voice_to("Grace")),
            ("change jane", lambda: self._change_voice_to("Jane")),
            ("change raven", lambda: self._change_voice_to("Raven")),

            # directory navigation
            ("command move back", lambda: self.move_back()),
        ]

        earliest_keyword = None
        earliest_action = None
        min_index = float('inf')

        # find which command appears first in the text
        for keyword, action in commands:
            idx = text.find(keyword)
            if idx != -1 and idx < min_index:
                min_index = idx
                earliest_keyword = keyword
                earliest_action = action

        is_waiting_for_value = (self.state == CardinalState.WAITING_FOR_NUMBER or self.state == CardinalState.WAITING_FOR_BOOK or self.state == CardinalState.WAITING_FOR_OPTION or self.state == CardinalState.WAITING_FOR_PATH)
        if is_waiting_for_value and earliest_keyword not in ("command repeat", "command help", "command go back", "command exit", "command main menu", "command pause", "command stop", "command play", "command continue"):
            self._cancel_repeating_audio()
            log.debug(f"Received raw text for number conversion: '{text}'")
                
            try:
                provided_number = w2n.word_to_num(text) # convert to int
                log.info(f"Successfully converted voice to number: {provided_number}")

                match self.state:
                    case CardinalState.WAITING_FOR_NUMBER:
                        if provided_number in list(self.manifest.keys()):
                            def _move_page():
                                self.state = CardinalState.READING
                                self.current_page_number = provided_number
                                self.position = TextID(page_number = self.manifest[self.current_page_number].page_number, block_id = "block_1")

                                self._play_current_reading_audio()

                            audio_path = Path("Data", "Cardinal Audios", "book_session", "page_moved.wav")
                            self.audio_controller.play(data=audio_path, is_wav=True, delay=0.0, on_complete=_move_page)

                        else:
                            def _continue():
                                self.state = CardinalState.WAITING_FOR_NUMBER

                            self.state = CardinalState.MAIN_MENU # not reading cuz move back and front become unlocked
                            audio_path = Path("Data", "Cardinal Audios", "book_session", "no_page_exists.wav")
                            self.audio_controller.play(data=audio_path, is_wav=True, delay=0.0, on_complete=_continue)

                    case CardinalState.WAITING_FOR_BOOK:
                        book_titles = sorted(item.name for item in Path("Data", "Books").iterdir() if item.is_file() and str(item).endswith(".audib"))
                        for idx, title in enumerate(book_titles, start=1):
                            if idx == provided_number:
                                self.load_audib(Path("Data", "Books", title))
                                return

                        def _retry():
                            self.state = CardinalState.WAITING_FOR_BOOK

                        self.state = CardinalState.MAIN_MENU
                        audio_path = Path("Data", "Cardinal Audios", "book_titles", "no_book.wav")
                        self.audio_controller.play(data=audio_path, is_wav=True, delay=0.0, on_complete=_retry)                        

                    case CardinalState.WAITING_FOR_OPTION:
                        if -100 <= provided_number and provided_number <= 100:  
                            SETTINGS.voice_speed = 1 + (-1 * (provided_number / 100)) # 1.2 means 20% slow so have to be inverted

                            audio_path = Path("Data", "Cardinal Audios", "system_prompts", "voice_speed_changed.wav")
                            self.audio_controller.play(data=audio_path, is_wav=True, delay=0.0, on_complete=self.option_menu)
                        else:
                            def _retry():
                                self.state = CardinalState.WAITING_FOR_OPTION

                            self.state = CardinalState.OPTIONS_MENU
                            audio_path = Path("Data", "Cardinal Audios", "system_prompts", "voice_speed_invalid.wav")
                            self.audio_controller.play(data=audio_path, is_wav=True, delay=0.0, on_complete=_retry)

                    case CardinalState.WAITING_FOR_PATH:
                        directory: list[str] = []
                        folders, files = self._get_directory_contents()
                        directory = folders + files

                        for idx, name in enumerate(directory, start=1):
                            if idx == provided_number:
                                if name.endswith(".pdf") or name.endswith(".audib"): # loadable file
                                    file = self._select_file(name)

                                    if file and file.suffix == ".pdf":
                                        self.state = CardinalState.PATH_LISTING
                                        processor = TextbookProcessor(file)
                                        processor.process_textbook()

                                        self.create_audib(Path("Books", name.removesuffix(".pdf"), "json"))
                                        self.load_audib(Path("Data", "Books", f"{name.removesuffix(".pdf")}.audib"))
                                        return
                                    else:
                                        destination_path = Path("Data", "Books")
                                        destination_path.mkdir(parents=True, exist_ok=True)

                                        shutil.copy2(file, destination_path) # copy to always make it available from menu
                                        generate_book_title_audio() # make title audio for it
                                        self.load_audib(Path("Data", "Books", name))
                                        return
                                    
                                else:
                                    def _new_dir_listing():
                                        self.state = CardinalState.PATH_LISTING
                                        directory_list_names = self._navigate_open(name)

                                        audio_bytes, phrase_durations = generate_dynamic_audio(directory_list_names)
                                        self._audio_repeater(
                                            repeat_command=_new_dir_listing,
                                            repeat_delay=10.0,
                                            audio_delay=1.0,
                                            audio_path=audio_bytes,
                                            is_wav=False,
                                            state_change=CardinalState.WAITING_FOR_PATH,
                                            audio_subtitle=' '.join(directory_list_names),
                                            audio_subtitle_phrases=directory_list_names,
                                            audio_subtitle_phrase_durations=phrase_durations,
                                        )

                                    _new_dir_listing()
                                    return
                            
                        def _retry():
                            self.state = CardinalState.WAITING_FOR_PATH

                        self.state = CardinalState.PATH_LISTING
                        audio_path = Path("Data", "Cardinal Audios", "system_prompts", "no_folder_file.wav")
                        self.audio_controller.play(data=audio_path, is_wav=True, delay=0.0, on_complete=_retry)        
        
            except ValueError:
                log.warning(f"Could not parse a valid number from: '{text}'")

        # Execute only the single earliest command found
        elif earliest_action:
            log.debug(f"Detected command: \"{earliest_keyword.split(maxsplit=1)[1]}\"")
            if earliest_keyword in ("command stop", "command pause", "command play", "command continue"):
                earliest_action()
            elif earliest_keyword == "command repeat":
                with self._repeat_lock:
                    has_repeat_thread = bool(self._repeat_threads)
                    if has_repeat_thread:
                        self._repeat_replay_event.set()

                if not has_repeat_thread:
                    earliest_action()
            else:
                self._cancel_repeating_audio()
                earliest_action()

    def initialize_audio_data_sender(self):
        threading.Thread(target=self.send_audio_data_to_gui, daemon=True).start()
    
    def send_audio_data_to_gui(self):
        last_subtitle = None
        while True:
            levels = self.audio_controller.get_current_audio_levels()
            self.window.evaluate_js(
                "window.viz.setAudioLevels("
                f"{levels[0]:.3f},{levels[1]:.3f},{levels[2]:.3f},{levels[3]:.3f})"
            )
            
            subtitle = self.audio_controller.subtitle
            if subtitle != last_subtitle:
                self.window.evaluate_js(f"window.viz.setSubtitle({json.dumps(subtitle)})")
                last_subtitle = subtitle

            time.sleep(1 / 30)

    def _cancel_repeating_audio(self):
        with self._repeat_lock:
            self._repeat_cancel_event.set()
            self._repeat_replay_event.set()
            repeat_threads = tuple(self._repeat_threads)

        if repeat_threads:
            self.audio_controller.stop()
            for repeat_thread in repeat_threads:
                if repeat_thread is not threading.current_thread():
                    repeat_thread.join()

    def create_audib(self, json_root_path: Path):
        log.info("Synthesizing audio...")
        generate_voice(json_root_path)
        log.info("Audio synthesized.")

        log.info("Generating audib file...")
        Path("Data", "Books").mkdir(parents=True, exist_ok=True)
        generate_audib(
            output_filename=str(Path("Data", f"{json_root_path.parent}.audib")), 
            manifest_path=Path(json_root_path, "manifest.json"),
            audio_folder=Path("audio")
        )
        log.info("Finished creating audib file.")

        generate_book_title_audio()

        if os.path.exists("audio"):
            shutil.rmtree("audio")            
            log.info("Removed temp data.")

    def load_audib(self, audib_file: Path):
        self._save_book_position()

        self.audib = audib_file
        self.manifest = read_audib_manifest(self.audib)

        log.debug("Audib file manifest loaded.")
        self.initialize_book_reading()

    def list_books(self):
        self._save_book_position()
        book_titles = sorted(item.name for item in Path("Data", "Books").iterdir() if item.is_file() and str(item).endswith(".audib"))

        def _play_title(index: int):
            if index == (len(book_titles) - 1):
                self._audio_repeater(
                    repeat_command=self.list_books,
                    repeat_delay=15.0,
                    audio_delay=1.0,
                    is_wav=True,
                    audio_path=Path("Data", "Cardinal Audios", "book_titles", "titles", f"{index + 1}.wav"),
                    state_change=CardinalState.WAITING_FOR_BOOK
                )
                return

            audio_path = Path("Data", "Cardinal Audios", "book_titles", "titles", f"{index + 1}.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=lambda: _play_title(index + 1))

        if book_titles:
            audio_path = Path("Data", "Cardinal Audios", "book_titles", "intro.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=lambda: _play_title(0))
        else:
            audio_path = Path("Data", "Cardinal Audios", "system_prompts", "no_book.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.main_menu)

    def initialize_book_reading(self):
        self.state = CardinalState.READING

        if self.audib in list(SETTINGS.saved_book_positions.keys()):
            audio_path = Path("Data", "Cardinal Audios", "book_session", "resume_prompt.wav")
            self._audio_repeater(
                repeat_command=self.initialize_book_reading,
                repeat_delay=15.0,
                audio_delay=0.0,
                audio_path=audio_path,
                is_wav=True
            )
        else:
            self.start_over_reading()

    def resume_reading(self):
        if not self.state == CardinalState.READING: # this command is only allowed on reading mode
            return
        self.current_page_number = SETTINGS.saved_book_positions[self.audib][1]
        self.position = SETTINGS.saved_book_positions[self.audib][0]

        self._play_current_reading_audio()

    def start_over_reading(self):
        if not self.state == CardinalState.READING: # this command is only allowed on reading mode
            return
        pages = list(self.manifest.keys())
        pages.sort()
        self.current_page_number = pages[0] # the first page number, it doesn't necessarily have to be page number: 1
        self.position = TextID(page_number = self.manifest[self.current_page_number].page_number, block_id = "block_1")

        self._play_current_reading_audio()

    def start_audio_hyperlink(self):
        if not self.state == CardinalState.READING: # this command is only allowed on reading mode
            return

        def play_audio_hyperlink():
            self._play_current_reading_audio() # position has been updated to link_1
        
        if self.manifest[self.current_page_number].reading_flow[self._get_id(self.position.block_id)-1].audio_hyperlinks and not self.position.link_id:
            self.position.link_id = "link_1"
            audio_path = Path("Data", "Cardinal Audios", "book_session", "audio_hyperlink_started.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=play_audio_hyperlink) # the controller auto calls play_audio_hyperlink to start
        else:
            audio_path = Path("Data", "Cardinal Audios", "book_session", "no_audio_hyperlink.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=self.replay_audio) # the controller auto plays the paused block

    def go_back(self):
        match self.state:
            case CardinalState.INTRO_PAGE:
                audio_path = Path("Data", "Cardinal Audios", "system_prompts", "no_go_back.wav")
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.initialize_app_greet)

            case CardinalState.MAIN_MENU:
                self.initialize_app_greet()

            case CardinalState.WAITING_FOR_BOOK:
                self.main_menu()

            case CardinalState.OPTIONS_MENU:
                self.main_menu()

            case CardinalState.VOICE_OPTION:
                self.option_menu()

            case CardinalState.WAITING_FOR_OPTION:
                self.option_menu()

            case CardinalState.READING:
                self.list_books()

            case CardinalState.WAITING_FOR_NUMBER:
                self.state = CardinalState.READING
                self._play_current_reading_audio()

            case CardinalState.PATH_LISTING:
                self.main_menu()

            case CardinalState.WAITING_FOR_PATH:
                self.main_menu()

            case _:
                log.warning("A user have achieved the impossible with creating an 8th state of Cardinal!")

    def main_menu(self):
        self._save_book_position()
        self.state = CardinalState.MAIN_MENU
        def _option_1():
            audio_path = Path("Data", "Cardinal Audios", "menus", "main_menu", "options", "1.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_2)

        def _option_2():
            audio_path = Path("Data", "Cardinal Audios", "menus", "main_menu", "options", "2.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_3)

        def _option_3():
            audio_path = Path("Data", "Cardinal Audios", "menus", "main_menu", "options", "3.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_4)

        def _option_4():
            audio_path = Path("Data", "Cardinal Audios", "menus", "main_menu", "options", "4.wav")
            self._audio_repeater(
                repeat_command=self.main_menu,
                repeat_delay=15.0,
                audio_delay=1.0,
                audio_path=audio_path,
                is_wav=True
            )

        audio_path = Path("Data", "Cardinal Audios", "menus", "main_menu", "intro.wav")
        self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_1)

    def option_menu(self):
        self._save_book_position()
        self.state = CardinalState.OPTIONS_MENU
        def _option_1():
            audio_path = Path("Data", "Cardinal Audios", "menus", "options_menu", "options", "1.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_2)

        def _option_2():
            audio_path = Path("Data", "Cardinal Audios", "menus", "options_menu", "options", "2.wav")
            self._audio_repeater(
                repeat_command=self.option_menu,
                repeat_delay=15.0,
                audio_delay=1.0,
                audio_path=audio_path,
                is_wav=True
            )

        audio_path = Path("Data", "Cardinal Audios", "menus", "options_menu", "intro.wav")
        self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_1)

    def change_voice(self):
        self._save_book_position()
        self.state = CardinalState.VOICE_OPTION
        def _option_1():
            audio_path = Path("Data", "Cardinal Audios Test", "Clara.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_2)

        def _option_2():
            audio_path = Path("Data", "Cardinal Audios Test", "Grace.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_3)
 
        def _option_3():
            audio_path = Path("Data", "Cardinal Audios Test", "Raven.wav")
            self._audio_repeater(
                repeat_command=self.change_voice,
                repeat_delay=15.0,
                audio_delay=1.0,
                audio_path=audio_path,
                is_wav=True,
            )

        audio_path = Path("Data", "Cardinal Audios", "system_prompts", "voice_option.wav")
        self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_option_1)

    def change_speed(self):
        self._save_book_position()
        audio_path = Path("Data", "Cardinal Audios", "system_prompts", "voice_speed.wav")
        self._audio_repeater(
            repeat_command=self.change_speed,
            repeat_delay=15.0,
            audio_delay=1.0,
            audio_path=audio_path,
            is_wav=True,
            state_change=CardinalState.WAITING_FOR_NUMBER
        )

    def previous_audio(self):
        if not self.state == CardinalState.READING: # this command is only allowed on reading mode
            return
        
        if self.position.link_id:
            current_link = self._get_id(self.position.link_id)

            # checks if the current link is not the first index
            if (current_link - 1) != 0:
                self.position.link_id = f"link_{current_link - 1}"
            else:
                self.position.link_id = None # go back to the block
                self.replay_audio()
                return
        else:
            current_block = self._get_id(self.position.block_id)

            # checks if the current block is not the first index
            if (current_block - 1) != 0:
                self.position.block_id = f"block_{current_block - 1}"
            else:
                log.debug("Audib finished")
                return

        self._play_current_reading_audio()

    def next_audio(self):
        if not self.state == CardinalState.READING: # this command is only allowed on reading mode
            return
        
        current_block = self._get_id(self.position.block_id)

        if self.position.link_id:
            current_link = self._get_id(self.position.link_id)
            links_length = len(self.manifest[self.current_page_number].reading_flow[current_block - 1].audio_hyperlinks)

            # checks if the current audio hyperlink is not the last link
            if (links_length - 1) != (current_link - 1):
                self.position.link_id = f"link_{current_link + 1}"
            else:
                self.position.link_id = None # move back the block to replay the block
                self.replay_audio()
                return
        else:
            blocks_length = len(self.manifest[self.current_page_number].reading_flow)

            # checks if the current audio block is not the last block
            if (blocks_length - 1) != (current_block - 1):
                self.position.block_id = f"block_{current_block + 1}"
            else:
                log.debug("Audib finished")
                return
        
        self._play_current_reading_audio()

    def help_audio(self):
        def _replay():
            self.audio_controller.play(
                data=audio_replay_path,
                is_wav=False if self.state == CardinalState.READING else True,
                delay=1.0,
                subtitle=self._current_reading_subtitle() if self.state == CardinalState.READING else "",
            )

        match self.state:
            case CardinalState.INTRO_PAGE:
                audio_path = Path("Data", "Cardinal Audios", "system_prompts", "help_general.wav")
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.initialize_app_greet)
                return

            case CardinalState.MAIN_MENU:
                audio_path = Path("Data", "Cardinal Audios", "menus", "main_menu", "help.wav")
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.main_menu)
                return

            case CardinalState.WAITING_FOR_BOOK:
                audio_path = Path("Data", "Cardinal Audios", "book_titles", "help_chose_title.wav")
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.list_books)
                return

            case CardinalState.OPTIONS_MENU:
                audio_path = Path("Data", "Cardinal Audios", "menus", "options_menu", "help.wav")
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.option_menu)
                return
            
            case CardinalState.VOICE_OPTION:
                audio_path = Path("Data", "Cardinal Audios", "system_prompts", "help_general.wav")
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.change_voice)
                return

            case CardinalState.WAITING_FOR_OPTION:
                audio_path = Path("Data", "Cardinal Audios", "menus", "options_menu", "help.wav")
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.change_speed)
                return

            case CardinalState.READING:
                audio_path = Path("Data", "Cardinal Audios", "book_session", "help_active_reader.wav")
                audio_replay_path = read_audib_audio(self.audib, self._generate_audio_path(self.position))

            case CardinalState.WAITING_FOR_NUMBER:
                audio_path = Path("Data", "Cardinal Audios", "system_prompts", "help_general.wav")
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.move_page)

            case _:
                audio_path = Path("Data", "Cardinal Audios", "system_prompts", "help_general.wav")
                audio_replay_path = Path("Data", "Cardinal Audios", "system_prompts", "app_greet.wav")

        self.audio_controller.play(data=audio_path, is_wav=True, on_complete=_replay)

    def replay_audio(self):
            def _replay():
                self._play_current_reading_audio(delay=1.0)

            audio_path = Path("Data", "Cardinal Audios", "system_prompts", "replaying.wav")
            self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=_replay)

    def move_page(self):
        if not self.state == CardinalState.READING: # this command is only allowed on reading mode
            return
        audio_path = Path("Data", "Cardinal Audios", "system_prompts", "number.wav")
        self._audio_repeater(
            repeat_command=self.move_page,
            repeat_delay=15.0,
            audio_delay=1.0,
            audio_path=audio_path,
            is_wav=True,
            state_change=CardinalState.WAITING_FOR_NUMBER
        )

    def upload_book(self):
        self.state = CardinalState.PATH_LISTING
        self.audio_controller.stop()
        initial_text_list = self._generate_spoken_dir_list()
        audio_bytes, phrase_durations = generate_dynamic_audio(initial_text_list)
        self._audio_repeater(
            repeat_command=self.upload_book,
            repeat_delay=10.0,
            audio_delay=1.0,
            audio_path=audio_bytes,
            is_wav=False,
            state_change=CardinalState.WAITING_FOR_PATH,
            audio_subtitle=' '.join(initial_text_list),
            audio_subtitle_phrases=initial_text_list,
            audio_subtitle_phrase_durations=phrase_durations,
        )

    def move_back(self):
        if self.state != CardinalState.PATH_LISTING:
            return
        
        if self.current_path > self.root_dir:
            self.current_path = self.current_path.parent
            log.info(f"Moved back to: {self.current_path}")
            self.audio_controller.stop()
            directory_list_names = self._generate_spoken_dir_list()

            def _dir_listing():
                audio_bytes, phrase_durations = generate_dynamic_audio(directory_list_names)
                self._audio_repeater(
                    repeat_command=_dir_listing,
                    repeat_delay=10.0,
                    audio_delay=1.0,
                    audio_path=audio_bytes,
                    is_wav=False,
                    state_change=CardinalState.WAITING_FOR_PATH,
                    audio_subtitle=' '.join(directory_list_names),
                    audio_subtitle_phrases=directory_list_names,
                    audio_subtitle_phrase_durations=phrase_durations,
                )

    def shutdown(self):
        def close_listener_loop():
            SETTINGS.save()
            self.speech_listener_off_event.set()
            self._save_book_position()
            log.debug("Speech receiver closed successfully")
            self.window.destroy()

        audio_path = Path("Data", "Cardinal Audios", "system_prompts", "exit_app.wav")
        self.audio_controller.play(data=audio_path, is_wav=True, delay=1.0, on_complete=close_listener_loop)

    def _navigate_open(self, target_name: str) -> str:
        target_path = self.current_path / target_name
        if target_path.is_dir():
            self.current_path = target_path.resolve()
            log.info(f"Navigated into: {self.current_path}")
            return self._generate_spoken_dir_list()
        return "Folder not found. Please try again with different folder."

    def _select_file(self, filename: str) -> Path | None:
        file_path = self.current_path / filename
        if file_path.is_file() and file_path.suffix.lower() in ['.pdf', '.audib']:
            log.info(f"File selected for ingestion: {file_path}")
            return file_path
        return None

    def _get_directory_contents(self) -> tuple[list[str], list[str]]:
        folders = [d.name for d in self.current_path.iterdir() if d.is_dir()]
        files = [f.name for f in self.current_path.iterdir() if f.is_file() and f.suffix.lower() in ['.pdf', '.audib']]
        return sorted(folders), sorted(files)

    def _generate_spoken_dir_list(self) -> list[str]:
        folders, files = self._get_directory_contents()
        
        location_name = self.current_path.name if self.current_path != self.root_dir else "Documents"

        directory_list: list[str] = []
        directory_list.append(f"Currently inside the folder {location_name}. To load a folder or a file please say the number at which it is located. For example to load a folder that is listed on the fifth position say the number five.")
        folder_count = 0
        
        if folders:
            directory_list.append("Currently available folders to open are.")
            for idx, name in enumerate(folders, start=1):
                directory_list.append(f"Location {idx}. {name}.")
                folder_count += 1
        if files:
            directory_list.append("Currently available files to load are.")
            for idx, name in enumerate(files, start=folder_count+1):
                directory_list.append(f"Location {idx}. {name}.")
        if not folders and not files:
            directory_list.append("The current folder is empty. To go back to the previous folder say the starter key followed by move back.")
            
        return directory_list

    def _change_voice_to(self, voice: str):
        SETTINGS.cardinal_voice_character = voice

        def _replay():
            self.audio_controller.play(
                data=audio_replay_path,
                is_wav=False if self.state == CardinalState.READING else True,
                delay=1.0,
                subtitle=self._current_reading_subtitle() if self.state == CardinalState.READING else "",
            )

        audio_path = Path("Data", "Cardinal Audios", "system_prompts", "voice_changed.wav")

        match self.state:
            case CardinalState.INTRO_PAGE:
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.initialize_app_greet)
                return

            case CardinalState.MAIN_MENU:
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.main_menu)
                return

            case CardinalState.WAITING_FOR_BOOK:
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.list_books)
                return

            case CardinalState.OPTIONS_MENU:
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.option_menu)
                return
            
            case CardinalState.VOICE_OPTION:
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.option_menu)
                return
            
            case CardinalState.WAITING_FOR_OPTION:
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.change_speed)
                return

            case CardinalState.READING:
                audio_replay_path = read_audib_audio(self.audib, self._generate_audio_path(self.position))
            
            case CardinalState.WAITING_FOR_NUMBER:
                self.audio_controller.play(data=audio_path, is_wav=True, on_complete=self.move_page)
                return

            case _:
                audio_replay_path = Path("Data", "Cardinal Audios", "system_prompts", "app_greet.wav")

        self.audio_controller.play(data=audio_path, is_wav=True, on_complete=_replay)

    def _save_book_position(self):
        try:
            if self.audib and self.manifest and self.current_page_number and self.position:
                SETTINGS.saved_book_positions[self.audib] = [self.position, self.current_page_number]
        except Exception as e:
            return # we don't care just save if stars align or smth        

    def _generate_audio_path(self, textID: TextID) -> str:
        if textID.link_id:
            return f"page{textID.page_number}_{textID.block_id}_{textID.link_id}.wav"
        else:
            return f"page{textID.page_number}_{textID.block_id}.wav"

    def _current_reading_subtitle(self) -> str:
        block = self.manifest[self.current_page_number].reading_flow[self._get_id(self.position.block_id) - 1]
        if self.position.link_id:
            link = block.audio_hyperlinks[self._get_id(self.position.link_id) - 1]
            return f"{link.term}: {link.explanation}"
        if block.context_title:
            return f"{block.context_title}. {block.text}"
        return block.text

    def _play_current_reading_audio(self, delay: float = 0.0):
        audio_bytes = read_audib_audio(self.audib, self._generate_audio_path(self.position))
        self.audio_controller.play(
            audio_bytes,
            delay=delay,
            subtitle=self._current_reading_subtitle(),
        )

    def _get_id(self, data: str) -> int:
        name, id = data.split("_")
        return int(id)

    def _audio_repeater(self, repeat_command: function, repeat_delay: float, audio_delay: float, audio_path: Path, is_wav: bool, state_change: CardinalState = None, audio_subtitle: str = "", audio_subtitle_phrases: list[str] | None = None, audio_subtitle_phrase_durations: tuple[float, ...] | None = None):
        current_thread = threading.current_thread()
        with self._repeat_lock:
            if current_thread in self._repeat_threads:
                cancel_event = self._repeat_cancel_event
            elif self._repeat_threads:
                return
            else:
                cancel_event = threading.Event()
                self._repeat_cancel_event = cancel_event
                self._repeat_replay_event = threading.Event()

            replay_event = self._repeat_replay_event

            if cancel_event.is_set():
                return

            def _repeat():
                playback_finished = threading.Event()

                def start_playback() -> bool:
                    with self._repeat_lock:
                        def on_playback_complete():
                            if state_change is not None:
                                self.state = state_change
                            playback_finished.set()

                        if cancel_event.is_set():
                            return False
                        playback_finished.clear()
                        self.audio_controller.play(
                            data=audio_path,
                            is_wav=is_wav,
                            delay=0.0,
                            on_complete=on_playback_complete,
                            subtitle=audio_subtitle,
                            has_phrase_pauses=audio_subtitle_phrases is not None,
                            subtitle_phrases=audio_subtitle_phrases,
                            subtitle_phrase_durations=audio_subtitle_phrase_durations,
                        )
                        return self.audio_controller.is_playing

                try:
                    replay_event.wait(audio_delay)
                    replay_event.clear()
                    if cancel_event.is_set():
                        return

                    if not start_playback():
                        return

                    while True:
                        while not playback_finished.wait(0.1):
                            if cancel_event.is_set():
                                return
                            if replay_event.is_set():
                                replay_event.clear()
                                if not start_playback():
                                    return

                        if cancel_event.is_set():
                            return

                        if replay_event.wait(repeat_delay):
                            replay_event.clear()
                            if cancel_event.is_set():
                                return
                            if not start_playback():
                                return
                        else:
                            if cancel_event.is_set():
                                return
                            repeat_command()
                            return
                finally:
                    with self._repeat_lock:
                        self._repeat_threads.discard(threading.current_thread())

            repeat_thread = threading.Thread(target=_repeat, daemon=True)
            self._repeat_threads.add(repeat_thread)
            repeat_thread.start()