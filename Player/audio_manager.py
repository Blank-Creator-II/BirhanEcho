import io
import json
import threading
import time
import logging
import re
import wave
import numpy as np
from pygame import mixer
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional
from cardinal_state import CardinalState

if TYPE_CHECKING:
    from cardinal_system import Cardinal

log = logging.getLogger(__name__)

class AudioController:
    POLL_INTERVAL = 0.05   # how often the watcher checks for end-of-track
    START_GRACE = 0.2      # ignore "not busy" briefly right after starting
    MAX_SUBTITLE_WORDS = 10

    def __init__(self, cardinal: "Cardinal"):
        self.cardinal = cardinal
        self.is_playing = False
        self.is_paused = False

        self.current_on_complete_method = None
        self._lock = threading.RLock()
        self._token = 0
        
        # Store raw data and type instead of a volatile stream object
        self._raw_data = None 
        self._is_wav = False
        self._sample_reader: Optional[wave.Wave_read] = None
        self._subtitle = ""
        self._subtitle_schedule: tuple[tuple[float, str], ...] = ()
        self._audio_duration = 0.0
        self._play_started_at = 0.0
        self._static_subtitles = self._load_static_subtitles()

        if not mixer.get_init():
            mixer.init()

    def play(self, data, is_wav: bool = False, delay: float = 1.0, on_complete: Optional[Callable[[], None]] = None, subtitle: str = "",):
        # claim a new token immediately: this cancels any older pending play()
        with self._lock:
            self._token += 1
            token = self._token
            self._halt()
            self._subtitle = ""
            self._subtitle_schedule = ()
            self._audio_duration = 0.0
            self._play_started_at = 0.0
            self._close_sample_reader()

        # pause between track transitions
        if delay > 0:
            time.sleep(delay)

        with self._lock:
            if token != self._token:
                return  # superseded by a newer play()/stop() during the delay

            # Save reference parameters for clean replaying
            self._raw_data = data
            self._is_wav = is_wav
            self.current_on_complete_method = on_complete

            source = io.BytesIO(data) if not is_wav else data
            try:
                mixer.music.load(source)
            except Exception as e:
                log.error(f"Failed to play audio: {e}")
                self._raw_data = None
                self._close_sample_reader()
                self.is_playing = self.is_paused = False
                return

            audio_duration = 0.0
            try:
                sample_source = str(data) if is_wav else io.BytesIO(data)
                self._sample_reader = wave.open(sample_source, "rb")
                frame_rate = self._sample_reader.getframerate()
                if frame_rate > 0:
                    audio_duration = self._sample_reader.getnframes() / frame_rate
                if self._sample_reader.getsampwidth() != 2:
                    log.warning("Audio visualization supports 16-bit PCM WAV files only.")
                    self._close_sample_reader()
            except (wave.Error, EOFError, OSError) as e:
                log.warning(f"Unable to read audio samples for visualization: {e}")
                self._close_sample_reader()

            try:
                mixer.music.play()
            except Exception as e:
                log.error(f"Failed to play audio: {e}")
                self._raw_data = None
                self._close_sample_reader()
                self.is_playing = self.is_paused = False
                return

            self.is_playing = True
            self.is_paused = False
            self._subtitle = subtitle or self._get_static_subtitle(data)
            self._audio_duration = audio_duration
            self._subtitle_schedule = self._make_subtitle_schedule(self._subtitle, audio_duration)
            self._play_started_at = time.monotonic()
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
            self._subtitle = ""
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
                source = io.BytesIO(self._raw_data) if not self._is_wav else self._raw_data
                mixer.music.stop()
                mixer.music.load(source)
                mixer.music.play()
                self._play_started_at = time.monotonic()
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
                self._subtitle = ""
                self._token += 1  # make sure nothing else fires for this track

            log.debug("End of audio reached.")
            
            # Execute the specific completion callback if provided, otherwise check state
            if on_complete:
                on_complete()
            elif self.cardinal.state == CardinalState.READING:
                self.on_end()
            return

    def get_current_audio_levels(self) -> tuple[float, float, float, float]:
        with self._lock:
            if not self.is_playing or self.is_paused or self._sample_reader is None:
                return 0.0, 0.0, 0.0, 0.0

            pos_ms = mixer.music.get_pos()
            if pos_ms < 0:
                return 0.0, 0.0, 0.0, 0.0

            reader = self._sample_reader
            frame_position = int(pos_ms * reader.getframerate() / 1000)
            if frame_position >= reader.getnframes():
                return 0.0, 0.0, 0.0, 0.0

            reader.setpos(frame_position)
            chunk = reader.readframes(2048)
            if not chunk:
                return 0.0, 0.0, 0.0, 0.0

            channels = reader.getnchannels()
            audio_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            if channels > 1:
                audio_array = audio_array.reshape(-1, channels).mean(axis=1)
            audio_array /= 32768.0
            rms = float(np.sqrt(np.mean(audio_array**2)))

            spectrum = np.fft.rfft(audio_array * np.hanning(len(audio_array)))
            frequencies = np.fft.rfftfreq(len(audio_array), d=1 / reader.getframerate())
            power = np.abs(spectrum) ** 2
            if len(audio_array) > 1:
                power[1:-1] *= 2
            power /= len(audio_array) ** 2

            def band_level(low: float, high: float) -> float:
                band_power = power[(frequencies >= low) & (frequencies < high)]
                return min(float(np.sqrt(np.sum(band_power))) * 5.0, 1.0)

            overall = min(rms * 3.5, 1.0)
            low = band_level(60, 300)
            mid = band_level(300, 2400)
            high = band_level(2400, reader.getframerate() / 2 + 1)
            return overall, low, mid, high

    def get_current_volume_level(self) -> float:
        return self.get_current_audio_levels()[0]

    @property
    def subtitle(self) -> str:
        with self._lock:
            if not self.is_playing or self.is_paused or not self._subtitle:
                return ""
            if not self._subtitle_schedule or self._audio_duration <= 0:
                return self._subtitle

            position = mixer.music.get_pos()
            if position < 0:
                if time.monotonic() - self._play_started_at < self.START_GRACE:
                    return self._subtitle_schedule[0][1]
                return ""
            elapsed = position / 1000
            for end_time, chunk in self._subtitle_schedule:
                if elapsed < end_time:
                    return chunk
            return self._subtitle_schedule[-1][1]

    @classmethod
    def _make_subtitle_schedule(cls, text: str, duration: float) -> tuple[tuple[float, str], ...]:
        if not text.strip() or duration <= 0:
            return ()

        chunks = []
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
            words = sentence.split()
            while len(words) > cls.MAX_SUBTITLE_WORDS:
                chunk_end = cls.MAX_SUBTITLE_WORDS
                for candidate in range(cls.MAX_SUBTITLE_WORDS, 7, -1):
                    if words[candidate - 1].endswith((",", ";", ":")):
                        chunk_end = candidate
                        break
                chunks.append(" ".join(words[:chunk_end]))
                words = words[chunk_end:]
            if words:
                chunks.append(" ".join(words))

        total_weight = sum(
            len(chunk.split()) + (0.35 if chunk.endswith((".", "!", "?")) else 0)
            for chunk in chunks
        )
        elapsed = 0.0
        schedule = []
        for index, chunk in enumerate(chunks):
            weight = len(chunk.split()) + (0.35 if chunk.endswith((".", "!", "?")) else 0)
            elapsed += duration * weight / total_weight
            if index == len(chunks) - 1:
                elapsed = duration
            schedule.append((elapsed, chunk))
        return tuple(schedule)

    def _load_static_subtitles(self) -> dict[str, str]:
        manifest_path = Path("Data", "cardinal_audios_manifest.json")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log.warning("Unable to load static audio subtitles from %s: %s", manifest_path, error)
            return {}

        if not isinstance(manifest, dict):
            log.warning("Static audio subtitle manifest must contain a JSON object.")
            return {}

        subtitles: dict[str, str] = {}
        audio_root = Path("Data", "Cardinal Audios")

        def add_subtitle(path: Path, text: object):
            if isinstance(text, str) and text.strip():
                subtitles[path.as_posix().casefold()] = text

        for category in ("system_prompts", "book_session", "book_titles"):
            entries = manifest.get(category, {})
            if isinstance(entries, dict):
                for key, text in entries.items():
                    add_subtitle(audio_root / category / f"{key}.wav", text)

        menus = manifest.get("menus", {})
        if isinstance(menus, dict):
            for menu_name, menu in menus.items():
                if not isinstance(menu, dict):
                    continue
                menu_root = audio_root / "menus" / menu_name
                for key in ("intro", "help"):
                    add_subtitle(menu_root / f"{key}.wav", menu.get(key))
                options = menu.get("options", [])
                if isinstance(options, list):
                    for option in options:
                        if isinstance(option, dict) and "id" in option:
                            add_subtitle(
                                menu_root / "options" / f"{option['id']}.wav",
                                option.get("spoken_text"),
                            )

        voice_tests = manifest.get("voice_test", {})
        if isinstance(voice_tests, dict):
            test_root = Path("Data", "Cardinal Audios Test")
            for voice_name, text in voice_tests.items():
                add_subtitle(test_root / f"{voice_name}.wav", text)

        books_root = Path("Data", "Books")
        if books_root.is_dir():
            book_titles = sorted(
                path.name for path in books_root.iterdir()
                if path.is_file() and path.suffix.casefold() == ".audib"
            )
            titles_root = audio_root / "book_titles" / "titles"
            for index, title in enumerate(book_titles, start=1):
                add_subtitle(titles_root / f"{index}.wav", Path(title).stem)

        log.debug("Loaded subtitles for %d static audio files.", len(subtitles))
        return subtitles

    def _get_static_subtitle(self, data: object) -> str:
        if not isinstance(data, (str, Path)):
            return ""

        audio_path = Path(data).as_posix().replace("\\", "/").casefold()
        for relative_path, text in self._static_subtitles.items():
            if audio_path == relative_path or audio_path.endswith(f"/{relative_path}"):
                return text
        return ""

    def _close_sample_reader(self):
        if self._sample_reader is not None:
            self._sample_reader.close()
            self._sample_reader = None