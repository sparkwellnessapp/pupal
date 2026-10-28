"""Draw the model's anchors ON the student's ink: a dot at each feature's [y, x] point with its
`as_written` label, and the figure's box. If the dots sit on the marks they name, an
overlay of the reading on the ink is a viable v1 surface; if they drift, it is not."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

OUT, PAGES = sys.argv[1], sys.argv[2]
raw = json.load(open(os.path.join(OUT, "raw.json"), encoding="utf-8"))
try:
    FONT = ImageFont.truetype("arial.ttf", 22)
except Exception:
    FONT = ImageFont.load_default()

COLORS = {"vertical_asymptote": (220, 30, 30), "horizontal_asymptote": (220, 30, 30),
          "minimum": (0, 120, 220), "maximum": (0, 120, 220),
          "x_intercept": (0, 150, 60), "y_intercept": (0, 150, 60)}

for arm in ("v2-flash", "v2-pro"):
    for page in ("math4_p10", "math4_p11", "math4_p12", "math3_p07", "math3_p08"):
        draws = raw.get(f"E2|{arm}|{page}", [])
        ok = [d for d in draws if d.get("ok")]
        if not ok:
            continue
        src = next(os.path.join(PAGES, page + e) for e in (".jpeg", ".png") if os.path.exists(os.path.join(PAGES, page + e)))
        im = Image.open(src).convert("RGB"); W, H = im.size
        dr = ImageDraw.Draw(im)
        for fig in ok[0]["data"].get("figures") or []:
            b = fig.get("box_2d") or []
            if len(b) == 4:
                dr.rectangle([b[1] * W / 1000, b[0] * H / 1000, b[3] * W / 1000, b[2] * H / 1000],
                             outline=(150, 0, 200), width=3)
            for f in fig.get("features") or []:
                p = f.get("point") or []
                if len(p) != 2:
                    continue
                x, y = p[1] * W / 1000, p[0] * H / 1000
                c = COLORS.get(f.get("kind"), (255, 120, 0))
                dr.ellipse([x - 9, y - 9, x + 9, y + 9], outline=c, width=4)
                dr.text((x + 12, y - 12), f"{f.get('as_written','')}", fill=c, font=FONT)
        out = os.path.join(OUT, f"overlay_{arm}_{page}.jpg")
        im.save(out, quality=82)
        print("wrote", out)
