# Rig Binder (`rig-binder`): USDZ to Mixamo & Spatial Editor Pipeline

**Rig Binder** (`rig-binder`) is an automated Python tool that converts USDZ 3D character models for **Adobe Mixamo** auto-rigging and animation, processes the rigged base mesh into clean T-pose USDZ and animation USDC files using **Blender**, and automatically integrates them into **PICO Spatial Editor** projects.

---

## 🌟 Key Features

- **Automated USDZ $\rightarrow$ FBX Conversion**: Converts input `.usdz` character models to Mixamo-compatible `.fbx` packages with embedded texture unpacking.
- **Interactive Headful Browser Automation**: Launches an automated, stealth-configured Chromium browser using **Playwright** to auto-upload character packages to Mixamo while allowing manual rigging marker adjustments and animation selection.
- **Robust Download Intercept**: Detects Playwright blob download streams, UUID temporary files, and `~/Downloads` additions with file stream stability verification to prevent early browser closure.
- **T-Pose Base Mesh USDZ Export**: Clears active animation actions and NLA tracks in Blender, resets all armature pose bone transforms to default rest position (T-pose), and fixes Principled BSDF shader node texture links (Base Color linked, Emission zeroed).
- **Animation Data USDC Export**: Exports pure skeletal animation USDC files while preserving original Mixamo animation titles in the USD `SkelAnimation` prim track.
- **Spatial Editor Auto-Import**: Places base models into `Sources/Assets/`, animation tracks into `Sources/Assets/anims/`, and automatically composes or updates scene `.usda` files under `Sources/Scenes/<SceneName>.usda`.
- **Smart Animation FBX Reuse**: Automatically detects previously downloaded `{xxx}_anim_{yyy}.fbx` files to skip Steps 1–4 and re-generate USD outputs instantly.

---

## 📋 Requirements & Prerequisites

1. **Operating System**: macOS (ARM64 / x86_64) or Linux / Windows.
2. **Python 3.10+**: Standard Python installation.
3. **Blender 4.x**: Blender binary installed (e.g. `/Applications/Blender.app/Contents/MacOS/Blender`).
4. **Playwright**: Python Playwright library and bundled Chromium browser.

### Installation

```bash
# 1. Install Playwright Python package
pip install playwright

# 2. Install Playwright Chromium browser
playwright install chromium
```

---

## 🚀 Quick Start & Usage

### 1. Complete End-to-End Pipeline (USDZ $\rightarrow$ Mixamo $\rightarrow$ Spatial Editor)

Convert a character USDZ model, open Mixamo for rigging & animation selection, export USD files, and import directly into a Spatial Editor project scene:

```bash
python3 rig_binder.py \
  --input-usdz verify/nan_ye_gde.usdz \
  --output-dir verify/ \
  --import-to-se ~/Editor/my_project \
  --scene MainScene
```

### 2. Fast Execution with Animation Reuse (`--reuse-anim`)

If an animated FBX file (e.g. `nan_ye_gde_anim_body_block.fbx`) was already downloaded in `--output-dir`, skip Steps 1–4 (USDZ conversion, ZIP packaging, and Mixamo browser upload) and generate USD outputs directly:

```bash
python3 rig_binder.py \
  --input-usdz verify/nan_ye_gde.usdz \
  --output-dir verify/ \
  --import-to-se ~/Editor/my_project \
  --scene MainScene \
  --reuse-anim
```

### 3. Force Re-upload to Mixamo (`--force-mixamo`)

Ignore existing animated FBX files in `--output-dir` and force a new Mixamo upload & download session:

```bash
python3 rig_binder.py \
  --input-usdz verify/nan_ye_gde.usdz \
  --output-dir verify/ \
  --force-mixamo
```

### 4. Running Specific Pipeline Steps (`--step`)

You can execute individual phases of the pipeline using the `--step` flag:

- `--step prep`: Execute Steps 1–3 (USDZ to FBX conversion and ZIP packaging).
- `--step mixamo`: Execute Step 4 (Launch interactive Playwright browser for Mixamo).
- `--step base`: Execute Step 5 (Export base mesh USDZ in T-pose).
- `--step anim`: Execute Step 6 (Export animation USDC).
- `--step se`: Execute Step 7 (Import generated USD assets into Spatial Editor project).

```bash
# Example: Only export base mesh USDZ from an existing animated FBX
python3 rig_binder.py \
  --input-usdz verify/nan_ye_gde.usdz \
  --anim-fbx verify/nan_ye_gde_anim_body_block.fbx \
  --step base
```

---

## 📁 Output File Naming Conventions

Let **`xxx`** be the `snake_case` name of the input USDZ model (e.g. `mrye`), and **`yyy`** be the `snake_case` name of the selected Mixamo animation (e.g. `defeated`, `body_block`):

| Pipeline Step | Generated Output Path | Description |
| :--- | :--- | :--- |
| **Step 2** | `{xxx}_upload_to_mixamo/model.fbx`<br>`{xxx}_upload_to_mixamo/textures/` | Converted FBX model and unpacked embedded textures. |
| **Step 3** | `{xxx}_upload_to_mixamo.zip` | Zip archive containing FBX and `textures/` for Mixamo upload. |
| **Step 4** | `{xxx}_anim_{yyy}.fbx` | Rigged & animated FBX captured from Mixamo download. |
| **Step 5** | `{xxx}_anim_base.usdz` | Rigged base mesh USDZ reset to T-pose (rest pose) with fixed shaders. |
| **Step 6** | `{xxx}_anim_{yyy}.usdc` | Pure skeletal animation USDC with preserved `SkelAnimation` track title. |
| **Step 7** | `<SE_Project>/Sources/Assets/{xxx}_without_anim.usdz`<br>`<SE_Project>/Sources/Assets/anims/{yyy}.usdc`<br>`<SE_Project>/Sources/Scenes/<SceneName>.usda` | Integrated Spatial Editor assets and composed USDA scene file. |

---

## ⚙️ Command-Line Arguments Reference

```text
options:
  -h, --help            show this help message and exit
  --input-usdz INPUT_USDZ
                        Path to input USDZ file (default: 1_model_orig.usdz)
  --anim-fbx ANIM_FBX   Path to animated FBX from Mixamo (default: auto-detected)
  --output-dir OUTPUT_DIR
                        Output directory for pipeline artifacts (default: current directory)
  --blender-path BLENDER_PATH
                        Path to Blender executable binary (optional)
  --step {all,prep,mixamo,base,anim,se}
                        Pipeline phase to execute (default: all)
  --auto-browser        Automatically open headful browser for Mixamo in Step 4 (default: True)
  --no-auto-browser     Disable automatic headful browser for Step 4
  --import-to-se IMPORT_TO_SE
                        Target Spatial Editor project directory (e.g. ~/Editor/maple)
  --scene SCENE         Scene name for Spatial Editor import (converted to PascalCase, default: Default)
  --reuse-anim          Automatically reuse existing animated FBX file if found and skip Steps 1-4
  --force-mixamo        Force running Steps 1-4 (Mixamo upload & download) even if FBX exists
```

---

## 📜 License

The pipeline automation script is open and can be integrated into proprietary or commercial projects. See [`ARCHITECTURE.md`](file:///Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/rig-binder/ARCHITECTURE.md) for licensing and architectural details.

