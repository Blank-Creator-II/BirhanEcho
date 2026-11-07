import json
import queue
import threading
import sounddevice
import logging
from pathlib import Path
from vosk import Model, KaldiRecognizer
from Player.audio_manager import AudioController
from typing import TYPE_CHECKING
from cardinal_state import CardinalState

if TYPE_CHECKING:
    from cardinal_system import Cardinal

log = logging.getLogger(__name__)

model_path = str(Path("Vosk", "model"))
model = Model(model_path)

# command list
allowed_commands = [
    # system & global commands
    "command exit",
    "command help",
    "command repeat",
    "command go back",
    "command main menu",

    # menu & configuration choices
    "command list books",
    "command upload",
    "command options",
    "command change voice",
    "command change speed",

    # book session flow
    "command resume",
    "command start over",

    # playback controls
    "command stop", 
    "command pause",
    "command play", 
    "command continue",

    # reader navigation & context
    "command explain more",
    "command jump forward",
    "command go forward",
    "command jump backward",
    "command go backward", 
    "command move page",

    # voice options
    "change grace",
    "change jane",
    "change raven",

    # directory navigation
    "command move back",
    
    "[unk]"  # Unknown word catch-all for Vosk grammar constraint
]

# constrained recognizer for system commands
command_recognizer = KaldiRecognizer(model, 16000, json.dumps(allowed_commands))

# open recognizer for numeric inputs
number_recognizer = KaldiRecognizer(model, 16000)

_queue = queue.Queue()

def audio_receiver(indata, frames, time, status): # captures microphone input.
    if status:
        log.warning(f"Audio status warning: {status}", flush=True)

    _queue.put(bytes(indata))

def clear_audio_queue():
    while not _queue.empty():
        try:
            _queue.get_nowait()
        except queue.Empty:
            break

def listen_for_commands(cardinal: "Cardinal", stop_event: threading.Event):
    sample_rate = 16000  # needs 16kHz audio

    # Open stream explicitly at 16kHz mono
    with sounddevice.RawInputStream(samplerate=sample_rate, blocksize=4000, dtype='int16', channels=1, callback=audio_receiver):
        log.info(f"Voice engine active at {sample_rate}Hz. Listening for commands...")
        
        while not stop_event.is_set():
                    try:
                        # Use a timeout so the loop wakes up and checks stop_event regularly
                        data = _queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    if stop_event.is_set():
                        break

                    # Select recognizer instance based on current Cardinal state
                    is_waiting_for_value = (cardinal.state == CardinalState.WAITING_FOR_NUMBER or cardinal.state == CardinalState.WAITING_FOR_BOOK or cardinal.state == CardinalState.WAITING_FOR_OPTION or cardinal.state == CardinalState.WAITING_FOR_PATH)
                    if is_waiting_for_value:
                        active_recognizer = number_recognizer
                    else:
                        active_recognizer = command_recognizer

                    if active_recognizer.AcceptWaveform(data):
                        result = json.loads(active_recognizer.Result())
                        text = result.get("text", "").strip()
                        
                        if text and text != "[unk]":
                            cardinal.receive_command(text)