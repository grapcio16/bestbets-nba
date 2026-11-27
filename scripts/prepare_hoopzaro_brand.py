"""Extract original Hoopzaro brand assets from the owner-provided 1536x1024 PNG.
No tracing, recoloring or background removal. Requires Pillow.
Usage: python scripts/prepare_hoopzaro_brand.py SOURCE.png OUTPUT_DIR
"""
import argparse
from pathlib import Path
from PIL import Image

def prepare(source: Path, output: Path):
    with Image.open(source) as image:
        if image.size != (1536, 1024):
            raise ValueError("Expected the approved 1536 x 1024 composite; review new source manually.")
        rgb = image.convert("RGB")
    output.mkdir(parents=True, exist_ok=True)
    web = rgb.crop((76, 160, 905, 796))
    mobile = rgb.crop((978, 237, 1478, 737))
    emblem = rgb.crop((288, 190, 690, 592))
    web.save(output / "hoopzaro-web-master.png", optimize=True)
    web.resize((414, 318), Image.Resampling.LANCZOS).save(output / "hoopzaro-web.webp", quality=92, method=6)
    mobile.save(output / "hoopzaro-mobile-master.png", optimize=True)
    for size in (192, 512, 1024):
        mobile.resize((size, size), Image.Resampling.LANCZOS).save(output / f"hoopzaro-icon-{size}.png", optimize=True)
    for size in (32, 48):
        emblem.resize((size, size), Image.Resampling.LANCZOS).save(output / f"favicon-{size}.png", optimize=True)
    emblem.resize((48, 48), Image.Resampling.LANCZOS).save(output / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # Validate generated dimensions; native source remains the authority.
    for name, expected in {"hoopzaro-web-master.png": (829, 636), "hoopzaro-web.webp": (414, 318),
                            "hoopzaro-mobile-master.png": (500, 500),
                            **{f"hoopzaro-icon-{n}.png": (n, n) for n in (192, 512, 1024)},
                            **{f"favicon-{n}.png": (n, n) for n in (32, 48)}}.items():
        with Image.open(output / name) as result:
            if result.size != expected:
                raise RuntimeError(f"Unexpected size for {name}: {result.size}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.source, args.output)
