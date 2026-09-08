"""
Blender worker script for Human Composer.
Runs inside Blender to unpack USDZ, prevent texture collision,
align hair mesh to head using reference data, rig hair to armature,
export the bound USDZ, and render static & animated previews.
"""

import sys
import os
import json
import zipfile
import shutil
import tempfile
import math
import bpy
import numpy as np


def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = sys.argv[1:]

    config_path = None
    for i, arg in enumerate(argv):
        if arg == "--config" and i + 1 < len(argv):
            config_path = argv[i + 1]
            break

    if not config_path or not os.path.exists(config_path):
        raise ValueError(f"Config file not found or not specified: {config_path}")

    with open(config_path, "r") as f:
        return json.load(f)


def safe_extract_usdz(usdz_path, dest_dir):
    """Extract USDZ file into destination directory."""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(usdz_path, "r") as z:
        z.extractall(dest_dir)


def isolate_part_texture(part_dir, prefix):
    """
    Ensure textures in part_dir do not collide with the same name across models (e.g. shaded.png).
    Renames the file to prefix_filename and returns the new absolute path.
    """
    if not part_dir or not os.path.exists(part_dir):
        return None
    tex_dir = os.path.join(part_dir, "textures")
    if not os.path.exists(tex_dir):
        return None
    for fname in os.listdir(tex_dir):
        if fname.lower().endswith((".png", ".jpg", ".jpeg")):
            src = os.path.join(tex_dir, fname)
            dst = os.path.join(tex_dir, f"{prefix}_{fname}")
            if os.path.exists(src) and not fname.startswith(f"{prefix}_"):
                os.rename(src, dst)
                return dst
            elif fname.startswith(f"{prefix}_"):
                return src
    return None


def align_upper_garment(upper_mesh, body_mesh, armature):
    """
    Align upper garment (e.g. suit/shirt/jacket) to body using skeletal shoulder armhole landmarks,
    properly scaling torso, aligning sleeves to arm bones, exposing hands, and preventing clipping.
    """
    l_arm_bone = armature.data.bones.get("mixamorig_LeftArm") or armature.data.bones.get("LeftArm")
    r_arm_bone = armature.data.bones.get("mixamorig_RightArm") or armature.data.bones.get("RightArm")
    l_hand_bone = armature.data.bones.get("mixamorig_LeftHand") or armature.data.bones.get("LeftHand")
    r_hand_bone = armature.data.bones.get("mixamorig_RightHand") or armature.data.bones.get("RightHand")
    neck_bone = armature.data.bones.get("mixamorig_Neck") or armature.data.bones.get("Neck")

    if not (l_arm_bone and r_arm_bone and l_hand_bone and r_hand_bone and neck_bone):
        return

    p_sh_l = armature.matrix_world @ l_arm_bone.head_local
    p_sh_r = armature.matrix_world @ r_arm_bone.head_local
    p_wr_l = armature.matrix_world @ l_hand_bone.head_local
    p_wr_r = armature.matrix_world @ r_hand_bone.head_local
    p_neck = armature.matrix_world @ neck_bone.head_local

    body_sh_w = (p_sh_l - p_sh_r).length
    ref_sh_w = 0.3852  # standard male shoulder width
    sh_ratio = body_sh_w / ref_sh_w

    # 1. Proportional Scaling
    scale_x = 0.90 * sh_ratio
    scale_y = 0.96 * sh_ratio
    scale_z = 0.88 * sh_ratio

    upper_mesh.scale = (scale_x, scale_y, scale_z)
    bpy.context.view_layer.objects.active = upper_mesh
    upper_mesh.select_set(True)
    bpy.ops.object.transform_apply(scale=True)

    # 2. Torso Positioning: align shoulder line and neck base with forward chest clearance
    target_z = (p_sh_l.z + 0.090) - (0.890 * scale_z)
    target_y = p_neck.y - 0.045 * sh_ratio
    target_x = (p_sh_l.x + p_sh_r.x) / 2.0
    upper_mesh.location = (target_x, target_y, target_z)
    bpy.ops.object.transform_apply(location=True)

    # 3. Align Sleeves to Arm Bones (eliminate arm drop & expose hands outside cuffs)
    coords = np.array([v.co for v in upper_mesh.data.vertices])
    x_seam_l = p_sh_l.x + 0.02
    x_seam_r = p_sh_r.x - 0.02
    x_cuff_l = coords[:, 0].max()
    x_cuff_r = coords[:, 0].min()

    cuff_l_pts = coords[coords[:, 0] > x_cuff_l - 0.04]
    cuff_l_z = cuff_l_pts[:, 2].mean()
    cuff_l_x = cuff_l_pts[:, 0].mean()

    delta_z = p_wr_l.z - cuff_l_z + 0.015
    target_cuff_x = p_wr_l.x - 0.010
    delta_x = cuff_l_x - target_cuff_x

    for i, v in enumerate(coords):
        sh_dist = min(abs(v[0] - x_seam_l), abs(v[0] - x_seam_r))
        sh_boost = max(0.0, 1.0 - (sh_dist / 0.09)**2) * 0.022

        if v[0] > x_seam_l:
            u = min(1.0, max(0.0, (v[0] - x_seam_l) / (x_cuff_l - x_seam_l)))
            lift_curve = u**0.7
            contract_curve = 3 * u**2 - 2 * u**3
            cuff_flare = 1.0 + 0.02 * (u**2)
            rad_clearance = (1.06 + 0.04 * lift_curve) * cuff_flare

            bone_y = p_sh_l.y + u * (p_wr_l.y - p_sh_l.y)
            shift_y = (bone_y - (target_y + 0.018 * scale_y)) * (u**0.6)

            upper_mesh.data.vertices[i].co.x = v[0] - delta_x * contract_curve
            upper_mesh.data.vertices[i].co.y = (v[1] + shift_y - target_y) * rad_clearance + target_y
            upper_mesh.data.vertices[i].co.z = v[2] + delta_z * lift_curve + sh_boost
        elif v[0] < x_seam_r:
            u = min(1.0, max(0.0, (abs(v[0]) - abs(x_seam_r)) / (abs(x_cuff_r) - abs(x_seam_r))))
            lift_curve = u**0.7
            contract_curve = 3 * u**2 - 2 * u**3
            cuff_flare = 1.0 + 0.02 * (u**2)
            rad_clearance = (1.06 + 0.04 * lift_curve) * cuff_flare

            bone_y = p_sh_r.y + u * (p_wr_r.y - p_sh_r.y)
            shift_y = (bone_y - (target_y + 0.018 * scale_y)) * (u**0.6)

            upper_mesh.data.vertices[i].co.x = v[0] + delta_x * contract_curve
            upper_mesh.data.vertices[i].co.y = (v[1] + shift_y - target_y) * rad_clearance + target_y
            upper_mesh.data.vertices[i].co.z = v[2] + delta_z * lift_curve + sh_boost
        else:
            upper_mesh.data.vertices[i].co.z = v[2] + sh_boost

    upper_mesh.data.update()

    print(f"[Blender Binder] Upper garment scale: ({scale_x:.4f}, {scale_y:.4f}, {scale_z:.4f})")
    print(f"[Blender Binder] Upper garment location: ({target_x:.4f}, {target_y:.4f}, {target_z:.4f})")
    print(f"[Blender Binder] Sleeves aligned to T-pose (lift: {delta_z:.3f}m, cuff retraction: {delta_x:.3f}m)")


