import os
import io
import json
import zipfile
from pathlib import Path
from Player.audib_manifest_model import PageData

def generate_audib(output_filename: str, manifest_path: Path, audio_folder: Path):
    # packs the manifest JSON and the folder of pre-rendered audios into a single true .audib container.
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as audib:
        # add the structured JSON manifest
        audib.write(manifest_path, arcname="manifest.json")
        
        # add all the pre-rendered audio files
        for root, dirs, files in os.walk(audio_folder):
            for file in files:
                if file.endswith(".wav"):
                    file_path = os.path.join(root, file)
                    # Preserve relative path inside the archive
                    arcname = os.path.join("audio", file)
                    audib.write(file_path, arcname=arcname)

def read_audib_manifest(audib_file: Path) -> dict[int, PageData]:
    with zipfile.ZipFile(audib_file, 'r') as audib:
        with audib.open("manifest.json") as manifest_file:
            _manifest = json.loads(manifest_file.read().decode('utf-8'))

            manifest_holder: dict[int, PageData] = {}
            for key, page_data in _manifest.items():
                manifest_holder[int(key)] = PageData(**page_data)

            return manifest_holder

def read_audib_audio(audib_file: Path, audio_file: str) -> bytes:
    with zipfile.ZipFile(audib_file, 'r') as audib:
        # Returns raw bytes safely without closing any stream
        return audib.read(os.path.join("audio", audio_file))