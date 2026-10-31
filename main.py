import time
from pathlib import Path
from Player.voice_manager import generate_voice
from Player.audib_manager import generate_audib
from Player.audio_manager import AudioController

if __name__ == "__main__":
    json_path = Path("Book", "1", "189.json")

    """
    generate_voice(json_path)
    generate_audib("test.audib", json_path, Path("audio"))
    
    controller = AudioController()
    controller.play(Path("test.audib"),5)
    time.sleep(3)
    controller.pause()
    time.sleep(4)
    controller.resume()
    time.sleep(7)
    controller.replay()
    time.sleep(10)
    """