import shutil
import os
import logging
import threading
import time
from Player.speech_manager import listen_for_commands
from Player.audio_manager import AudioController
from Player.audib_manager import *
from Player.audib_manifest_model import PageData, TextID
from Player.voice_manager import generate_voice

logging.basicConfig(
    level=logging.DEBUG,  # Capture DEBUG level and above (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

log = logging.getLogger(__name__)

class Cardinal:
    def __init__(self):
        self.speech_listener_off_event = threading.Event()
        self.audio_controller = AudioController(self)
        self.manifest: PageData
        self.audib: Path
        self.position: TextID

    def initialize_speech_receiver(self):
        receiver = threading.Thread(daemon=False, target=listen_for_commands, args=(self, self.speech_listener_off_event))
        receiver.start()
        log.info("Speech receiver initialized.")

    def receive_command(self, text: str ):
        # map command keywords to their respective player actions
        commands = [
            ("command repeat", lambda: self.audio_controller.replay()),
            ("command stop", lambda: self.audio_controller.stop()),
            ("command pause", lambda: self.audio_controller.pause()),

            ("command play", lambda: self.audio_controller.resume()),
            ("command continue", lambda: self.audio_controller.resume()),

            ("command exit", lambda: self.shutdown()),

            ("command jump forward", lambda: self.next_audio()),
            ("command go forward", lambda: self.next_audio()),

            ("command jump backward", lambda: self.previous_audio()),
            ("command go backward", lambda: self.previous_audio()),
            
            #TODO:
            #("command explain more", lambda: placeholder),
            #("command move to page", lambda: placeholder)
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

        log.debug(f"Detected command: \"{earliest_keyword.split(maxsplit=1)[1]}\"")
        # Execute only the single earliest command found
        if earliest_action:
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
        self.position = TextID(
            page_number = self.manifest.page_number,
            block_id = "block_1",
            link_id = self.manifest.reading_flow[0].audio_hyperlinks[0].id if len(self.manifest.reading_flow[0].audio_hyperlinks) != 0 else None 
        )

        audio_bytes = read_audib_audio(self.audib, self._generate_audio_path(self.position))
        self.audio_controller.play(audio_bytes)

    def previous_audio(self):
        if self.position.link_id:
            current_link = self._get_id(self.position.link_id)

            # checks if the current link is not the first index
            if (current_link - 1) != 0:
                self.position.link_id = f"link_{current_link - 1}"
            else:
                self.position.link_id = None
                self.previous_audio() # call again to go back to previous block
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
        current_block = self._get_id(self.position.block_id)

        if self.position.link_id:
            current_link = self._get_id(self.position.link_id)
            links_length = len(self.manifest.reading_flow[current_block - 1].audio_hyperlinks)

            # checks if the current audio hyperlink has more links and if it is not the last link
            if links_length > 1 and (links_length - 1) != (current_link - 1):
                self.position.link_id = f"link_{current_link + 1}"
            else:
                self.position.link_id = None
                self.next_audio() # call again to move to next block
                return
        else:
            blocks_length = len(self.manifest.reading_flow)

            # checks if the current audio block has more blocks and if it is not the last block
            if blocks_length > 1 and (blocks_length - 1) != (current_block - 1):
                self.position.block_id = f"block_{current_block + 1}"
            else:
                log.debug("Audib finished")
                return
        
        audio_bytes = read_audib_audio(self.audib, self._generate_audio_path(self.position))
        self.audio_controller.play(audio_bytes)

    def shutdown(self):
        self.speech_listener_off_event.set()
        self.audio_controller.stop()

    def _generate_audio_path(self, textID: TextID) -> str:
        if textID.link_id:
            return f"page{textID.page_number}_{textID.block_id}_{textID.link_id}.wav"
        else:
            return f"page{textID.page_number}_{textID.block_id}.wav"

    def _get_id(self, data: str) -> int:
        name, id = data.split("_")
        return int(id)