import os
import io
import json
import wave
import logging
import numpy as np
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

def generate_voice(json_root_path: Path):
    # loop inside the root path to fetch all json paths
    json_paths = sorted(item for item in json_root_path.iterdir() if item.is_file() and str(item).endswith(".json") and item.name != "manifest.json")

    create_manifest(json_paths, json_root_path)

    manifest = read_manifest(Path(json_root_path, "manifest.json"))

    process_manifest(manifest)

def create_manifest(json_paths: list[Path], output_path: Path):
    # this will hold all files nested by their number
    manifest = {}

    for file_name in json_paths:
        file_key = int(os.path.splitext(os.path.basename(file_name))[0])

        # open and load the original JSON structure
        with open(file_name, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # assign the entire original JSON structure to its respective key
            manifest[file_key] = data

    with open(Path(output_path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4, ensure_ascii=False)

def read_manifest(manifest_path: Path) -> list[PageData]:
    with open(manifest_path, "r", encoding="utf-8") as file:
        data = json.load(file)

        page_data_holder: list[PageData] = []
        for page_data in data.values():
            page_data = PageData(**page_data)
            page_data_holder.append(page_data)

        return page_data_holder


def process_manifest(manifest: list[PageData]):
    for page_data in manifest:
        page_number = page_data.page_number

        for block in page_data.reading_flow:
            block_text_id = TextID(
                page_number=page_number,
                block_id=block.id,
                link_id=None
            )
            
            block_text = f"{block.context_title}. {block.text}" if block.context_title else block.text
            generate_audio(block_text, block_text_id)

            for link in block.audio_hyperlinks:
                link_text_id = TextID(
                    page_number=page_number,
                    block_id=block.id,
                    link_id=link.id
                )
                
                link_text = f"{link.term}: {link.explanation}"
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

    # synthesize book titles intro
    if "book_titles" in cardinal_audio_manifest:
        for key, text in cardinal_audio_manifest["book_titles"].items():
            out_path = Path(directory_holder[6], f"{key}.wav")
            with wave.open(str(out_path), "wb") as wav_file:
                voice.synthesize_wav(text, wav_file, syn_config=syn_config)

    # synthesize actual book titles
    generate_book_title_audio()

    # save cardinal voice and speed data
    SETTINGS.cardinal_voice_character = VOICE_CHARACTER
    SETTINGS.cardinal_voice_speed = SETTINGS.voice_speed
    SETTINGS.save()

    log.debug("Cardinal static audio generated successfully")

def generate_book_title_audio():
    book_titles = sorted(item.name for item in Path("Data", "Books").iterdir() if item.is_file() and str(item).endswith(".audib"))
    if book_titles:
        for idx, title in enumerate(book_titles, start=1):
            out_path = Path("Data", "Cardinal Audios", "book_titles", "titles", f"{idx}.wav")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(out_path), "wb") as wav_file:
                voice.synthesize_wav(title.removesuffix(".audib"), wav_file, syn_config=syn_config)

def generate_dynamic_audio(phrases: list[str], pause_seconds: float = 0.5, sample_rate: int = 22050,) -> tuple[bytes, tuple[float, ...]]:
    final_pcm_chunks = []
    phrase_durations = []
    spoken_phrases = [text for text in phrases if text.strip()]

    silence_samples = int(sample_rate * pause_seconds)
    silence_bytes = np.zeros(silence_samples, dtype=np.int16).tobytes()

    for idx, text in enumerate(spoken_phrases):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            voice.synthesize_wav(text, wf, syn_config=syn_config)

        buf.seek(0)
        with wave.open(buf, "rb") as phrase_wav:
            if (
                phrase_wav.getframerate() != sample_rate
                or phrase_wav.getnchannels() != 1
                or phrase_wav.getsampwidth() != 2
            ):
                raise ValueError("Dynamic phrase audio must be 16-bit mono WAV at the requested sample rate.")
            phrase_durations.append(phrase_wav.getnframes() / sample_rate)
            final_pcm_chunks.append(phrase_wav.readframes(phrase_wav.getnframes()))

        if idx < len(spoken_phrases) - 1:
            final_pcm_chunks.append(silence_bytes)

    final_buffer = io.BytesIO()
    with wave.open(final_buffer, "wb") as final_wf:
        final_wf.setnchannels(1)
        final_wf.setsampwidth(2)
        final_wf.setframerate(sample_rate)

        for chunk in final_pcm_chunks:
            final_wf.writeframes(chunk)

    final_buffer.seek(0)
    return final_buffer.read(), tuple(phrase_durations)
