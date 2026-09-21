# 3D Model Creator (`model-creator`)

A modular, extensible Python pipeline and CLI tool to generate high-fidelity 3D assets (`.glb`, `.usdz`, `.fbx`, `.obj`, `.stl`) from **text descriptions** or **reference images** across multiple AI providers.

Currently supports **Hyper3D (Rodin Gen-2.5 API v2)** with full parameter configurability, async task polling with exponential backoff, rate-limit resilience, and automatic artifact downloading.

---

## Features

- **Multi-Provider Architecture**: Clean, pluggable design via `Base3DModelProvider` and `@register_provider`. Easily add new generative 3D providers (e.g. Tripo3D, Meshy, CSM).
- **Text-to-3D & Image-to-3D**:
  - Direct prompt-to-mesh generation.
  - Single or multi-view reference image uploads (1–5 images) with optional camera angle labels (`F`, `B`, `L`, `R`, etc.).
- **Hyper3D (Rodin Gen-2.5)** Integration:
  - Supports all tiers: `Gen-2.5-Medium` (default), `Gen-2.5-High`, `Gen-2.5-Extreme-High`, `Gen-2.5-Low`, `Gen-2.5-Extreme-Low`, `Gen-2`, and legacy tiers.
  - Multi-format output: `glb`, `usdz`, `fbx`, `obj`, `stl`.
  - Topology control: `Raw` (triangles) or `Quad` (quads).
  - Target face count quality presets (`extra-low`, `low`, `medium`, `high`) and custom `quality_override` (500–2,000,000 faces).
  - Texture modes: `legacy`, `extreme-low`, `low`, `medium`, `high`, `extreme-high` (up to 12K textures).
  - Materials: `PBR`, `Shaded`, `All`, `Hybrid`, `None`.
  - Humanoid animation prep: `ta_pose` flag for T-pose / A-pose generation.
  - Addon packs (e.g. `HighPack` for 4K packed textures).
  - Symmetry & instruction mode (`creative` vs `faithful`).
- **Flexible Execution**:
  - **Synchronous**: Submits generation, monitors task progress with live CLI updates and exponential backoff, and automatically downloads all files upon completion.
  - **Asynchronous (`--no-wait`)**: Submits task and outputs `task_uuid` & `subscription_key` for later status checks or download.
- **Credit Balance Monitoring**: Query remaining API credits via `--balance`.

---

## Installation & Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your Hyper3D API Key (obtain from [Hyper3D Dashboard](https://hyper3d.ai/workspace/api-dashboard)):
   ```bash
   export HYPER3D_API_KEY="your-api-key-here"
   # Or alternatively:
   export RODIN_API_KEY="your-api-key-here"
   ```

---

## CLI Usage

Run either `python3 model_creator.py` or `./model-creator.py`:

### 1. Text-to-3D Generation

Generate a 3D asset from a text description:

```bash
# 1. Text-to-3D with exact triangle count (e.g. 5,000 or 10,000 triangles)
python3 model_creator.py \
  --prompt "A medieval fantasy wooden treasure chest with engraved brass fittings" \
  --download-type glb \
  --triangles 5000 \
  --output-dir ./outputs/chest_5k

# 2. Text-to-3D with USDZ download format and 10,000 triangles
python3 model_creator.py \
  --prompt "A futuristic flying drone" \
  --download-type usdz \
  --triangles 10000 \
  --output-dir ./outputs/drone_10k

# 3. High-fidelity USDZ character model in T-Pose with Quad topology
python3 model_creator.py \
  --prompt "Stylized fantasy warrior in silver armor" \
  --format usdz \
  --tier Gen-2.5-High \
  --mesh-mode Quad \
  --ta-pose \
  --preview-render \
  --output-dir ./outputs/warrior
```

### 2. Image-to-3D Generation

Generate a 3D model from one or multiple reference images with custom mesh complexity and download format:

```bash
# Single image input with 15,000 triangles in FBX format
python3 model_creator.py \
  --images concept_front.png \
  --prompt "Keep metallic reflections and sharp edges" \
  --download-type fbx \
  --triangles 15000 \
  --output-dir ./outputs/chair_fbx

# Multi-view images with direction labels
python3 model_creator.py \
  --images front.png back.png left.png \
  --image-labels F B L \
  --download-type usdz \
  --triangles 50000 \
  --tier Gen-2.5-High \
  --addons HighPack \
  --output-dir ./outputs/hero
```

### 3. Asynchronous Workflow

For background or long-running tasks:

```bash
# 1. Submit task without waiting
python3 model_creator.py \
  --prompt "Cyberpunk hovercar" \
  --no-wait

# Output:
# Task UUID:         123e4567-e89b-12d3-a456-426614174000
# Subscription Key:  sub-abcdef-123456

# 2. Check task status at any time
python3 model_creator.py --status sub-abcdef-123456

# 3. Download results once status is Done
python3 model_creator.py --download 123e4567-e89b-12d3-a456-426614174000 -o ./outputs/hovercar
```

