import os
import time
import tempfile
import threading
import ollama
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pdf2image import convert_from_path

# --- CONFIGURATION ---
WATCH_FOLDER = r"Z:\Scans" # Update this path
POPPLER_PATH = r"D:\poppler-25.12.0\Library\bin"         # Path to your poppler/bin folder
MODEL = "qwen3-vl:32b"

PROMPT = (
    "Analyze this image and return ONLY a filename. NO explanation. NO reasoning. NO extra text.\n"
    "\n"
    "FORMAT:\n"
    "Documents: YYYY-MM-DD - Sender - Three Word Summary\n"
    "Photos: Year - Subject - Location\n"
    "\n"
    "EXAMPLES:\n"
    "Electric bill from Florida Power dated Dec 23, 2025 → 2025-12-23 - FloridaPower - Electric Bill\n"
    "Marriage certificate from county clerk dated Jan 15, 2024 → 2024-01-15 - County Clerk - Marriage Certificate\n"
    "Medical form from hospital with no date → 0000-00-00 - Hospital Name - Medical Form\n"
    "Family photo at beach from 2010 → 2010 - Family Beach - Summer Vacation\n"
    "Old photo with unknown year → 0000 - Person Name - Location Description\n"
    "\n"
    "Return ONLY the filename:"
)

class DocRenamer(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.pdf', '.png', '.jpg')):
            self.process_document(event.src_path)

    def wait_for_file_stability(self, file_path, timeout=30):
        """Waits until the file size is stable AND file is readable."""
        last_size = -1
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                current_size = os.path.getsize(file_path)
                if current_size == last_size and current_size > 0:
                    # Size is stable, now try to actually open it
                    with open(file_path, 'rb') as f:
                        f.read(1024)  # Try reading first 1KB
                    return True
                last_size = current_size
            except (OSError, IOError, PermissionError):
                pass
            time.sleep(1)
        return False

    def process_document(self, file_path):
        try:
            # Skip if file was already renamed/moved
            if not os.path.exists(file_path):
                return

            # Wait for the network/scanner to finish writing the file
            if not self.wait_for_file_stability(file_path):
                print(f"[WARN] Timeout: File {file_path} is still changing or locked.")
                return

            process_start = time.time()

            # 1. Prepare image for the AI
            img_to_send = file_path
            temp_img = None

            if file_path.lower().endswith('.pdf'):
                # Convert first page to image for the vision model
                pages = convert_from_path(file_path, first_page=1, last_page=1, poppler_path=POPPLER_PATH)
                temp_img = os.path.join(tempfile.gettempdir(), f"ai_renamer_{os.getpid()}.jpg")
                pages[0].save(temp_img, 'JPEG')
                img_to_send = temp_img

            # 2. Query vision model via Ollama (with live timer)
            stop_timer = threading.Event()
            def _timer():
                start = time.time()
                while not stop_timer.is_set():
                    elapsed = int(time.time() - start)
                    print(f"\r[...] Processing: {os.path.basename(file_path)}... {elapsed}s", end="", flush=True)
                    stop_timer.wait(1)

            timer_thread = threading.Thread(target=_timer, daemon=True)
            timer_thread.start()
            try:
                response = ollama.chat(
                    model=MODEL,
                    messages=[{
                        'role': 'user',
                        'content': PROMPT,
                        'images': [img_to_send]
                    }],
                    options={'temperature': 0}
                )
            finally:
                stop_timer.set()
                timer_thread.join()
            raw_name = response['message']['content'].strip()

            # Clean illegal characters - Windows doesn't allow: \ / : * ? " < > |
            for char in [':', '/', '"', '?', '*', '<', '>', '|', '\\']:
                raw_name = raw_name.replace(char, '')

            # Remove leading/trailing periods or spaces (Windows hates these)
            clean_name = raw_name.strip().strip('. ')

            # Validate we got a usable filename
            if not clean_name or len(clean_name) < 5:
                print(f"\r[WARN] AI returned unusable name: '{raw_name}' - skipping          ")
                return

            # 3. Rename original file
            ext = os.path.splitext(file_path)[1]
            new_path = os.path.join(os.path.dirname(file_path), f"{clean_name}{ext}")
            
            os.rename(file_path, new_path)
            elapsed = time.time() - process_start
            print(f"\r[OK] Renamed to: {clean_name}{ext} ({elapsed:.1f}s)          ")

            # Cleanup temp image
            if temp_img and os.path.exists(temp_img):
                os.remove(temp_img)

        except Exception as e:
            print(f"[ERR] Error: {e}")

if __name__ == "__main__":
    if not os.path.exists(WATCH_FOLDER): os.makedirs(WATCH_FOLDER)

    handler = DocRenamer()

    # Process any existing files first (skip files that look already renamed: start with YYYY-)
    existing_files = [f for f in os.listdir(WATCH_FOLDER)
                      if f.lower().endswith(('.pdf', '.png', '.jpg'))
                      and not (len(f) > 10 and f[:4].isdigit() and f[4] == '-')]

    if existing_files:
        print(f"\nFound {len(existing_files)} unprocessed file(s):")
        for i, f in enumerate(existing_files, 1):
            print(f"  {i}. {f}")

        choice = input("\nEnter numbers to process (e.g. '1,3,5'), 'all', or 'skip': ").strip()

        if choice.lower() == 'all':
            to_process = existing_files
        elif choice.lower() == 'skip':
            to_process = []
        else:
            indices = [int(x.strip())-1 for x in choice.split(',') if x.strip().isdigit()]
            to_process = [existing_files[i] for i in indices if 0 <= i < len(existing_files)]

        for filename in to_process:
            handler.process_document(os.path.join(WATCH_FOLDER, filename))

    # Now watch for new files
    observer = Observer()
    observer.schedule(handler, WATCH_FOLDER, recursive=False)

    print(f"\nAI Watcher running on {WATCH_FOLDER}. Drop a file in to test!")
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        observer.stop()
        print("Unloading model from VRAM...")
        try:
            ollama.generate(model=MODEL, keep_alive=0)
            print("Model unloaded.")
        except Exception as e:
            print(f"Could not unload model: {e}")
    observer.join()