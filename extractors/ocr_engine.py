import os
import io
import shutil
import logging
from typing import List, Dict, Any, Optional, Union
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Try importing pytesseract
try:
    import pytesseract
    from pytesseract import Output
    PYTESSERACT_INSTALLED = True
except ImportError:
    pytesseract = None
    Output = None
    PYTESSERACT_INSTALLED = False

# Known standard Windows paths for Tesseract
WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
]


class OCRStatus:
    SUCCESS = "SUCCESS"
    UNAVAILABLE = "UNAVAILABLE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    FAILED = "FAILED"


class OCRResult:
    def __init__(
        self,
        status: str,
        text: str,
        confidence: float = 0.0,
        blocks: Optional[List[Dict[str, Any]]] = None,
        error_message: Optional[str] = None,
        engine_used: str = "none",
        is_uncertain: bool = False
    ):
        self.status = status
        self.text = text
        self.confidence = confidence
        self.blocks = blocks or []
        self.error_message = error_message
        self.engine_used = engine_used
        self.is_uncertain = is_uncertain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "text": self.text,
            "confidence": self.confidence,
            "blocks_count": len(self.blocks),
            "error_message": self.error_message,
            "engine_used": self.engine_used,
            "is_uncertain": self.is_uncertain
        }


class OCREngine:
    def __init__(self, confidence_threshold: float = 0.60):
        self.confidence_threshold = confidence_threshold
        self._is_available: Optional[bool] = None
        self._tesseract_path: Optional[str] = None
        self._check_tesseract_availability()

    def _check_tesseract_availability(self):
        """Detect if Tesseract binary is accessible on the system."""
        if not PYTESSERACT_INSTALLED:
            self._is_available = False
            return

        # 1. Check custom environment variable
        custom_env = os.environ.get("TESSERACT_CMD")
        if custom_env and os.path.isfile(custom_env):
            pytesseract.pytesseract.tesseract_cmd = custom_env
            self._tesseract_path = custom_env
            self._is_available = True
            return

        # 2. Check if default command 'tesseract' is in PATH
        which_path = shutil.which("tesseract")
        if which_path:
            self._tesseract_path = which_path
            self._is_available = True
            return

        # 3. Check common Windows paths
        for p in WINDOWS_TESSERACT_PATHS:
            if os.path.isfile(p):
                pytesseract.pytesseract.tesseract_cmd = p
                self._tesseract_path = p
                self._is_available = True
                return

        # 4. Verify by attempting version check if still uncertain
        try:
            version = pytesseract.get_tesseract_version()
            self._is_available = True
        except Exception:
            self._is_available = False

    @property
    def is_available(self) -> bool:
        return bool(self._is_available)

    @property
    def tesseract_path(self) -> Optional[str]:
        return self._tesseract_path

    def preprocess_image(
        self,
        image: Image.Image,
        grayscale: bool = True,
        enhance_contrast: bool = True,
        threshold: bool = False
    ) -> Image.Image:
        """
        Enhance image quality prior to OCR using Pillow.
        - Grayscale conversion
        - Contrast amplification
        - Optional binarization thresholding
        """
        img = image.copy()
        if grayscale and img.mode != "L":
            img = img.convert("L")

        if enhance_contrast:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)

        if threshold and img.mode == "L":
            # Simple Otsu-like midpoint thresholding
            img = img.point(lambda p: 255 if p > 128 else 0)

        return img

    def _load_image(self, image_input: Union[Image.Image, bytes, bytearray, str]) -> Image.Image:
        if isinstance(image_input, Image.Image):
            return image_input
        elif isinstance(image_input, (bytes, bytearray)):
            return Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, str):
            return Image.open(image_input)
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

    def extract_text(
        self,
        image_input: Union[Image.Image, bytes, bytearray, str],
        lang: str = "eng",
        preprocess: bool = True
    ) -> OCRResult:
        """
        Execute OCR on the provided image and return structured OCRResult.
        Never pretends OCR succeeded if Tesseract is missing or execution fails.
        """
        if not self.is_available:
            return OCRResult(
                status=OCRStatus.UNAVAILABLE,
                text="[OCR_UNAVAILABLE: Tesseract OCR binary not found on system]",
                confidence=0.0,
                blocks=[],
                error_message=(
                    "Tesseract OCR is not installed or not configured in PATH. "
                    "Cannot safely extract text from image."
                ),
                engine_used="none",
                is_uncertain=True
            )

        try:
            pil_img = self._load_image(image_input)
            img_w, img_h = pil_img.size

            if preprocess:
                processed_img = self.preprocess_image(pil_img)
            else:
                processed_img = pil_img

            # Extract structured line/word data
            data = pytesseract.image_to_data(processed_img, lang=lang, output_type=Output.DICT)

            blocks_map = {}
            confidences = []
            full_text_parts = []

            n_boxes = len(data["level"])
            for i in range(n_boxes):
                word_text = data["text"][i].strip()
                raw_conf = float(data["conf"][i])

                if word_text:
                    full_text_parts.append(word_text)
                    if raw_conf >= 0:
                        confidences.append(raw_conf / 100.0)

                    block_num = data["block_num"][i]
                    line_num = data["line_num"][i]
                    key = (block_num, line_num)

                    left = data["left"][i]
                    top = data["top"][i]
                    width = data["width"][i]
                    height = data["height"][i]

                    norm_bbox = {
                        "x0": round(left / max(1, img_w), 4),
                        "y0": round(top / max(1, img_h), 4),
                        "x1": round((left + width) / max(1, img_w), 4),
                        "y1": round((top + height) / max(1, img_h), 4)
                    }

                    if key not in blocks_map:
                        blocks_map[key] = {
                            "block_num": block_num,
                            "line_num": line_num,
                            "words": [word_text],
                            "confidences": [raw_conf / 100.0] if raw_conf >= 0 else [],
                            "bbox": norm_bbox
                        }
                    else:
                        blocks_map[key]["words"].append(word_text)
                        if raw_conf >= 0:
                            blocks_map[key]["confidences"].append(raw_conf / 100.0)
                        # Expand bbox
                        curr = blocks_map[key]["bbox"]
                        curr["x0"] = min(curr["x0"], norm_bbox["x0"])
                        curr["y0"] = min(curr["y0"], norm_bbox["y0"])
                        curr["x1"] = max(curr["x1"], norm_bbox["x1"])
                        curr["y1"] = max(curr["y1"], norm_bbox["y1"])

            aggregated_blocks = []
            for (b_num, l_num), b_info in sorted(blocks_map.items()):
                b_text = " ".join(b_info["words"])
                b_conf = (
                    sum(b_info["confidences"]) / len(b_info["confidences"])
                    if b_info["confidences"] else 0.5
                )
                aggregated_blocks.append({
                    "text": b_text,
                    "confidence": round(b_conf, 3),
                    "bbox": b_info["bbox"],
                    "block_num": b_num,
                    "line_num": l_num
                })

            final_text = "\n".join([b["text"] for b in aggregated_blocks])
            avg_confidence = (
                sum(confidences) / len(confidences)
                if confidences else 0.0
            )

            # Determine security status
            if not final_text.strip():
                # Visual image had no readable text
                return OCRResult(
                    status=OCRStatus.SUCCESS,
                    text="",
                    confidence=1.0,
                    blocks=[],
                    engine_used="pytesseract",
                    is_uncertain=False
                )

            if avg_confidence < self.confidence_threshold:
                return OCRResult(
                    status=OCRStatus.LOW_CONFIDENCE,
                    text=final_text,
                    confidence=round(avg_confidence, 3),
                    blocks=aggregated_blocks,
                    engine_used="pytesseract",
                    is_uncertain=True,
                    error_message=f"Low OCR confidence ({avg_confidence*100:.1f}%)"
                )

            return OCRResult(
                status=OCRStatus.SUCCESS,
                text=final_text,
                confidence=round(avg_confidence, 3),
                blocks=aggregated_blocks,
                engine_used="pytesseract",
                is_uncertain=False
            )

        except Exception as e:
            logger.error(f"OCR execution failed: {e}")
            return OCRResult(
                status=OCRStatus.FAILED,
                text=f"[OCR_FAILED: {str(e)}]",
                confidence=0.0,
                blocks=[],
                error_message=str(e),
                engine_used="pytesseract" if self.is_available else "none",
                is_uncertain=True
            )


# Default shared instance
default_ocr_engine = OCREngine()
