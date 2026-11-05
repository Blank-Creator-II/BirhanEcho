from google import genai
from pathlib import Path
from typing import Optional
import logging
import json
from dotenv import load_dotenv
import os

from Processor.schemas import PageData
from Processor.prompts import get_master_prompt

logger = logging.getLogger(__name__)

# gemini-3.8-flash, gemini-3.6-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite
DEFAULT_MODEL = "gemini-3.1-flash-lite"


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            load_dotenv()
            load_dotenv(Path(__file__).with_name(".env"), override=False)
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY not found in environment variables. "
                    "Please set it in a .env file or pass it directly."
                )
            self.client = genai.Client(api_key=api_key)

        logger.info(f"Gemini client initialized (model={self.model})")

    def process_page_pdf(self, page_pdf_path: Path, page_number: int) -> Optional[PageData]:
        try:
            # Read the PDF file
            with open(page_pdf_path, "rb") as f:
                pdf_bytes = f.read()

            # Get the master prompt
            prompt = get_master_prompt(page_number)

            logger.info(f"Sending page {page_number} to Gemini for analysis...")

            # Send to Gemini with the PDF as an inline file
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    genai.types.Part.from_bytes(
                        data=pdf_bytes,
                        mime_type="application/pdf"
                    ),
                    prompt
                ],
                config={
                    "response_mime_type": "application/json",
                }
            )

            # Parse the response
            response_text = response.text
            logger.info(f"Received response from Gemini for page {page_number}")

            # Parse JSON
            response_json = json.loads(response_text)

            # Validate using Pydantic
            page_data = PageData(**response_json)

            logger.info(f"Successfully validated JSON for page {page_number}")
            return page_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for page {page_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing page {page_number} with Gemini: {e}")
            return None

    def process_page_with_context(self, page_pdf_path: Path, context_pdfs: list[Path], page_number: int) -> Optional[PageData]:
        try:
            # Read all PDFs
            parts = []

            # Add context pages first
            for ctx_pdf in context_pdfs:
                with open(ctx_pdf, "rb") as f:
                    parts.append(
                        genai.types.Part.from_bytes(
                            data=f.read(),
                            mime_type="application/pdf"
                        )
                    )

            # Add target page
            with open(page_pdf_path, "rb") as f:
                parts.append(
                    genai.types.Part.from_bytes(
                        data=f.read(),
                        mime_type="application/pdf"
                    )
                )

            # Get the master prompt
            prompt = get_master_prompt(page_number)
            prompt += "\n\nNote: I have provided context pages before the target page. Analyze only the last page provided and return JSON for that page only."

            parts.append(prompt)

            logger.info(f"Sending page {page_number} with context to Gemini...")

            # Send to Gemini
            response = self.client.models.generate_content(
                model=self.model,
                contents=parts,
                config={
                    "response_mime_type": "application/json",
                }
            )

            # Parse and validate
            response_text = response.text
            response_json = json.loads(response_text)
            page_data = PageData(**response_json)

            logger.info(f"Successfully processed page {page_number} with context")
            return page_data

        except Exception as e:
            logger.error(f"Error processing page {page_number} with context: {e}")
            return None
