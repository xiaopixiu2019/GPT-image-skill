# Repository Instructions

## Purpose

This repository distributes the `image2-generator` Codex skill and its deterministic command-line helper.

## Structure

- `SKILL.md`: Codex workflow and safety rules.
- `agents/openai.yaml`: Skill display metadata.
- `scripts/generate_image.py`: OpenAI-compatible image generation client.
- `README.md`: Human installation and usage guide.

## Security

- Never commit API keys, credentials, generated private images, personal data, or internal endpoints.
- Use only the dedicated `IMAGE2_API_KEY` environment variable for authentication.
- Treat the default gateway as a third-party service; use synthetic or public-safe prompts and assets.
- Keep high-impact government actions outside model-generated workflows.

## Validation

Run these checks after changes:

```bash
python3 -m py_compile scripts/generate_image.py
python3 scripts/generate_image.py --prompt "Safe synthetic test image" --dry-run
```

Validate `SKILL.md` with Codex's `quick_validate.py` when that tool is available.