def bind_and_skin_garment(garment_mesh, body_mesh, armature, root_empty=None):
    """
    Skin garment to the armature by transferring vertex weights directly from the clean body mesh.
    Ensures clothing never inherits mixamorig_Head weights so head movement does not stretch clothing.
    """
    # 1. Transfer vertex weights from clean body mesh
    mod_dt = garment_mesh.modifiers.new(name="DataTransfer", type="DATA_TRANSFER")
    mod_dt.object = body_mesh
    mod_dt.use_vert_data = True
    mod_dt.data_types_verts = {"VGROUP_WEIGHTS"}
    mod_dt.vert_mapping = "POLYINTERP_NEAREST"
    bpy.context.view_layer.objects.active = garment_mesh
    garment_mesh.select_set(True)
    bpy.ops.object.datalayout_transfer(modifier="DataTransfer")
    bpy.ops.object.modifier_apply(modifier="DataTransfer")

    # 2. Eliminate head bone influence on upper garment
    # Reassign any mixamorig_Head weights to mixamorig_Neck, then remove Head group
    head_vg = garment_mesh.vertex_groups.get("mixamorig_Head") or garment_mesh.vertex_groups.get("Head")
    neck_vg = garment_mesh.vertex_groups.get("mixamorig_Neck") or garment_mesh.vertex_groups.get("Neck")
    if head_vg:
        head_name = head_vg.name
        neck_name = neck_vg.name if neck_vg else "none"
        if neck_vg:
            for v in garment_mesh.data.vertices:
                for g in v.groups:
                    if g.group == head_vg.index and g.weight > 0:
                        neck_vg.add([v.index], g.weight, "ADD")
        garment_mesh.vertex_groups.remove(head_vg)
        print(f"[Blender Binder] Reassigned '{head_name}' weights to '{neck_name}' and removed head group from upper garment.")

    # 3. Parent to armature
    if root_empty:
        garment_mesh.parent = root_empty
        garment_mesh.matrix_parent_inverse = root_empty.matrix_world.inverted()
    else:
        garment_mesh.parent = armature
        garment_mesh.matrix_parent_inverse = armature.matrix_world.inverted()

    # 4. Add Armature modifier
    mod_arm = garment_mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod_arm.object = armature
    print(f"[Blender Binder] Rigged upper garment '{garment_mesh.name}' with {len(garment_mesh.vertex_groups)} vertex groups.")


