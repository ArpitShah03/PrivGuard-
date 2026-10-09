import pytest
from PIL import Image, ImageDraw

from extractors.ocr_enhancer import OCREnhancer, default_ocr_enhancer


def test_ocr_enhancer_image_enhancement():
    enhancer = default_ocr_enhancer
    # Create low contrast image
    img = Image.new("RGB", (100, 100), color=(120, 120, 120))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "TEST", fill=(130, 130, 130))
    
    enhanced = enhancer.enhance_image(img, upscale_factor=2.0)
    assert enhanced.size == (200, 200)
    assert enhanced.mode == "L"


def test_ocr_enhancer_otsu_binarization():
    enhancer = default_ocr_enhancer
    img = Image.new("L", (50, 50), color=50)
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 40, 40], fill=220)
    
    binarized = enhancer.binarize_otsu(img)
    # Unique values should only be 0 and 255
    unique_vals = set(binarized.getdata())
    assert unique_vals.issubset({0, 255})


def test_ocr_disagreement_detection_critical_substitution():
    enhancer = default_ocr_enhancer
    text_pass1 = "Taxpayer ID is 0123-456-789"
    text_pass2 = "Taxpayer ID is O123-456-789"  # Substitution of 0 with O
    
    has_critical, disagreements = enhancer.detect_disagreements(text_pass1, text_pass2)
    assert has_critical is True
    assert len(disagreements) >= 1
    assert any(d["is_critical"] for d in disagreements)


def test_ocr_disagreement_detection_identical():
    enhancer = default_ocr_enhancer
    text1 = "Clean text without any confusion"
    text2 = "Clean text without any confusion"
    
    has_critical, disagreements = enhancer.detect_disagreements(text1, text2)
    assert has_critical is False
    assert len(disagreements) == 0


def test_ocr_quality_metadata():
    enhancer = default_ocr_enhancer
    img = Image.new("RGB", (300, 400), color=(255, 255, 255))
    meta = enhancer.compute_quality_metadata(
        image=img,
        confidence=0.88,
        retry_count=1,
        disagreements=[]
    )
    assert meta["image_dimensions"] == "300x400"
    assert meta["retry_count"] == 1
    assert meta["quality_status"] == "EXCELLENT"
