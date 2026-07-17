from __future__ import annotations

import importlib.util
import os
import struct
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "generate_image.py"
SPEC = importlib.util.spec_from_file_location("generate_image", SCRIPT_PATH)
assert SPEC and SPEC.loader
generate_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_image)


class GenerateImageTests(unittest.TestCase):
    def test_requires_dedicated_api_key(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "must-not-be-used"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                generate_image.GenerationError,
                "dedicated IMAGE2_API_KEY",
            ):
                generate_image.load_api_key()

    def test_reads_and_trims_dedicated_api_key(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"IMAGE2_API_KEY": "  dedicated-key  "},
            clear=True,
        ):
            self.assertEqual(generate_image.load_api_key(), "dedicated-key")

    def test_builds_endpoint_for_base_and_v1_urls(self) -> None:
        self.assertEqual(
            generate_image.build_endpoint("https://example.com"),
            "https://example.com/v1/images/generations",
        )
        self.assertEqual(
            generate_image.build_endpoint("https://example.com/v1/"),
            "https://example.com/v1/images/generations",
        )

    def test_reads_png_dimensions(self) -> None:
        header = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 8) + struct.pack(">II", 1536, 1024)
        self.assertEqual(
            generate_image.inspect_image(header),
            {"format": "png", "width": 1536, "height": 1024},
        )

    def test_rejects_unknown_image_bytes(self) -> None:
        with self.assertRaisesRegex(
            generate_image.GenerationError,
            "not a supported PNG, JPEG, or WebP",
        ):
            generate_image.inspect_image(b"not-an-image")


if __name__ == "__main__":
    unittest.main()
