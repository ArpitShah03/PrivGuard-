import io
import re
from typing import Dict, Any, List, Optional, Tuple, Union
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class OCREnhancer:
    """
    Advanced OCR Preprocessing, Reliability Enhancer, and Multi-Pass Disagreement Resolver.
    - Preprocessing: Upscaling, unsharp masking, adaptive binarization, noise reduction.
    - Multi-Pass Retry: If initial confidence < threshold, retries with aggressive contrast.
    - Disagreement Marking: Discrepancies between passes flag extraction uncertainty.
    """

    CONFUSION_CHARS = {
        'O': '0', '0': 'O',
        'I': '1', '1': 'I', 'l': '1',
        'S': '5', '5': 'S',
        'B': '8', '8': 'B',
        'Z': '2', '2': 'Z'
    }

    def __init__(self, target_dpi: int = 300, min_conf_threshold: float = 0.65):
        self.target_dpi = target_dpi
        self.min_conf_threshold = min_conf_threshold

    def enhance_image(
        self,
        image: Image.Image,
        upscale_factor: float = 1.5,
        sharpen: bool = True,
        denoise: bool = True,
        contrast_factor: float = 2.2
    ) -> Image.Image:
        """Apply high-fidelity image enhancement for difficult OCR scans."""
        img = image.copy()

        # Convert to Grayscale
        if img.mode != "L":
            img = img.convert("L")

        # 1. Upscale if low resolution
        if upscale_factor > 1.0:
            new_w = int(img.width * upscale_factor)
            new_h = int(img.height * upscale_factor)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 2. Denoise with light median filter
        if denoise:
            img = img.filter(ImageFilter.MedianFilter(size=3))

        # 3. Enhance Contrast & Auto-contrast
        img = ImageOps.autocontrast(img, cutoff=2)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast_factor)

        # 4. Sharpening
        if sharpen:
            img = img.filter(ImageFilter.SHARPEN)

        return img

    def binarize_otsu(self, image: Image.Image) -> Image.Image:
        """Deterministic Otsu-like threshold binarization for document scans."""
        img = image.convert("L") if image.mode != "L" else image.copy()
        # Compute histogram
        hist = img.histogram()
        total_pixels = img.width * img.height

        sum_all = sum(i * hist[i] for i in range(256))
        sum_b = 0
        w_b = 0
        var_max = 0.0
        threshold = 128

        for t in range(256):
            w_b += hist[t]
            if w_b == 0:
                continue
            w_f = total_pixels - w_b
            if w_f == 0:
                break

            sum_b += t * hist[t]
            m_b = sum_b / w_b
            m_f = (sum_all - sum_b) / w_f

            # Between-class variance
            var_between = w_b * w_f * ((m_b - m_f) ** 2)
            if var_between > var_max:
                var_max = var_between
                threshold = t

        # Apply threshold
        return img.point(lambda p: 255 if p > threshold else 0)

    def detect_disagreements(self, text_pass1: str, text_pass2: str) -> Tuple[bool, List[Dict[str, str]]]:
        """
        Compare OCR text outputs from Pass 1 and Pass 2.
        Flag critical character substitutions (e.g. O vs 0, S vs 5, 1 vs I).
        """
        words1 = text_pass1.split()
        words2 = text_pass2.split()

        disagreements = []
        # Fast align
        min_len = min(len(words1), len(words2))
        for i in range(min_len):
            w1 = words1[i]
            w2 = words2[i]
            if w1 != w2:
                # Check for confusion pairs
                is_critical = False
                for c1, c2 in zip(w1, w2):
                    if c1 != c2 and (self.CONFUSION_CHARS.get(c1) == c2 or self.CONFUSION_CHARS.get(c2) == c1):
                        is_critical = True
                        break
                disagreements.append({
                    "pass1": w1,
                    "pass2": w2,
                    "is_critical": is_critical
                })

        has_critical = any(d["is_critical"] for d in disagreements) or (abs(len(words1) - len(words2)) > 3)
        return has_critical, disagreements

    def compute_quality_metadata(
        self,
        image: Image.Image,
        confidence: float,
        retry_count: int,
        disagreements: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Generate structured quality metadata for audit and policy verification."""
        w, h = image.size
        # Approximate DPI assuming standard document dimensions if not tagged
        dpi_x = image.info.get("dpi", (150, 150))[0] if "dpi" in image.info else 150

        return {
            "image_dimensions": f"{w}x{h}",
            "estimated_dpi": int(dpi_x),
            "retry_count": retry_count,
            "average_confidence": round(confidence, 3),
            "disagreements_count": len(disagreements),
            "disagreements": disagreements[:5],
            "quality_status": "EXCELLENT" if confidence >= 0.85 and not disagreements else (
                "FAIR" if confidence >= 0.65 else "POOR"
            )
        }


default_ocr_enhancer = OCREnhancer()
