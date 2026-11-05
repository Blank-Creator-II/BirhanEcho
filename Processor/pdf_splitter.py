from pypdf import PdfReader, PdfWriter
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PDFSplitter:
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.reader = PdfReader(pdf_path)
        self.total_pages = len(self.reader.pages)

    def get_page_count(self) -> int:
        return self.total_pages

    def extract_page(self, page_number: int, output_path: Path) -> bool:
        try:
            # Convert to 0-indexed for pypdf
            page_index = page_number - 1

            if page_index < 0 or page_index >= self.total_pages:
                logger.error(f"Invalid page number: {page_number}. Valid range: 1-{self.total_pages}")
                return False

            # Create a new PDF writer for this page
            writer = PdfWriter()
            writer.add_page(self.reader.pages[page_index])

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the extracted page
            with open(output_path, "wb") as f:
                writer.write(f)

            logger.info(f"Extracted page {page_number} to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to extract page {page_number}: {e}")
            return False

    def extract_page_range(self, start_page: int, end_page: int, output_dir: Path) -> dict[int, bool]:
        results = {}

        for page_num in range(start_page, end_page + 1):
            output_path = output_dir / f"page_{page_num:03d}.pdf"
            results[page_num] = self.extract_page(page_num, output_path)

        return results

    def extract_all_pages(self, output_dir: Path) -> dict[int, bool]:
        return self.extract_page_range(1, self.total_pages, output_dir)
