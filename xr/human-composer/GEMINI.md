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
                    |                        |
     (Bind in isolation)          (Bind in isolation)
                    v                        v
          +-------------------+    +--------------------+
          |    Hair Model     |    |   Upper Garment    |
          |  (Scalp Geometry) |    |  (Weight Transfer) |
          +-------------------+    +--------------------+
                    \                        /
                     \                      /
                      v                    v
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

1. **Isolated Binding on Clean Body**: Every accessory or garment (`--hair`, `--upper`, future `--lower`, `--shoes`) is bound in isolation against the clean base body and armature. Never chain bindings sequentially.
2. **Skinning via Data Transfer**: Vertex weights are transferred from the clean body using Blender's `DATA_TRANSFER` modifier (`NEAREST_POLYNORMAL`), avoiding heat-diffusion cross-limb bridging.
3. **Weight Sanitization**: Upper garments strip `mixamorig_Head` weights and reassign them to `mixamorig_Neck` to prevent collar stretching during head motion.
4. **Bone-Axis Centerline Alignment**: Sleeves and limb tubes are aligned to their respective bone axes ($Y_{\text{bone}}(u)$), preventing the forward chest offset from causing rear triceps/elbow penetration.

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

# 4. Generate 3-Phase Showcase Animation Video (MP4)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
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
