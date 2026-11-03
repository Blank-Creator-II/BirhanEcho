import json
from dataclasses import dataclass, field
from pathlib import Path
from Player.audib_manifest_model import TextID

SETTINGS_FILE = Path("Data", "settings.json")

@dataclass
class Settings:
    reading_position: TextID = field(default_factory=lambda: TextID(page_number=1, block_id="block_1"))
    voice_character: str = "Minerva"
    voice_speed: float = 1.2
    cardinal_voice_character: str = "Minerva"
    cardinal_voice_speed: float = 1.2

    def save(self) -> None:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "reading_position": self.reading_position.model_dump(),
            "voice_character": self.voice_character,
            "voice_speed": self.voice_speed,
            "cardinal_voice_character": self.cardinal_voice_character,
            "cardinal_voice_speed": self.cardinal_voice_speed
        }
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8",)

    @classmethod
    def load(cls) -> "Settings":
        if not SETTINGS_FILE.exists():
            return cls() # use default for first creation

        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        data["reading_position"] = TextID(**data["reading_position"])
        return cls(**data)