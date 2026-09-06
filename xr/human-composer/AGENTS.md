# AGENTS.md - Developer & Agent Guide for Human Composer

This document provides the foundational principles, architecture, binding standards, verification workflows, and known pitfalls for AI agents and human developers working on the `xr/human-composer` project.

---

## 1. Repository Overview & How It Works

`human-composer` is an automated CLI tool powered by headless Blender that composes, aligns, and binds 3D accessories and clothing (hair, upper garments, lower garments, accessories) to skinned 3D humanoid avatars in USDZ format.

### Key Files & Directories
- `human-composer.py`: CLI interface, argument parser, 2D reference image analysis orchestrator, configuration generator, and Blender subprocess invoker.
- `core/blender_binder.py`: Headless Blender automation script that executes inside Blender's Python runtime (`blender -b -P`). Performs USDZ unpacking, texture collision resolution, mesh alignment/deformation, clean body vertex weight transfer, USDZ export, multi-angle camera rendering, and preview animation video generation.
- `core/reference_aligner.py`: Computer vision analysis of 2D character turnarounds (front, left, right, back) to guide 3D placement.
- `tests/`: Verified sample assets:
  - Base bodies: `tests/man_anim_base.usdz`, `tests/woman_anim_base.usdz`
  - Hair models: `tests/man_hair.usdz`, `tests/woman_hair.usdz`
  - Garments: `tests/man_suit.usdz`
  - Animation clips: `tests/anim_hip_hop.usda`, `tests/anim_head_turn.usda`
  - 2D turnaround references: `tests/*_ref_*.png`
- `outputs/`: Output directory structure per model:
  ```text
  outputs/<model_name>/
  ├── <model_name>_bound.usdz       # Final bound USDZ model
  ├── preview.png                   # High-res orthographic static render
  ├── preview_animation.mp4         # Sequenced 3-phase preview animation video
  └── intermediates/                # Multi-angle inspection & verification renders
      ├── part_<name>.png           # Isolated part render on clean body
      ├── part_final.png            # Composite render
      ├── render_front.png          # Front view
      ├── render_back.png           # Back view
      ├── render_left.png           # Left profile view
      ├── render_right.png          # Right profile view
      └── render_bottom.png         # Bottom-up underside inspection view
  ```

---

## 2. Core Architectural Principles

### Principle 1: Isolated Part Binding on Clean Body (Golden Rule)
> **Always bind each part in isolation against the pristine, clean body mesh and armature.**
> 
> Never bind Part B onto a body that has already been deformed, combined, or weight-transferred with Part A!

- **Why?**
  - Chaining bindings introduces compounding errors: weight pollution from earlier accessories, altered vertex counts, and false geometric bounds.
  - Hair must be aligned and bound against the pristine bald skull.
  - Upper garments (suits, jackets) must be aligned and weighted against the bare torso and clean arm bones.
  - Lower garments (trousers, skirts) must be aligned and weighted against the bare legs and pelvis.
- **Workflow**:
  1. Load clean body mesh and clean armature.
  2. Bind Part 1 (e.g. hair) -> save intermediate/record state.
  3. Bind Part 2 (e.g. upper garment) against clean body -> save intermediate/record state.
  4. Once all parts are independently bound and skinned to the same clean armature, combine/unhide them into the final composite scene.
  5. Export the clean unified USDZ.

### Principle 2: Skinning via Clean Body Vertex Weight Transfer
Do **not** use Blender's automatic heat-diffusion weighting (`bpy.ops.object.parent_set(type='ARMATURE_AUTO')`) on clothing or accessories:
- Automatic weights bridge across disconnected limbs (e.g. binding coat tails to legs, or sleeve undersides to chest ribs).
- Instead, use Blender's `DATA_TRANSFER` modifier:
  ```python
  dt = garment_mesh.modifiers.new(name="WeightTransfer", type='DATA_TRANSFER')
  dt.object = clean_body_mesh
  dt.use_vert_data = True
  dt.data_types_verts = {'VGROUP_WEIGHTS'}
  dt.vert_mapping = 'NEAREST_POLYNORMAL'
  dt.ray_radius = 0.05
  bpy.ops.object.datalayout_transfer(modifier=dt.name)
  ```
