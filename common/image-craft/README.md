# gemini-image

A comprehensive Python CLI tool for generating and editing images using the Google Gemini API (Nano Banana & Gemini 3 Image models), built according to the official [Gemini Image Generation documentation](https://ai.google.dev/gemini-api/docs/image-generation).

---

## Complete Features

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

- **Multi-Image & Image-to-Image Input (`-i` / `--image` or positional paths)**:
  - Mix text prompt with 1 or up to 14 reference images
  - Perform image editing, style transfer, character consistency, and object inclusion

- **Video-to-Image Generation (`--video`)**:
  - Pass a YouTube URL or local video file for Gemini 3.1 Flash Image to generate posters/thumbnails

- **Multi-Turn Editing (`--previous-id`)**:
  - Continue a conversation and edit an image iteratively using `previous_interaction_id`

- **Search & Image Search Grounding (`--search`, `--image-search`)**:
  - Incorporate real-time web & Google Image Search data into generated images

- **Thinking Level (`--thinking-level`)**:
  - Adjust model thinking level (`minimal` or `high`)

---

## Installation & Setup

1. Install dependencies:
   ```bash
   pip install google-genai pillow
   ```

2. Set your Gemini API Key:
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   ```

---

## Usage Examples

### 1. Text-to-Image (4K Resolution, 16:9 Aspect Ratio)
```bash
./gemini-image "A futuristic cyberpunk city in rain with neon lights" -m 3.1-flash -r 16:9 -s 4K -o cyberpunk_4k.png
```

### 2. Image-to-Image Editing
```bash
./gemini-image "Make this cat wear a superhero suit and standing on a skyscraper" -i cat.png -s 2K -o superhero_cat.png
# Or pass image path directly:
./gemini-image cat.png "Make this cat wear a superhero suit" -s 2K
```

### 3. Multi-Turn Image Editing
```bash
# Step 1: Initial image creation
./gemini-image "Create a vibrant infographic about photosynthesis" --search -r 16:9 -s 2K
# Returns: Interaction ID: int_xyz123

# Step 2: Edit previous interaction
./gemini-image "Update this infographic to be in Spanish" --previous-id int_xyz123 -r 16:9 -s 2K -o spanish.png
```

### 4. Grounding with Google Web & Image Search
```bash
./gemini-image "A detailed painting of a Timareta butterfly resting on a flower" -m 3.1-flash --search --image-search -r 16:9 -s 4K
```

### 5. Video-to-Image Poster Generation
```bash
./gemini-image "Generate a movie poster capturing key themes of this video" --video "https://www.youtube.com/watch?v=UTdfxFyOQTI" -r 16:9 -s 2K -o poster.png
```

---

## Command Line Options

| Flag | Short | Description |
|---|---|---|
| `positional_inputs` | | Text prompt describing the image to generate/edit, or path(s) to input images |
| `--model` | `-m` | Model to use (`3.1-flash`, `3.1-lite`, `3-pro`, `2.5-flash`, `imagen3`) |
| `--ratio` | `-r`, `-a` | Aspect ratio (`1:1`, `1:4`, `1:8`, `3:2`, `2:3`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `16:9`, `21:9`) |
| `--size` | `-s` | Output resolution (`0.5K`, `1K`, `2K`, `4K`) |
| `--image` | `-i` | Path(s) to input reference image file(s) |
| `--video` | | Path to local video file or YouTube URL |
| `--previous-id` | `--prev` | ID of previous interaction for multi-turn editing |
| `--output` | `-o` | Output file path (default: `generated_image.png`) |
| `--format` | `-f` | Output image format (`png`, `jpeg`, `webp`) |
| `--search` | | Enable Google Search web grounding |
| `--image-search` | | Enable Google Image Search grounding (Gemini 3.1 Flash Image) |
| `--thinking-level` | | Set model thinking level (`minimal`, `high`) |
| `--api-key` | | Pass Gemini API key explicitly |
| `--list-models` | | List available models and descriptions |
| `--list-ratios` | | List supported aspect ratios and sizes |
| `--verbose` | `-v` | Print detailed execution logs and thinking steps |
