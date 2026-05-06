# Mini Agent CLI

Mini Agent CLI is a workspace-first coding assistant that can inspect a target homepage, plan a rebuild, and generate a static frontend with HTML, CSS, and JavaScript.

## What It Does

- Accepts natural language requests from a terminal session.
- Uses a structured `THINK -> TOOL -> OBSERVE -> OUTPUT` loop internally.
- Fetches a compact summary of a target homepage.
- Generates `index.html`, `styles.css`, and `script.js` for a static clone.
- Opens the finished page in the browser.
- Writes generated artifacts directly to files in the workspace.

## Runtime Model

The agent uses three tools:

- `fetch_website` to collect a compact homepage brief.
- `write_file` to create or overwrite generated assets.
- `execute_command` for limited local actions such as folder creation and opening the result.

By default, the CLI keeps the terminal output minimal and user-facing. If you want to inspect the full internal step trace, set `SHOW_AGENT_TRACE=true`.

## Stack

- Python 3.9+
- OpenAI-compatible SDK
- Hugging Face Router or a compatible chat-completions endpoint
- `requests`
- `beautifulsoup4`
- `python-dotenv`

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
HUGGINGFACE_API_KEY=your_hf_token_here
MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct
SHOW_AGENT_TRACE=false
```

## Run

```bash
python agent.py
```

Example prompt:

```text
Clone https://www.scaler.com for me
```

## Project Layout

```text
.
├── agent.py
├── prompt_config.py
├── tools.py
├── requirements.txt
├── README.md
└── <generated_clone>/
    ├── index.html
    ├── styles.css
    └── script.js
```

## Notes

- The agent is optimized for homepage reconstruction, not full multi-page scraping.
- Remote CSS and JS are not imported directly; the page is rebuilt as a static approximation.
- If the source site does not expose usable images, the prompt instructs the model to fall back to a strong text-first layout instead of rendering broken media.
