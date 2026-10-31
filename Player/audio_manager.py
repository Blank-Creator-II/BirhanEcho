import io
from pathlib import Path
import time
import sounddevice
import soundfile
from Player.audib_manifest_model import PageData
from Player.audib_manager import read_audib_audio, read_audib_manifest

class AudioController:
    
    def __init__(self):
        self.current_data = None
        self.sample_rate = None
        self.current_frame = 0
        self.start_time = None
        self.is_playing = False
        self.is_paused = False

    def play(self, audib_file: Path, block: int):
        manifest = read_audib_manifest(audib_file)

        # Fetch audio bytes for the requested block
        audio_bytes = read_audib_audio(audib_file, manifest.reading_flow[block - 1].audio_file)

        # Stop any ongoing playback
        sounddevice.stop()

        # Read data from BytesIO buffer into a numpy array
        with io.BytesIO(audio_bytes) as buffer:
            self.current_data, self.sample_rate = soundfile.read(buffer)

        # Reset position and start playing from the beginning
        self.current_frame = 0
        self._play_slice()
        print(f"Playing block {block} in the background...")

    def _play_slice(self): # helper method to play audio starting from self.current_frame
        if self.current_data is None:
            return

        # Slice the array from the current frame to the end
        audio_slice = self.current_data[self.current_frame :]
        if len(audio_slice) == 0:
            print("End of audio reached.")
            return

        sounddevice.play(audio_slice, self.sample_rate)
        self.start_time = time.time()
        self.is_playing = True
        self.is_paused = False

    def pause(self):
        if self.is_playing and not self.is_paused:
            # Calculate how many frames played since we started/resumed
            elapsed_time = time.time() - self.start_time
            played_frames = int(elapsed_time * self.sample_rate)

            # Update our overall frame position
            self.current_frame += played_frames

            # Prevent going past the audio's length
            if self.current_frame > len(self.current_data):
                self.current_frame = len(self.current_data)

            sounddevice.stop()
            self.is_playing = False
            self.is_paused = True
            print("Playback paused.")

    def resume(self):
        if self.is_paused:
            self._play_slice()
            print("Playback resumed.")

    def stop(self):
        sounddevice.stop()
        self.current_frame = 0
        self.is_playing = False
        self.is_paused = False
        print("Playback stopped.")

    def replay(self):
        if self.current_data is not None:
            sounddevice.stop()
            sounddevice.play(self.current_data, self.sample_rate)
            self.is_playing = True
            print("Restarted playback.")