import json
import queue
import threading
import sounddevice
import logging
from pathlib import Path
from vosk import Model, KaldiRecognizer
from Player.audio_manager import AudioController
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardinal_system import Cardinal

log = logging.getLogger(__name__)

model_path = str(Path("Vosk", "model"))
model = Model(model_path)

# command list
allowed_commands = [
    "command exit",

    "command repeat", 
    "command stop", 
    "command pause",

    "command play", 
    "command continue",

    "command explain more",

    "command jump forward",
    "command go forward",

    "command jump backward",
    "command go backward", 

    "command move to page",
    "[unk]"  # if unknown word
]

# Vosk expects a JSON string array for grammar constraint aka the commands
recognizer = KaldiRecognizer(model, 16000, json.dumps(allowed_commands))

_queue = queue.Queue()

def audio_receiver(indata, frames, time, status): # captures microphone input.
    if status:
        log.warning(f"Audio status warning: {status}", flush=True)

    _queue.put(bytes(indata))

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

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").strip()
                        
                        if text and text != "[unk]":
                            cardinal.receive_command(text)