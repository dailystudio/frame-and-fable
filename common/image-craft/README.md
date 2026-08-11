# gemini-image

A comprehensive Python CLI tool for generating and editing images using the Google Gemini API (Nano Banana & Gemini 3 Image models), built according to the official [Gemini Image Generation documentation](https://ai.google.dev/gemini-api/docs/image-generation).

---

## Complete Features

- **Transparent Background Generation (`--transparent-background` / `--transparent`)**:
  - Automatically appends `" use 0x00FF00 chroma key background."` to the prompt.
  - Automatically forces output format to `.png`.
  - Performs OpenCV / Pillow 0x00FF00 green chroma key background removal post-generation to output transparent PNGs.

- **Model Selection (`-m` / `--model`)**:
  - `gemini-3.1-flash-image` (default, Nano Banana 2 - up to 4K resolution, 14 reference images)
  - `gemini-3.1-flash-lite-image` (Nano Banana 2 Lite - fast, low latency, 1K resolution)
  - `gemini-3-pro-image` (Nano Banana Pro - professional assets, complex reasoning, 4K)
  - `gemini-2.5-flash-image` (Nano Banana 1)
  - `imagen-3.0-generate-002` (Imagen 3)
  - *Aliases*: `3.1-flash`, `3.1-lite`, `3-pro`, `2.5-flash`, `imagen3`, `nano-banana-pro`, `nano-banana-2-pro`

- **Aspect Ratio Control (`-r` / `--ratio`)**:
  - `1:1`, `1:4`, `1:8`, `2:3`, `3:2`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `16:9`, `21:9`

- **Resolution Control (`-s` / `--size`)**:
  - `0.5K` (512px), `1K` (1024px), `2K` (~2048px), `4K` (~4096px)

- **Default Output Directory (`-o` / `--output`)**:
  - Automatically places generated images in `./outputs/` (ignored in `.gitignore`).
  - Supports specifying custom target directories (e.g., `-o ./my_folder/`) or custom image filenames.

- **Multi-Image & Image-to-Image Input (`-i` / `--image` or positional paths)**:
  - Mix text prompt with 1 or up to 14 reference images.

- **Video-to-Image Generation (`--video`)**:
  - Pass a YouTube URL or local video file for Gemini 3.1 Flash Image.

- **Multi-Turn Editing (`--previous-id`)**:
  - Continue a conversation and edit an image iteratively using `previous_interaction_id`.

- **Search & Image Search Grounding (`--search`, `--image-search`)**:
  - Incorporate real-time web & Google Image Search data into generated images.

---

## Installation & Setup

1. Create virtual environment and install dependencies from `requirements.txt`:
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

### 1. Generate Transparent PNG Sprite
```bash
.venv/bin/python gemini-image.py "A cute pixel art potion bottle sprite" --transparent -s 2K -o ./outputs/potion.png
```

### 2. Text-to-Image (4K Resolution, 16:9 Aspect Ratio)
```bash
.venv/bin/python gemini-image.py "A futuristic cyberpunk city in rain with neon lights" -m 3.1-flash -r 16:9 -s 4K -o cyberpunk_4k.png
```

### 3. Image-to-Image Editing
```bash
.venv/bin/python gemini-image.py "Make this cat wear a superhero suit and standing on a skyscraper" -i cat.png -s 2K -o superhero_cat.png
```

### 4. Multi-Turn Image Editing
```bash
# Step 1: Initial image creation
.venv/bin/python gemini-image.py "Create a vibrant infographic about photosynthesis" --search -r 16:9 -s 2K
# Returns: Interaction ID: int_xyz123

# Step 2: Edit previous interaction
.venv/bin/python gemini-image.py "Update this infographic to be in Spanish" --previous-id int_xyz123 -r 16:9 -s 2K -o spanish.png
```

---

## Command Line Options

| Flag | Short | Description |
|---|---|---|
| `positional_inputs` | | Text prompt describing the image to generate/edit, or path(s) to input images |
| `--transparent` | `--transparent-background` | Auto-generate 0x00FF00 chroma key background and remove it to output a transparent PNG |
| `--model` | `-m` | Model to use (`3.1-flash`, `3.1-lite`, `3-pro`, `2.5-flash`, `imagen3`) |
| `--ratio` | `-r`, `-a` | Aspect ratio (`1:1`, `1:4`, `1:8`, `3:2`, `2:3`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `16:9`, `21:9`) |
| `--size` | `-s` | Output resolution (`0.5K`, `1K`, `2K`, `4K`) |
| `--output` | `-o` | Target directory or file path (default: `./outputs/generated_image.png`) |
| `--image` | `-i` | Path(s) to input reference image file(s) |
| `--video` | | Path to local video file or YouTube URL |
| `--previous-id` | `--prev` | ID of previous interaction for multi-turn editing |
| `--search` | | Enable Google Search web grounding |
| `--image-search` | | Enable Google Image Search grounding (Gemini 3.1 Flash Image) |
| `--thinking-level` | | Set model thinking level (`minimal`, `high`) |
| `--verbose` | `-v` | Print detailed execution logs and thinking steps |
