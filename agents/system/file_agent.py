from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from groq import Groq

from config.settings import GROQ_API_KEY, MODEL_NAME
from memory.vector_memory import store_memory


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAFE_FILE_ROOTS: tuple[Path, ...] = (
    PROJECT_ROOT.resolve(),
)
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".py", ".js", ".html", ".css", ".json"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
SAFE_FILE_ACCESS_MESSAGE = (
    "AURA file access is limited to the active workspace. "
    "Choose a file inside the current AURA project."
)

client = Groq(api_key=GROQ_API_KEY)


def clean(text):
    if not text:
        return "I couldn't analyze the file right now."

    text = str(text)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"`{3}[\w]*\n?", "", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _path_contains_traversal(raw_path: str) -> bool:
    separators_normalized = str(raw_path or "").replace("\\", "/")
    return any(part == ".." for part in separators_normalized.split("/"))


def _path_within_root(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_safe_path(path_value: str, *, must_exist: bool = True) -> tuple[bool, Path | None, str | None]:
    raw = str(path_value or "").strip().strip("\"'")
    if not raw:
        return False, None, "Please provide a file path inside the current workspace."

    if _path_contains_traversal(raw):
        return False, None, "Path traversal is blocked. Use a direct path inside the current workspace."

    candidate = Path(raw)
    try:
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve(strict=False)
        else:
            candidate = candidate.resolve(strict=False)
    except Exception:
        return False, None, SAFE_FILE_ACCESS_MESSAGE

    if not any(_path_within_root(candidate, root) for root in SAFE_FILE_ROOTS):
        return False, None, SAFE_FILE_ACCESS_MESSAGE

    if must_exist and not candidate.exists():
        return False, None, f"File not found inside the current workspace: {candidate.name or raw}"

    return True, candidate, None


def summarize_content(content, file_type="Text Document"):
    try:
        content_preview = content[:4000]

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AURA File Agent. "
                        "Summarize file content clearly in plain text.\n\n"
                        "Structure:\n"
                        "FILE SUMMARY\n"
                        "FILE TYPE\n"
                        "MAIN CONTENT\n"
                        "KEY POINTS\n"
                        "CONCLUSION\n\n"
                        "Do not use markdown symbols like *, #, or backticks."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Summarize this {file_type} content:\n{content_preview}",
                },
            ],
            max_tokens=900,
            temperature=0.3,
        )

        result = response.choices[0].message.content if response.choices else ""
        return clean(result)

    except Exception as e:
        return f"File summarization error: {str(e)}"


def _store_file_memory(message: str, metadata: dict) -> None:
    try:
        store_memory(message, metadata)
    except Exception:
        return None


def read_text_file(file_path):
    allowed, safe_path, error = _validate_safe_path(file_path, must_exist=True)
    if not allowed or safe_path is None:
        return error or SAFE_FILE_ACCESS_MESSAGE

    try:
        content = safe_path.read_text(encoding="utf-8")

        if not content.strip():
            return f"The file is empty: {safe_path.name}"

        _store_file_memory(
            f"Text file read: {safe_path}",
            {
                "type": "file",
                "file_path": str(safe_path),
                "file_kind": "text",
            },
        )

        if len(content) > 3000:
            return summarize_content(content, "Text Document")

        return f"FILE CONTENT\n\n{content}"

    except UnicodeDecodeError:
        try:
            content = safe_path.read_text(encoding="latin-1")

            _store_file_memory(
                f"Text file read with fallback encoding: {safe_path}",
                {
                    "type": "file",
                    "file_path": str(safe_path),
                    "file_kind": "text",
                },
            )

            if len(content) > 3000:
                return summarize_content(content, "Text Document")

            return f"FILE CONTENT\n\n{content}"

        except Exception as e:
            return f"Could not decode file: {str(e)}"

    except FileNotFoundError:
        return f"File not found inside the current workspace: {safe_path.name}"
    except Exception as e:
        return f"Could not read file: {str(e)}"


def read_pdf_file(file_path):
    allowed, safe_path, error = _validate_safe_path(file_path, must_exist=True)
    if not allowed or safe_path is None:
        return error or SAFE_FILE_ACCESS_MESSAGE

    try:
        import PyPDF2

        text = ""
        with safe_path.open("rb") as f:
            reader = PyPDF2.PdfReader(f)

            for page in reader.pages[:10]:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"

        if not text.strip():
            return "Could not extract readable text from the PDF."

        _store_file_memory(
            f"PDF file read: {safe_path}",
            {
                "type": "file",
                "file_path": str(safe_path),
                "file_kind": "pdf",
            },
        )

        return summarize_content(text, "PDF Document")

    except ImportError:
        return "PDF reading requires PyPDF2. Run: pip install PyPDF2"
    except FileNotFoundError:
        return f"File not found inside the current workspace: {safe_path.name}"
    except Exception as e:
        return f"Could not read PDF: {str(e)}"


def _render_directory_listing(directory: Path, files: Iterable[Path]) -> str:
    folders = sorted(path for path in files if path.is_dir())
    file_list = sorted(path for path in files if path.is_file())

    try:
        relative_dir = directory.relative_to(PROJECT_ROOT)
        display_dir = f".\\{relative_dir}" if str(relative_dir) != "." else "."
    except ValueError:
        display_dir = str(directory)

    result = f"FILES IN {display_dir}\n\n"

    if folders:
        result += "FOLDERS:\n"
        for folder in folders:
            result += f"  {folder.name}/\n"
        result += "\n"

    if file_list:
        result += "FILES:\n"
        for file_name in file_list:
            size = file_name.stat().st_size
            result += f"  {file_name.name} ({size} bytes)\n"

    if not folders and not file_list:
        result += "No files or folders found."

    return result.strip()


def list_files(directory="."):
    allowed, safe_path, error = _validate_safe_path(directory, must_exist=True)
    if not allowed or safe_path is None:
        return error or SAFE_FILE_ACCESS_MESSAGE

    if not safe_path.is_dir():
        return "Please provide a folder path inside the current workspace."

    try:
        files = list(safe_path.iterdir())

        _store_file_memory(
            f"Files listed in: {safe_path}",
            {
                "type": "file_list",
                "directory": str(safe_path),
            },
        )

        return _render_directory_listing(safe_path, files)

    except Exception as e:
        return f"Could not list files: {str(e)}"


def extract_file_path(command):
    command = str(command or "").strip()

    prefixes = [
        "read file",
        "open file",
        "analyze file",
        "read pdf",
        "read document",
    ]

    lowered = command.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            return command[len(prefix):].strip()

    return command


def analyze_file(file_path):
    normalized_file_path = extract_file_path(file_path)
    ext = Path(normalized_file_path).suffix.lower()

    if ext in SUPPORTED_PDF_EXTENSIONS:
        return read_pdf_file(normalized_file_path)

    if ext in SUPPORTED_TEXT_EXTENSIONS:
        return read_text_file(normalized_file_path)

    if not ext:
        return (
            "Please provide a valid file path with an extension.\n"
            "Supported: .pdf, .txt, .md, .py, .js, .html, .css, .json"
        )

    return (
        f"File type {ext} is not supported yet.\n"
        "Supported: .pdf, .txt, .md, .py, .js, .html, .css, .json"
    )
