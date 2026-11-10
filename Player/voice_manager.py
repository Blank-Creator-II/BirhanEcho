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
log.info("Loading Piper voice model: character=%s path=%s", VOICE_CHARACTER, MODEL_PATH)
try:
    voice = PiperVoice.load(MODEL_PATH)
    syn_config = SynthesisConfig(length_scale=SETTINGS.voice_speed) # > 1.0 slows down speech (1.2 is 20% slower)
except Exception:
    log.exception("Unable to load/configure Piper voice: character=%s path=%s", VOICE_CHARACTER, MODEL_PATH)
    raise
log.info("Piper voice ready: character=%s speed=%s", VOICE_CHARACTER, SETTINGS.voice_speed)

def _synthesize_wav(text: str, wav_file: wave.Wave_write, output_description: str):
    log.debug(
        "Piper synthesis started: output=%s text_chars=%s voice=%s speed=%s",
        output_description,
        len(text),
        VOICE_CHARACTER,
        SETTINGS.voice_speed,
    )
    try:
        voice.synthesize_wav(text, wav_file, syn_config=syn_config)
    except Exception:
        log.exception("Piper synthesis failed: output=%s text_chars=%s", output_description, len(text))
        raise

def generate_voice(json_root_path: Path):
    log.info("Generating textbook audio: json_root=%s", json_root_path)
    # loop inside the root path to fetch all json paths
    json_paths = sorted(item for item in json_root_path.iterdir() if item.is_file() and str(item).endswith(".json") and item.name != "manifest.json")
    log.info("Found %s textbook page JSON files in %s", len(json_paths), json_root_path)

    create_manifest(json_paths, json_root_path)

    manifest = read_manifest(Path(json_root_path, "manifest.json"))

    process_manifest(manifest)
    log.info("Finished textbook audio generation: pages=%s", len(manifest))

def create_manifest(json_paths: list[Path], output_path: Path):
    log.debug("Creating textbook manifest: source_files=%s output=%s", len(json_paths), output_path)
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
    log.debug("Reading textbook manifest: %s", manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as file:
        data = json.load(file)

        page_data_holder: list[PageData] = []
        for page_data in data.values():
            page_data = PageData(**page_data)
            page_data_holder.append(page_data)

        log.info("Loaded textbook manifest: pages=%s path=%s", len(page_data_holder), manifest_path)
        return page_data_holder


def process_manifest(manifest: list[PageData]):
    log.info("Synthesizing manifest audio: pages=%s", len(manifest))
    for page_data in manifest:
        page_number = page_data.page_number
        log.debug("Synthesizing page %s: blocks=%s", page_number, len(page_data.reading_flow))

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
        _synthesize_wav(text_to_read, wav_file, str(output_path))

def generate_cardinal_audio():
    json_path = Path("Data", "cardinal_audios_manifest.json")
    log.info("Generating static Cardinal audio from %s", json_path)
    if not json_path.exists():
        log.error("Cardinal audio manifest not found: %s", json_path)
        return

    try:
        with open(json_path, 'r', encoding="utf-8") as file:
            cardinal_audio_manifest = json.load(file)
    except Exception:
        log.exception("Unable to read Cardinal audio manifest: %s", json_path)
        raise

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
                _synthesize_wav(text, wav_file, str(out_path))

    # synthesize book session prompts
    if "book_session" in cardinal_audio_manifest:
        for key, text in cardinal_audio_manifest["book_session"].items():
            out_path = Path(directory_holder[1], f"{key}.wav")
            with wave.open(str(out_path), "wb") as wav_file:
                _synthesize_wav(text, wav_file, str(out_path))

    # synthesize menus (intro, help, and option items)
    if "menus" in cardinal_audio_manifest:
        for menu_name, menu_content in cardinal_audio_manifest["menus"].items():
            # menu intro
            if "intro" in menu_content:
                out_path = Path(directory_holder[2], "intro.wav") if menu_name == "main_menu" else Path(directory_holder[4], "intro.wav")
                with wave.open(str(out_path), "wb") as wav_file:
                    _synthesize_wav(menu_content["intro"], wav_file, str(out_path))
            
            # menu help
            if "help" in menu_content:
                out_path = Path(directory_holder[2], "help.wav") if menu_name == "main_menu" else Path(directory_holder[4], "help.wav")
                with wave.open(str(out_path), "wb") as wav_file:
                    _synthesize_wav(menu_content["help"], wav_file, str(out_path))

            # menu options
            if "options" in menu_content:
                for option in menu_content["options"]:
                    opt_id = option["id"]
                    spoken_text = option["spoken_text"]
                    out_path = Path(directory_holder[3], f"{opt_id}.wav") if menu_name == "main_menu" else Path(directory_holder[5], f"{opt_id}.wav")
                    with wave.open(str(out_path), "wb") as wav_file:
                        _synthesize_wav(spoken_text, wav_file, str(out_path))

    # synthesize book titles intro
    if "book_titles" in cardinal_audio_manifest:
        for key, text in cardinal_audio_manifest["book_titles"].items():
            out_path = Path(directory_holder[6], f"{key}.wav")
            with wave.open(str(out_path), "wb") as wav_file:
                _synthesize_wav(text, wav_file, str(out_path))

    # synthesize actual book titles
    generate_book_title_audio()

    # save cardinal voice and speed data
    SETTINGS.cardinal_voice_character = VOICE_CHARACTER
    SETTINGS.cardinal_voice_speed = SETTINGS.voice_speed
    SETTINGS.save()

    log.info("Cardinal static audio generated successfully: voice=%s speed=%s", VOICE_CHARACTER, SETTINGS.voice_speed)

def generate_book_title_audio():
    books_path = Path("Data", "Books")
    try:
        book_titles = sorted(item.name for item in books_path.iterdir() if item.is_file() and str(item).endswith(".audib"))
    except OSError:
        log.exception("Unable to list books for title synthesis: %s", books_path)
        raise
    log.info("Generating book-title audio: books=%s", len(book_titles))
    if book_titles:
        for idx, title in enumerate(book_titles, start=1):
            out_path = Path("Data", "Cardinal Audios", "book_titles", "titles", f"{idx}.wav")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(out_path), "wb") as wav_file:
                _synthesize_wav(f"Book {idx}. " + title.removesuffix(".audib"), wav_file, str(out_path))

def generate_dynamic_audio(phrases: list[str], pause_seconds: float = 0.5, sample_rate: int = 22050,) -> tuple[bytes, tuple[float, ...]]:
    log.info(
        "Generating dynamic audio: phrases=%s pause_seconds=%s sample_rate=%s",
        len(phrases),
        pause_seconds,
        sample_rate,
    )
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
            _synthesize_wav(text, wf, f"<dynamic phrase {idx + 1}>")

        buf.seek(0)
        with wave.open(buf, "rb") as phrase_wav:
            if (
                phrase_wav.getframerate() != sample_rate
                or phrase_wav.getnchannels() != 1
                or phrase_wav.getsampwidth() != 2
            ):
                log.error(
                    "Invalid dynamic phrase WAV: phrase=%s rate=%s channels=%s sample_width=%s expected_rate=%s",
                    idx + 1,
                    phrase_wav.getframerate(),
                    phrase_wav.getnchannels(),
                    phrase_wav.getsampwidth(),
                    sample_rate,
                )
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
    audio_data = final_buffer.read()
    log.info("Dynamic audio generated: bytes=%s phrase_durations=%s", len(audio_data), phrase_durations)
    return audio_data, tuple(phrase_durations)
