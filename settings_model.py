import json
from dataclasses import dataclass, field
from pathlib import Path
from Player.audib_manifest_model import TextID

SETTINGS_FILE = Path("Data", "settings.json")

@dataclass
class Settings:
    saved_book_positions: dict[Path, list[TextID | int]] = field(default_factory=dict)
    voice_character: str = "Grace"
    voice_speed: float = 1.2
    cardinal_voice_character: str = "Grace"
    cardinal_voice_speed: float = 1.2

    def save(self) -> None:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "saved_book_positions": {
                str(audib_path): [
                    saved_position[0].model_dump(),
                    saved_position[1],
                ]
                for audib_path, saved_position in self.saved_book_positions.items()
            },
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
        data["saved_book_positions"] = {
            Path(audib_path): [TextID(**saved_position[0]), saved_position[1]]
            for audib_path, saved_position in data.get("saved_book_positions", {}).items()
        }
        return cls(**data)