### 4. Check Credit Balance

```bash
python3 model_creator.py --balance
```

---

## Python API Usage

You can also use `model-creator` as a Python library:

```python
from core.factory import get_provider

# Initialize provider (automatically reads HYPER3D_API_KEY from environment)
provider = get_provider("hyper3d")

# 1. Text-to-3D
result = provider.create_from_text(
    prompt="A sci-fi energy blaster weapon",
    output_dir="./outputs/blaster",
    geometry_file_format="glb",
    tier="Gen-2.5-Medium",
    mesh_mode="Raw",
    quality="high",
    preview_render=True,
)

print(f"Primary model saved to: {result.primary_model_file}")
print(f"Preview render saved to: {result.preview_file}")
for f in result.downloaded_files:
    print(f" - {f}")

# 2. Image-to-3D
result = provider.create_from_image(
    images=["concept.png"],
    output_dir="./outputs/character",
    prompt="Detailed fantasy creature",
    geometry_file_format="usdz",
    tier="Gen-2.5-High",
    ta_pose=True,
)
```

---

## Generation Parameters Reference (Hyper3D)

| Parameter | Options / Type | Default | Description |
|---|---|---|---|
| `--prompt`, `-p` | `str` | `None` | Text description or image conditioning prompt |
| `--images`, `-i` | 1 to 5 file paths | `None` | Reference image(s) for Image-to-3D |
| `--image-labels` | `F`, `B`, `L`, `R`, `FL`, `FR`, `BL`, `BR`, `U`, `D`, `?` | `None` | View orientation corresponding to each input image |
| `--format`, `--download-type`, `-f` | `glb`, `usdz`, `fbx`, `obj`, `stl` | `glb` | Generated 3D model format (also handles `udsz` typo) |
| `--triangles`, `--mesh-complexity` | `int` (500 to 2,000,000) | `None` | Custom target triangle count (e.g. `5000`, `10000`, `50000`), sets `Raw` mode |
| `--tier` | `Gen-2.5-Medium`, `Gen-2.5-High`, `Gen-2.5-Extreme-High`, `Gen-2.5-Low`, `Gen-2.5-Extreme-Low`, etc. | `Gen-2.5-Medium` | Generation model family and capability |
| `--mesh-mode` | `Raw`, `Quad` | `Raw` (for Gen-2.5) | Mesh topology: Triangles (`Raw`) or Quads (`Quad`) |
| `--quality` | `high`, `medium`, `low`, `extra-low` | `medium` | Preset polygon density target |
| `--quality-override`| `500` to `2000000` | `None` | Exact custom target face count (overrides `--quality`) |
| `--texture-mode` | `legacy`, `extreme-low`, `low`, `medium`, `high`, `extreme-high` | Depends on tier | Texture quality level (up to 12K textures) |
| `--material` | `PBR`, `Shaded`, `All`, `Hybrid`, `None` | `PBR` | Material workflow |
| `--seed` | `0` to `65535` | `None` | Random seed for deterministic generation |
| `--ta-pose` | Flag | `False` | For humanoids: generates model in T/A pose for rigging |
| `--preview-render`| Flag | `False` | Generates a high-quality preview render image |
| `--symmetry` | `symmetric`, `balanced`, `asymmetric`, `unknown` | `None` | Mesh symmetry constraint |
| `--instruct-mode` | `creative`, `faithful` | `creative` | Geometry generation strategy |
| `--addons` | List, e.g. `HighPack` | `None` | Upgrades packed textures to 4K |
| `--param KEY=VAL` | Arbitrary key-value pairs | `None` | Pass any additional Hyper3D API parameters |

---

## Adding a New Provider

To integrate another 3D generation service (e.g. Tripo3D):

1. Create `providers/tripo3d.py`:
   ```python
   from core.factory import register_provider
   from providers.base import Base3DModelProvider
   from core.models import GenerationTask, TaskStatus

   @register_provider("tripo3d")
   class Tripo3DProvider(Base3DModelProvider):
       provider_name = "tripo3d"

       def generate_from_text(self, prompt: str, **kwargs) -> GenerationTask:
           ...

       def generate_from_image(self, images, prompt=None, **kwargs) -> GenerationTask:
           ...

       def get_task_status(self, task_or_key) -> TaskStatus:
           ...

       def download_results(self, task_or_uuid, output_dir):
           ...

       def check_balance(self):
           ...
   ```
2. The new provider is immediately usable via CLI (`--provider tripo3d`) or `get_provider("tripo3d")`.

---

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```
