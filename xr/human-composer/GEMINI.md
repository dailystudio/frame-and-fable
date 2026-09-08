# GEMINI.md - Human Composer Quick Reference & Architecture Guide

Welcome to **Human Composer**, the automated 3D character composition and accessory/garment binding pipeline in USDZ format powered by headless Blender.

> [!IMPORTANT]
> **Comprehensive Agent Guidelines**:
> For the complete technical specifications, architectural rules, step-by-step instructions for adding new parts, testing workflows, and lessons learned, please read:
> 👉 **[AGENTS.md](AGENTS.md)**

---

## Quick Architecture Summary

```text
               +----------------------------------+
               | Clean Body Mesh & Clean Armature |
               +----------------------------------+
                 /              |               \
   (In isolation)        (In isolation)    (In isolation)
               v                v                v
      +----------------+ +----------------+ +----------------+
      |   Hair Model   | | Upper Garment  | | Lower Garment  |
      | (Scalp Align)  | |(WeightTransfer)| |(WeightTransfer)|
      +----------------+ +----------------+ +----------------+
               \                |               /
                \               |              /
                 v              v             v
               +----------------------------------+
               | Unified Scene Composite & Export |
               |     (Zero Weight Pollution)      |
               +----------------------------------+
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
+------------------------+             +-----------------------+
|  Outputs / USDZ Model  |             |  5-Angle Renders &    |
| (outputs/<model>/...)  |             | Showcase Animation    |
+------------------------+             +-----------------------+
```

1. **Isolated Binding on Clean Body**: Every accessory or garment (`--hair`, `--upper`, `--lower`, future `--shoes`) is bound in isolation against the clean base body and armature. Never chain bindings sequentially.
2. **Skinning via Data Transfer**: Vertex weights are transferred from the clean body using Blender's `DATA_TRANSFER` modifier (`POLYINTERP_NEAREST`), avoiding heat-diffusion cross-limb bridging.
3. **Weight Sanitization & Cleansing**: Upper garments strip `mixamorig_Head` weights and reassign them to `mixamorig_Neck`. Lower garments prune all upper-body/arm weights, reassign `mixamorig_Spine1`/`mixamorig_Spine2` to `mixamorig_Spine`, and reassign crotch-apex cross-limb weights to `mixamorig_Hips`. Below the crotch, cross-limb weights are strictly reassigned to the corresponding same-side leg bone, and all erroneous `mixamorig_Hips` weights on lower legs/shins are transferred to leg bones, preventing any sticky webbing ("粘在一起") during dynamic leg animation.
4. **Bone-Axis Centerline Alignment, Cuff Tapering & Sagittal Clearance**: Sleeves and pant legs are aligned to their respective bone axes ($Y_{\text{bone}}(u)$, leg bone polyline), ensuring proper volume clearance around limbs without poke-through. Pant cuffs taper down proportionally to the avatar's ankle width ($R_{\text{ankle}} \times 1.08$) with strict sagittal medial clearance below the crotch to guarantee full leg independence and clean air gap between ankles.
5. **Regional Pelvic & Gastrocnemius Clearance**: Lower garment crotch is dynamically positioned 2cm below the lowest body perineum vertex ($Z_{\text{body\_crotch\_min}} - 0.020\text{m}$). The pelvis volume is scanned across greater trochanters and glutes with synchronized centerline tapering and anterior ease. The calf region applies circumferential and directional gastrocnemius muscle clearance ($\text{calf\_boost}_x = 0.08 \cdot \text{calf\_factor}$, $\text{calf\_boost}_y = 0.15 \cdot \text{calf\_factor}$), eliminating poke-through across both male and female body silhouettes.

---

## Quick Commands

```bash
# 1. Activate Environment
source .venv/bin/activate

# 2. Bind Male Avatar (Hair + Suit) with Previews and 5-Angle Intermediates
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_man_hair_suit

# 3. Bind Female Avatar (Suit)
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --upper tests/man_suit.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_woman_suit

# 4. Bind Male Avatar (Pants)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --lower tests/man_pants.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_man_pants

# 5. Bind Female Avatar (Pants)
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --lower tests/man_pants.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_woman_pants

# 6. Full Male Ensemble (Hair + Suit + Pants)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
  --lower tests/man_pants.usdz \
  --intermediate \
  --preview \
  --output-dir outputs/test_man_full_ensemble

# 7. Generate 3-Phase Showcase Animation Video (MP4)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
  --lower tests/man_pants.usdz \
  --anim tests/anim_hip_hop.usda \
  --preview-anim \
  --output-dir outputs/test_anim
```

---

## 5-Angle Quality Checklist

Before completing any task modifying or adding binding parts, verify all 5 renders in `outputs/<model>/intermediates/`:
- [ ] `render_front.png`: Chest, lapels, collar, and tie centered; hands emerge cleanly.
- [ ] `render_back.png`: Zero skin holes on sleeves; spine and shoulder blades covered.
- [ ] `render_bottom.png`: Arm underside and axilla 100% enclosed within sleeves.
- [ ] `render_left.png`: Smooth sleeve curvature along arm profile.
- [ ] `render_right.png`: Symmetrical arm curvature and wrist emergence.
- [ ] `preview_animation.mp4`: 180° head turn does not stretch or twist the garment collar.

For in-depth mathematical formulas, slice clearance data, and implementation details, see [AGENTS.md](AGENTS.md).
