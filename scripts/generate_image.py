#!/usr/bin/env python3
"""Generate images through the configured GPT Image 2 compatible endpoint."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import struct
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://kuaikuaiai.top"
DEFAULT_MODEL = "gpt-image-2"
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
FORMAT_SUFFIXES = {
    "png": {".png"},
    "jpeg": {".jpg", ".jpeg"},
    "webp": {".webp"},
}


class GenerationError(RuntimeError):
    """Raised when the image API or returned artifact is invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a bitmap with GPT Image 2.")
    parser.add_argument("--prompt", required=True, help="Production-ready image prompt.")
    parser.add_argument("--output", type=Path, help="Output file path.")
    parser.add_argument(
        "--size",
        choices=("1024x1024", "1536x1024", "1024x1536"),
        default="1024x1024",
    )
    parser.add_argument(
        "--quality", choices=("low", "medium", "high"), default="high"
    )
    parser.add_argument(
        "--format", choices=("png", "jpeg", "webp"), default="png"
    )
    parser.add_argument(
        "--background", choices=("auto", "opaque", "transparent"), default="auto"
    )
    parser.add_argument("--n", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--force", action="store_true", help="Replace existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Print request, do not call API.")
    return parser.parse_args()


def default_output(output_format: str) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    extension = "jpg" if output_format == "jpeg" else output_format
    return Path.home() / "Pictures" / "Codex" / f"image2-{timestamp}.{extension}"


def load_api_key() -> str:
    value = os.environ.get("IMAGE2_API_KEY", "").strip()
    if not value:
        raise GenerationError("No API key found; set the dedicated IMAGE2_API_KEY.")
    return value


def build_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    suffix = "/images/generations" if normalized.endswith("/v1") else "/v1/images/generations"
    return normalized + suffix


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": os.environ.get("IMAGE2_MODEL", DEFAULT_MODEL),
        "prompt": args.prompt,
        "size": args.size,
        "quality": args.quality,
        "output_format": args.format,
        "n": args.n,
    }
    if args.background != "auto":
        payload["background"] = args.background
    return payload


def api_error_message(status: int, raw: bytes) -> str:
    try:
        body = json.loads(raw.decode("utf-8"))
        detail = body.get("error", body)
        if isinstance(detail, dict):
            detail = detail.get("message", json.dumps(detail, ensure_ascii=False))
        return f"Image API returned HTTP {status}: {detail}"
    except (UnicodeDecodeError, json.JSONDecodeError):
        return f"Image API returned HTTP {status} with a non-JSON response."


def call_api(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        build_endpoint(os.environ.get("IMAGE2_BASE_URL", DEFAULT_BASE_URL)),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            if exc.code not in RETRYABLE_STATUS or attempt == 2:
                raise GenerationError(api_error_message(exc.code, raw)) from exc
        except urllib.error.URLError as exc:
            if attempt == 2:
                raise GenerationError(f"Image API connection failed: {exc.reason}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GenerationError("Image API returned invalid JSON.") from exc
        time.sleep(2**attempt)
    raise GenerationError("Image API request failed after retries.")


def decode_item(item: dict[str, Any]) -> bytes:
    encoded = item.get("b64_json")
    if encoded:
        try:
            return base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise GenerationError("Image API returned invalid base64 data.") from exc
    url = item.get("url")
    if isinstance(url, str) and url.startswith("https://"):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except urllib.error.URLError as exc:
            raise GenerationError(f"Generated image download failed: {exc.reason}") from exc
    raise GenerationError("Image response contains neither b64_json nor an HTTPS URL.")


def inspect_image(data: bytes) -> dict[str, Any]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return {"format": "png", "width": width, "height": height}
    if data.startswith(b"\xff\xd8\xff"):
        return {"format": "jpeg", "width": None, "height": None}
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return {"format": "webp", "width": None, "height": None}
    raise GenerationError("Returned bytes are not a supported PNG, JPEG, or WebP image.")


def numbered_path(base: Path, index: int, count: int) -> Path:
    if count == 1:
        return base
    return base.with_name(f"{base.stem}-{index + 1}{base.suffix}")


def validate_output(path: Path, output_format: str, count: int, force: bool) -> None:
    if path.suffix.lower() not in FORMAT_SUFFIXES[output_format]:
        expected = ", ".join(sorted(FORMAT_SUFFIXES[output_format]))
        raise GenerationError(
            f"Output extension must match {output_format}; expected {expected}."
        )
    for index in range(count):
        candidate = numbered_path(path, index, count).expanduser()
        if candidate.exists() and not force:
            raise GenerationError(
                f"Output already exists: {candidate}. Use --force to replace it."
            )


def write_atomic(path: Path, data: bytes, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise GenerationError(f"Output already exists: {path}. Use --force to replace it.")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def save_outputs(response: dict[str, Any], output: Path, force: bool) -> list[dict[str, Any]]:
    items = response.get("data")
    if not isinstance(items, list) or not items:
        raise GenerationError("Image API response has no generated image data.")
    results = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise GenerationError("Image API returned a malformed image item.")
        data = decode_item(item)
        metadata = inspect_image(data)
        path = numbered_path(output, index, len(items)).expanduser().resolve()
        write_atomic(path, data, force)
        results.append({"path": str(path), "bytes": len(data), **metadata})
    return results


def main() -> int:
    args = parse_args()
    if not args.prompt.strip():
        raise GenerationError("Prompt must not be empty.")
    if args.background == "transparent" and args.format == "jpeg":
        raise GenerationError("Transparent background requires PNG or WebP output.")
    payload = build_payload(args)
    output = args.output or default_output(args.format)
    validate_output(output, args.format, args.n, args.force)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "endpoint": build_endpoint(
                        os.environ.get("IMAGE2_BASE_URL", DEFAULT_BASE_URL)
                    ),
                    "payload": payload,
                    "output": str(output),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    response = call_api(payload, load_api_key())
    outputs = save_outputs(response, output, args.force)
    print(
        json.dumps(
            {"model": payload["model"], "requested_size": args.size, "outputs": outputs},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GenerationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