- **Weight Sanitization (Critical)**:
  Always inspect and prune inappropriate vertex groups transferred from the body.
  - *Upper Garments*: Transfer will naturally copy `mixamorig_Head` weights onto collars/lapels close to the jaw. If left in place, turning the head stretches the entire jacket collar! Always reassign `mixamorig_Head` weights to `mixamorig_Neck` and delete the `mixamorig_Head` vertex group from the garment:
    ```python
    reassign_and_remove_vertex_group(garment_mesh, "mixamorig_Head", "mixamorig_Neck")
    ```

### Principle 3: Anatomical Deformation & Centerline Alignment
When adapting a canonical garment to an avatar, you must distinguish between the **torso placement** and the **limb bone axes**:

1. **Torso Placement**:
   - The torso center $Y_{\text{target}}$ is shifted forward (e.g. $Y_{\text{target}} = p_{\text{neck}}.y - 0.045 \cdot r_{\text{sh}}$) to provide clearance for the avatar's muscular chest and pectoral depth.
2. **Limb Bone Axis Discrepancy (Crucial Lesson Learned)**:
   - While the torso moves forward to $-Y$, the arm bones (`mixamorig_LeftArm`, `mixamorig_LeftForeArm`) sit further back at $Y \approx +0.035\text{m}$.
   - If sleeves are deformed around $Y_{\text{target}}$, the sleeve center is displaced ~5 cm forward from the arm bone axis. This leaves excess room in front while the tricep, elbow, and forearm burst through the back and underside of the sleeve!
   - **Rule**: Along the sleeve length $u \in [0, 1]$ (from shoulder seam to cuff), smoothly transition the sleeve's $Y$ center from the torso shoulder seam to the true arm bone axis:
     $$Y_{\text{bone}}(u) = Y_{\text{shoulder}} + u \cdot (Y_{\text{wrist}} - Y_{\text{shoulder}})$$
     $$\text{shift\_y}(u) = (Y_{\text{bone}}(u) - (Y_{\text{target}} + Y_{\text{suit\_center\_local}} \cdot \text{scale\_y})) \cdot u^{0.6}$$
     $$Y_{\text{new}} = (v_y + \text{shift\_y} - Y_{\text{target}}) \cdot \text{rad\_clearance} + Y_{\text{target}}$$
3. **Radial Clearances**:
   - Apply radial clearance around the bone axis in both $Y$ (depth) and $Z$ (height/underside) so the sleeve envelops the arm symmetrically with $\ge 2.5\text{cm}$ clearance in front, back, top, and bottom.
4. **Wrist Cuff Anchor Retraction**:
   - Avatar hands widen rapidly past the wrist joint into the palm and thumb base.
   - Anchor the cuff rim just before the wrist joint:
     $$X_{\text{cuff}} = X_{\text{wrist}} - 0.010\text{m}$$
   - Apply quadratic flare at the cuff opening ($1.0 + 0.02 \cdot u^2$) so the hands emerge cleanly with no cuff rim clipping.

---

## 3. Principles for Adding a New Binding Part

When adding a new part (e.g. `lower` garment, `dress`, `shoes`, `gloves`, `hat`):

| Step | Action | Requirements & Rules |
| :--- | :--- | :--- |
| **1. CLI Options** | Add `--<part>` argument in `human-composer.py` | Add optional argument, pass path through config dict. |
| **2. Texture Isolation** | Extract & isolate textures in `isolate_part_texture()` | Avoid collisions with identically named textures (e.g. `textures/shaded.png`). |
| **3. Clean Body Import** | Unpack & load part on clean scene | Always perform alignment against the clean body mesh. |
| **4. Anatomical Alignment** | Create `align_<part>_garment()` | Sample relevant armature bones (`Hips`, `UpLeg`, `Leg`, `Foot`, `Hand`, etc.). Compute proportional scale ratio $r = \text{span} / \text{ref\_span}$. |
| **5. Limb Axis Transition** | Center limbs on bone axes | Ensure limb tubes (pant legs, sleeves, glove fingers) center on the respective bone lines, not the torso/pelvis center. |
| **6. Weight Transfer** | Skin using clean body vertex weights | Transfer weights via `DATA_TRANSFER` (Nearest Face Interpolated / Polynormal). |
| **7. Weight Sanitization** | Prune unwanted vertex groups | Lower garments: remove `Head`/`Arm` weights. Shoes: keep only `Foot`/`ToeBase`/`Leg` weights. |
| **8. Multi-Angle Preview** | Export intermediate previews | Include `part_<name>.png` and multi-angle renders. |

