import io
import threading
import time
import logging
from pygame import mixer
from typing import TYPE_CHECKING

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

        self._lock = threading.RLock()
        self._token = 0
        self._source = None  # keep a reference so the BytesIO isn't dumped to garbage

        if not mixer.get_init():
            mixer.init()

    def play(self, data, menu: bool = False, delay: float = 1.0):
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

            source = io.BytesIO(data) if not menu else data
            try:
                mixer.music.load(source)
                mixer.music.play()
            except Exception as e:
                log.error(f"Failed to play audio: {e}")
                self._source = None
                self.is_playing = self.is_paused = False
                return

            self._source = source
            self.is_playing = True
            self.is_paused = False
            self._start_watcher(token)
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
            if self._source is None:
                return
            self._token += 1
            token = self._token
            try:
                if isinstance(self._source, io.BytesIO):
                    self._source.seek(0)
                mixer.music.stop()
                mixer.music.load(self._source)
                mixer.music.play()
            except Exception as e:
                log.error(f"Failed to replay audio: {e}")
                return
            self.is_playing = True
            self.is_paused = False
            self._start_watcher(token)
            log.debug("Restarted playback.")

    def get_position(self) -> float:
        # seconds played since the last start (pause-aware). -1 if idle
        with self._lock:
            return mixer.music.get_pos() / 1000 if self.is_playing else -1.0

    def on_end(self):
        self.cardinal.next_audio()

    # internal bs
    def _halt(self):
        # stop output and reset flags, caller must hold the lock
        mixer.music.stop()
        self.is_playing = False
        self.is_paused = False

    def _start_watcher(self, token: int):
        threading.Thread(
            target=self._watch, args=(token,), daemon=True
        ).start()

    def _watch(self, token: int):
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
            self.on_end()  # outside the lock: next_audio() will call play()
            return