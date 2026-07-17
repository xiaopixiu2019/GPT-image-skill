from __future__ import annotations

import importlib.util
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "generate_image.py"
SPEC = importlib.util.spec_from_file_location("generate_image", SCRIPT_PATH)
assert SPEC and SPEC.loader
generate_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_image)


class GenerateImageTests(unittest.TestCase):
    def write_codex_files(
        self,
        root: Path,
        *,
        base_url: str = "https://kuaikuaiai.top",
        requires_openai_auth: bool = True,
        api_key: str | None = "codex-key",
    ) -> None:
        root.mkdir(parents=True, exist_ok=True)
        requires = "true" if requires_openai_auth else "false"
        (root / "config.toml").write_text(
            "model_provider = \"custom\"\n\n"
            "[model_providers.custom]\n"
            f"base_url = \"{base_url}\"\n"
            f"requires_openai_auth = {requires}\n",
            encoding="utf-8",
        )
        if api_key is not None:
            (root / "auth.json").write_text(
                json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": api_key}),
                encoding="utf-8",
            )

    def test_dedicated_key_supports_custom_gateway(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "IMAGE2_API_KEY": "  dedicated-key  ",
                "IMAGE2_BASE_URL": "https://images.example/v1",
            },
            clear=True,
        ):
            self.assertEqual(
                generate_image.resolve_credentials(),
                ("dedicated-key", "https://images.example/v1"),
            )

    def test_rejects_insecure_dedicated_gateway(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "IMAGE2_API_KEY": "dedicated-key",
                "IMAGE2_BASE_URL": "http://images.example",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                generate_image.GenerationError,
                "must be an HTTPS URL",
            ):
                generate_image.resolve_credentials()

    def test_reuses_codex_file_auth_for_allowed_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_codex_files(root, base_url="https://kuaikuaiai.top/v1/")
            with mock.patch.dict(os.environ, {"CODEX_HOME": temporary}, clear=True):
                self.assertEqual(
                    generate_image.resolve_credentials(),
                    ("codex-key", "https://kuaikuaiai.top/v1"),
                )

    def test_rejects_codex_auth_for_unapproved_gateway(self) -> None:
        unsafe_urls = (
            "http://kuaikuaiai.top",
            "https://attacker.example",
            "https://kuaikuaiai.top.attacker.example",
            "https://kuaikuaiai.top@attacker.example",
            "https://kuaikuaiai.top/v2",
            "https://kuaikuaiai.top?redirect=https://attacker.example",
        )
        for base_url in unsafe_urls:
            with self.subTest(base_url=base_url), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.write_codex_files(root, base_url=base_url, api_key=None)
                with mock.patch.dict(os.environ, {"CODEX_HOME": temporary}, clear=True):
                    with self.assertRaisesRegex(
                        generate_image.GenerationError,
                        "only be reused with https://kuaikuaiai.top",
                    ):
                        generate_image.resolve_credentials()

    def test_rejects_override_without_dedicated_key(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "IMAGE2_BASE_URL": "https://attacker.example",
                "OPENAI_API_KEY": "must-not-be-used",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                generate_image.GenerationError,
                "requires a dedicated IMAGE2_API_KEY",
            ):
                generate_image.resolve_credentials()

    def test_requires_provider_to_enable_openai_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_codex_files(root, requires_openai_auth=False)
            with mock.patch.dict(os.environ, {"CODEX_HOME": temporary}, clear=True):
                with self.assertRaisesRegex(
                    generate_image.GenerationError,
                    "does not allow guarded credential reuse",
                ):
                    generate_image.resolve_credentials()

    def test_reports_keychain_only_auth_as_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_codex_files(root, api_key=None)
            with mock.patch.dict(os.environ, {"CODEX_HOME": temporary}, clear=True):
                with self.assertRaisesRegex(
                    generate_image.GenerationError,
                    "OS keychain credentials are not read",
                ):
                    generate_image.resolve_credentials()

    def test_rejects_stale_key_from_another_auth_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_codex_files(root)
            (root / "auth.json").write_text(
                json.dumps(
                    {"auth_mode": "chatgpt", "OPENAI_API_KEY": "stale-key"}
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"CODEX_HOME": temporary}, clear=True):
                with self.assertRaisesRegex(
                    generate_image.GenerationError,
                    "not using active file-based API key authentication",
                ):
                    generate_image.resolve_credentials()

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
