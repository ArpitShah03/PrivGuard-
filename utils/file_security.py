import os
import shutil
import hashlib
import tempfile
import contextlib
from typing import Generator, Optional, List


def compute_file_sha256(file_path: str) -> str:
    """Compute cryptographic SHA-256 digest of a file on disk."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_bytes_sha256(data: bytes) -> str:
    """Compute cryptographic SHA-256 digest of in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def verify_file_sha256(file_path: str, expected_hash: str) -> bool:
    """Verify that a file on disk matches its expected SHA-256 digest."""
    actual_hash = compute_file_sha256(file_path)
    return actual_hash.lower() == expected_hash.lower()


def atomic_write(dest_path: str, content: bytes):
    """
    Safely write content to a file atomically via temp write and replace.
    Guarantees no partial file writes on process crashes.
    """
    dest_dir = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(dest_dir, exist_ok=True)

    fd, temp_file_path = tempfile.mkstemp(dir=dest_dir, prefix="tmp_atomic_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        if os.path.exists(dest_path):
            os.replace(temp_file_path, dest_path)
        else:
            shutil.move(temp_file_path, dest_path)
    except Exception:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
        raise


@contextlib.contextmanager
def secure_temp_workspace(prefix: str = "qs_secure_") -> Generator[str, None, None]:
    """
    Context manager that creates an isolated temporary directory and guarantees
    complete sanitization/cleanup of all scratch files upon exit or error.
    """
    temp_dir = tempfile.mkdtemp(prefix=prefix)
    try:
        yield temp_dir
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
