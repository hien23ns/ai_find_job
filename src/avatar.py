"""
Avatar extraction and embedding module.
Strictly confined to PROJECT_ROOT.
Extracts candidate portrait photo from PDF in data/private/ without modifying facial features or using AI.
Saves to data/private/assets/avatar.png (ignored by Git).
"""

import os
import io
import re
import zlib
import base64
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DIR = PROJECT_ROOT / "data" / "private"
ASSETS_DIR = PRIVATE_DIR / "assets"
AVATAR_PATH = ASSETS_DIR / "avatar.png"


def ensure_asset_dir():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def get_existing_avatar() -> Optional[Path]:
    """Check if avatar already exists."""
    if AVATAR_PATH.exists() and AVATAR_PATH.stat().st_size > 0:
        return AVATAR_PATH
    return None


def get_avatar_base64() -> Optional[str]:
    """Return base64 Data URI for avatar if available."""
    avatar = get_existing_avatar()
    if avatar:
        data = avatar.read_bytes()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    return None


def extract_avatar_from_pdf(pdf_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Extract original portrait photo from PDF without modification.
    Looks for PDF in data/private/ if not specified.
    Returns (success, message).
    """
    ensure_asset_dir()

    if pdf_path is None:
        target_name = "CV_NgoVanHien_Network-And-Information-Security.pdf"
        direct_path = PRIVATE_DIR / target_name
        assets_path = ASSETS_DIR / target_name
        if direct_path.exists():
            pdf_path = direct_path
        elif assets_path.exists():
            pdf_path = assets_path
        else:
            # Check for any PDF inside data/private/
            pdf_files = list(PRIVATE_DIR.rglob("*.pdf"))
            if pdf_files:
                pdf_path = pdf_files[0]
            else:
                return False, (
                    f"File '{target_name}' chưa nằm trong thư mục dự án. "
                    f"Theo đúng quy tắc an toàn bảo mật, hệ thống không quét ra ngoài PROJECT_ROOT. "
                    f"Xin vui lòng chép file PDF vào 'data/private/' để hệ thống trích xuất ảnh chân dung gốc."
                )

    if not pdf_path.exists():
        return False, f"Không tìm thấy file: {pdf_path}"

    # Try PyMuPDF image extraction first
    try:
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / ".local" / "lib"))
        import pymupdf
        doc = pymupdf.open(pdf_path)
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                base_img = doc.extract_image(xref)
                img_bytes = base_img["image"]
                img = Image.open(io.BytesIO(img_bytes))
                w, h = img.size
                if w >= 80 and h >= 80:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(AVATAR_PATH, format="PNG")
                    return True, f"Trích xuất thành công ảnh chân dung gốc ({w}x{h}) vào '{AVATAR_PATH.relative_to(PROJECT_ROOT)}'."
    except Exception:
        pass

    try:
        pdf_bytes = pdf_path.read_bytes()
    except Exception as e:
        return False, f"Không thể đọc file PDF: {e}"

    # Search for embedded JPEG streams (magic bytes \xff\xd8\xff ... \xff\xd9)
    jpeg_matches = list(re.finditer(b"\xff\xd8\xff[\s\S]+?\xff\xd9", pdf_bytes))
    extracted_images = []

    for idx, match in enumerate(jpeg_matches):
        img_bytes = match.group(0)
        try:
            img = Image.open(io.BytesIO(img_bytes))
            w, h = img.size
            if w >= 80 and h >= 80:
                aspect = h / float(w)
                extracted_images.append({
                    "image": img,
                    "bytes": img_bytes,
                    "size": (w, h),
                    "aspect": aspect,
                    "area": w * h
                })
        except Exception:
            continue

    if extracted_images:
        # Sort by aspect ratio closest to standard portrait (1.25 to 1.33: 4x5 or 3x4) and reasonable size
        def portrait_score(item):
            aspect_diff = abs(item["aspect"] - 1.3)
            return (aspect_diff, -item["area"])

        best = sorted(extracted_images, key=portrait_score)[0]
        try:
            best_img = best["image"]
            # Convert to RGB if needed
            if best_img.mode != "RGB":
                best_img = best_img.convert("RGB")
            best_img.save(AVATAR_PATH, format="PNG")
            return True, f"Trích xuất thành công ảnh chân dung gốc ({best['size'][0]}x{best['size'][1]}) vào '{AVATAR_PATH.relative_to(PROJECT_ROOT)}'."
        except Exception as e:
            return False, f"Lỗi khi lưu ảnh chân dung: {e}"

    # Fallback: check FlateDecode streams if no raw JPEG found
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1200, "height": 1600})
            page.goto(f"file:///{pdf_path.resolve().as_posix()}")
            page.wait_for_timeout(1000)
            # Clip top-right or top-left portrait area
            screenshot_bytes = page.screenshot(type="png")
            browser.close()
            
            page_img = Image.open(io.BytesIO(screenshot_bytes))
            # Typically portrait is in top 30% of page
            w, h = page_img.size
            # Crop top-right or top-left if detectable
            # For safety, save original image without modifying facial features
            return False, "Không phát hiện luồng ảnh JPEG riêng biệt trong PDF. Cần rà soát cấu trúc PDF."
    except Exception:
        pass

    return False, "Không tìm thấy luồng ảnh chân dung phù hợp trong file PDF."
