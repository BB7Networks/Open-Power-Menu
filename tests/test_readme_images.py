"""Keep the product gallery's actual PNG references usable in source archives."""
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]


def test_readme_gallery_images_exist():
    for doc in (ROOT / 'README.md', ROOT / 'docs/images/README.md'):
        references = re.findall(r'<img\s+src="([^"]+)"\s+alt="([^"]+)"', doc.read_text())
        assert len(references) >= 3
        for target, alt in references:
            image = (doc.parent / target).read_bytes()
            assert image[:8] == b'\x89PNG\r\n\x1a\n'
            width, height = struct.unpack('>II', image[16:24])
            assert width > 100 and height > 100
            assert alt