def align_lower_garment(lower_mesh, body_mesh, armature):
    """
    Align lower garment (e.g. trousers, pants) to body using skeletal landmarks:
    waist (Spine bone), hips, leg bones (UpLeg, Leg, Foot).
    Performs proportional scaling, vertical height mapping (waist, crotch, ankles),
    limb bone centerline alignment, gluteal/calf clearances, and seamless crotch closure.
    """
    l_upleg_b = armature.data.bones.get("mixamorig_LeftUpLeg") or armature.data.bones.get("LeftUpLeg")
    r_upleg_b = armature.data.bones.get("mixamorig_RightUpLeg") or armature.data.bones.get("RightUpLeg")
    l_leg_b = armature.data.bones.get("mixamorig_LeftLeg") or armature.data.bones.get("LeftLeg")
    r_leg_b = armature.data.bones.get("mixamorig_RightLeg") or armature.data.bones.get("RightLeg")
    l_foot_b = armature.data.bones.get("mixamorig_LeftFoot") or armature.data.bones.get("LeftFoot")
    r_foot_b = armature.data.bones.get("mixamorig_RightFoot") or armature.data.bones.get("RightFoot")
    spine_b = armature.data.bones.get("mixamorig_Spine") or armature.data.bones.get("Spine")
    hips_b = armature.data.bones.get("mixamorig_Hips") or armature.data.bones.get("Hips")

    if not (l_upleg_b and r_upleg_b and l_leg_b and r_leg_b and l_foot_b and r_foot_b and spine_b and hips_b):
        return

    p_lupleg = armature.matrix_world @ l_upleg_b.head_local
    p_rupleg = armature.matrix_world @ r_upleg_b.head_local
    p_lknee = armature.matrix_world @ l_leg_b.head_local
    p_rknee = armature.matrix_world @ r_leg_b.head_local
    p_lfoot = armature.matrix_world @ l_foot_b.head_local
    p_rfoot = armature.matrix_world @ r_foot_b.head_local
    p_spine = armature.matrix_world @ spine_b.head_local
    p_hips = armature.matrix_world @ hips_b.head_local

    bpts = np.array([v.co for v in body_mesh.data.vertices])

    body_leg_len = (p_hips.z - p_lfoot.z)
    ref_leg_len = 0.5452
    leg_ratio = body_leg_len / ref_leg_len

    # Natural waistline target (sitting comfortably at the waist above underwear)
    target_waist_z = float(p_spine.z + 0.050 * leg_ratio)
    target_ankle_z = float((p_lfoot.z + p_rfoot.z) / 2.0 + 0.012)

    # Detect lowest crotch vertex on body
    crotch_search = bpts[(np.abs(bpts[:, 0]) < 0.025) & (bpts[:, 2] > p_lknee.z + 0.05) & (bpts[:, 2] < p_lupleg.z + 0.1)]
    body_crotch_min_z = float(crotch_search[:, 2].min()) if len(crotch_search) > 0 else float((p_lupleg.z + p_rupleg.z) / 2.0 - 0.10)

    # Trouser crotch target: 20mm below lowest body crotch vertex
    target_crotch_z = float(body_crotch_min_z - 0.020)

    # Body waist & hips cross sections
    waist_bpts = bpts[np.abs(bpts[:, 2] - target_waist_z) < 0.025]
    body_waist_w = float(waist_bpts[:, 0].ptp()) if len(waist_bpts) > 0 else 0.35
    body_waist_d = float(waist_bpts[:, 1].ptp()) if len(waist_bpts) > 0 else 0.28
    body_waist_center_y = float((waist_bpts[:, 1].min() + waist_bpts[:, 1].max()) / 2.0) if len(waist_bpts) > 0 else 0.0

    # Regional pelvic scan across greater trochanters & glutes (accommodates curvier female and muscular male hips)
    hips_zone_z_min = target_crotch_z + 0.30 * (p_hips.z - target_crotch_z)
    hips_zone_z_max = p_hips.z + 0.030
    pelvis_slice_widths = []
    pelvis_slice_depths = []
    pelvis_slice_cys = []
    for z_s in np.arange(hips_zone_z_min, hips_zone_z_max, 0.015):
        sl = bpts[np.abs(bpts[:, 2] - z_s) < 0.012]
        if len(sl) > 0:
            pelvis_slice_widths.append(float(sl[:, 0].ptp()))
            pelvis_slice_depths.append(float(sl[:, 1].ptp()))
            pelvis_slice_cys.append(float((sl[:, 1].min() + sl[:, 1].max()) / 2.0))

    body_hips_w = max(pelvis_slice_widths) if pelvis_slice_widths else 0.42
    body_hips_d = max(pelvis_slice_depths) if pelvis_slice_depths else 0.32
    body_hips_center_y = float(np.mean(pelvis_slice_cys)) if pelvis_slice_cys else 0.0

    # Pants raw geometry
    ppts = np.array([v.co for v in lower_mesh.data.vertices])
    p_z_min = float(ppts[:, 2].min())
    p_z_max = float(ppts[:, 2].max())

    p_center_pts = ppts[np.abs(ppts[:, 0]) < 0.018]
    p_crotch_z = float(p_center_pts[:, 2].min()) if len(p_center_pts) > 0 else (p_z_min + 0.63 * (p_z_max - p_z_min))

    p_waist_pts = ppts[ppts[:, 2] > p_z_max - 0.05]
    p_waist_w = float(p_waist_pts[:, 0].ptp())
    p_waist_d = float(p_waist_pts[:, 1].ptp())
    p_waist_center_y = float((p_waist_pts[:, 1].min() + p_waist_pts[:, 1].max()) / 2.0)

    # Ankle measurements for tailoring cuff width
    ankle_bpts = bpts[np.abs(bpts[:, 2] - target_ankle_z) < 0.025]
    left_ankle_bpts = ankle_bpts[ankle_bpts[:, 0] > 0]
    body_ankle_w = float(left_ankle_bpts[:, 0].ptp()) if len(left_ankle_bpts) > 0 else 0.11

    raw_cuff_pts = ppts[(ppts[:, 2] < p_z_min + 0.05) & (ppts[:, 0] > 0)]
    raw_cuff_w = float(raw_cuff_pts[:, 0].ptp()) if len(raw_cuff_pts) > 0 else 0.368

    p_hips_pts = ppts[(ppts[:, 2] >= p_crotch_z + 0.20 * (p_z_max - p_crotch_z)) & (ppts[:, 2] <= p_crotch_z + 0.70 * (p_z_max - p_crotch_z))]
    p_hips_w = float(p_hips_pts[:, 0].ptp()) if len(p_hips_pts) > 0 else 0.94
    p_hips_d = float(p_hips_pts[:, 1].ptp()) if len(p_hips_pts) > 0 else 0.73

    # Slim-fit tapered scaling:
    # Waist attaches closely to body with 8% ease
    waist_ease = 1.08
    target_waist_scale_x = (body_waist_w / p_waist_w) * waist_ease
    target_waist_scale_y = (body_waist_d / p_waist_d) * waist_ease

    # Hips fits comfortably with 10% ease
    hips_ease = 1.10
    target_hips_scale_x = (body_hips_w / p_hips_w) * hips_ease
    target_hips_scale_y = (body_hips_d / p_hips_d) * hips_ease

    target_cuff_scale_x = min(target_hips_scale_x, max(0.28, (body_ankle_w * 1.08) / raw_cuff_w))

    # Legs use hips scale for smooth continuity into thighs
    leg_scale_x = target_hips_scale_x
    leg_scale_y = target_hips_scale_y

    u_hips = (p_hips.z - target_crotch_z) / (target_waist_z - target_crotch_z)

    print(f"[Blender Binder] Lower garment target waist Z: {target_waist_z:.3f}m, crotch Z: {target_crotch_z:.3f}m, ankle Z: {target_ankle_z:.3f}m")
    print(f"[Blender Binder] Lower garment waist scale: X={target_waist_scale_x:.4f}, Y={target_waist_scale_y:.4f} (slim-fit)")
    print(f"[Blender Binder] Lower garment hips scale:  X={target_hips_scale_x:.4f}, Y={target_hips_scale_y:.4f}")
    print(f"[Blender Binder] Lower garment cuff scale:  X={target_cuff_scale_x:.4f}")

    new_coords = np.zeros_like(ppts)
    for i, pt in enumerate(ppts):
        rx, ry, rz = pt[0], pt[1], pt[2]

        # Piecewise vertical height mapping
        if rz <= p_crotch_z:
            u = (rz - p_z_min) / (p_crotch_z - p_z_min)
            vz = target_ankle_z + u * (target_crotch_z - target_ankle_z)
        else:
            u = (rz - p_crotch_z) / (p_z_max - p_crotch_z)
            vz = target_crotch_z + u * (target_waist_z - target_crotch_z)

        if rz > p_crotch_z:
            pelvis_u = (rz - p_crotch_z) / (p_z_max - p_crotch_z)

            # Smooth convex taper from hips to waist
            if pelvis_u <= u_hips:
                cur_scale_x = target_hips_scale_x
                cur_scale_y = target_hips_scale_y
                target_cy = body_hips_center_y
            else:
                t = (pelvis_u - u_hips) / (1.0 - u_hips)
                blend = t ** 1.8
                cur_scale_x = target_hips_scale_x + blend * (target_waist_scale_x - target_hips_scale_x)
                cur_scale_y = target_hips_scale_y + blend * (target_waist_scale_y - target_hips_scale_y)
                target_cy = body_hips_center_y + blend * (body_waist_center_y - body_hips_center_y)

            # Anterior ease: subtle forward offset for fly/abdominal curvature
            anterior_ease = -0.007 if ry < p_waist_center_y else 0.0

            vx = rx * cur_scale_x
            vy = target_cy + (ry - p_waist_center_y) * cur_scale_y + anterior_ease
        else:
            leg_u = (rz - p_z_min) / (p_crotch_z - p_z_min)
            is_left = (rx >= 0)

            # Taper leg tube width towards the ankle cuff to avoid wide cuffs merging
            cur_leg_scale_x = target_cuff_scale_x + leg_u * (target_hips_scale_x - target_cuff_scale_x)

            bone_upleg = p_lupleg if is_left else p_rupleg
            bone_knee = p_lknee if is_left else p_rknee
            bone_foot = p_lfoot if is_left else p_rfoot

            # Interpolate bone coordinates along leg
            if leg_u < 0.5:
                s = leg_u / 0.5
                bone_x = bone_foot.x + s * (bone_knee.x - bone_foot.x)
                bone_y = bone_foot.y + s * (bone_knee.y - bone_foot.y)
            else:
                s = (leg_u - 0.5) / 0.5
                bone_x = bone_knee.x + s * (bone_upleg.x - bone_knee.x)
                bone_y = bone_knee.y + s * (bone_upleg.y - bone_knee.y)

            raw_center_x = 0.250 if is_left else -0.250
            raw_center_y = -0.048

            scaled_center_x = raw_center_x * cur_leg_scale_x
            scaled_center_y = body_hips_center_y + (raw_center_y - p_waist_center_y) * leg_scale_y

            shift_x = bone_x - scaled_center_x
            shift_y = bone_y - scaled_center_y

            # Smooth bone shift transition: full tracking along leg, blending into pelvis near crotch
            shift_weight = math.cos((math.pi / 2.0) * (leg_u ** 2.0))

            # Anatomical gastrocnemius center (72% up from foot to knee)
            calf_mid_z = bone_foot.z + 0.72 * (bone_knee.z - bone_foot.z)
            calf_dist = abs(vz - calf_mid_z)
            calf_factor = max(0.0, 1.0 - (calf_dist / 0.16)**2)

            vx_unscaled = rx * cur_leg_scale_x
            vy_unscaled = body_hips_center_y + (ry - p_waist_center_y) * leg_scale_y

            dx = vx_unscaled - scaled_center_x
            dy = vy_unscaled - scaled_center_y

            # Posterior and circumferential calf boost for gastrocnemius muscle clearance
            calf_boost_y = 0.15 * calf_factor if dy > 0 else 0.0
            calf_boost_x = 0.08 * calf_factor

            rad_clearance_x = 1.04 + calf_boost_x
            rad_clearance_y = 1.08 + calf_boost_y

            vx = scaled_center_x + shift_x * shift_weight + dx * rad_clearance_x
            vy = scaled_center_y + shift_y * shift_weight + dy * rad_clearance_y

            # Sagittal medial clearance: guarantee legs stay strictly on their own anatomical sides
            medial_clearance = 0.008 * (1.0 - leg_u)
            if is_left:
                vx = max(vx, medial_clearance)
            else:
                vx = min(vx, -medial_clearance)

        new_coords[i] = (vx, vy, vz)

    for i, v in enumerate(lower_mesh.data.vertices):
        v.co.x = new_coords[i, 0]
        v.co.y = new_coords[i, 1]
        v.co.z = new_coords[i, 2]

    lower_mesh.data.update()
    print("[Blender Binder] Lower garment anatomical alignment and deformation complete.")