---

## 4. How to Test & Verify

Always test any modification using the complete automated test suite:

### 1. Multi-Angle Static Inspection (Male & Female Models)
Run both genders to ensure no cross-gender regressions:
```bash
# Male Avatar (Hair + Suit)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_man_hair_suit

# Female Avatar (Suit)
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --upper tests/man_suit.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_woman_suit
```

### 2. Required Inspection Angles (Check All 5!)
Do not stop after checking `render_front.png`. You **must** verify all 5 views under `outputs/<model_name>/intermediates/`:
1. `render_front.png`: Chest, lapels, collar, tie, wrist cuff front.
2. `render_back.png`: Triceps, elbows, rear sleeve seam, spine, shoulder blades.
3. `render_bottom.png` (Bottom-Up): Arm underside, armpit/axilla, sleeve cuff rim interior.
4. `render_left.png`: Left arm profile, sleeve curvature, wrist emergence.
5. `render_right.png`: Right arm profile, sleeve curvature, wrist emergence.

### 3. Quantitative Pixel & Penetration Verification
Run programmatic checks with Blender and PIL to verify **0 skin leak pixels**:
```python
from PIL import Image
import numpy as np

img = Image.open("outputs/<model>/intermediates/render_back.png")
arr = np.array(img)
# Skin mask (avatar skin tone)
is_skin = (arr[:, :, 0] > 200) & (arr[:, :, 0] - arr[:, :, 1] > 20) & (arr[:, :, 1] > 140) & (arr[:, :, 2] > 130)
# Ensure count in sleeve regions is exactly 0
```

### 4. Dynamic Animation & Stress Testing
Verify weight transfer under dynamic joint articulation:
```bash
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
  --anim tests/anim_hip_hop.usda \
  --preview-anim \
  --output-dir outputs/test_anim
```
Inspect `preview_animation.mp4`:
- **Phase 1 (Frames 1–48, Turntable)**: 360° rotation; verify full coverage from every angle.
- **Phase 2 (Frames 49–96, Head Turn)**: 180° head turn; verify collar, tie, and lapels do not stretch or twist with head motion.
- **Phase 3 (Frames 97+, Skeletal Motion)**: High-articulation limb movement; verify underarm and elbow joints deform smoothly.

---

## 5. Pitfalls & Watch-Outs (Lessons Learned)

1. **Torso vs Limb Axis Offset Discrepancy**:
   - Pushing the torso forward to clear the chest moves the entire garment forward.
   - You **must** counteract this displacement on the sleeves and legs by centering each limb vertex along its respective bone vector.
2. **Bottom-Up Camera Orientation**:
   - In Blender orthographic view, a camera at $(0, 0, -4.0)$ looking straight UP along $+Z$ requires Euler rotation `(math.radians(180), 0, 0)`.
   - Ensure `clip_start = 0.01` and `clip_end = 100.0` are set explicitly; otherwise near-plane clipping will render an empty background.
3. **Headless Blender Script Execution**:
   - Blender CLI does not support reading script content from standard input (`-P -`).
   - Always execute via Python script file paths (`blender -b -P /path/to/script.py`).
4. **Texture Name Collisions**:
   - Many USDZ assets export with default texture names like `textures/shaded.png`.
   - If both the body and hair USDZ contain `shaded.png`, extracting them to the same directory overwrites the texture.
   - Always extract to separate isolated folders and rename before importing to Blender.
5. **Preserve Untouched Subsystems**:
   - When modifying clothing or adding new parts, keep hair binding algorithms strictly untouched. Verify hair fit on both male and female models after any pipeline change.
