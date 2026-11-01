import shutil
import os
import logging
import threading
import time
from word2number import w2n
from cardinal_state import CardinalState
from Player.speech_manager import listen_for_commands, clear_audio_queue
from Player.audio_manager import AudioController
from Player.audib_manager import *
from Player.audib_manifest_model import PageData, TextID
from Player.voice_manager import generate_voice, generate_cardinal_audio

logging.basicConfig(
    level=logging.DEBUG,  # Capture DEBUG level and above (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

class Cardinal:
    def __init__(self):
        self.state: CardinalState = CardinalState.MENU
        self.speech_listener_off_event = threading.Event()
        self.audio_controller = AudioController(self)
        self.manifest: PageData
        self.audib: Path
        self.position: TextID

        if not Path("Data", "Cardinal_Audio", "system_prompts-app_greet.wav").is_file():
            log.debug("No Cardinal audio detected. Generating audio.")
            generate_cardinal_audio()

    def initialize_speech_receiver(self):
        receiver = threading.Thread(daemon=False, target=listen_for_commands, args=(self, self.speech_listener_off_event))
        receiver.start()
        log.info("Speech receiver initialized.")

    def receive_command(self, text: str ):
        if self.state == CardinalState.WAITING_FOR_NUMBER and text != "command repeat":
            log.debug(f"Received raw text for number conversion: '{text}'")
                
            try:
                page_num = w2n.word_to_num(text) # convert to int
                log.info(f"Successfully converted voice to page number: {page_num}")

                audio_path = Path("Data", "Cardinal_Audio", "book_session-page_moved.wav")
                self.audio_controller.play(data=audio_path, menu=True, delay=0.0)
                # TODO:
                # self.load_page(page_num)
                
                self.state = CardinalState.READING
                
            except ValueError:
                log.warning(f"Could not parse a valid number from: '{text}'")
        else:
            # map command keywords to their respective player actions
            commands = [
                ("command repeat", lambda: self.audio_controller.replay()),
                ("command stop", lambda: self.audio_controller.pause()),
                ("command pause", lambda: self.audio_controller.pause()),

                ("command play", lambda: self.audio_controller.resume()),
                ("command continue", lambda: self.audio_controller.resume()),

                ("command exit", lambda: self.shutdown()),

                ("command jump forward", lambda: self.next_audio()),
                ("command go forward", lambda: self.next_audio()),

                ("command jump backward", lambda: self.previous_audio()),
                ("command go backward", lambda: self.previous_audio()),
                
                ("command explain more", lambda: self.start_audio_hyperlink()),
                ("command move page", lambda: self.receive_number())
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

            # Execute only the single earliest command found
            if earliest_action:
                log.debug(f"Detected command: \"{earliest_keyword.split(maxsplit=1)[1]}\"")
                earliest_action()

    def create_audib(self, json_path: Path):
        log.info("Synthesizing audio...")
        generate_voice(json_path)
        log.info("Audio synthesized.")

        log.info("Generating audib file...")
        generate_audib(str(Path("Data", "Placeholder.audib")), json_path, Path("audio"))
        log.info("Finished creating audib file.")

        if os.path.exists("audio"):
            shutil.rmtree("audio")            
            log.info("Removed temp data.")

    def load_audib(self, audib_file: Path):
        self.audib = audib_file
        self.manifest = read_audib_manifest(self.audib)
        log.debug("Audib file manifest loaded.")

        #self.audio_controller.play(Path("Menu"))
    
    def initialize_audio(self):
        self.state = CardinalState.READING
        self.position = TextID(
            page_number = self.manifest.page_number,
            block_id = "block_1",
            link_id = self.manifest.reading_flow[0].audio_hyperlinks[0].id if len(self.manifest.reading_flow[0].audio_hyperlinks) != 0 else None 
        )

        audio_bytes = read_audib_audio(self.audib, self._generate_audio_path(self.position))
        self.audio_controller.play(audio_bytes)

    def start_audio_hyperlink(self):
        if not self.state == CardinalState.READING: # this command is only allowed on reading mode
            return

        def play_audio_hyperlink():
            audio_bytes = read_audib_audio(self.audib, self._generate_audio_path(self.position)) # position have been updated to link_1
            self.audio_controller.play(audio_bytes)
        
        if self.manifest.reading_flow[self._get_id(self.position.block_id)-1].audio_hyperlinks and not self.position.link_id:
            self.position.link_id = "link_1"
            audio_path = Path("Data", "Cardinal_Audio", "book_session-audio_hyperlink_started.wav")
            self.audio_controller.play(data=audio_path, menu=True, delay=1.0, on_complete=play_audio_hyperlink) # the controller auto calls play_audio_hyperlink to start
        else:
            audio_path = Path("Data", "Cardinal_Audio", "book_session-no_audio_hyperlink.wav")
            self.audio_controller.play(data=audio_path, menu=True, delay=1.0, on_complete=self.replay_audio) # the controller auto calls self.next_audio()
    
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

        audio_bytes = read_audib_audio(self.audib, self._generate_audio_path(self.position))
        self.audio_controller.play(audio_bytes)        

    def next_audio(self):
        if not self.state == CardinalState.READING: # this command is only allowed on reading mode
            return
        
        current_block = self._get_id(self.position.block_id)

        if self.position.link_id:
            current_link = self._get_id(self.position.link_id)
            links_length = len(self.manifest.reading_flow[current_block - 1].audio_hyperlinks)

            # checks if the current audio hyperlink is not the last link
            if (links_length - 1) != (current_link - 1):
                self.position.link_id = f"link_{current_link + 1}"
            else:
                self.position.link_id = None # move back the block to replay the block
                self.replay_audio()
                return
        else:
            blocks_length = len(self.manifest.reading_flow)

            # checks if the current audio block is not the last block
            if (blocks_length - 1) != (current_block - 1):
                self.position.block_id = f"block_{current_block + 1}"
            else:
                log.debug("Audib finished")
                return
        
        audio_bytes = read_audib_audio(self.audib, self._generate_audio_path(self.position))
        self.audio_controller.play(audio_bytes)

    def replay_audio(self):
            def _replay():
                audio_bytes = read_audib_audio(self.audib, self._generate_audio_path(self.position))
                self.audio_controller.play(audio_bytes, delay=1.0)

            audio_path = Path("Data", "Cardinal_Audio", "system_prompts-replaying.wav")
            self.audio_controller.play(data=audio_path, menu=True, delay=1.0, on_complete=_replay)

    def receive_number(self):
        def on_prompt_finished():
            clear_audio_queue()
            self.state = CardinalState.WAITING_FOR_NUMBER
            log.debug("System prompt finished. Switched to WAITING_FOR_NUMBER state.")

        audio_path = Path("Data", "Cardinal_Audio", "system_prompts-number.wav")
        self.audio_controller.play(data=audio_path, menu=True, delay=1.0, on_complete=on_prompt_finished)

    def shutdown(self):
        def close_listener_loop():
            self.speech_listener_off_event.set()

        audio_path = Path("Data", "Cardinal_Audio", "system_prompts-exit_app.wav")
        self.audio_controller.play(data=audio_path, menu=True, delay=1.0, on_complete=close_listener_loop)
   
    def _generate_audio_path(self, textID: TextID) -> str:
        if textID.link_id:
            return f"page{textID.page_number}_{textID.block_id}_{textID.link_id}.wav"
        else:
            return f"page{textID.page_number}_{textID.block_id}.wav"

    def _get_id(self, data: str) -> int:
        name, id = data.split("_")
        return int(id)
    