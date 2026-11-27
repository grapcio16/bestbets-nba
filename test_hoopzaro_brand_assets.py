"""Offline brand extraction checks. No production assets or network needed."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from scripts.prepare_hoopzaro_brand import prepare

class BrandExportTests(unittest.TestCase):
    def test_native_crops_and_icon_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            image = Image.new("RGB", (1536, 1024), "#05091e")
            image.putpixel((76,160), (22,233,250))
            image.putpixel((978,237), (154,79,246))
            image.save(source)
            out = root / "out"
            prepare(source, out)
            with Image.open(out / "hoopzaro-web-master.png") as web:
                self.assertEqual(web.size, (829,636))
                self.assertEqual(web.getpixel((0,0)), (22,233,250))
            with Image.open(out / "hoopzaro-mobile-master.png") as mobile:
                self.assertEqual(mobile.size, (500,500))
                self.assertEqual(mobile.getpixel((0,0)), (154,79,246))
            for n in (192,512,1024):
                with Image.open(out / f"hoopzaro-icon-{n}.png") as icon:
                    self.assertEqual(icon.size, (n,n))
            with Image.open(out / "favicon.ico") as favicon:
                self.assertEqual(favicon.ico.sizes(), {(16,16),(32,32),(48,48)})

    def test_wrong_size_fails_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "wrong.png"
            Image.new("RGB", (100,100)).save(source)
            with self.assertRaises(ValueError):
                prepare(source, root / "out")
            self.assertFalse((root / "out").exists())

if __name__ == "__main__":
    unittest.main()
