# Scan Organizer

An AI-powered document scanner organizer that automatically renames scanned documents and photos using a local vision AI model.

Drop a PDF, JPG, or PNG into your scan folder and the AI will analyze it and rename it with a descriptive filename like:
- `2025-12-23 - FloridaPower - Electric Bill.pdf`
- `2003 - Family - Beach Vacation.jpg`

## Requirements

- Python 3.8+
- [Ollama](https://ollama.ai/) - Local AI runtime
- [Poppler](https://poppler.freedesktop.org/) - PDF rendering library (for PDF support)

## Installation

### 1. Install Ollama

Download and install from [ollama.ai](https://ollama.ai/)

### 2. Pull the Vision Model

```bash
ollama pull qwen3-vl:8b
```

### 3. Install Poppler (for PDF support)

**Windows:**
- Download from [poppler releases](https://github.com/osber/poppler/releases)
- Extract to a folder (e.g., `D:\poppler-24.08.0\`)
- Update `POPPLER_PATH` in `scan_organizer.py` to point to the `bin` folder

**macOS:**
```bash
brew install poppler
```

**Linux:**
```bash
sudo apt install poppler-utils
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

Edit the top of `scan_organizer.py`:

```python
WATCH_FOLDER = r"Z:\Scans"  # Your scanner's output folder
POPPLER_PATH = r"D:\poppler-24.08.0\Library\bin"  # Path to poppler (Windows only)
MODEL = "qwen3-vl:8b"  # Ollama model to use
```

## Usage

```bash
python scan_organizer.py
```

On startup, the script will:
1. List any existing unprocessed files and let you choose which to process
2. Start watching for new files

When a new scan arrives, it will:
1. Wait for the file to finish uploading
2. Send the first page to the AI for analysis
3. Rename the file based on the AI's response

### File Naming

**Documents** (letters, forms, bills): `YYYY-MM-DD - [Sender] - [Summary].pdf`

**Photos** (pictures of people, places): `[Year] - [Subject] - [Location].jpg`

## License

MIT
