import os
import json
import wave
from piper import PiperVoice
from piper.config import SynthesisConfig
from pathlib import Path
from Player.audib_manifest_model import PageData
from Player.audib_manifest_model import TextID

# load the voice model
VOICE_CHARACTER = "Minerva"
MODEL_PATH = Path("Voices", VOICE_CHARACTER, f"{VOICE_CHARACTER}.onnx")
voice = PiperVoice.load(MODEL_PATH)
syn_config = SynthesisConfig(length_scale=1.2) # > 1.0 slows down speech (1.2 is 20% slower)

def generate_voice(json_path: Path):
    manifest = read_json(json_path)
    process_manifest(manifest)

def read_json(json_path: Path) -> PageData:
    with open(json_path, 'r') as file:
        data = json.load(file)
    return PageData(**data)

def process_manifest(manifest: PageData):
    #Iterates through all blocks and hyperlinks in the page manifest to generate TextIDs and audio.
    page_number = manifest.page_number

    for block in manifest.reading_flow:
        # TextID for the main content block
        block_text_id = TextID(
            page_number=page_number,
            block_id=block.id,
            link_id=None
        )
        
        # Include context title if present and make the text to gen audio
        block_text = f"{block.context_title}... {block.text}" if block.context_title else block.text
        generate_audio(block_text, block_text_id)

        # TextID and audio for each audio hyperlink in the block
        for link in block.audio_hyperlinks:
            link_text_id = TextID(
                page_number=page_number,
                block_id=block.id,
                link_id=link.id
            )
            
            # Combine term and explanation to make the text to gen audio
            link_text = f"{link.term}... {link.explanation}"
            generate_audio(link_text, link_text_id)

def generate_audio(text_to_read: str, textID: TextID):
    if textID.link_id:
        audio_path = f"page{textID.page_number}_{textID.block_id}_{textID.link_id}.wav"
    else:
        audio_path = f"page{textID.page_number}_{textID.block_id}.wav"

    output_path = Path("audio", audio_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), "wb") as wav_file:
        voice.synthesize_wav(text_to_read, wav_file, syn_config=syn_config)
