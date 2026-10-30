import os
import json
import wave
from piper import PiperVoice
from piper.config import SynthesisConfig
from pathlib import Path
from Player.audib_manifest_model import PageData

VOICE_CHARACTER = "Minerva"
MODEL_PATH = Path("Voices", VOICE_CHARACTER, f"{VOICE_CHARACTER}.onnx")

# load the voice model
voice = PiperVoice.load(MODEL_PATH)

def readJson(jsonPath: Path) -> PageData:
    with open(jsonPath, 'r') as file:
        data = json.load(file)
    return PageData(**data)

def test():
    # Configure custom parameters for accessibility
    syn_config = SynthesisConfig(length_scale=1.2) # > 1.0 slows down speech (1.2 is 20% slower)

    text_to_read = readJson(Path("Book", "1", "189.json")).reading_flow[1].text

    output_path = Path("Test", f"{VOICE_CHARACTER}_test.wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), "wb") as wav_file:
        voice.synthesize_wav(text_to_read, wav_file, syn_config=syn_config)

    print(f"Generated accessible audio at: {output_path}")
