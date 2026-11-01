import io
import threading
import time
import logging
from pygame import mixer
from typing import TYPE_CHECKING, Callable, Optional
from cardinal_state import CardinalState

if TYPE_CHECKING:
    from cardinal_system import Cardinal

log = logging.getLogger(__name__)

class AudioController:
    POLL_INTERVAL = 0.05   # how often the watcher checks for end-of-track
    START_GRACE = 0.2      # ignore "not busy" briefly right after starting

    def __init__(self, cardinal: "Cardinal"):
        self.cardinal = cardinal
        self.is_playing = False
        self.is_paused = False

        self.current_on_complete_method = None
        self._lock = threading.RLock()
        self._token = 0
        
        # Store raw data and type instead of a volatile stream object
        self._raw_data = None 
        self._is_menu = False

        if not mixer.get_init():
            mixer.init()

    def play(self, data, menu: bool = False, delay: float = 1.0, on_complete: Optional[Callable[[], None]] = None):
        # claim a new token immediately: this cancels any older pending play()
        with self._lock:
            self._token += 1
            token = self._token
            self._halt()

        # pause between track transitions
        if delay > 0:
            time.sleep(delay)

        with self._lock:
            if token != self._token:
                return  # superseded by a newer play()/stop() during the delay

            # Save reference parameters for clean replaying
            self._raw_data = data
            self._is_menu = menu
            self.current_on_complete_method = on_complete

            source = io.BytesIO(data) if not menu else data
            try:
                mixer.music.load(source)
                mixer.music.play()
            except Exception as e:
                log.error(f"Failed to play audio: {e}")
                self._raw_data = None
                self.is_playing = self.is_paused = False
                return

            self.is_playing = True
            self.is_paused = False
            self._start_watcher(token, on_complete)
        log.debug(f"Playing audio track.")

    def pause(self):
        with self._lock:
            if self.is_playing and not self.is_paused:
                mixer.music.pause()
                self.is_paused = True
                log.debug("Playback paused.")

    def resume(self):
        with self._lock:
            if self.is_playing and self.is_paused:
                mixer.music.unpause()
                self.is_paused = False
                log.debug("Playback resumed.")

    def toggle_pause(self):
        with self._lock:
            if self.is_paused:
                self.resume()
            else:
                self.pause()

    def stop(self):
        with self._lock:
            self._token += 1  # invalidate watcher / pending play()
            self._halt()
            log.debug("Playback stopped.")

    def replay(self):
        with self._lock:
            if self._raw_data is None:
                log.warning("Replay requested, but no audio source is loaded.")
                return
            
            self._token += 1
            token = self._token
            
            try:
                # always generate a fresh BytesIO stream from the stored raw bytes so we don't get ValueError: I/O operation on closed file.
                source = io.BytesIO(self._raw_data) if not self._is_menu else self._raw_data
                mixer.music.stop()
                mixer.music.load(source)
                mixer.music.play()
            except Exception as e:
                log.error(f"Failed to replay audio: {e}")
                return

            self.is_playing = True
            self.is_paused = False
            self._start_watcher(token, on_complete=self.current_on_complete_method)
            log.debug("Restarted playback.")

    def get_position(self) -> float:
        with self._lock:
            return mixer.music.get_pos() / 1000 if self.is_playing else -1.0

    def on_end(self):
        self.cardinal.next_audio()

    def _halt(self):
        mixer.music.stop()
        self.is_playing = False
        self.is_paused = False

    def _start_watcher(self, token: int, on_complete: Optional[Callable[[], None]]):
        threading.Thread(
            target=self._watch, args=(token, on_complete), daemon=True
        ).start()

    def _watch(self, token: int, on_complete: Optional[Callable[[], None]]):
        started = time.monotonic()
        while True:
            time.sleep(self.POLL_INTERVAL)
            with self._lock:
                if token != self._token:
                    return  # stopped, replaced, or replayed: not our track
                if self.is_paused:
                    continue
                if time.monotonic() - started < self.START_GRACE:
                    continue
                if mixer.music.get_busy():
                    continue

                # finished naturally
                self.is_playing = False
                self.is_paused = False
                self._token += 1  # make sure nothing else fires for this track

            log.debug("End of audio reached.")
            
            # Execute the specific completion callback if provided, otherwise check state
            if on_complete:
                on_complete()
            elif self.cardinal.state == CardinalState.READING:
                self.on_end()
            return