# Pose Binder (`pose-binder`): USDZ to Mixamo & Spatial Editor Pipeline

**Pose Binder** (`pose-binder`) is an automated Python tool that converts USDZ 3D character models for **Adobe Mixamo** auto-rigging and animation, processes the rigged base mesh into clean T-pose USDZ and animation USDC files using **Blender**, and automatically integrates them into **PICO Spatial Editor** projects.

---

## 🌟 Key Features

- **Automated USDZ $\rightarrow$ FBX Conversion**: Converts input `.usdz` character models to Mixamo-compatible `.fbx` packages with embedded texture unpacking.
- **Interactive Headful Browser Automation**: Launches an automated, stealth-configured Chromium browser using **Playwright** to auto-upload character packages to Mixamo while allowing manual rigging marker adjustments and animation selection.
- **Robust Download Intercept**: Detects Playwright blob download streams, UUID temporary files, and `~/Downloads` additions with file stream stability verification to prevent early browser closure.
- **T-Pose Base Mesh USDZ Export**: Clears active animation actions and NLA tracks in Blender, resets all armature pose bone transforms to default rest position (T-pose), and fixes Principled BSDF shader node texture links (Base Color linked, Emission zeroed).
- **Animation Data USDC Export**: Exports pure skeletal animation USDC files while preserving original Mixamo animation titles in the USD `SkelAnimation` prim track.
- **Spatial Editor Auto-Import**: Places base models into `Sources/Assets/`, animation tracks into `Sources/Assets/anims/`, and automatically composes or updates scene `.usda` files under `Sources/Scenes/<SceneName>.usda`.
- **Flexible Input Workflows**: Support full end-to-end USDZ conversion (`--input`), processing pre-downloaded animated FBX files (`--input-anim`), or selecting new actions for active Mixamo sessions (`--input-mixamo`).

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

## 🚀 Quick Start & Usage Modes

### Mode 1: Full Pipeline from USDZ Model (`--input`)

Convert a character USDZ model, open Mixamo for auto-rigging & animation selection (Steps 1–4), export USD files (Steps 5–6), and optionally import into Spatial Editor (Step 7):

```bash
python3 pose_binder.py \
  --input verify/nan_ye_gde.usdz \
  --output outputs/ \
  --import-to-se ~/Editor/my_project \
  --scene MainScene
```

### Mode 2: Process Existing Mixamo Animated FBX (`--input-anim`)

Skip USDZ conversion and Mixamo upload (Steps 1–4). Directly generate T-pose USDZ base mesh and animation USDC files from a previously downloaded Mixamo FBX file (Steps 5–6), and optionally import into Spatial Editor (Step 7):

```bash
python3 pose_binder.py \
  --input-anim verify/nan_ye_gde_anim_body_block.fbx \
  --output outputs/ \
  --import-to-se ~/Editor/my_project \
  --scene MainScene
```

### Mode 3: Select New Action for Uploaded Mixamo Character (`--input-mixamo`)

Skip USDZ conversion and model zip upload (Steps 1–3). Open the interactive Mixamo browser session to pick a new animation action for an already uploaded character, capture the download (Step 4), export USD files (Steps 5–6), and optionally import into Spatial Editor (Step 7):

```bash
python3 pose_binder.py \
  --input-mixamo nan_ye_gde \
  --output outputs/ \
  --import-to-se ~/Editor/my_project \
  --scene MainScene
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
  --input INPUT         Path to input USDZ file (runs full pipeline: Steps 1-6)
  --input-anim INPUT_ANIM
                        Path to Mixamo animated FBX file (skips Steps 1-4, runs Steps 5-6)
  --input-mixamo [INPUT_MIXAMO]
                        Reuse existing Mixamo.com character session to select a new animation action (skips Steps 1-3, runs Steps 4-6)
  --output OUTPUT       Output directory for generated pipeline artifacts (default: outputs/)
  --import-to-se IMPORT_TO_SE
                        Target Spatial Editor project path (runs Step 7)
  --scene SCENE         Scene name for Spatial Editor import (converted to PascalCase, default: Default)
  --blender-path BLENDER_PATH
                        Path to Blender executable binary (optional)
  --auto-browser        Automatically open headful browser for Mixamo in Step 4 (default: True)
  --no-auto-browser     Disable automatic headful browser for Step 4
```

---

## 📜 License

The pipeline automation script is open and can be integrated into proprietary or commercial projects. See [`ARCHITECTURE.md`](file:///Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/pose-binder/ARCHITECTURE.md) for licensing and architectural details.


