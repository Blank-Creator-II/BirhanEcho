import os
import io
import json
import zipfile
from pathlib import Path
from Player.audib_manifest_model import PageData

def generate_audib(output_filename: str, json_path: Path, audio_folder: Path):
    # packs the manifest JSON and the folder of pre-rendered audios into a single true .audib container.
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as audib:
        # add the structured JSON manifest
        audib.write(json_path, arcname="manifest.json")
        
        # add all the pre-rendered audio files
        for root, dirs, files in os.walk(audio_folder):
            for file in files:
                if file.endswith(".wav"):
                    file_path = os.path.join(root, file)
                    # Preserve relative path inside the archive
                    arcname = os.path.join("audio", file)
                    audib.write(file_path, arcname=arcname)

def read_audib_manifest(audib_file: Path) -> PageData:
    with zipfile.ZipFile(audib_file, 'r') as audib:
        with audib.open("manifest.json") as manifest_file:
            _manifest = json.loads(manifest_file.read().decode('utf-8'))
            return PageData(**_manifest)

def read_audib_audio(audib_file: Path, audio_file: str) -> bytes:
    with zipfile.ZipFile(audib_file, 'r') as audib:
        # Returns raw bytes safely without closing any stream
        return audib.read(os.path.join("audio", audio_file))