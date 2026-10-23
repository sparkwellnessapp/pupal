"""Synthetic pages for the pure pipeline tests — deterministic, no fixtures on disk."""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

A4_W, A4_H = 827, 1170          # an A4-proportioned page at 100 DPI


def text_page(w: int = A4_W, h: int = A4_H) -> np.ndarray:
    """White paper with dark "handwriting": text lines, a box, a diagonal."""
    page = np.full((h, w, 3), 245, np.uint8)
    rng = np.random.default_rng(7)
    for i, y in enumerate(range(80, h - 80, 46)):
        x = 60
        while x < w - 120:
            word = "".join(rng.choice(list("abcdefghij0123")) for _ in range(rng.integers(2, 7)))
            cv2.putText(page, word, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (25, 25, 30), 2,
                        cv2.LINE_AA)
            x += 22 * len(word) + 30
    cv2.rectangle(page, (60, h // 2), (w // 2, h // 2 + 200), (20, 20, 120), 3)
    cv2.line(page, (w // 2 + 40, h // 2), (w - 60, h // 2 + 200), (140, 20, 20), 3)
    return page


def on_desk(page: np.ndarray, corners_px, canvas=(1600, 1200)) -> np.ndarray:
    """Warp `page` onto a dark textured desk so its corners land at
    `corners_px` (TL,TR,BR,BL, canvas pixels)."""
    cw, ch = canvas
    rng = np.random.default_rng(11)
    desk = np.clip(rng.normal(60, 6, (ch, cw, 3)), 0, 255).astype(np.uint8)
    desk = cv2.GaussianBlur(desk, (7, 7), 0)
    h, w = page.shape[:2]
    src = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float32)
    dst = np.array(corners_px, np.float32)
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(page, m, (cw, ch), flags=cv2.INTER_CUBIC)
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), m, (cw, ch))
    out = desk.copy()
    out[mask > 127] = warped[mask > 127]
    return out


def to_jpeg(rgb: np.ndarray, quality: int = 95) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Mean SSIM of two same-size grayscale images (Wang et al., Gaussian window)."""
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    blur = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)
    mu_a, mu_b = blur(a), blur(b)
    s_a = blur(a * a) - mu_a ** 2
    s_b = blur(b * b) - mu_b ** 2
    s_ab = blur(a * b) - mu_a * mu_b
    num = (2 * mu_a * mu_b + c1) * (2 * s_ab + c2)
    den = (mu_a ** 2 + mu_b ** 2 + c1) * (s_a + s_b + c2)
    return float((num / den).mean())
