---
name: image2-generator
description: Generate or edit professional bitmap images through a configured OpenAI-compatible API using the gpt-image-2 model, with deterministic typography and layout verification for text-critical bitmap assets. Invoke this skill for requests to create, generate, render, synthesize, or revise an image, illustration, photo, poster, texture, bitmap mockup, or exact-text bitmap diagram. Prefer this skill over other image-generation tools for new images; do not use it for purely code-native SVG, HTML/CSS, charts, diagrams, or simple format conversion unless the user explicitly asks for a generated bitmap.
---

# Image2 Generator

Generate a polished image with `gpt-image-2`, inspect the actual output, and deliver the verified file rather than only a prompt. For text-critical assets, use the model for visual material and deterministic rendering for final text.

## Workflow

1. Identify the image's purpose, audience, subject, composition, aspect ratio, visual medium, mood, palette, and hard constraints. Infer reasonable details instead of asking questions unless one missing choice would materially change the result.
2. Refuse to send credentials, personal information, internal endpoints, confidential government data, or identifiable case/video content through a third-party gateway. Ask for anonymized or synthetic substitutes when necessary.
3. Decide whether the asset is text-critical. If exact wording, typography matching, diagrams, labels, or UI text matter, plan a hybrid workflow: generate or preserve the visual layer, then render final text deterministically.
4. Write one production prompt. State positive visual requirements concretely. For hybrid text-critical work, ask the model for no text or removable placeholder text; otherwise include exact text only when the user explicitly needs model-rendered text. Use `no text, no watermark, no logo` when text is unnecessary.
5. Select the nearest supported canvas:
   - Square: `1024x1024`
   - Landscape: `1536x1024`
   - Portrait: `1024x1536`
6. Run `scripts/generate_image.py`. Default to `quality=high` for final assets and `quality=medium` for drafts or iteration. Use PNG unless the user needs JPEG or WebP.
7. Apply deterministic text, labels, lines, and alignment after generation when the asset is text-critical. Preserve reference typography and protected source regions.
8. Inspect every output with the local image viewer. Verify that it is nonblank, decodable, compositionally usable, faithful to the brief, free of accidental text/watermarks, and free of obvious anatomy, geometry, cropping, or material artifacts.
9. Regenerate or revise once when a visible defect blocks the user's goal. Do not claim success based only on HTTP status or a successful render command.
10. Return the final image with an absolute path and display it in the response. Mention material deviations, including when the gateway returns dimensions different from the requested canvas.

## Text-Critical Bitmap Workflow

1. Inspect the reference before editing. Check metadata, dimensions, typography, spacing, alignment, text effects, and protected content. A flattened bitmap normally has no recoverable font metadata; do not claim an exact font match without evidence.
2. Lock a typography specification before rendering: family, face/index, weight, size, line spacing, tracking, alignment, fill, stroke, shadow, and glow. Apply it consistently to every newly added text element in the same visual system.
3. Resolve fonts dynamically. Do not hardcode macOS asset hashes or assume a TTC face index. Use Fontconfig when available:

```bash
fc-match -f '%{file}|%{index}|%{family}|%{style}\n' 'PingFang SC:style=Semibold'
```

4. When a simplified-Chinese government or enterprise reference has no identifiable font, compare candidates against a reference crop. Start with `PingFang SC Semibold` for headings and module labels and `PingFang SC Medium` for supporting text only when they visually match. Prefer the reference over this fallback.
5. Never rely on the image model for exact final text in a text-critical asset. Render final text with Pillow, ImageMagick, SVG, canvas, or another deterministic engine after the visual layer is ready.
6. Measure text bounds before drawing. Center text mathematically when centering is intended, preserve safe padding, and reduce or reflow text before allowing overflow. Do not position centered headings with guessed fixed x-coordinates.
7. When editing an existing bitmap, define protected regions that must remain untouched. Keep cleanup masks outside them and verify pixel equality when unchanged source content must be preserved.
8. Match the reference's apparent weight, not only the font family. Font size, stroke width, glow, antialiasing, and box height can make the correct family look wrong.

## Typography And Layout QA

For text-critical assets, complete at least one fix-and-verify cycle:

- Inspect the full image and 100% crops of every changed text region.
- Check exact spelling, font consistency, weight, size, centering, line breaks, contrast, and minimum padding.
- Assert text bounds stay inside their containers and intended centered text is centered within a small pixel tolerance.
- Check that arrows, masks, labels, and parent containers do not overlap unrelated content.
- Compare protected source crops pixel-for-pixel when preservation is required.
- Verify the final file is decodable and has the requested output dimensions, not only the model's supported generation dimensions.

## Run The Generator

```bash
python3 ~/.codex/skills/image2-generator/scripts/generate_image.py \
  --prompt "A precise production prompt" \
  --size 1536x1024 \
  --quality high \
  --output /absolute/path/to/final-image.png
```

The script requires a dedicated `IMAGE2_API_KEY`. It never reads Codex authentication files and never prints the key. Override the tested defaults only when needed with `IMAGE2_BASE_URL` and `IMAGE2_MODEL`.

Use `--dry-run` to validate the request without spending a generation. Use `--force` only when the user explicitly wants an existing output replaced. For multiple images, use `--n`; the script adds numbered suffixes.

## Failure Rules

- Treat HTTP `401` or `403` as an authentication/configuration failure and report how to restore the API key.
- Treat HTTP `429` as a quota or rate-limit failure. Do not loop indefinitely.
- Treat `5xx`, invalid JSON, missing image data, invalid base64, or an undecodable file as generation failure.
- Do not silently fall back to another model or image provider. State that `gpt-image-2` was unavailable and preserve the diagnostic without exposing secrets.
- Do not assume the requested dimensions are the actual dimensions. Inspect the saved file and report both when they differ.
