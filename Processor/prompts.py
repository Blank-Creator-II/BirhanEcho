from pathlib import Path


MASTER_PROMPT_PATH = Path(__file__).resolve().parents[1] / "master_prompt.md"


def get_master_prompt(page_number: int) -> str:
    prompt = MASTER_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        f"{prompt}\n\nPDF page position: {page_number}. "
        "Use this position only if the printed textbook page number is not visible."
    )
