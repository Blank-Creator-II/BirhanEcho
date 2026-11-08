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

_AUDIO_QUEUE_MAX_CHUNKS = 8
_queue = queue.Queue(maxsize=_AUDIO_QUEUE_MAX_CHUNKS)
_dropped_audio_chunks = 0

def audio_receiver(indata, frames, time, status): # captures microphone input.
    global _dropped_audio_chunks
    if status:
        log.warning("Microphone callback status: %s (frames=%s)", status, frames)

    audio_chunk = bytes(indata)
    try:
        _queue.put_nowait(audio_chunk)
    except queue.Full:
        try:
            _queue.get_nowait()
        except queue.Empty:
            pass
        _queue.put_nowait(audio_chunk)
        _dropped_audio_chunks += 1
        if _dropped_audio_chunks == 1 or _dropped_audio_chunks % 100 == 0:
            log.warning(
                "Microphone queue full; dropped oldest audio chunks to stay current: total_dropped=%s",
                _dropped_audio_chunks,
            )

def clear_audio_queue():
    cleared_count = 0
    while not _queue.empty():
        try:
            _queue.get_nowait()
            cleared_count += 1
        except queue.Empty:
            break
    log.info(
        "Cleared %s pending microphone audio chunks; total_overflow_drops=%s",
        cleared_count,
        _dropped_audio_chunks,
    )

def listen_for_commands(cardinal: "Cardinal", stop_event: threading.Event):
    sample_rate = 16000  # needs 16kHz audio
    previous_state = None
    previous_partial = ""

    # Open stream explicitly at 16kHz mono
    log.info("Opening microphone stream: samplerate=%s blocksize=%s dtype=int16 channels=1", sample_rate, 4000)
    try:
        with sounddevice.RawInputStream(samplerate=sample_rate, blocksize=4000, dtype='int16', channels=1, callback=audio_receiver):
            log.info("Voice engine active at %sHz. Listening for commands...", sample_rate)

            while not stop_event.is_set():
                try:
                    # Use a timeout so the loop wakes up and checks stop_event regularly
                    data = _queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if stop_event.is_set():
                    break

                current_state = cardinal.state
                if current_state != previous_state:
                    log.info("Speech recognizer state changed: %s", current_state)
                    previous_state = current_state
                    previous_partial = ""

                # Select recognizer instance based on current Cardinal state
                is_waiting_for_value = current_state in (
                    CardinalState.WAITING_FOR_NUMBER,
                    CardinalState.WAITING_FOR_BOOK,
                    CardinalState.WAITING_FOR_OPTION,
                    CardinalState.WAITING_FOR_PATH,
                )
                recognizer_name = "number" if is_waiting_for_value else "commands"
                active_recognizer = number_recognizer if is_waiting_for_value else command_recognizer

                if active_recognizer.AcceptWaveform(data):
                    result = json.loads(active_recognizer.Result())
                    text = result.get("text", "").strip()
                    log.info(
                        "Vosk final result: state=%s recognizer=%s text=%r result=%s",
                        current_state,
                        recognizer_name,
                        text,
                        result,
                    )
                    previous_partial = ""

                    if text and text != "[unk]":
                        log.debug("Dispatching recognized speech to Cardinal: %r", text)
                        cardinal.receive_command(text)
                    else:
                        log.debug("Ignoring empty or unknown Vosk result: %r", text)
                else:
                    partial_result = json.loads(active_recognizer.PartialResult())
                    partial_text = partial_result.get("partial", "").strip()
                    if partial_text and partial_text != previous_partial:
                        log.debug(
                            "Vosk partial result: state=%s recognizer=%s text=%r",
                            current_state,
                            recognizer_name,
                            partial_text,
                        )
                    previous_partial = partial_text
    except Exception:
        log.exception("Speech input stream or recognition loop failed.")
        raise
    finally:
        log.info("Speech input loop stopped: stop_requested=%s", stop_event.is_set())