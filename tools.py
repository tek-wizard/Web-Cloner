import json
import os
import platform
import shlex
import subprocess
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


USER_OS = platform.system()
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
ALLOWED_COMMANDS = {"mkdir", "open", "xdg-open", "start"}


def fetch_website(url: str) -> str:
    """Fetch a simple homepage summary for the agent."""
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup(["script", "style", "noscript", "svg"]):
            element.extract()

        page_title = soup.title.get_text(" ", strip=True)[:180] if soup.title else ""

        nav_items = []
        for nav in soup.find_all("nav"):
            for anchor in nav.find_all("a"):
                text = anchor.get_text(" ", strip=True)
                if text and text not in nav_items:
                    nav_items.append(text)
                if len(nav_items) >= 10:
                    break
            if len(nav_items) >= 10:
                break

        headings = []
        for tag in soup.find_all(["h1", "h2", "h3"]):
            text = tag.get_text(" ", strip=True)
            if text and text not in headings:
                headings.append(text)
            if len(headings) >= 10:
                break

        paragraphs = []
        for tag in soup.find_all("p"):
            text = tag.get_text(" ", strip=True)
            if text and text not in paragraphs:
                paragraphs.append(text[:180])
            if len(paragraphs) >= 6:
                break

        buttons = []
        for tag in soup.find_all(["a", "button"]):
            text = tag.get_text(" ", strip=True)
            if text and text not in buttons:
                buttons.append(text)
            if len(buttons) >= 8:
                break

        image_urls = []
        for image in soup.find_all("img", src=True):
            full_url = urljoin(url, image["src"]) # type: ignore
            try:
                image_response = requests.head(full_url, headers=REQUEST_HEADERS, timeout=5, allow_redirects=True)
                content_type = image_response.headers.get("Content-Type", "").lower()
                if image_response.status_code < 400 and content_type.startswith("image/") and full_url not in image_urls:
                    image_urls.append(full_url)
            except Exception:
                continue
            if len(image_urls) >= 5:
                break

        result = {
            "source_url": url,
            "page_title": page_title,
            "nav_items": nav_items,
            "headings": headings,
            "paragraphs": paragraphs,
            "cta_texts": buttons,
            "image_urls": image_urls,
            "note": "If image_urls is empty, build a premium text-first clone without broken images.",
        }
        return json.dumps(result, ensure_ascii=True)
    except Exception as error:
        return f"Failed to fetch website: {error}"


def execute_command(cmd: str) -> str:
    """Run only minimal terminal commands needed by the assignment."""
    try:
        parts = shlex.split(cmd)
    except ValueError as error:
        return f"Error: Invalid command syntax: {error}"

    if not parts:
        return "Error: Empty command."

    if parts[0] not in ALLOWED_COMMANDS:
        return f"Error: Command '{parts[0]}' is not allowed."

    if parts[0] == "mkdir" and len(parts) >= 2 and parts[1] != "-p":
        parts.insert(1, "-p")

    try:
        result = subprocess.run(parts, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            output = result.stdout.strip() or result.stderr.strip() or "Command completed successfully."
            return f"Success: {output}"
        error_output = result.stderr.strip() or result.stdout.strip() or "Command failed."
        return f"Error: {error_output}"
    except Exception as error:
        return f"Exception occurred: {error}"


def write_file(filename: str, content: str) -> str:
    """Create or overwrite a file."""
    try:
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        with open(filename, "w", encoding="utf-8") as file_handle:
            file_handle.write(content)
        return f"Successfully wrote to {filename}"
    except Exception as error:
        return f"Failed to write file: {error}"


TOOL_MAP = {
    "fetch_website": fetch_website,
    "write_file": write_file,
    "execute_command": execute_command,
}
