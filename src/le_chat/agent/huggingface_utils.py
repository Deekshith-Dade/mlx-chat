"""Utilities for downloading models from Hugging Face Hub.

Includes tqdm patches to prevent multiprocessing lock conflicts with Textual.
"""
import re
import subprocess
import sys
from typing import Callable

# Patch tqdm to prevent multiprocessing lock creation which conflicts with Textual
# tqdm tries to create mp locks in __new__ before checking 'disable', causing
# "ValueError: bad value(s) in fds_to_keep" in subprocess contexts
import tqdm.std


class _DummyLock:
    """A dummy lock that does nothing, for use with tqdm in Textual."""
    def acquire(self, *args, **kwargs): return True
    def release(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


# Pre-set the locks so tqdm doesn't try to create real multiprocessing locks
tqdm.std.tqdm._lock = _DummyLock()
tqdm.std.tqdm._instances = set()


def _safe_tqdm_del(self):
    try:
        self.close()
    except (AttributeError, ValueError):
        pass


tqdm.std.tqdm.__del__ = _safe_tqdm_del


def parse_progress_line(line: str) -> str | None:
    """Parse tqdm progress output into a readable status message."""
    line = line.strip()
    if not line:
        return None
    
    # Match "Fetching N files: X%|...| current/total"
    fetch_match = re.search(r'Fetching (\d+) files?:\s*(\d+)%\|[^|]*\|\s*(\d+)/(\d+)', line)
    if fetch_match:
        total = fetch_match.group(1)
        percent = fetch_match.group(2)
        current = fetch_match.group(3)
        return f"Fetching files ({current}/{total}) {percent}%"
    
    # Match large file download: "model.safetensors:  48%|...| 1.48G/3.09G [time, speed]"
    large_file_match = re.search(r'^(.+?):\s*(\d+)%\|[^|]*\|\s*([\d.]+[KMGT]?B?)/(\S+)', line)
    if large_file_match:
        filename = large_file_match.group(1).strip()
        percent = large_file_match.group(2)
        current = large_file_match.group(3)
        total = large_file_match.group(4).split()[0]
        if len(filename) > 25:
            filename = filename[:22] + "..."
        return f"{filename}: {current}/{total} ({percent}%)"
    
    # Match completed file: "filename: 100%|...| size/size"
    complete_match = re.search(r'^(.+?):\s*100%', line)
    if complete_match:
        filename = complete_match.group(1).strip()
        if len(filename) > 30:
            filename = filename[:27] + "..."
        return f"Downloaded {filename}"
    
    # Match simple file progress: "filename: size [time, speed]"
    simple_match = re.search(r'^(.+?):\s*([\d.]+[kKMGT]?B)\s*\[', line)
    if simple_match:
        filename = simple_match.group(1).strip()
        size = simple_match.group(2)
        if len(filename) > 30:
            filename = filename[:27] + "..."
        return f"Downloading {filename} ({size})"
    
    return None


def download_model(model_name: str, on_progress: Callable[[str], None] | None = None) -> bool:
    """Download a model from Hugging Face Hub in a subprocess.
    
    Uses subprocess to show download progress without tqdm conflicts.
    
    Args:
        model_name: The model identifier (e.g., "mlx-community/gemma-3n-E2B-it-4bit")
        on_progress: Optional callback that receives progress status messages
        
    Returns:
        True if download succeeded, False otherwise
    """
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", f"""
import sys
from huggingface_hub import snapshot_download
try:
    snapshot_download('{model_name}')
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
"""],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    last_status = ""
    while True:
        char = process.stderr.read(1)
        if not char and process.poll() is not None:
            break
        
        if char in ('\r', '\n'):
            if last_status and on_progress:
                parsed = parse_progress_line(last_status)
                if parsed:
                    on_progress(parsed)
            last_status = ""
        else:
            last_status += char
    
    return process.returncode == 0
