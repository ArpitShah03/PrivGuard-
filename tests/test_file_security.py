import os
import pytest
from utils.file_security import (
    compute_file_sha256,
    compute_bytes_sha256,
    verify_file_sha256,
    atomic_write,
    secure_temp_workspace
)


def test_file_sha256_hashing_and_verification(tmp_path):
    test_file = tmp_path / "sample.txt"
    content = b"Enterprise Security Gateway Confidential Payload"
    test_file.write_bytes(content)
    
    expected_hash = compute_bytes_sha256(content)
    actual_hash = compute_file_sha256(str(test_file))
    
    assert actual_hash == expected_hash
    assert verify_file_sha256(str(test_file), expected_hash) is True
    assert verify_file_sha256(str(test_file), "0" * 64) is False


def test_atomic_write(tmp_path):
    target = tmp_path / "output.bin"
    content = b"Atomic payload content"
    
    atomic_write(str(target), content)
    assert target.exists()
    assert target.read_bytes() == content
    
    # Overwrite test
    new_content = b"Updated atomic payload"
    atomic_write(str(target), new_content)
    assert target.read_bytes() == new_content


def test_secure_temp_workspace_guaranteed_cleanup():
    created_dir = None
    with secure_temp_workspace() as temp_dir:
        created_dir = temp_dir
        assert os.path.exists(created_dir)
        # Create scratch files inside
        scratch_file = os.path.join(temp_dir, "scratch_ocr_page1.png")
        with open(scratch_file, "wb") as f:
            f.write(b"fake image data")
        assert os.path.exists(scratch_file)

    # Upon exit from context, directory must be completely removed
    assert not os.path.exists(created_dir)
