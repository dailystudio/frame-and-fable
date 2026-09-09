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
  - Garments: `tests/man_suit.usdz`, `tests/man_pants.usdz`
  - Animation clips: `tests/anim_hip_hop.usda`, `tests/anim_head_turn.usda`
  - 2D turnaround references: `tests/*_ref_*.png`
- `outputs/`: Output directory structure per model:
  ```text
  outputs/<model_name>/
  ├── <model_name>_bound.usdz       # Final bound USDZ model (canonical T-pose)
  ├── <model_name>_animated.usdz    # Final bound USDZ model with embedded skeletal animation (when --anim provided)
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
  - *Lower Garments*: Transfer can capture upper-body vertex groups on the waistband. Prune all upper-body vertex groups (`Head`, `Neck`, `Spine1`, `Spine2`, `Shoulder`, `Arm`, `Hand`, etc.) and reassign `mixamorig_Spine1`/`mixamorig_Spine2` weights to `mixamorig_Spine` so upper-body motion does not pull on trousers.

### Principle 3: Anatomical Deformation & Centerline Alignment
When adapting canonical garments (upper or lower) to an avatar, you must distinguish between the root torso/pelvis placement and the limb bone axes:

#### Upper Garment Centerline Alignment
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

#### Lower Garment (Trousers/Pants) Centerline & Volume Alignment
1. **Piecewise Vertical Mapping**:
   - Trousers feature two distinct anatomical zones: the **inseam** (ankles to crotch) and the **pelvis rise** (crotch to waistband).
   - Compute `target_waist_z` ($p_{\text{spine}}.z + 0.050 \cdot \text{leg\_ratio}$), `target_crotch_z` ($Z_{\text{body\_crotch\_min}} - 0.020\text{m}$), and `target_ankle_z` ($p_{\text{foot}}.z + 0.012\text{m}$).
   - Map canonical garment vertices piecewise to eliminate crotch drop while anchoring cuffs above shoes and waistbands at the natural waist.
2. **Dynamic Crotch Perineum Clearance**:
   - Rather than relying solely on hip bones, sample the avatar's clean body mesh between the thighs to find $Z_{\text{body\_crotch\_min}}$.
   - Position `target_crotch_z = body_crotch_min_z - 0.020m` (2cm below the lowest perineum vertex). This unconditionally encloses avatar underwear/crotch geometry on both male and female avatars without poke-through.
3. **Regional Pelvic Scanning & Slim-Fit Tapered Circumference Scaling**:
   - Rather than sampling a single arbitrary slice at `p_hips.z`, scan the pelvic zone across greater trochanters & glutes ($Z \in [Z_{\text{crotch}} + 0.3 \cdot (p_{\text{hips}}.z - Z_{\text{crotch}}), p_{\text{hips}}.z + 0.03\text{m}]$) to extract true anatomical maximum width `body_hips_w` and depth `body_hips_d`.
   - Compute separate tailored scales for waist and hips:
     $$\text{scale}_{\text{waist}, x} = \frac{\text{body\_waist\_w}}{\text{raw\_waist\_w}} \cdot 1.08, \quad \text{scale}_{\text{waist}, y} = \frac{\text{body\_waist\_d}}{\text{raw\_waist\_d}} \cdot 1.08$$
     $$\text{scale}_{\text{hips}, x} = \frac{\text{body\_hips\_w}}{\text{raw\_hips\_w}} \cdot 1.10, \quad \text{scale}_{\text{hips}, y} = \frac{\text{body\_hips\_d}}{\text{raw\_hips\_d}} \cdot 1.10$$
   - **Convex Pelvic Rise & Centerline Taper**:
     Between crotch and hips ($u \le u_{\text{hips}}$), retain hip scale and anchor `target_cy = body_hips_center_y`. Between hips and waist ($u > u_{\text{hips}}$), apply convex blend ($t^{1.8}$ where $t = \frac{u - u_{\text{hips}}}{1 - u_{\text{hips}}}$) to smoothly taper both width/depth scales and $Y$-center into the waistline.
   - **Anterior Fly Ease**:
     Apply subtle anterior ease ($-0.007\text{m}$) when $ry < p_{\text{waist\_center\_y}}$ to envelope the lower abdomen and front fly cleanly while keeping the posterior seat 100% flush within the suit jacket back hem.
4. **Leg Bone Centerline Tracking, Cuff Tapering & Sagittal Clearance**:
   - Raw pants legs sit at canonical positions ($X \approx \pm 0.250\text{m}$). Avatars vary widely in stance width (e.g. female ankle $X \approx \pm 0.065\text{m}$ vs male $\pm 0.129\text{m}$).
   - Sample the leg bone vector piecewise along `mixamorig_*UpLeg` $\to$ `mixamorig_*Leg` $\to$ `mixamorig_*Foot`.
   - Apply smooth cosine blend factor $w(u) = \cos(\frac{\pi}{2} u^2)$ where $u \in [0, 1]$ is normalized distance from ankle ($u=0$) to crotch ($u=1$), transitioning smoothly from leg bone tracking into the unified pelvis.
   - Scale leg tube width down towards cuff: $\text{scale}_{\text{cuff}, x} = \min(\text{scale}_{\text{hips}, x}, \max(0.28, \frac{\text{body\_ankle\_w} \cdot 1.08}{\text{raw\_cuff\_w}}))$, preventing oversized cuffs from colliding or overlapping between the ankles.
   - **Sagittal Medial Invariance**: Apply medial clearance below crotch ($\text{medial\_clearance} = 0.008 \cdot (1.0 - u)$), guaranteeing left leg vertices remain strictly at $X \ge \text{medial\_clearance}$ and right leg vertices at $X \le -\text{medial\_clearance}$.
5. **Anatomical Calf Gastrocnemius Clearance**:
   - The gastrocnemius muscle peak sits at 72% between ankle and knee:
     $$Z_{\text{calf\_peak}} = Z_{\text{foot}} + 0.72 \cdot (Z_{\text{knee}} - Z_{\text{foot}})$$
   - Directional posterior ease ($\text{calf\_boost}_y = 0.15 \cdot \text{calf\_factor}$ when $\Delta Y > 0$) and circumferential lateral/medial ease ($\text{calf\_boost}_x = 0.08 \cdot \text{calf\_factor}$) envelope the entire gastrocnemius belly without poke-through or shin bagginess:
     $$\text{rad\_clearance}_x = 1.04 + \text{calf\_boost}_x, \quad \text{rad\_clearance}_y = 1.08 + \text{calf\_boost}_y$$
6. **Strict Cross-Limb & Lower-Leg Weight Cleansing (Zero Leg Sticking)**:
   - Skinning lower garments via `DATA_TRANSFER` inevitably transfers opposite-leg weights at the crotch apex, and erroneously assigns pelvis/`mixamorig_Hips` weights to lower legs when stances are narrow.
   - If lower leg/shin vertices have `mixamorig_Hips` weights, they remain pinned to the stationary pelvis during kicks/dance steps, creating severe sticky webbing ("粘在一起").
   - **Sanitization Rules**:
     1. Below crotch ($Z < Z_{\text{crotch}} - 0.02\text{m}$): reassign all opposite-leg weights directly to the corresponding same-side leg bone (`LeftLeg`/`LeftUpLeg` or `RightLeg`/`RightUpLeg`), **never** to `Hips`.
     2. Lower legs ($Z < Z_{\text{crotch}} - 0.05\text{m}$): strip all `mixamorig_Hips` weights completely and transfer them to the leg bone (`LeftLeg`/`RightLeg`), ensuring 100% leg articulation independence.
     3. Center crotch apex ($|X| \le 5\text{mm}$ and $Z \ge Z_{\text{crotch}} - 0.02\text{m}$): reassign leg weights to `mixamorig_Hips` to maintain seamless groin curvature.

#### Full-Length Dress Alignment & Skirt Articulation
1. **Piecewise Tri-Zone Vertical Mapping**:
   - Dresses span three anatomical zones: the **bodice** ($rz \ge \text{raw\_waist\_z}$), the **pelvic rise** ($rz \in [\text{raw\_hips\_z}, \text{raw\_waist\_z}]$), and the **skirt** ($rz < \text{raw\_hips\_z}$).
   - **Top Rim Target Calibration**:
     - For strapless tube gowns (top rim width $\le 0.50\text{m}$), target high bust neck base (`target_top_z = p_neck.z + 0.010m`), ensuring sweetheart dips cover the full bust without poke-through while side peaks cover the axilla.
     - For off-the-shoulder gowns with shoulder bands (top rim width $> 0.50\text{m}$), target shoulder collar height (`target_top_z = p_neck.z - 0.012m`).
   - `target_waist_z = p_spine.z + 0.050 * leg_ratio`, `target_hips_z = p_hips.z + 0.010m`, and `target_hem_z = 0.030m` (skimming floor without footwear clipping).
2. **Proportional Skirt Flare & Ruffle Preservation**:
   - Unlike tight pants or pencil skirts, dresses feature flared, tiered, or cascading ruffles (e.g. `woman_tube.usdz` with 1.9m wide side ruffles).
   - Never collapse the skirt based purely on hip bounding width (`body_hips_w / raw_hips_w`), which would crush the skirt to less than half its width and squash side ruffles into the crotch.
   - Anchor the skirt scale to the character waist scale, while guaranteeing anatomical clearance for the pelvis:
     $$\text{hips\_scale\_x} = \max\left(\text{waist\_scale\_x}, \frac{\text{body\_hips\_w}}{\text{raw\_hips\_w}} \cdot 1.12\right)$$
     $$\text{hips\_scale\_y} = \max\left(\text{waist\_scale\_y}, \frac{\text{body\_hips\_d}}{\text{raw\_hips\_d}} \cdot 1.14\right)$$
   - This ensures the cascading ruffles on both sides along the legs retain their natural silhouette and spread without poke-through or clipping.
3. **Anterior Bust & Abdomen Ease**:
   - Bodice center Y tracks the spine line (`body_waist_cy` to `body_bust_cy`), decoupled from top rim asymmetric cutout dips.
   - Smooth sinusoidal anterior bust ease ($\Delta Y = -0.022 \cdot \sin(u \pi)$) guarantees zero chest poke-through across full volume.
   - Sinusoidal anterior abdomen ease ($\Delta Y = -0.015 \cdot \sin(u \pi)$) along the pelvic rise envelopes the lower abdomen and navel seamlessly.
4. **Dual-Zone Weight Cleansing (Zero Tearing & Zero Stretching)**:
   - **Bodice Sanitization**: All head, neck, shoulder, arm, and hand weights are transferred to `mixamorig_Spine2`. Dynamic head turns (Phase 2) and waving/dancing motions leave the strapless bodice perfectly rigid and stable.
   - **Skirt Sanitization**: Foot and toe weights are transferred to same-side `UpLeg`. Shin/leg weights are blended 70% to same-side `UpLeg` and 30% to `mixamorig_Hips`. This allows the skirt to swing gracefully with thigh movement without tearing across knees or sticking between the legs.

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

# Male Avatar (Pants)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --lower tests/man_pants.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_man_pants

# Female Avatar (Pants)
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --lower tests/man_pants.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_woman_pants

# Full Ensemble (Hair + Suit + Pants)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
  --lower tests/man_pants.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_man_full_ensemble

# Female Avatar (Strapless Tiered Tube Dress)
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --hair tests/woman_hair.usdz \
  --dress tests/woman_tube.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_woman_tube

# Female Avatar (Off-the-Shoulder Slit Evening Gown)
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --hair tests/woman_hair.usdz \
  --dress tests/women_tube_2.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_woman_tube2
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
# Male Articulation (Hip Hop Dancing)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
  --anim tests/anim_hip_hop.usda \
  --preview-anim \
  --output-dir outputs/test_anim

# Female Articulation (Standing Greeting)
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --hair tests/woman_hair.usdz \
  --dress tests/woman_tube.usdz \
  --anim tests/woman_anim_standing_greeting.usdc \
  --preview-anim \
  --output-dir outputs/test_woman_tube_anim_greeting
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
6. **Bodice Centerline Stability & Sweetheart Necklines**:
   - On dresses with asymmetric top rims (sweetheart dips, scooped backs), the highest vertices only exist in the front cups. Sampling the top rim center shifts $Y$ far anteriorly, erroneously pushing the mid-bodice into the chest.
   - Decouple the bodice center axis from top cutouts by anchoring on `(raw_waist_cy + raw_bust_cy) / 2.0`.
7. **USDZ Texture Mapping (Emission vs Base Color)**:
   - Several USDZ models export textures mapped solely to `Principled BSDF` Emission Color with a default white Base Color, producing washed-out surfaces.
   - Always link `TEX_IMAGE` Color to `Base Color` and reset `Emission Strength` to 0.0.
8. **Armature Parent Inverse Matrix**:
   - Parenting imported meshes to an armature without setting `mesh.matrix_parent_inverse = armature.matrix_world.inverted()` will apply the armature's unit scale (e.g. 0.01x) and collapse the garment into a tiny speck. Always set `matrix_parent_inverse`.
9. **Flared & Ruffled Skirt Proportional Scaling**:
   - When binding dresses with flared tiers or side ruffles, bounding box sampling at the hip level (`raw_hips_w`) captures the outer ruffle span rather than the inner body cylinder.
   - If `hips_scale_x` is computed simply as `body_hips_w / raw_hips_w`, the skirt collapses to less than half its designed width, crushing side ruffles inward against the legs and causing avatar thighs to poke out laterally.
   - Always clamp skirt scaling with `max(waist_scale_x, ...)` and `max(waist_scale_y, ...)`.