def bind_and_skin_lower_garment(lower_mesh, body_mesh, armature, root_empty=None):
    """
    Skin lower garment to the armature by transferring vertex weights directly from the clean body mesh.
    Prunes upper-body and arm vertex groups, reassigning Spine1/Spine2 to Spine so upper body/arms
    do not pull on the lower garment.
    """
    # 1. Transfer vertex weights from clean body mesh
    mod_dt = lower_mesh.modifiers.new(name="DataTransfer", type="DATA_TRANSFER")
    mod_dt.object = body_mesh
    mod_dt.use_vert_data = True
    mod_dt.data_types_verts = {"VGROUP_WEIGHTS"}
    mod_dt.vert_mapping = "POLYINTERP_NEAREST"
    bpy.context.view_layer.objects.active = lower_mesh
    lower_mesh.select_set(True)
    bpy.ops.object.datalayout_transfer(modifier="DataTransfer")
    bpy.ops.object.modifier_apply(modifier="DataTransfer")

    # 2. Weight sanitization: prune non-lower vertex groups
    keep_prefixes = [
        "mixamorig_Hips", "mixamorig_Spine", "mixamorig_LeftUpLeg", "mixamorig_RightUpLeg",
        "mixamorig_LeftLeg", "mixamorig_RightLeg", "mixamorig_LeftFoot", "mixamorig_RightFoot",
        "mixamorig_LeftToeBase", "mixamorig_RightToeBase",
        "Hips", "Spine", "LeftUpLeg", "RightUpLeg",
        "LeftLeg", "RightLeg", "LeftFoot", "RightFoot",
        "LeftToeBase", "RightToeBase"
    ]
    spine_vg = lower_mesh.vertex_groups.get("mixamorig_Spine") or lower_mesh.vertex_groups.get("Spine")
    removed_count = 0
    for vg in list(lower_mesh.vertex_groups):
        vg_name = vg.name
        if vg_name in ("mixamorig_Spine1", "mixamorig_Spine2", "Spine1", "Spine2"):
            if spine_vg:
                for v in lower_mesh.data.vertices:
                    for g in v.groups:
                        if g.group == vg.index and g.weight > 0:
                            spine_vg.add([v.index], g.weight, "ADD")
            lower_mesh.vertex_groups.remove(vg)
            removed_count += 1
        elif not any(vg_name.startswith(p) for p in keep_prefixes):
            lower_mesh.vertex_groups.remove(vg)
            removed_count += 1

    print(f"[Blender Binder] Lower garment weight sanitization: pruned {removed_count} upper-body/arm vertex groups, retained {len(lower_mesh.vertex_groups)} groups.")

    # 2.5 Strict cross-limb weight sanitization (prevents legs from pulling/sticking together in animation)
    left_leg_vgs = [vg for vg in lower_mesh.vertex_groups if any(k in vg.name for k in ["LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"])]
    right_leg_vgs = [vg for vg in lower_mesh.vertex_groups if any(k in vg.name for k in ["RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"])]
    hips_vg = lower_mesh.vertex_groups.get("mixamorig_Hips") or lower_mesh.vertex_groups.get("Hips")

    l_upleg_vg = lower_mesh.vertex_groups.get("mixamorig_LeftUpLeg") or lower_mesh.vertex_groups.get("LeftUpLeg")
    r_upleg_vg = lower_mesh.vertex_groups.get("mixamorig_RightUpLeg") or lower_mesh.vertex_groups.get("RightUpLeg")
    l_leg_vg = lower_mesh.vertex_groups.get("mixamorig_LeftLeg") or lower_mesh.vertex_groups.get("LeftLeg")
    r_leg_vg = lower_mesh.vertex_groups.get("mixamorig_RightLeg") or lower_mesh.vertex_groups.get("RightLeg")

    # Detect crotch reference height for separating pelvis basin from independent leg tubes
    l_upleg_b = armature.data.bones.get("mixamorig_LeftUpLeg") or armature.data.bones.get("LeftUpLeg")
    r_upleg_b = armature.data.bones.get("mixamorig_RightUpLeg") or armature.data.bones.get("RightUpLeg")
    if l_upleg_b and r_upleg_b:
        p_lupleg = armature.matrix_world @ l_upleg_b.head_local
        p_rupleg = armature.matrix_world @ r_upleg_b.head_local
        crotch_ref_z = (p_lupleg.z + p_rupleg.z) / 2.0 - 0.08
    else:
        crotch_ref_z = 0.50

    left_vg_map = {vg.index: vg for vg in left_leg_vgs}
    right_vg_map = {vg.index: vg for vg in right_leg_vgs}

    cross_cleaned = 0
    lower_hips_cleaned = 0
    for v in lower_mesh.data.vertices:
        vx = v.co.x
        vz = v.co.z
        v_groups = [(g.group, g.weight) for g in v.groups if g.weight > 0]
        if vx > 0.005:
            # Left leg side (+X): clear any right leg weights
            for grp_idx, w in v_groups:
                if grp_idx in right_vg_map:
                    if vz < crotch_ref_z - 0.02:
                        target_l_vg = l_leg_vg if "Leg" in right_vg_map[grp_idx].name or "Foot" in right_vg_map[grp_idx].name else l_upleg_vg
                        if target_l_vg:
                            target_l_vg.add([v.index], w, "ADD")
                    else:
                        if hips_vg:
                            hips_vg.add([v.index], w, "ADD")
                    right_vg_map[grp_idx].add([v.index], 0.0, "REPLACE")
                    cross_cleaned += 1

            # Remove erroneous Hips weights on lower leg/shins/cuffs (vz < crotch_ref_z - 0.05)
            if vz < crotch_ref_z - 0.05 and hips_vg:
                for grp_idx, w in v_groups:
                    if grp_idx == hips_vg.index:
                        target_l_vg = l_leg_vg if vz < (crotch_ref_z - 0.15) else l_upleg_vg
                        if target_l_vg:
                            target_l_vg.add([v.index], w, "ADD")
                        hips_vg.add([v.index], 0.0, "REPLACE")
                        lower_hips_cleaned += 1

        elif vx < -0.005:
            # Right leg side (-X): clear any left leg weights
            for grp_idx, w in v_groups:
                if grp_idx in left_vg_map:
                    if vz < crotch_ref_z - 0.02:
                        target_r_vg = r_leg_vg if "Leg" in left_vg_map[grp_idx].name or "Foot" in left_vg_map[grp_idx].name else r_upleg_vg
                        if target_r_vg:
                            target_r_vg.add([v.index], w, "ADD")
                    else:
                        if hips_vg:
                            hips_vg.add([v.index], w, "ADD")
                    left_vg_map[grp_idx].add([v.index], 0.0, "REPLACE")
                    cross_cleaned += 1

            # Remove erroneous Hips weights on lower leg/shins/cuffs (vz < crotch_ref_z - 0.05)
            if vz < crotch_ref_z - 0.05 and hips_vg:
                for grp_idx, w in v_groups:
                    if grp_idx == hips_vg.index:
                        target_r_vg = r_leg_vg if vz < (crotch_ref_z - 0.15) else r_upleg_vg
                        if target_r_vg:
                            target_r_vg.add([v.index], w, "ADD")
                        hips_vg.add([v.index], 0.0, "REPLACE")
                        lower_hips_cleaned += 1
        else:
            # Center crotch apex (|X| <= 5mm): assign to hips and clear both leg weights
            for grp_idx, w in v_groups:
                if grp_idx in left_vg_map:
                    if hips_vg:
                        hips_vg.add([v.index], w, "ADD")
                    left_vg_map[grp_idx].add([v.index], 0.0, "REPLACE")
                    cross_cleaned += 1
                elif grp_idx in right_vg_map:
                    if hips_vg:
                        hips_vg.add([v.index], w, "ADD")
                    right_vg_map[grp_idx].add([v.index], 0.0, "REPLACE")
                    cross_cleaned += 1

    print(f"[Blender Binder] Sanitized {cross_cleaned} cross-limb and {lower_hips_cleaned} lower-leg hips vertex group assignments.")

    # 3. Parent to armature
    if root_empty:
        lower_mesh.parent = root_empty
        lower_mesh.matrix_parent_inverse = root_empty.matrix_world.inverted()
    else:
        lower_mesh.parent = armature
        lower_mesh.matrix_parent_inverse = armature.matrix_world.inverted()

    # 4. Add Armature modifier
    mod_arm = lower_mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod_arm.object = armature
    print(f"[Blender Binder] Rigged lower garment '{lower_mesh.name}' with {len(lower_mesh.vertex_groups)} vertex groups.")


