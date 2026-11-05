"""Orchestrate PDF extraction, Gemini analysis, and progress storage."""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Processor.directory_manager import DirectoryManager
from Processor.gemini_client import GeminiClient
from Processor.pdf_splitter import PDFSplitter
from Processor.prompts import MASTER_PROMPT_PATH
from Processor.schemas import ProcessingProgress
from Processor.storage_manager import StorageManager

logger = logging.getLogger(__name__)
PAGE_DELAY_SECONDS = 1.0


class TextbookProcessor:
    def __init__(self, pdf_path: Path,) -> None:
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.is_file():
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF file: {self.pdf_path}")

        self.book_id = self.pdf_path.stem
        self.last_error: Optional[str] = None
        self.pdf_splitter = PDFSplitter(self.pdf_path)
        self.dir_manager = DirectoryManager(Path("Books") / self.book_id)
        self.storage = StorageManager(self.dir_manager)
        self.gemini_client = GeminiClient()

        self.dir_manager.create_textbook_structure()
        self.dir_manager.copy_original_pdf(self.pdf_path)

    def process_single_page(self, page_number: int, use_context: bool = False,) -> bool:
        self.last_error = None

        try:
            page_pdf_path = self.dir_manager.get_page_pdf_path(page_number)
            if not self.pdf_splitter.extract_page(page_number, page_pdf_path):
                raise RuntimeError(f"Failed to extract page {page_number} from the PDF")

            context_pdfs: list[Path] = []
            if use_context:
                for context_page in (page_number - 1, page_number + 1):
                    if not 1 <= context_page <= self.pdf_splitter.total_pages:
                        continue
                    context_path = self.dir_manager.get_page_pdf_path(context_page)
                    if context_path.exists():
                        context_pdfs.append(context_path)

            if context_pdfs:
                page_data = self.gemini_client.process_page_with_context(
                    page_pdf_path, context_pdfs, page_number
                )
            else:
                page_data = self.gemini_client.process_page_pdf(
                    page_pdf_path, page_number
                )

            if page_data is None:
                raise RuntimeError(f"Gemini returned no valid result for page {page_number}")
            if not self.storage.save_page_json(page_data, page_number):
                raise RuntimeError(f"Failed to save JSON for page {page_number}")

            logger.info("Processed page %s", page_number)
            return True
        except Exception as error:
            self.last_error = str(error)
            logger.error("Could not process page %s: %s", page_number, error)
            return False

    def process_textbook(self, start_page: Optional[int] = None, end_page: Optional[int] = None, use_context: bool = False, resume: bool = True,) -> ProcessingProgress:
        total_pages = self.pdf_splitter.get_page_count()
        prompt_hash = hashlib.sha256(MASTER_PROMPT_PATH.read_bytes()).hexdigest()
        start = 1 if start_page is None else start_page
        end = total_pages if end_page is None else end_page
        if start < 1 or end > total_pages or start > end:
            raise ValueError(f"Page range must be within 1-{total_pages}: {start}-{end}")

        progress = self.storage.load_progress() if resume else None
        if progress is None:
            progress = self.storage.initialize_progress(
                self.book_id, total_pages, prompt_hash
            )
        else:
            progress.book_id = self.book_id
            progress.total_pages = total_pages
            if progress.prompt_hash != prompt_hash:
                logger.info("Prompt changed; reprocessing all PDF pages")
                progress.completed_pages.clear()
                progress.failed_pages.clear()
                progress.page_errors.clear()
                progress.prompt_hash = prompt_hash

        if resume:
            pages = [
                page for page in self.storage.get_remaining_pages(progress)
                if start <= page <= end
            ]
        else:
            pages = list(range(start, end + 1))
            progress.completed_pages = [
                page for page in progress.completed_pages
                if not start <= page <= end
            ]
            progress.failed_pages = [
                page for page in progress.failed_pages
                if not start <= page <= end
            ]
            for page in range(start, end + 1):
                progress.page_errors.pop(str(page), None)

        logger.info("Processing %s page(s) from %s to %s", len(pages), start, end)
        progress.status = "in_progress"
        self.storage.save_progress(progress)
        self._process_pages(progress, pages, use_context)
        return self.storage.mark_processing_complete(progress)

    def retry_failed_pages(self, use_context: bool = False,) -> Optional[ProcessingProgress]:
        progress = self.storage.load_progress()
        if progress is None:
            logger.info("No saved progress to retry")
            return None
        if not progress.failed_pages:
            logger.info("No failed pages to retry")
            return progress

        pages = sorted(progress.failed_pages)
        progress.status = "in_progress"
        self.storage.save_progress(progress)
        self._process_pages(progress, pages, use_context)
        return self.storage.mark_processing_complete(progress)

    def _process_pages(self, progress: ProcessingProgress, pages: list[int], use_context: bool,) -> None:
        for index, page_number in enumerate(pages, start=1):
            progress.current_page = page_number
            self.storage.save_progress(progress)

            success = self.process_single_page(page_number, use_context)
            if success:
                progress.page_errors.pop(str(page_number), None)
                progress = self.storage.mark_page_completed(progress, page_number)
            else:
                progress.page_errors[str(page_number)] = (
                    self.last_error or "Unknown processing error"
                )
                progress = self.storage.mark_page_failed(progress, page_number)

            logger.info("Finished page %s (%s/%s)", page_number, index, len(pages))
            if PAGE_DELAY_SECONDS:
                time.sleep(PAGE_DELAY_SECONDS)
