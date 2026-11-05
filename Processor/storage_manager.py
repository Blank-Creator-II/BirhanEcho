import json
import logging
from datetime import datetime
from typing import Optional

from Processor.directory_manager import DirectoryManager
from Processor.schemas import PageData, ProcessingProgress

logger = logging.getLogger(__name__)


class StorageManager:
    def __init__(self, dir_manager: DirectoryManager):
        self.dir_manager = dir_manager

    def save_page_json(self, page_data: PageData, pdf_page_position: int) -> bool:
        path = self.dir_manager.get_page_json_path(page_data.page_number)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(page_data.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            legacy_path = self.dir_manager.get_legacy_page_json_path(pdf_page_position)
            if legacy_path != path and legacy_path.exists():
                legacy_path.unlink()
                logger.info("Removed obsolete page-position JSON %s", legacy_path)
            logger.info("Saved JSON for page %s to %s", page_data.page_number, path)
            return True
        except Exception as error:
            logger.error("Failed to save JSON for page %s: %s", page_data.page_number, error)
            return False

    def load_page_json(self, page_number: int) -> Optional[PageData]:
        path = self.dir_manager.get_page_json_path(page_number)
        try:
            if not path.exists():
                logger.warning("JSON file not found for page %s", page_number)
                return None
            return PageData(**json.loads(path.read_text(encoding="utf-8")))
        except Exception as error:
            logger.error("Failed to load JSON for page %s: %s", page_number, error)
            return None

    def save_progress(self, progress: ProcessingProgress) -> bool:
        path = self.dir_manager.get_progress_file_path()
        try:
            progress.last_updated = datetime.now().isoformat()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(progress.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
            logger.info("Saved progress for %s", progress.book_id)
            return True
        except Exception as error:
            logger.error("Failed to save progress: %s", error)
            return False

    def load_progress(self) -> Optional[ProcessingProgress]:
        path = self.dir_manager.get_progress_file_path()
        try:
            if not path.exists():
                logger.info("No existing progress file found")
                return None
            progress = ProcessingProgress(**json.loads(path.read_text(encoding="utf-8")))
            logger.info("Loaded progress for %s", progress.book_id)
            return progress
        except Exception as error:
            logger.error("Failed to load progress: %s", error)
            return None

    def initialize_progress(self, book_id: str, total_pages: int, prompt_hash: str,) -> ProcessingProgress:
        progress = ProcessingProgress(
            book_id=book_id,
            total_pages=total_pages,
            last_updated=datetime.now().isoformat(),
            prompt_hash=prompt_hash,
        )
        self.save_progress(progress)
        return progress

    def mark_page_completed(self, progress: ProcessingProgress, page_number: int) -> ProcessingProgress:
        if page_number not in progress.completed_pages:
            progress.completed_pages.append(page_number)
        if page_number in progress.failed_pages:
            progress.failed_pages.remove(page_number)
        progress.status = "in_progress"
        self.save_progress(progress)
        logger.info("Marked page %s as completed", page_number)
        return progress

    def mark_page_failed(self, progress: ProcessingProgress, page_number: int) -> ProcessingProgress:
        if page_number not in progress.failed_pages:
            progress.failed_pages.append(page_number)
        self.save_progress(progress)
        logger.error("Marked page %s as failed", page_number)
        return progress

    def mark_processing_complete(self, progress: ProcessingProgress) -> ProcessingProgress:
        progress.status = "completed"
        progress.current_page = None
        self.save_progress(progress)
        logger.info("Marked processing as complete for %s", progress.book_id)
        return progress

    def get_remaining_pages(self, progress: ProcessingProgress) -> list[int]:
        processed_pages = set(progress.completed_pages + progress.failed_pages)
        all_pages = set(range(1, progress.total_pages + 1))
        return sorted(all_pages - processed_pages)
