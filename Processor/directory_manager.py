from pathlib import Path
import logging
import shutil

logger = logging.getLogger(__name__)


class DirectoryManager:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def create_textbook_structure(self) -> dict[str, Path]:
        paths = {
            "base": self.base_dir,
            "original": self.base_dir / "original",
            "pages": self.base_dir / "pages",
            "json": self.base_dir / "json",
            "processing": self.base_dir / "processing",
        }
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
            logger.info("Created directory: %s", path)
        return paths

    def copy_original_pdf(self, source_pdf: Path) -> Path:
        destination = self.base_dir / "original" / source_pdf.name
        shutil.copy2(source_pdf, destination)
        logger.info("Copied original PDF to %s", destination)
        return destination

    def get_page_json_path(self, page_number: int) -> Path:
        return self.base_dir / "json" / f"{page_number}.json"

    def get_legacy_page_json_path(self, pdf_page_position: int) -> Path:
        return self.base_dir / "json" / f"page_{pdf_page_position:03d}.json"

    def get_page_pdf_path(self, page_number: int) -> Path:
        return self.base_dir / "pages" / f"page_{page_number:03d}.pdf"

    def get_progress_file_path(self) -> Path:
        return self.base_dir / "processing" / "progress.json"