def update_material_texture(mesh_obj, mat_name, tex_path):
    """Ensure the mesh object's material uses the specified texture image."""
    if not mesh_obj or not mesh_obj.data.materials:
        return

    mat = mesh_obj.data.materials[0]
    if mat:
        mat = mat.copy()
        mesh_obj.data.materials[0] = mat
        mat.name = mat_name

    if not mat.use_nodes:
        mat.use_nodes = True

    if tex_path and os.path.exists(tex_path):
        img = bpy.data.images.load(tex_path)
        img.name = os.path.basename(tex_path)
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                node.image = img


def setup_lighting_and_world():
    """Configure studio lighting and world background."""
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.92, 0.92, 0.92, 1.0)
        bg_node.inputs["Strength"].default_value = 1.0


def main():
    config = parse_args()
    body_usdz = config["body"]
    hair_usdz = config.get("hair")
    upper_usdz = config.get("upper")
    lower_usdz = config.get("lower")
    output_usdz = config["output_usdz"]
    preview_image_path = config.get("preview_image_path")
    preview_video_path = config.get("preview_video_path")
    intermediate_dir = config.get("intermediate_dir")
    render_intermediate = config.get("render_intermediate", False)
    ref_data = config.get("ref_data", {})

    temp_root = tempfile.mkdtemp(prefix="human_composer_")
    body_extract_dir = os.path.join(temp_root, "body_unpacked")
    hair_extract_dir = os.path.join(temp_root, "hair_unpacked") if hair_usdz else None
    upper_extract_dir = os.path.join(temp_root, "upper_unpacked") if upper_usdz else None
    lower_extract_dir = os.path.join(temp_root, "lower_unpacked") if lower_usdz else None

    try:
        print("[Blender Binder] Unpacking USDZ archives...")
        safe_extract_usdz(body_usdz, body_extract_dir)
        body_tex = isolate_part_texture(body_extract_dir, "body")
        print(f"[Blender Binder] Body texture: {body_tex}")

        hair_tex = None
        if hair_usdz:
            safe_extract_usdz(hair_usdz, hair_extract_dir)
            hair_tex = isolate_part_texture(hair_extract_dir, "hair")
            print(f"[Blender Binder] Hair texture: {hair_tex}")

        upper_tex = None
        if upper_usdz:
            safe_extract_usdz(upper_usdz, upper_extract_dir)
            upper_tex = isolate_part_texture(upper_extract_dir, "upper")
            print(f"[Blender Binder] Upper garment texture: {upper_tex}")

        lower_tex = None
        if lower_usdz:
            safe_extract_usdz(lower_usdz, lower_extract_dir)
            lower_tex = isolate_part_texture(lower_extract_dir, "lower")
            print(f"[Blender Binder] Lower garment texture: {lower_tex}")

        # Reset Blender scene
        bpy.ops.wm.read_factory_settings(use_empty=True)

        # 1. Import Body USDZ
        print(f"[Blender Binder] Importing body USDZ: {body_usdz}")
        bpy.ops.wm.usd_import(filepath=body_usdz)

        root_empty = None
        armature = None
        body_mesh = None

        for o in bpy.context.scene.objects:
            if o.type == "ARMATURE":
                armature = o
            elif o.type == "EMPTY" and "Armature" in o.name:
                root_empty = o
            elif o.type == "MESH":
                body_mesh = o

        if not body_mesh:
            raise RuntimeError("Failed to locate body mesh in imported USDZ.")
        if not armature:
            raise RuntimeError("Failed to locate armature in imported USDZ.")

        # Detect head bone name from armature
        head_bone_name = "mixamorig_Head"
        if armature:
            bone_names = [b.name for b in armature.data.bones]
            if "mixamorig_Head" in bone_names:
                head_bone_name = "mixamorig_Head"
            elif "Head" in bone_names:
                head_bone_name = "Head"
            else:
                for b_name in bone_names:
                    b_low = b_name.lower()
                    if "head" in b_low and "end" not in b_low and "top" not in b_low:
                        head_bone_name = b_name
                        break

        # Detect any skeletal animation on imported body
        first_skeleton_action = None
        if armature.animation_data and armature.animation_data.action:
            first_skeleton_action = armature.animation_data.action
            armature.animation_data.action = None
        elif bpy.data.actions:
            first_skeleton_action = bpy.data.actions[0]

        # Load optional external animation file if provided (only needed if rendering preview animation)
        anim_file = config.get("anim")
        if preview_video_path and anim_file and os.path.exists(anim_file):
            print(f"[Blender Binder] Loading external animation from: {anim_file}")
            pre_anim_objs = set(bpy.context.scene.objects)
            bpy.ops.wm.usd_import(filepath=anim_file)
            new_anim_objs = [o for o in bpy.context.scene.objects if o not in pre_anim_objs]
            for o in new_anim_objs:
                if o.type == "ARMATURE" and o.animation_data and o.animation_data.action:
                    first_skeleton_action = o.animation_data.action
                bpy.data.objects.remove(o, do_unlink=True)
            if first_skeleton_action:
                print(f"[Blender Binder] Detected skeleton animation: {first_skeleton_action.name}")

        update_material_texture(body_mesh, "Body_Material", body_tex)

        bound_parts = {}

        # 2. Import & Bind Hair USDZ (if provided)
        if hair_usdz:
            existing_objs = set(bpy.context.scene.objects)
            print(f"[Blender Binder] Importing hair USDZ: {hair_usdz}")
            bpy.ops.wm.usd_import(filepath=hair_usdz)

            new_objs = [o for o in bpy.context.scene.objects if o not in existing_objs]
            hair_mesh = None
            for o in new_objs:
                if o.type == "MESH":
                    hair_mesh = o
                elif o.type == "EMPTY" and o.name.startswith("_materials"):
                    bpy.data.objects.remove(o)

            if not hair_mesh:
                raise RuntimeError("Failed to locate hair mesh in imported USDZ.")

            update_material_texture(hair_mesh, "Hair_Material", hair_tex)

            # 3. Analyze Body Head Geometry
            body_coords = np.array([v.co for v in body_mesh.data.vertices])
            body_z_min = float(body_coords[:, 2].min())
            body_z_max = float(body_coords[:, 2].max())
            body_height = body_z_max - body_z_min

            head_vg = body_mesh.vertex_groups.get(head_bone_name)
            head_vert_indices = []
            if head_vg:
                head_vert_indices = [
                    v.index for v in body_mesh.data.vertices
                    for g in v.groups if g.group == head_vg.index and g.weight > 0.1
                ]

            if not head_vert_indices:
                head_vert_indices = [
                    v.index for v in body_mesh.data.vertices
                    if v.co.z > (body_z_max - 0.65)
                ]

            head_coords = body_coords[head_vert_indices]
            head_x_min, head_x_max = float(head_coords[:, 0].min()), float(head_coords[:, 0].max())
            head_y_min, head_y_max = float(head_coords[:, 1].min()), float(head_coords[:, 1].max())
            head_z_min, head_z_max = float(head_coords[:, 2].min()), float(head_coords[:, 2].max())

            head_width = head_x_max - head_x_min
            head_depth = head_y_max - head_y_min
            head_x_center = (head_x_min + head_x_max) / 2.0
            head_y_center = (head_y_min + head_y_max) / 2.0

            # 4. Analyze Hair Geometry
            hair_coords = np.array([v.co for v in hair_mesh.data.vertices])
            hair_x_min, hair_x_max = float(hair_coords[:, 0].min()), float(hair_coords[:, 0].max())
            hair_y_min, hair_y_max = float(hair_coords[:, 1].min()), float(hair_coords[:, 1].max())
            hair_z_min, hair_z_max = float(hair_coords[:, 2].min()), float(hair_coords[:, 2].max())

            hair_width = hair_x_max - hair_x_min
            hair_depth = hair_y_max - hair_y_min
            hair_height = hair_z_max - hair_z_min
            hair_x_center = (hair_x_min + hair_x_max) / 2.0
            hair_y_center = (hair_y_min + hair_y_max) / 2.0

            print(f"[Blender Binder] Body height: {body_height:.3f}m, Head width: {head_width:.3f}m, depth: {head_depth:.3f}m")
            print(f"[Blender Binder] Raw Hair width: {hair_width:.3f}m, depth: {hair_depth:.3f}m, height: {hair_height:.3f}m")

            # 5. Compute Alignment Parameters
            ref_front = ref_data.get("front")
            ref_left = ref_data.get("left")
            ref_right = ref_data.get("right")
            ref_side = ref_left or ref_right

            if ref_front:
                ref_char_height = float(ref_front["char_height"])
                m_per_px = body_height / ref_char_height
                target_width = float(ref_front["head_width"]) * m_per_px
                target_top = body_z_min + (float(ref_front["char_y_max"] - ref_front["head_y_min"])) * m_per_px + 0.035
            else:
                m_per_px = body_height / 3950.0
                target_width = head_width * 1.16
                target_top = head_z_max + 0.055

            if ref_side:
                side_m_per_px = body_height / float(ref_side["char_height"])
                target_depth = float(ref_side["head_width"]) * side_m_per_px
                side_x_center = float(ref_side["head_x_center"])
                offset_px = side_x_center - (float(ref_side["width"]) / 2.0)
                if ref_left:
                    target_y_center = head_y_center + (offset_px * side_m_per_px)
                else:
                    target_y_center = head_y_center - (offset_px * side_m_per_px)
            else:
                target_depth = target_width * (head_depth / head_width) * 1.08
                target_y_center = head_y_center + 0.04

            scale_x = (target_width / hair_width) * 1.045
            scale_y = (target_depth / hair_depth) * 1.055
            scale_z = scale_x * 1.035

            target_y_center = max(target_y_center, head_y_center + 0.038)

            loc_x = head_x_center - (hair_x_center * scale_x)
            loc_y = target_y_center - (hair_y_center * scale_y)
            loc_z = target_top - (hair_z_max * scale_z)

            # Crown coverage check
            scaled_hair_top = hair_z_max * scale_z + loc_z
            if scaled_hair_top < head_z_max + 0.045:
                loc_z += (head_z_max + 0.048 - scaled_hair_top)

            # Rear skull coverage check
            scaled_hair_back = hair_y_max * scale_y + loc_y
            if scaled_hair_back < head_y_max + 0.025:
                loc_y += (head_y_max + 0.028 - scaled_hair_back)

            # Automated anti-clipping solver to prevent scalp poking through hair parting
            from mathutils.bvhtree import BVHTree
            import mathutils

            upper_head_verts = [v for v in head_coords if v[2] > (head_z_max - 0.10)]
            hair_polys = [p.vertices for p in hair_mesh.data.polygons]

            def check_scalp_clipping(sx, sy, sz, lx, ly, lz):
                th_coords = hair_coords.copy()
                th_coords[:, 0] = th_coords[:, 0] * sx + lx
                th_coords[:, 1] = th_coords[:, 1] * sy + ly
                th_coords[:, 2] = th_coords[:, 2] * sz + lz
                bvh = BVHTree.FromPolygons(th_coords, hair_polys)

                clips = 0
                for hv in upper_head_verts:
                    origin = mathutils.Vector(hv)
                    loc, _, _, _ = bvh.ray_cast(origin, mathutils.Vector((0, 0, 1)))
                    if loc is None:
                        dloc, _, _, ddist = bvh.ray_cast(origin, mathutils.Vector((0, 0, -1)))
                        if dloc is not None and ddist < 0.04:
                            clips += 1
                return clips

            clips = check_scalp_clipping(scale_x, scale_y, scale_z, loc_x, loc_y, loc_z)
            anti_clip_iters = 0
            while clips > 0 and anti_clip_iters < 6:
                anti_clip_iters += 1
                scale_x *= 1.015
                scale_y *= 1.015
                scale_z *= 1.015
                loc_z += 0.005
                clips = check_scalp_clipping(scale_x, scale_y, scale_z, loc_x, loc_y, loc_z)

            if anti_clip_iters > 0:
                print(f"[Blender Binder] Anti-clipping solver adjusted hair (iterations: {anti_clip_iters}, remaining clips: {clips})")

            print(f"[Blender Binder] Optimal scale: ({scale_x:.4f}, {scale_y:.4f}, {scale_z:.4f})")
            print(f"[Blender Binder] Optimal location: ({loc_x:.4f}, {loc_y:.4f}, {loc_z:.4f})")

            # 6. Apply Transformation to Hair
            hair_mesh.scale = (scale_x, scale_y, scale_z)
            hair_mesh.location = (loc_x, loc_y, loc_z)
            bpy.context.view_layer.objects.active = hair_mesh
            hair_mesh.select_set(True)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

            # 7. Bind & Skin Hair to Armature
            if root_empty:
                hair_mesh.parent = root_empty
                hair_mesh.matrix_parent_inverse = root_empty.matrix_world.inverted()
            else:
                hair_mesh.parent = armature

            mod = hair_mesh.modifiers.new(name="Armature", type="ARMATURE")
            mod.object = armature

            vg = hair_mesh.vertex_groups.new(name=head_bone_name)
            vg.add(list(range(len(hair_mesh.data.vertices))), 1.0, "REPLACE")
            print(f"[Blender Binder] Rigged hair to bone: {head_bone_name}")
            bound_parts["hair"] = hair_mesh

        # 3. Import & Bind Upper Garment USDZ (if provided)
        if upper_usdz:
            existing_objs = set(bpy.context.scene.objects)
            print(f"[Blender Binder] Importing upper garment USDZ: {upper_usdz}")
            bpy.ops.wm.usd_import(filepath=upper_usdz)

            new_objs = [o for o in bpy.context.scene.objects if o not in existing_objs]
            upper_mesh = None
            for o in new_objs:
                if o.type == "MESH":
                    upper_mesh = o
                elif o.type == "EMPTY" and o.name.startswith("_materials"):
                    bpy.data.objects.remove(o)

            if not upper_mesh:
                raise RuntimeError("Failed to locate upper garment mesh in imported USDZ.")

            update_material_texture(upper_mesh, "Upper_Material", upper_tex)

            # Align upper garment against clean body landmarks
            align_upper_garment(upper_mesh, body_mesh, armature)

            # Rig and skin to armature via clean body vertex weight transfer
            bind_and_skin_garment(upper_mesh, body_mesh, armature, root_empty)
            bound_parts["upper"] = upper_mesh

        # 4. Import & Bind Lower Garment USDZ (if provided)
        if lower_usdz:
            existing_objs = set(bpy.context.scene.objects)
            print(f"[Blender Binder] Importing lower garment USDZ: {lower_usdz}")
            bpy.ops.wm.usd_import(filepath=lower_usdz)

            new_objs = [o for o in bpy.context.scene.objects if o not in existing_objs]
            lower_mesh = None
            for o in new_objs:
                if o.type == "MESH":
                    lower_mesh = o
                elif o.type == "EMPTY" and o.name.startswith("_materials"):
                    bpy.data.objects.remove(o)

            if not lower_mesh:
                raise RuntimeError("Failed to locate lower garment mesh in imported USDZ.")

            update_material_texture(lower_mesh, "Lower_Material", lower_tex)

            # Align lower garment against clean body landmarks
            align_lower_garment(lower_mesh, body_mesh, armature)

            # Rig and skin to armature via clean body vertex weight transfer
            bind_and_skin_lower_garment(lower_mesh, body_mesh, armature, root_empty)
            bound_parts["lower"] = lower_mesh

        # 8. Export Bound USDZ
        print(f"[Blender Binder] Exporting USDZ to {output_usdz}...")
        os.makedirs(os.path.dirname(os.path.abspath(output_usdz)), exist_ok=True)

        bpy.ops.wm.usd_export(
            filepath=output_usdz,
            export_armatures=True,
            export_textures=True,
            export_materials=True,
            generate_preview_surface=True,
            relative_paths=True,
            selected_objects_only=False
        )
        print("[Blender Binder] USDZ export complete.")

        # Setup Camera & Lighting for Previews (only if rendering is needed)
        needs_render = bool(preview_image_path or (render_intermediate and intermediate_dir) or preview_video_path)
        if needs_render:
            setup_lighting_and_world()

            cam_data = bpy.data.cameras.new("PreviewCamera")
            cam_data.type = "ORTHO"
            cam_data.ortho_scale = 2.05
            cam_data.clip_start = 0.01
            cam_data.clip_end = 100.0
            cam_obj = bpy.data.objects.new("PreviewCamera", cam_data)
            bpy.context.scene.collection.objects.link(cam_obj)
            bpy.context.scene.camera = cam_obj

        # 9. Render Static Preview Image
        if preview_image_path:
            for p_mesh in bound_parts.values():
                p_mesh.hide_render = False
            print(f"[Blender Binder] Rendering static preview to {preview_image_path}...")
            os.makedirs(os.path.dirname(os.path.abspath(preview_image_path)), exist_ok=True)
            cam_obj.location = (0, -5.0, 0.95)
            cam_obj.rotation_euler = (math.radians(90), 0, 0)
            bpy.context.scene.render.resolution_x = 1024
            bpy.context.scene.render.resolution_y = 1024
            bpy.context.scene.render.image_settings.file_format = 'PNG'
            bpy.context.scene.render.filepath = preview_image_path
            bpy.ops.render.render(write_still=True)
            print(f"[Blender Binder] Saved static preview: {preview_image_path}")

        # 10. Render Intermediate Multi-Angle Images and Separate Part Renders
        if render_intermediate and intermediate_dir:
            print(f"[Blender Binder] Rendering intermediate previews to {intermediate_dir}...")
            os.makedirs(intermediate_dir, exist_ok=True)
            bpy.context.scene.render.resolution_x = 1024
            bpy.context.scene.render.resolution_y = 1024
            bpy.context.scene.render.image_settings.file_format = 'PNG'

            cam_front_loc = (0, -5.0, 0.95)
            cam_front_rot = (math.radians(90), 0, 0)

            # 10a. Render each separate bound part in isolation on the clean body
            for part_name, part_mesh in bound_parts.items():
                print(f"[Blender Binder] Rendering isolated preview for bound part: {part_name}...")
                for p_name, p_mesh in bound_parts.items():
                    p_mesh.hide_render = (p_name != part_name)

                cam_obj.location = cam_front_loc
                cam_obj.rotation_euler = cam_front_rot
                part_path = os.path.join(intermediate_dir, f"part_{part_name}.png")
                bpy.context.scene.render.filepath = part_path
                bpy.ops.render.render(write_still=True)
                print(f"[Blender Binder] Saved separate part preview: {part_path}")

            # 10b. Unhide all parts for final composite renders
            for p_mesh in bound_parts.values():
                p_mesh.hide_render = False

            final_comp_path = os.path.join(intermediate_dir, "part_final.png")
            cam_obj.location = cam_front_loc
            cam_obj.rotation_euler = cam_front_rot
            bpy.context.scene.render.filepath = final_comp_path
            bpy.ops.render.render(write_still=True)
            print(f"[Blender Binder] Saved final composite preview: {final_comp_path}")

            # Multi-angle views of the final composite
            cam_views = {
                "front": ((0, -5.0, 0.95), (math.radians(90), 0, 0)),
                "left": ((5.0, 0, 0.95), (math.radians(90), 0, math.radians(90))),
                "right": ((-5.0, 0, 0.95), (math.radians(90), 0, math.radians(-90))),
                "back": ((0, 5.0, 0.95), (math.radians(90), 0, math.radians(180))),
                "bottom": ((0, 0, -4.0), (math.radians(180), 0, 0)),
            }

            for view_name, (cam_loc, cam_rot) in cam_views.items():
                cam_obj.location = cam_loc
                cam_obj.rotation_euler = cam_rot
                img_path = os.path.join(intermediate_dir, f"render_{view_name}.png")
                bpy.context.scene.render.filepath = img_path
                bpy.ops.render.render(write_still=True)

        # 11. Render Sequenced Preview Animation (MP4)
        if preview_video_path:
            for p_mesh in bound_parts.values():
                p_mesh.hide_render = False
            print(f"[Blender Binder] Rendering preview animation to {preview_video_path}...")
            os.makedirs(os.path.dirname(os.path.abspath(preview_video_path)), exist_ok=True)

            phase1_frames = 48  # 360 Turntable rotation (2.0s)
            phase2_frames = 48  # 180 Look Left - Right Head animation (2.0s)
            phase2_start = phase1_frames + 1  # Frame 49
            phase2_end = phase1_frames + phase2_frames  # Frame 96

            phase3_start = phase2_end + 1  # Frame 97
            phase3_frames = 0

            armature.animation_data_create()
            armature.animation_data.action = None

            # Phase 2: 180° look left-right head animation
            head_pbone = armature.pose.bones.get(head_bone_name) if armature else None
            if head_pbone:
                head_action = bpy.data.actions.new(name="Head_Look_Action")
                armature.animation_data.action = head_action
                head_pbone.rotation_mode = 'XYZ'

                # Neutral at frame 49
                head_pbone.rotation_euler = (0, 0, 0)
                head_pbone.keyframe_insert(data_path="rotation_euler", index=1, frame=phase2_start)

                # Look left (+65 deg) at frame 61
                head_pbone.rotation_euler.y = math.radians(65)
                head_pbone.keyframe_insert(data_path="rotation_euler", index=1, frame=phase2_start + 12)

                # Look right (-65 deg) at frame 73 (~130-140 deg sweep)
                head_pbone.rotation_euler.y = math.radians(-65)
                head_pbone.keyframe_insert(data_path="rotation_euler", index=1, frame=phase2_start + 24)

                # Return to center at frame 85
                head_pbone.rotation_euler.y = 0.0
                head_pbone.keyframe_insert(data_path="rotation_euler", index=1, frame=phase2_start + 36)

                # Hold center until frame 96
                head_pbone.rotation_euler.y = 0.0
                head_pbone.keyframe_insert(data_path="rotation_euler", index=1, frame=phase2_end)

                for fc in head_action.fcurves:
                    for kf in fc.keyframe_points:
                        kf.interpolation = 'BEZIER'

                track_head = armature.animation_data.nla_tracks.new()
                track_head.name = "HeadLookTrack"
                strip_head = track_head.strips.new("HeadLookStrip", phase2_start, head_action)
                strip_head.action_frame_start = phase2_start
                strip_head.action_frame_end = phase2_end
                armature.animation_data.action = None

            # Phase 3: First skeleton animation (if present)
            if first_skeleton_action:
                act_start = int(first_skeleton_action.frame_range[0])
                act_end = int(first_skeleton_action.frame_range[1])
                act_len = max(1, act_end - act_start)
                phase3_frames = min(72, act_len)  # Play up to 3 seconds of the action
                track_skel = armature.animation_data.nla_tracks.new()
                track_skel.name = "SkeletonAnimTrack"
                strip_skel = track_skel.strips.new("SkeletonAnimStrip", phase3_start, first_skeleton_action)
                strip_skel.action_frame_start = act_start
                strip_skel.action_frame_end = act_start + phase3_frames
                strip_skel.blend_type = 'REPLACE'
                print(f"[Blender Binder] Sequenced skeleton action '{first_skeleton_action.name}' for Phase 3 (frames {phase3_start}-{phase3_start + phase3_frames})")

            total_frames = phase2_end + phase3_frames
            bpy.context.scene.frame_start = 1
            bpy.context.scene.frame_end = total_frames
            bpy.context.scene.render.fps = 24

            # Phase 1: 360° Turntable rotation on root empty / armature
            target_rot_obj = root_empty if root_empty else armature
            target_rot_obj.rotation_mode = 'XYZ'
            target_rot_obj.animation_data_clear()

            target_rot_obj.rotation_euler.z = 0.0
            target_rot_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=1)

            target_rot_obj.rotation_euler.z = 2.0 * math.pi * (phase1_frames - 1) / phase1_frames
            target_rot_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=phase1_frames)

            # Hold stationary (facing front) during Phase 2 and Phase 3
            target_rot_obj.rotation_euler.z = 0.0
            target_rot_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=phase2_start)
            target_rot_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=total_frames)

            if target_rot_obj.animation_data and target_rot_obj.animation_data.action:
                for fc in target_rot_obj.animation_data.action.fcurves:
                    for kf in fc.keyframe_points:
                        if kf.co.x <= phase1_frames:
                            kf.interpolation = 'LINEAR'
                        else:
                            kf.interpolation = 'CONSTANT'

            # Camera Framing: Full body in Phase 1 & 3, smooth zoom-in for Phase 2 head look
            cam_data.animation_data_clear()
            cam_obj.animation_data_clear()

            cam_obj.location = (0, -5.0, 0.95)
            cam_obj.rotation_euler = (math.radians(90), 0, 0)
            cam_data.ortho_scale = 2.05

            cam_data.keyframe_insert(data_path="ortho_scale", frame=1)
            cam_data.keyframe_insert(data_path="ortho_scale", frame=phase1_frames - 2)
            cam_obj.keyframe_insert(data_path="location", index=2, frame=1)
            cam_obj.keyframe_insert(data_path="location", index=2, frame=phase1_frames - 2)

            # Zoom into upper body / head for Phase 2
            if head_pbone and armature:
                head_z_level = float((armature.matrix_world @ head_pbone.head).z)
            elif 'head_coords' in locals():
                head_z_level = float(head_coords[:, 2].mean())
            else:
                head_z_level = 1.65
            cam_data.ortho_scale = 1.25
            cam_obj.location.z = head_z_level - 0.15
            cam_data.keyframe_insert(data_path="ortho_scale", frame=phase2_start)
            cam_data.keyframe_insert(data_path="ortho_scale", frame=phase2_end - 4)
            cam_obj.keyframe_insert(data_path="location", index=2, frame=phase2_start)
            cam_obj.keyframe_insert(data_path="location", index=2, frame=phase2_end - 4)

            # Zoom back out to full body for Phase 3
            cam_data.ortho_scale = 2.05
            cam_obj.location.z = 0.95
            cam_data.keyframe_insert(data_path="ortho_scale", frame=phase2_end)
            cam_data.keyframe_insert(data_path="ortho_scale", frame=total_frames)
            cam_obj.keyframe_insert(data_path="location", index=2, frame=phase2_end)
            cam_obj.keyframe_insert(data_path="location", index=2, frame=total_frames)

            # Video encoding settings
            bpy.context.scene.render.resolution_x = 512
            bpy.context.scene.render.resolution_y = 512
            bpy.context.scene.render.image_settings.file_format = 'FFMPEG'
            bpy.context.scene.render.ffmpeg.format = 'MPEG4'
            bpy.context.scene.render.ffmpeg.codec = 'H264'
            bpy.context.scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
            bpy.context.scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
            bpy.context.scene.render.filepath = preview_video_path

            bpy.ops.render.render(animation=True)
            print(f"[Blender Binder] Saved multi-phase preview animation ({total_frames} frames): {preview_video_path}")

    finally:
        if os.path.exists(temp_root):
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
