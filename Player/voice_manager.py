import os
import json
import wave
import logging
from piper import PiperVoice
from piper.config import SynthesisConfig
from pathlib import Path
from Player.audib_manifest_model import PageData, TextID
from singleton import SETTINGS

log = logging.getLogger(__name__)

# load the voice model
VOICE_CHARACTER = SETTINGS.voice_character
MODEL_PATH = Path("Voices", VOICE_CHARACTER, f"{VOICE_CHARACTER}.onnx")
voice = PiperVoice.load(MODEL_PATH)
syn_config = SynthesisConfig(length_scale=SETTINGS.voice_speed) # > 1.0 slows down speech (1.2 is 20% slower)

def generate_voice(json_path: Path):
    manifest = read_json(json_path)
    process_manifest(manifest)

def read_json(json_path: Path) -> PageData:
    with open(json_path, 'r') as file:
        data = json.load(file)
    return PageData(**data)

def process_manifest(manifest: PageData):
    page_number = manifest.page_number

    for block in manifest.reading_flow:
        block_text_id = TextID(
            page_number=page_number,
            block_id=block.id,
            link_id=None
        )
        
        block_text = f"{block.context_title}... {block.text}" if block.context_title else block.text
        generate_audio(block_text, block_text_id)

        for link in block.audio_hyperlinks:
            link_text_id = TextID(
                page_number=page_number,
                block_id=block.id,
                link_id=link.id
            )
            
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

def generate_cardinal_audio():
    json_path = Path("Data", "cardinal_audios_manifest.json")
    if not json_path.exists():
        log.error(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r') as file:
        cardinal_audio_manifest = json.load(file)

    # create initial directories
    root_output_dir = Path("Data", "Cardinal Audios")
    root_output_dir.mkdir(parents=True, exist_ok=True)
    directory_holder: list[Path] = [
        Path(root_output_dir, "system_prompts"),
        Path(root_output_dir, "book_session"),
        Path(root_output_dir, "menus", "main_menu"),
        Path(root_output_dir, "menus", "main_menu", "options"),
        Path(root_output_dir, "menus", "options_menu"),
        Path(root_output_dir, "menus", "options_menu", "options"),
        Path(root_output_dir, "book_titles"),
    ]
    for dir in directory_holder:
        dir.mkdir(parents=True, exist_ok=True)

    # synthesize main cardinal prompts
    if "system_prompts" in cardinal_audio_manifest:
        for key, text in cardinal_audio_manifest["system_prompts"].items():
            out_path = Path(directory_holder[0], f"{key}.wav")
            with wave.open(str(out_path), "wb") as wav_file:
                voice.synthesize_wav(text, wav_file, syn_config=syn_config)

    # synthesize book session prompts
    if "book_session" in cardinal_audio_manifest:
        for key, text in cardinal_audio_manifest["book_session"].items():
            out_path = Path(directory_holder[1], f"{key}.wav")
            with wave.open(str(out_path), "wb") as wav_file:
                voice.synthesize_wav(text, wav_file, syn_config=syn_config)

    # synthesize menus (intro, help, and option items)
    if "menus" in cardinal_audio_manifest:
        for menu_name, menu_content in cardinal_audio_manifest["menus"].items():
            # menu intro
            if "intro" in menu_content:
                out_path = Path(directory_holder[2], "intro.wav") if menu_name == "main_menu" else Path(directory_holder[4], "intro.wav")
                with wave.open(str(out_path), "wb") as wav_file:
                    voice.synthesize_wav(menu_content["intro"], wav_file, syn_config=syn_config)
            
            # menu help
            if "help" in menu_content:
                out_path = Path(directory_holder[2], "help.wav") if menu_name == "main_menu" else Path(directory_holder[4], "help.wav")
                with wave.open(str(out_path), "wb") as wav_file:
                    voice.synthesize_wav(menu_content["help"], wav_file, syn_config=syn_config)

            # menu options
            if "options" in menu_content:
                for option in menu_content["options"]:
                    opt_id = option["id"]
                    spoken_text = option["spoken_text"]
                    out_path = Path(directory_holder[3], f"{opt_id}.wav") if menu_name == "main_menu" else Path(directory_holder[5], f"{opt_id}.wav")
                    with wave.open(str(out_path), "wb") as wav_file:
                        voice.synthesize_wav(spoken_text, wav_file, syn_config=syn_config)

    book_titles = sorted(item.name for item in Path("Books").iterdir() if item.is_dir())
    if book_titles:
        for idx, title in enumerate(book_titles, start=1):
            out_path = Path(directory_holder[6], f"{idx}.wav")
            with wave.open(str(out_path), "wb") as wav_file:
                voice.synthesize_wav(title, wav_file, syn_config=syn_config)

    # save cardinal voice and speed data
    SETTINGS.cardinal_voice_character = VOICE_CHARACTER
    SETTINGS.cardinal_voice_speed = SETTINGS.voice_speed
    SETTINGS.save()

    log.debug("Cardinal static audio generated successfully")