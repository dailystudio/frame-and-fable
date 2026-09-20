# gemini-video

A comprehensive Python CLI tool for generating high-fidelity videos using the Google Gemini / Veo API (Veo 3.1 & Veo 3 models), built according to the official [Gemini Video Generation with Veo documentation](https://ai.google.dev/gemini-api/docs/veo).

---

## Complete Features

- **Reference Images-Guided Generation (`-i` / `--image` / `--ref-image`)**:
  - Guide the visual content, characters, items, and style of the video using up to 3 reference images.
  - Supports `--ref-type asset` (default, guides subject/character/outfit) and `--ref-type style` (visual aesthetics).
  - Explicit multi-reference flags: `--ref-asset` and `--ref-style`.

- **Image-to-Video Animation (`--start-frame` / `--first-frame`)**:
  - Animate an initial still image into a dynamic video scene.

- **First & Last Frame Interpolation (`--start-frame` and `--last-frame`)**:
  - Specify both starting and ending frames to generate a seamless transition video between the two images.

- **Gemini Chat API Prompt Generation & Visual Recognition (`--generate-prompt` / `--refine-prompt`)**:
  - Uses Gemini Chat API (multimodal vision) to inspect start/end frames or reference images and craft an optimal prompt.
  - When `--start-frame` and `--last-frame` are provided, Gemini recognizes the subjects, settings, and lighting in both frames and conceives a smooth, natural transition connecting them.
  - **Enforces strict default constraints**:
    * *No new characters*: Never invents or introduces extra characters/people not depicted in the source frames or reference images.
    * *Style alignment*: Strictly aligns art style, medium, color grading, lighting, and visual aesthetics with the reference images and keyframes.
    * *Character & asset consistency*: Keeps faces, hair, costumes, and props consistent throughout the video.
    * *Smooth motion*: Directs natural physical progression and cinematic camera choreography.
  - **Model:** Powered by Google's latest **Gemini 3.8 Flash** (`gemini-3.8-flash`) with automatic fallback to `gemini-2.5-flash`.
  - **Interactive Confirmation & `-y` / `--yes`:**
    * When `--generate-prompt` is run without `-y`, the tool displays the generated prompt and asks the user to confirm, edit, or cancel (`[Y/n/edit]`) before generating the video.
    * When `-y` or `--yes` is specified, the tool automatically generates the prompt and proceeds immediately to video generation.
  - Supports `--prompt-only` (preview prompt and exit without video generation), `--prompt-constraint` (custom limitations), and `--chat-model` (`gemini-3.8-flash` default).

- **Native Synchronized Audio**:
  - Veo 3.1 natively creates synchronized high-quality soundtracks including speech/dialogue in quotes, sound effects (SFX), and ambient soundscape.
  - Can be toggled with `--audio` (default) or `--no-audio`.

- **Model Selection (`-m` / `--model`)**:
  - `veo-3.1-generate-preview` (default, Veo 3.1 - up to 4K, 3 reference images, interpolation, native audio)
  - `veo-3.1-fast-generate-preview` (Veo 3.1 Fast - high speed generation with high quality, up to 4K)
  - `veo-3.1-lite-generate-preview` (Veo 3.1 Lite - low latency, cost-effective for scale, up to 1080p)
  - `veo-3.0-generate-001` (Veo 3.0 Stable - 720p & 1080p)
  - `veo-3.0-fast-generate-001` (Veo 3.0 Fast Stable)
  - `veo-2.0-generate-001` (Veo 2.0 Legacy)
  - *Aliases*: `3.1`, `3.1-fast`, `fast`, `3.1-lite`, `lite`, `3.0`, `3`, `2.0`, `2`

- **Aspect Ratio Control (`-r` / `--ratio`)**:
  - `16:9` (default landscape, cinematic widescreen)
  - `9:16` (portrait, vertical video for TikTok, Instagram Reels, YouTube Shorts)

- **Resolution Control (`-s` / `--size` / `--resolution`)**:
  - `720p` (1280x720 / 720x1280, default)
  - `1080p` (1920x1080 / 1080x1920, requires 8s duration)
  - `4k` (3840x2160 / 2160x3840, requires 8s duration, Veo 3.1 & Veo 3.1 Fast)

- **Duration Control (`-d` / `--duration`)**:
  - `4s`, `6s`, `8s` (default: `8s`)
  - Note: Reference images, 1080p, and 4K automatically enforce `8s` duration as required by the API.

- **Person Generation Control (`--person-generation`)**:
  - `allow_adult` (automatically selected for reference images and image inputs)
  - `allow_all` (available for text-to-video)

- **Default Output Directory & File Naming (`-o` / `--output`)**:
  - Automatically places generated videos in `./outputs/` (ignored in `.gitignore`).
  - By default, uses the unique operation ID or a sanitized hex token (e.g. `./outputs/64fa3b0c1e82.mp4`).
  - Supports specifying custom target directories (e.g. `-o ./my_videos/`) or exact filenames (e.g. `-o final.mp4`).

- **Video Extension (`--video` / `--extend`)**:
  - Extend existing Veo-generated videos up to 141 seconds.

- **Progress Feedback & Polling**:
  - Automatic progress reporting in the terminal with elapsed time and spinner.
  - Safe error reporting and fallback downloading.

---

## Installation & Setup

1. Create a virtual environment and install dependencies from `requirements.txt`:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Set your Gemini API Key:
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   ```

---

## Usage Examples

### 1. Video Generation Guided by Reference Images & Prompt
Pass up to 3 reference images (e.g., character portrait, costume, scenery) to guide the video generation:
```bash
python3 gemini-video.py "A graceful dancer wearing this dress performs inside a crystal palace, torchlight flickering, ethereal music echoing" \
  -i character.png dress.png \
  -o outputs/dance.mp4
```

### 2. Specify Reference Types (Asset vs Style)
Guide specific aspects using `--ref-asset` for subjects/characters and `--ref-style` for aesthetics:
```bash
python3 gemini-video.py "A warrior walking through a ruined temple in a neon rainstorm" \
  --ref-asset warrior.png \
  --ref-style cyberpunk_art.png \
  -o outputs/temple.mp4
```

### 3. Text-to-Video (4K Resolution, Cinematic 16:9, Native Audio)
Generate high-fidelity video with dialogue and sound effects:
```bash
python3 gemini-video.py "Drone shot following a classic red sports car along a winding coastal road at sunset. The driver accelerates, engine roaring loudly, waves crashing against the rocks below." \
  -r 16:9 \
  -s 4k \
  -o outputs/sunset_drive.mp4
```

### 4. Portrait Video for Social Media (9:16)
Create vertical videos tailored for TikTok, Instagram Reels, or YouTube Shorts:
```bash
python3 gemini-video.py "A barista carefully pouring steamed milk into espresso creating intricate latte art, coffee shop background ambience, soft jazz music" \
  -r 9:16 \
  -s 1080p \
  -o outputs/latte_art.mp4
```

### 5. Image-to-Video (Animate an Initial Image)
Bring an existing photo or character illustration to life:
```bash
python3 gemini-video.py "The sleeping kitten slowly opens its eyes, stretches its paws, and yawns cutely" \
  --start-frame kitten.png \
  -o outputs/kitten_wakes.mp4
```

### 6. Start, Middle & End Frames in a Single Shot
Start at `start.png`, end at `end.png`, and guide the intermediate motion/content using middle reference images (`mid1.png`, `mid2.png`):
```bash
python3 gemini-video.py "A continuous morphing transformation" \
  --start-frame start.png \
  --mid-frames mid1.png mid2.png \
  --last-frame end.png \
  -o outputs/single_shot_morph.mp4
```

### 7. Multi-Keyframe Sequential Storyboard (`--keyframes`)
Generate a multi-scene video that sequentially journeys through `start` -> `middle 1` -> `middle 2` -> `end`, automatically interpolated across scenes and stitched together via FFmpeg:
```bash
python3 gemini-video.py "A character journeying across four distinct seasons from spring to winter" \
  --keyframes spring_start.png summer_mid1.png autumn_mid2.png winter_end.png \
  -o outputs/four_seasons.mp4
```

### 8. Frame Interpolation with Gemini Chat AI Prompt Generation (`--generate-prompt`)
Gemini 3.8 Flash recognizes the visual content in `start.png` and `end.png`, devises a natural transition prompt between them with style & character constraints, prompts user for confirmation (`[y/n/r/s]`), and generates the video:
- `y` (yes): Proceed with video generation using current prompt.
- `n` (no): Cancel video generation.
- `r` (regeneration): Ask Gemini Chat API to regenerate a fresh alternative prompt.
- `s` (suggestion): Enter your suggestion / feedback to have Gemini Chat API modify and adapt the prompt.

```bash
python3 gemini-video.py \
  --start-frame start.png \
  --last-frame end.png \
  --generate-prompt \
  -o outputs/transition.mp4
```

### 9. Automatic Generation Without Asking Confirmation (`-y` / `--yes`)
Automatically generate prompt and proceed directly to video generation:
```bash
python3 gemini-video.py \
  --start-frame start.png \
  --last-frame end.png \
  --generate-prompt \
  -y \
  -o outputs/transition.mp4
```

### 10. Preview / Inspect Prompt Without Generating Video (`--prompt-only`)
Use Gemini Chat API to inspect frames and print the refined prompt without spending video generation credits:
```bash
python3 gemini-video.py \
  --start-frame start.png \
  --last-frame end.png \
  --generate-prompt \
  --prompt-only
```

### 11. Frame Interpolation with User Description
Create a seamless transition connecting two keyframe images with explicit user prompt:
```bash
python3 gemini-video.py "A mystical garden where flowers rapidly bloom as time speeds up from dawn to twilight" \
  --start-frame dawn.png \
  --last-frame twilight.png \
  -o outputs/timelapse.mp4
```

### 12. Fast Iteration with Veo 3.1 Fast
Generate rapid drafts with lower latency:
```bash
python3 gemini-video.py "Futuristic neon train arriving at an underground station" \
  -m fast \
  -o outputs/train.mp4
```

---

## Command Line Options

| Flag | Short | Description |
|---|---|---|
| `positional_inputs` | | Text prompt describing the video, or path(s) to input reference images |
| `--prompt` | `-p` | Text prompt description |
| `--image` / `--ref` | `-i` | Path(s) to reference image(s) (up to 3 images) |
| `--ref-type` | | Type of reference image (`asset` or `style`, default: `asset`) |
| `--ref-asset` | | Specific asset reference image (subject/character/costume) |
| `--ref-style` | | Specific style reference image (aesthetic/lighting) |
| `--start-frame` | `--first-frame` | Starting image to animate (Image-to-Video or start frame for interpolation) |
| `--mid-frames` | `--middle-frames` | Middle reference image(s) to guide motion between start and end frames |
| `--last-frame` | `--end-frame` | Ending image for frame interpolation (used with `--start-frame`) |
| `--keyframes` | `--sequence` | Ordered list of keyframe images (e.g. `start mid1 mid2 end`). Generates sequential scene transitions and stitches them via FFmpeg |
| `--model` | `-m` | Model to use (`3.1`, `3.1-fast`, `3.1-lite`, `3.0`, `3.0-fast`, `2.0`) |
| `--ratio` | `-r`, `-a` | Aspect ratio: `16:9` (default landscape) or `9:16` (portrait) |
| `--resolution` | `-s` | Output resolution (`720p`, `1080p`, `4k`) |
| `--duration` | `-d` | Duration in seconds (`4`, `6`, `8`, default: `8`) |
| `--fps` | | Output frame rate (default: `24`) |
| `--output` | `-o` | Target directory or specific file path (default: `./outputs/<operation_id>.mp4`) |
| `--audio` / `--no-audio` | | Toggle synchronized audio generation (speech, SFX, ambient) |
| `--negative-prompt` | | Elements or sounds to avoid in the generation |
| `--generate-prompt` | `--refine-prompt` | Call Gemini Chat API to analyze start/end frames or reference images and generate/refine prompt |
| `--enhance-prompt` | | Alias for `--generate-prompt` |
| `--prompt-only` | `--generate-prompt-only` | Generate and output prompt with Gemini Chat API, then exit without creating video |
| `--chat-model` | | Model for Gemini Chat prompt generation (default: `gemini-3.8-flash`) |
| `--yes` | `-y` | Automatically proceed with video generation after prompt generation without asking for confirmation |
| `--prompt-constraint` | `--constraint` | Add custom constraint(s) or limitation(s) to prompt generation |
| `--no-default-constraints` | | Disable default prompt constraints (no new characters, style alignment, etc.) |
| `--person-generation` | | Person generation policy (`allow_adult` or `allow_all`) |
| `--seed` | | Seed for reproducibility |
| `--video` | `--extend` | Video to extend (Veo 3.1) |
| `--mode` | | Handling mode (`auto`, `reference`, `start-frame`, `interpolate`) |
| `--poll-interval` | | Seconds between status polling queries (default: `10`) |
| `--timeout` | | Generation timeout in seconds (default: `600`) |
| `--list-models` | | Display all available models and their capabilities |
| `--list-ratios` | | Display supported aspect ratios, resolutions, and durations |
| `--verbose` | `-v` | Print detailed execution logs and API parameters |
