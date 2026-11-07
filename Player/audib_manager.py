import os
import io
import json
import logging
import zipfile
from pathlib import Path, PurePosixPath
from Player.audib_manifest_model import PageData

log = logging.getLogger(__name__)

def generate_audib(output_filename: str, manifest_path: Path, audio_folder: Path):
    # packs the manifest JSON and the folder of pre-rendered audios into a single true .audib container.
    log.info("Creating audib archive: output=%s manifest=%s audio_folder=%s", output_filename, manifest_path, audio_folder)
    audio_count = 0
    try:
        with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as audib:
            # add the structured JSON manifest
            audib.write(manifest_path, arcname="manifest.json")

            # add all the pre-rendered audios with ZIP-standard separators
            for root, dirs, files in os.walk(audio_folder):
                for file in files:
                    if file.endswith(".wav"):
                        file_path = Path(root, file)
                        relative_path = file_path.relative_to(audio_folder)
                        arcname = PurePosixPath("audio", *relative_path.parts).as_posix()
                        audib.write(file_path, arcname=arcname)
                        audio_count += 1
    except Exception:
        log.exception("Failed to create audib archive: output=%s", output_filename)
        raise
    log.info("Created audib archive: output=%s audio_files=%s bytes=%s", output_filename, audio_count, Path(output_filename).stat().st_size)

def read_audib_manifest(audib_file: Path) -> dict[int, PageData]:
    log.info("Reading audib manifest: %s", audib_file)
    try:
        with zipfile.ZipFile(audib_file, 'r') as audib:
            with audib.open("manifest.json") as manifest_file:
                _manifest = json.loads(manifest_file.read().decode('utf-8'))

                manifest_holder: dict[int, PageData] = {}
                for key, page_data in _manifest.items():
                    manifest_holder[int(key)] = PageData(**page_data)

    except Exception:
        log.exception("Failed to read audib manifest: %s", audib_file)
        raise
    log.info("Read audib manifest: %s pages=%s", audib_file, len(manifest_holder))
    return manifest_holder

def read_audib_audio(audib_file: Path, audio_file: str) -> bytes:
    archive_path = PurePosixPath("audio", audio_file.replace("\\", "/")).as_posix()
    log.debug("Reading audib audio: archive=%s member=%s", audib_file, archive_path)
    try:
        with zipfile.ZipFile(audib_file, 'r') as audib:
            # Returns raw bytes safely without closing any stream
            audio_data = audib.read(archive_path)
    except Exception:
        log.exception("Failed to read audib audio: archive=%s member=%s", audib_file, archive_path)
        raise
    log.debug("Read audib audio: archive=%s member=%s bytes=%s", audib_file, archive_path, len(audio_data))
    return audio_data