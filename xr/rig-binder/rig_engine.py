"""
Rig Engine (rig_engine.py) - Universal Blender Backend for Rig Binder
=====================================================================
Executes inside Blender to provide:
  - Universal 3D/2D mesh landmark extraction
  - Armature generation from presets (Shadow Puppet 19, Humanoid 65, Biped 24, Custom JSON)
  - Automatic skinning and bone weight assignment
  - Rig-specific procedural animation generation
  - Multi-format export (USDZ, GLB, Blend, FBX)
  - Contact sheet and MP4 preview rendering
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import bpy
import mathutils
import numpy as np


# ---------------------------------------------------------------------------
# Landmark Extractor
# ---------------------------------------------------------------------------

class SkeletalLandmarkExtractor:
    """Extracts proportional anatomical landmarks from arbitrary 3D character meshes."""

    def __init__(self, model_obj, is_2d=False):
        self.model = model_obj
        self.is_2d = is_2d
        self.landmarks = {}

    def extract(self):
        mesh = self.model.data
        coords = np.array([self.model.matrix_world @ v.co for v in mesh.vertices])

        if len(coords) == 0:
            raise ValueError("Target mesh contains 0 vertices.")

        x_min, x_max = float(coords[:, 0].min()), float(coords[:, 0].max())
        y_min, y_max = float(coords[:, 1].min()), float(coords[:, 1].max())
        z_min, z_max = float(coords[:, 2].min()), float(coords[:, 2].max())

        width = max(x_max - x_min, 0.001)
        depth = max(y_max - y_min, 0.001)
        height = max(z_max - z_min, 0.001)

        x_center = (x_min + x_max) * 0.5
        y_center = (y_min + y_max) * 0.5 if self.is_2d else (y_min + y_max) * 0.5
        y_front = y_min if not self.is_2d else y_center

        def cluster(mask, fallback_vec):
            pts = coords[mask]
            if len(pts) > 0:
                c = pts.mean(axis=0)
                y_val = y_center if self.is_2d else float(c[1])
                return mathutils.Vector((float(c[0]), y_val, float(c[2])))
            return mathutils.Vector(fallback_vec)

        # 1. Core Center Column
        root_pos = mathutils.Vector((0.0, y_center, z_min))

        waist_mask = (
            (coords[:, 2] >= z_min + height * 0.30)
            & (coords[:, 2] <= z_min + height * 0.42)
            & (np.abs(coords[:, 0]) < width * 0.25)
        )
        waist_pos = cluster(waist_mask, (0.0, y_center, z_min + height * 0.35))
        hips_pos = waist_pos.copy()

        spine_mask = (
            (coords[:, 2] >= z_min + height * 0.42)
            & (coords[:, 2] <= z_min + height * 0.50)
            & (np.abs(coords[:, 0]) < width * 0.25)
        )
        spine_pos = cluster(spine_mask, (0.0, y_center, z_min + height * 0.44))

        spine1_pos = mathutils.Vector((0.0, y_center, z_min + height * 0.51))
        spine2_pos = mathutils.Vector((0.0, y_center, z_min + height * 0.57))

        chest_mask = (
            (coords[:, 2] >= z_min + height * 0.55)
            & (coords[:, 2] <= z_min + height * 0.65)
            & (np.abs(coords[:, 0]) < width * 0.25)
        )
        chest_pos = cluster(chest_mask, (0.0, y_center, z_min + height * 0.62))

        neck_mask = (
            (coords[:, 2] >= z_min + height * 0.64)
            & (coords[:, 2] <= z_min + height * 0.72)
            & (np.abs(coords[:, 0]) < width * 0.18)
        )
        neck_pos = cluster(neck_mask, (0.0, y_center, z_min + height * 0.68))

        head_mask = (
            (coords[:, 2] >= z_min + height * 0.72)
            & (coords[:, 2] <= z_min + height * 0.88)
            & (np.abs(coords[:, 0]) < width * 0.22)
        )
        head_pos = cluster(head_mask, (0.0, y_center, z_min + height * 0.77))
        head_top = mathutils.Vector((0.0, y_center, z_max))

        # Facial Anchors
        jaw_pos = mathutils.Vector((0.0, y_center - (depth * 0.15 if not self.is_2d else 0), z_min + height * 0.71))
        l_eye = mathutils.Vector((width * 0.08, y_center - (depth * 0.12 if not self.is_2d else 0), z_min + height * 0.78))
        r_eye = mathutils.Vector((-width * 0.08, y_center - (depth * 0.12 if not self.is_2d else 0), z_min + height * 0.78))

        # 2. Left Arm Chain (+X)
        l_sh_mask = (
            (coords[:, 0] >= x_max * 0.20)
            & (coords[:, 0] <= x_max * 0.42)
            & (coords[:, 2] >= z_min + height * 0.54)
            & (coords[:, 2] <= z_min + height * 0.68)
        )
        l_shoulder = cluster(l_sh_mask, (x_max * 0.30, y_center, z_min + height * 0.60))
        l_clavicle_mid = mathutils.Vector(((spine_pos.x + l_shoulder.x) * 0.5, y_center, neck_pos.z))

        l_elb_mask = (
            (coords[:, 0] >= x_max * 0.45)
            & (coords[:, 0] <= x_max * 0.68)
            & (coords[:, 2] >= z_min + height * 0.52)
            & (coords[:, 2] <= z_min + height * 0.66)
        )
        l_elbow = cluster(l_elb_mask, (x_max * 0.58, y_center, z_min + height * 0.59))

        l_wri_mask = (
            (coords[:, 0] >= x_max * 0.70)
            & (coords[:, 0] <= x_max * 0.88)
            & (coords[:, 2] >= z_min + height * 0.52)
            & (coords[:, 2] <= z_min + height * 0.66)
        )
        l_wrist = cluster(l_wri_mask, (x_max * 0.80, y_center, z_min + height * 0.59))

        l_hand_mask = (
            (coords[:, 0] >= x_max * 0.88)
            & (coords[:, 2] >= z_min + height * 0.52)
            & (coords[:, 2] <= z_min + height * 0.66)
        )
        l_hand = cluster(l_hand_mask, (x_max * 0.95, y_center, z_min + height * 0.59))

        # 3. Right Arm Chain (-X)
        r_sh_mask = (
            (coords[:, 0] <= x_min * 0.20)
            & (coords[:, 0] >= x_min * 0.42)
            & (coords[:, 2] >= z_min + height * 0.54)
            & (coords[:, 2] <= z_min + height * 0.68)
        )
        r_shoulder = cluster(r_sh_mask, (x_min * 0.30, y_center, z_min + height * 0.60))
        r_clavicle_mid = mathutils.Vector(((spine_pos.x + r_shoulder.x) * 0.5, y_center, neck_pos.z))

        r_elb_mask = (
            (coords[:, 0] <= x_min * 0.45)
            & (coords[:, 0] >= x_min * 0.68)
            & (coords[:, 2] >= z_min + height * 0.52)
            & (coords[:, 2] <= z_min + height * 0.66)
        )
        r_elbow = cluster(r_elb_mask, (x_min * 0.58, y_center, z_min + height * 0.59))

        r_wri_mask = (
            (coords[:, 0] <= x_min * 0.70)
            & (coords[:, 0] >= x_min * 0.88)
            & (coords[:, 2] >= z_min + height * 0.52)
            & (coords[:, 2] <= z_min + height * 0.66)
        )
        r_wrist = cluster(r_wri_mask, (x_min * 0.80, y_center, z_min + height * 0.59))

        r_hand_mask = (
            (coords[:, 0] <= x_min * 0.88)
            & (coords[:, 2] >= z_min + height * 0.52)
            & (coords[:, 2] <= z_min + height * 0.66)
        )
        r_hand = cluster(r_hand_mask, (x_min * 0.95, y_center, z_min + height * 0.59))

        # 4. Finger chains generation (Left and Right)
        def generate_fingers(wrist, hand, side_sign=1.0):
            arm_dir = (hand - wrist).normalized() if (hand - wrist).length > 0 else mathutils.Vector((side_sign, 0, 0))
            hand_len = max((hand - wrist).length, 0.08)
            z_up = mathutils.Vector((0, 0, 1))
            f_spread = 0.02 * (1.0 if not self.is_2d else 1.0)

            fingers = {}
            f_configs = [
                ("thumb", -0.025, -0.02, 0.7),
                ("index", 0.015, 0.01, 0.95),
                ("middle", 0.0, 0.0, 1.0),
                ("ring", -0.015, -0.01, 0.92),
                ("pinky", -0.03, -0.02, 0.8),
            ]
            prefix = "l_" if side_sign > 0 else "r_"

            for f_name, z_off, y_off, len_mult in f_configs:
                f_dir = arm_dir.copy()
                base_p = wrist + arm_dir * (hand_len * 0.3) + z_up * z_off + mathutils.Vector((0, y_off, 0))
                seg_len = (hand_len * 0.7 * len_mult) / 3.0
                p1 = base_p + f_dir * (seg_len * 0.33)
                p2 = p1 + f_dir * (seg_len * 0.33)
                p3 = p2 + f_dir * (seg_len * 0.33)
                p_tip = p3 + f_dir * (seg_len * 0.2)

                fingers[f"{prefix}{f_name}_01"] = base_p
                fingers[f"{prefix}{f_name}_02"] = p1
                fingers[f"{prefix}{f_name}_03"] = p2
                fingers[f"{prefix}{f_name}_tip"] = p_tip

            return fingers

        l_fingers = generate_fingers(l_wrist, l_hand, side_sign=1.0)
        r_fingers = generate_fingers(r_wrist, r_hand, side_sign=-1.0)

        # 5. Left Leg (+X)
        l_hip_mask = (
            (coords[:, 0] >= width * 0.05)
            & (coords[:, 0] <= width * 0.30)
            & (coords[:, 2] >= z_min + height * 0.28)
            & (coords[:, 2] <= z_min + height * 0.38)
        )
        l_hip = cluster(l_hip_mask, (width * 0.16, y_center, z_min + height * 0.33))

        l_knee_mask = (
            (coords[:, 0] >= width * 0.05)
            & (coords[:, 0] <= width * 0.30)
            & (coords[:, 2] >= z_min + height * 0.14)
            & (coords[:, 2] <= z_min + height * 0.24)
        )
        l_knee = cluster(l_knee_mask, (width * 0.16, y_center, z_min + height * 0.19))

        l_ank_mask = (
            (coords[:, 0] >= width * 0.05)
            & (coords[:, 0] <= width * 0.30)
            & (coords[:, 2] >= z_min + height * 0.04)
            & (coords[:, 2] <= z_min + height * 0.12)
        )
        l_ankle = cluster(l_ank_mask, (width * 0.17, y_center, z_min + height * 0.07))

        l_foot_mask = (
            (coords[:, 0] >= width * 0.05)
            & (coords[:, 0] <= width * 0.35)
            & (coords[:, 2] <= z_min + height * 0.05)
        )
        l_foot = cluster(l_foot_mask, (width * 0.24, y_center, z_min + 0.02))
        l_toe = mathutils.Vector((width * 0.22, y_center - (depth * 0.15 if not self.is_2d else 0), z_min + 0.02))
        l_toe_tip = mathutils.Vector((width * 0.28, y_center - (depth * 0.25 if not self.is_2d else 0), z_min + 0.01))

        # 6. Right Leg (-X)
        r_hip_mask = (
            (coords[:, 0] <= -width * 0.05)
            & (coords[:, 0] >= -width * 0.30)
            & (coords[:, 2] >= z_min + height * 0.28)
            & (coords[:, 2] <= z_min + height * 0.38)
        )
        r_hip = cluster(r_hip_mask, (-width * 0.16, y_center, z_min + height * 0.33))

        r_knee_mask = (
            (coords[:, 0] <= -width * 0.05)
            & (coords[:, 0] >= -width * 0.30)
            & (coords[:, 2] >= z_min + height * 0.14)
            & (coords[:, 2] <= z_min + height * 0.24)
        )
        r_knee = cluster(r_knee_mask, (-width * 0.16, y_center, z_min + height * 0.19))

        r_ank_mask = (
            (coords[:, 0] <= -width * 0.05)
            & (coords[:, 0] >= -width * 0.30)
            & (coords[:, 2] >= z_min + height * 0.04)
            & (coords[:, 2] <= z_min + height * 0.12)
        )
        r_ankle = cluster(r_ank_mask, (-width * 0.17, y_center, z_min + height * 0.07))

        r_foot_mask = (
            (coords[:, 0] <= -width * 0.05)
            & (coords[:, 0] >= -width * 0.35)
            & (coords[:, 2] <= z_min + height * 0.05)
        )
        r_foot = cluster(r_foot_mask, (-width * 0.24, y_center, z_min + 0.02))
        r_toe = mathutils.Vector((-width * 0.22, y_center - (depth * 0.15 if not self.is_2d else 0), z_min + 0.02))
        r_toe_tip = mathutils.Vector((-width * 0.28, y_center - (depth * 0.25 if not self.is_2d else 0), z_min + 0.01))

        self.landmarks = {
            'root': root_pos,
            'waist': waist_pos,
            'hips': hips_pos,
            'spine': spine_pos,
            'spine1': spine1_pos,
            'spine2': spine2_pos,
            'chest': chest_pos,
            'neck': neck_pos,
            'head': head_pos,
            'head_top': head_top,
            'jaw': jaw_pos,
            'l_eye': l_eye,
            'r_eye': r_eye,
            'l_shoulder': l_shoulder,
            'l_clavicle_mid': l_clavicle_mid,
            'l_elbow': l_elbow,
            'l_wrist': l_wrist,
            'l_hand': l_hand,
            'r_shoulder': r_shoulder,
            'r_clavicle_mid': r_clavicle_mid,
            'r_elbow': r_elbow,
            'r_wrist': r_wrist,
            'r_hand': r_hand,
            'l_hip': l_hip,
            'l_knee': l_knee,
            'l_ankle': l_ankle,
            'l_foot': l_foot,
            'l_toe': l_toe,
            'l_toe_tip': l_toe_tip,
            'r_hip': r_hip,
            'r_knee': r_knee,
            'r_ankle': r_ankle,
            'r_foot': r_foot,
            'r_toe': r_toe,
            'r_toe_tip': r_toe_tip,
            **l_fingers,
            **r_fingers,
        }
        return self.landmarks


# ---------------------------------------------------------------------------
# Universal Armature Builder
# ---------------------------------------------------------------------------

class UniversalArmatureBuilder:
    """Builds an armature and binds skinning according to a rig preset specification."""

    def __init__(self, model_obj, rig_config):
        self.model = model_obj
        self.config = rig_config
        self.is_2d = (self.config.get("type") == "planar_2d")
        self.armature_obj = None
        self.armature_data = None

    def build_and_bind(self):
        extractor = SkeletalLandmarkExtractor(self.model, is_2d=self.is_2d)
        landmarks = extractor.extract()

        bpy.ops.object.select_all(action='DESELECT')
        arm_name = f"Armature_{self.config.get('name', 'Rig')}"
        arm_data = bpy.data.armatures.new(f"{arm_name}_Data")
        arm_data.display_type = 'OCTAHEDRAL'
        arm_obj = bpy.data.objects.new(arm_name, arm_data)

        bpy.context.scene.collection.objects.link(arm_obj)
        bpy.context.view_layer.objects.active = arm_obj
        arm_obj.select_set(True)

        self.armature_obj = arm_obj
        self.armature_data = arm_data

        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm_data.edit_bones

        created_bones = {}

        for bone_spec in self.config.get("bones", []):
            b_name = bone_spec["name"]
            b = eb.new(b_name)

            # Resolve Head position
            head_p = None
            if "head_key" in bone_spec and bone_spec["head_key"] in landmarks:
                head_p = landmarks[bone_spec["head_key"]].copy()
            elif "head_pos" in bone_spec:
                head_p = mathutils.Vector(bone_spec["head_pos"])
            else:
                head_p = mathutils.Vector((0, 0, 0))

            # Resolve Tail position
            tail_p = None
            if "tail_key" in bone_spec and bone_spec["tail_key"] in landmarks:
                tail_p = landmarks[bone_spec["tail_key"]].copy()
            elif "tail_pos" in bone_spec:
                tail_p = mathutils.Vector(bone_spec["tail_pos"])
            elif "tail_offset" in bone_spec:
                tail_p = head_p + mathutils.Vector(bone_spec["tail_offset"])
            else:
                tail_p = head_p + mathutils.Vector((0, 0, 0.1))

            # Ensure minimum bone length
            if (tail_p - head_p).length < 0.001:
                tail_p = head_p + mathutils.Vector((0, 0, 0.05))

            b.head = head_p
            b.tail = tail_p
            created_bones[b_name] = b

        # Setup Parent Relationships
        for bone_spec in self.config.get("bones", []):
            b_name = bone_spec["name"]
            p_name = bone_spec.get("parent")
            if p_name and p_name in created_bones:
                created_bones[b_name].parent = created_bones[p_name]

        # 2D Planar Roll Alignment
        if self.is_2d:
            normal = self.config.get("normal_axis", [0, 1, 0])
            for b in eb:
                b.align_roll(normal)

        bpy.ops.object.mode_set(mode='OBJECT')

        # Configure Pose Mode constraints
        if self.is_2d and self.config.get("lock_out_of_plane", True):
            bpy.ops.object.mode_set(mode='POSE')
            pb = arm_obj.pose.bones
            for b in pb.values():
                b.rotation_mode = 'XYZ'
                b.lock_rotation[0] = True  # X locked
                b.lock_rotation[1] = True  # Y locked
                b.lock_rotation[2] = False  # Z free (2D planar)
                b.lock_location[1] = True  # Depth Y locked
            bpy.ops.object.mode_set(mode='OBJECT')

        # Bind skinning weights
        print(f"[*] Binding mesh '{self.model.name}' to armature '{arm_obj.name}'...")
        bpy.ops.object.select_all(action='DESELECT')
        self.model.select_set(True)
        arm_obj.select_set(True)
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        print(f"[+] Skinning binding completed ({len(self.model.vertex_groups)} vertex groups).")

        return arm_obj


# ---------------------------------------------------------------------------
# Animation Engines
# ---------------------------------------------------------------------------

def apply_shadow_puppet_animation(armature_obj):
    """Bakes the classic 100-frame 2D Planar Chinese Shadow Play performance routine."""
    print("[*] Applying 2D Planar Chinese Shadow Play performance routine (100 frames)...")
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    armature_obj.animation_data_create()
    action = bpy.data.actions.new(name="Action_ShadowPlay_Routine")
    armature_obj.animation_data.action = action

    bpy.ops.object.mode_set(mode='POSE')
    pb = armature_obj.pose.bones

    def kf(name, frame, rz_deg=0.0, tx=0.0, tz=0.0):
        if name in pb:
            b = pb[name]
            b.rotation_euler = (0.0, 0.0, math.radians(rz_deg))
            b.keyframe_insert(data_path="rotation_euler", frame=frame)
            if name in ['waist', 'root']:
                b.location = (tx, 0.0, tz)
                b.keyframe_insert(data_path="location", frame=frame)

    all_bones = list(pb.keys())
    for b in all_bones:
        kf(b, 1, 0.0)

    # Frame 15: Walk Stride 1
    kf('waist', 15, 3.0, tx=0.01, tz=0.02)
    kf('spine', 15, -2.0)
    kf('neck', 15, 4.0)
    kf('head', 15, 3.0)
    kf('shoulder.R', 15, -15.0)
    kf('upper_arm.R', 15, -30.0)
    kf('elbow.R', 15, -45.0)
    kf('wrist.R', 15, -20.0)
    kf('shoulder.L', 15, -10.0)
    kf('upper_arm.L', 15, -25.0)
    kf('elbow.L', 15, 20.0)
    kf('wrist.L', 15, 15.0)
    kf('thigh.L', 15, 25.0)
    kf('knee.L', 15, -35.0)
    kf('ankle.L', 15, 15.0)
    kf('thigh.R', 15, -20.0)
    kf('knee.R', 15, -15.0)
    kf('ankle.R', 15, -10.0)

    # Frame 30: Walk Stride 2
    kf('waist', 30, -3.0, tx=-0.01, tz=0.02)
    kf('spine', 30, 2.0)
    kf('neck', 30, -4.0)
    kf('head', 30, -3.0)
    kf('shoulder.L', 30, 15.0)
    kf('upper_arm.L', 30, 30.0)
    kf('elbow.L', 30, 45.0)
    kf('wrist.L', 30, 20.0)
    kf('shoulder.R', 30, 10.0)
    kf('upper_arm.R', 30, 25.0)
    kf('elbow.R', 30, -20.0)
    kf('wrist.R', 30, -15.0)
    kf('thigh.R', 30, -25.0)
    kf('knee.R', 30, 35.0)
    kf('ankle.R', 30, -15.0)
    kf('thigh.L', 30, 20.0)
    kf('knee.L', 30, 15.0)
    kf('ankle.L', 30, 10.0)

    # Frame 50: Theatrical High-Knee Strike Pose
    kf('waist', 50, -6.0, tx=-0.02, tz=0.04)
    kf('spine', 50, 4.0)
    kf('neck', 50, -8.0)
    kf('head', 50, -6.0)
    kf('shoulder.R', 50, -35.0)
    kf('upper_arm.R', 50, -55.0)
    kf('elbow.R', 50, -60.0)
    kf('wrist.R', 50, -25.0)
    kf('shoulder.L', 50, -20.0)
    kf('upper_arm.L', 50, -40.0)
    kf('elbow.L', 50, 75.0)
    kf('wrist.L', 50, 30.0)
    kf('thigh.R', 50, -55.0)
    kf('knee.R', 50, 80.0)
    kf('ankle.R', 50, -25.0)
    kf('thigh.L', 50, 5.0)
    kf('knee.L', 50, 10.0)
    kf('ankle.L', 50, 0.0)

    # Frame 75: Traditional Bow & Salute
    kf('waist', 75, 0.0, tx=0.0, tz=-0.03)
    kf('spine', 75, 0.0)
    kf('neck', 75, -10.0)
    kf('head', 75, -15.0)
    kf('shoulder.R', 75, -15.0)
    kf('upper_arm.R', 75, -35.0)
    kf('elbow.R', 75, -75.0)
    kf('wrist.R', 75, -30.0)
    kf('shoulder.L', 75, 15.0)
    kf('upper_arm.L', 75, 35.0)
    kf('elbow.L', 75, 75.0)
    kf('wrist.L', 75, 30.0)
    kf('thigh.R', 75, -10.0)
    kf('knee.R', 75, 20.0)
    kf('ankle.R', 75, -10.0)
    kf('thigh.L', 75, 10.0)
    kf('knee.L', 75, -20.0)
    kf('ankle.L', 75, 10.0)

    # Frame 100: Return to Rest Pose
    for b in all_bones:
        kf(b, 100, 0.0)

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 100
    bpy.ops.object.mode_set(mode='OBJECT')
    print("[+] Shadow Play routine animation created.")


def apply_humanoid_walk_to_run_animation(armature_obj):
    """Bakes a realistic 100-frame 3D Humanoid Walk-to-Run progression routine.

    Progression Stages:
      - Frames 1-10:   Ready Stance -> Smooth transition into first walk stride
      - Frames 11-45:  Natural Ground Walk Cycle (upright posture, rhythmic arm swing, heel-strikes)
      - Frames 46-70:  Acceleration & Jogging Phase (forward chest pitch, bent elbows, flight bounce)
      - Frames 71-92:  Full Athletic Sprint Running (deep thigh drive, high knee lift, runner's arm pump, toe push-off)
      - Frames 93-100: Controlled Deceleration & return to ready stance
    """
    print("[*] Applying 3D Humanoid Walk-to-Run performance routine (100 frames)...")
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    armature_obj.animation_data_create()
    action = bpy.data.actions.new(name="Action_Humanoid_WalkToRun")
    armature_obj.animation_data.action = action

    bpy.ops.object.mode_set(mode='POSE')
    pb = armature_obj.pose.bones

    def kf3d(name, frame, rx=0.0, ry=0.0, rz=0.0, tx=0.0, ty=0.0, tz=0.0):
        if name in pb:
            b = pb[name]
            b.rotation_mode = 'XYZ'
            b.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
            b.keyframe_insert(data_path="rotation_euler", frame=frame)
            if name in ['root', 'hips']:
                b.location = (tx, ty, tz)
                b.keyframe_insert(data_path="location", frame=frame)

    total_frames = 100

    def get_alpha(f):
        if f <= 10:
            return (f - 1) / 9.0 * 0.18
        elif f <= 45:
            return 0.18 + (f - 10) / 35.0 * 0.27   # 0.18 -> 0.45 (steady walk)
        elif f <= 70:
            return 0.45 + (f - 45) / 25.0 * 0.40   # 0.45 -> 0.85 (acceleration to jog/run)
        elif f <= 92:
            return 0.85 + (f - 70) / 22.0 * 0.15   # 0.85 -> 1.00 (peak sprint)
        else:
            decay = (f - 92) / 8.0
            return 1.0 * (1.0 - decay) + 0.05 * decay

    # Integrate frequency to build continuous phase phi
    current_phi = 0.0
    phi_table = {}
    alpha_table = {}
    for f in range(1, total_frames + 1):
        a = get_alpha(f)
        alpha_table[f] = a
        period = 22.0 * (1.0 - a) + 10.0 * a
        omega = (2.0 * math.pi) / period
        current_phi += omega
        phi_table[f] = current_phi

    # Keyframe every frame for smooth motion
    for f in range(1, total_frames + 1):
        a = alpha_table[f]
        phi = phi_table[f]

        # 1. Pelvis / Hips
        hip_tx = math.sin(phi) * (0.022 * (1.0 - a) + 0.006 * a)
        bounce = math.sin(2.0 * phi - math.pi * 0.5)
        hip_tz = bounce * (0.015 * (1.0 - a) + 0.045 * a) - 0.035 * a
        hip_rx = 2.0 * (1.0 - a) + 9.0 * a + math.sin(2.0 * phi) * 2.0 * a
        hip_rz = -math.cos(phi) * (4.0 * (1.0 - a) + 7.5 * a)
        hip_ry = math.sin(phi) * (2.5 * (1.0 - a) + 4.0 * a)

        kf3d('hips', f, rx=hip_rx, ry=hip_ry, rz=hip_rz, tx=hip_tx, ty=0.0, tz=hip_tz)

        # 2. Spine, Chest, Head
        spine_rx = 1.0 * (1.0 - a) + 4.0 * a
        chest_rx = 1.5 * (1.0 - a) + 5.5 * a + math.sin(2.0 * phi) * 1.5 * a
        chest_twist = math.cos(phi) * (3.5 * (1.0 - a) + 7.5 * a)

        kf3d('spine', f, rx=spine_rx, ry=0.0, rz=chest_twist * 0.3)
        kf3d('spine1', f, rx=spine_rx, ry=0.0, rz=chest_twist * 0.5)
        kf3d('spine2', f, rx=spine_rx, ry=0.0, rz=chest_twist * 0.7)
        kf3d('chest', f, rx=chest_rx, ry=0.0, rz=chest_twist)

        head_rx = -(2.5 * (1.0 - a) + 13.5 * a) + math.sin(2.0 * phi) * 1.2 * a
        head_rz = -chest_twist * 0.65
        kf3d('neck', f, rx=-(1.0 * (1.0 - a) + 3.0 * a), ry=0.0, rz=0.0)
        kf3d('head', f, rx=head_rx, ry=0.0, rz=head_rz)

        # 3. Lower Limbs (Legs, Knees, Feet, Toes)
        for side, side_phi, sign in [('L', phi, 1.0), ('R', phi + math.pi, -1.0)]:
            s = math.sin(side_phi)
            c = math.cos(side_phi)

            if s > 0:
                thigh_fwd_amp = 24.0 * (1.0 - a) + 52.0 * a
                thigh_rx = -thigh_fwd_amp * (s ** 0.85)
            else:
                thigh_back_amp = 18.0 * (1.0 - a) + 28.0 * a
                thigh_rx = thigh_back_amp * ((-s) ** 0.85)

            thigh_rz = sign * (1.5 * (1.0 - a) + 3.0 * a * s)
            kf3d(f'thigh.{side}', f, rx=thigh_rx, ry=0.0, rz=thigh_rz)

            # Knee flexion (swing fold vs stance support)
            swing_knee_phase = math.sin(side_phi - 0.35)
            if swing_knee_phase > 0:
                knee_swing_max = 45.0 * (1.0 - a) + 95.0 * a
                calf_rx = knee_swing_max * (swing_knee_phase ** 1.3) + (5.0 * (1.0 - a) + 10.0 * a)
            else:
                calf_rx = (5.0 * (1.0 - a) + 12.0 * a) * max(0.0, -s)

            kf3d(f'calf.{side}', f, rx=calf_rx, ry=0.0, rz=0.0)

            # Ankle / Foot
            if c < 0 and s < 0.2:
                foot_rx = (18.0 * (1.0 - a) + 38.0 * a) * max(0.0, -c)
            elif s > 0:
                foot_rx = -(8.0 * (1.0 - a) + 14.0 * a) * max(0.0, s)
            else:
                foot_rx = 0.0

            kf3d(f'foot.{side}', f, rx=foot_rx, ry=0.0, rz=0.0)

            # Toe roll on push-off
            toe_rx = (15.0 * (1.0 - a) + 32.0 * a) * (max(0.0, -c) ** 2.0)
            kf3d(f'toe.{side}', f, rx=toe_rx, ry=0.0, rz=0.0)

        # 4. Upper Limbs (Clavicles, Arms, Elbows, Hands, Fingers)
        # Note on T-pose models: In rest pose, arms point horizontally along +/- X.
        # 1. Base lowering: rotating upper_arm around local X by -78 deg places the arm straight DOWN vertically along -Z.
        # 2. Front-Back wave swing: once lowered, rotating around local Y swings the arm FORWARD and BACKWARD along the Y-axis.
        # 3. Forearm flexion: rotating forearm around local Y flexes the elbow FORWARD in front of the torso.
        for side, arm_phi, sign in [('L', phi + math.pi, 1.0), ('R', phi, -1.0)]:
            s_arm = math.sin(arm_phi)

            # Shoulder / Clavicle slight pump
            clav_rx = -2.0 * a * s_arm
            kf3d(f'clavicle.{side}', f, rx=clav_rx, ry=0.0, rz=-sign * (1.5 * a))

            # Upper Arm:
            # 1. Base downward vertical stance (-78 deg rx)
            rx_arm = -78.0
            
            # 2. Front-Back wave swing along world Y via local ry:
            arm_fwd_amp = 22.0 * (1.0 - a) + 48.0 * a
            arm_back_amp = 16.0 * (1.0 - a) + 32.0 * a
            if s_arm > 0:
                ry_arm = -sign * (arm_fwd_amp * s_arm)
            else:
                ry_arm = -sign * (arm_back_amp * s_arm)

            kf3d(f'upper_arm.{side}', f, rx=rx_arm, ry=ry_arm, rz=0.0)

            # Forearm Elbow Flexion:
            # Flexes forward at elbow via local ry (-sign on Left, +sign on Right)
            # Walking: relaxed ~15-25 deg bend; Running: athletic ~45-80 deg power angle
            base_elbow = 15.0 * (1.0 - a) + 45.0 * a
            dynamic_elbow = (12.0 * (1.0 - a) + 35.0 * a) * max(0.0, s_arm)
            forearm_ry = -sign * (base_elbow + dynamic_elbow)
            kf3d(f'forearm.{side}', f, rx=0.0, ry=forearm_ry, rz=0.0)

            # Wrist / Hand: flexes in sync with arm drive
            hand_ry = -sign * ((6.0 * (1.0 - a) + 14.0 * a) * s_arm)
            kf3d(f'hand.{side}', f, rx=0.0, ry=hand_ry, rz=0.0)

            # Fingers: curl forward from open hand to cupped runner's fist
            finger_curl = -sign * (15.0 * (1.0 - a) + 35.0 * a)
            for finger_name in ['thumb', 'index', 'middle', 'ring', 'pinky']:
                for seg in ['01', '02', '03']:
                    kf3d(f'{finger_name}.{seg}.{side}', f, rx=0.0, ry=0.0, rz=finger_curl)

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = total_frames
    bpy.ops.object.mode_set(mode='OBJECT')
    print("[+] Humanoid walk-to-run progression animation created successfully.")


# Alias for backward compatibility
apply_humanoid_inspection_animation = apply_humanoid_walk_to_run_animation




# ---------------------------------------------------------------------------
# Import / Export Utilities
# ---------------------------------------------------------------------------

def import_mesh(file_path):
    """Imports 3D model according to file extension."""
    print(f"[*] Importing mesh from '{file_path}'...")
    ext = os.path.splitext(file_path)[1].lower()

    bpy.ops.wm.read_factory_settings(use_empty=True)

    if ext in ['.usdz', '.usda', '.usdc']:
        bpy.ops.wm.usd_import(filepath=file_path)
    elif ext in ['.glb', '.gltf']:
        bpy.ops.import_scene.gltf(filepath=file_path)
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=file_path)
    elif ext == '.obj':
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=file_path)
        else:
            bpy.ops.import_scene.obj(filepath=file_path)
    else:
        raise ValueError(f"Unsupported model format '{ext}'.")

    mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
    if not mesh_objs:
        raise ValueError(f"No mesh objects found in {file_path}")

    # If multiple meshes exist, join them into a single unified character mesh
    if len(mesh_objs) > 1:
        print(f"[*] Joining {len(mesh_objs)} mesh parts into unified character mesh...")
        bpy.ops.object.select_all(action='DESELECT')
        for o in mesh_objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = mesh_objs[0]
        bpy.ops.object.join()
        primary_mesh = bpy.context.view_layer.objects.active
    else:
        primary_mesh = mesh_objs[0]

    return primary_mesh


def setup_camera_and_lighting():
    if not bpy.context.scene.camera:
        cam_data = bpy.data.cameras.new('PreviewCamera')
        cam_obj = bpy.data.objects.new('PreviewCamera', cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj
        cam_obj.location = (0, -3.4, 1.05)
        cam_obj.rotation_euler = (math.radians(90), 0, 0)

    if not any(o.type == 'LIGHT' for o in bpy.data.objects):
        light_data = bpy.data.lights.new(name='KeyLight', type='SUN')
        light_obj = bpy.data.objects.new(name='KeyLight', object_data=light_data)
        bpy.context.scene.collection.objects.link(light_obj)
        light_obj.location = (2, -3, 3)


def export_file(filepath, fmt):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    setup_camera_and_lighting()
    print(f"[*] Exporting to '{filepath}' ({fmt.upper()})...")

    if fmt == 'blend':
        bpy.ops.wm.save_as_mainfile(filepath=filepath)
    elif fmt == 'usdz':
        bpy.ops.wm.usd_export(
            filepath=filepath,
            export_armatures=True,
            only_deform_bones=True,
            export_materials=True,
            export_textures=True,
            export_animation=True
        )
    elif fmt == 'glb':
        gltf_kwargs = {
            'filepath': filepath,
            'export_format': 'GLB',
            'export_skins': True,
            'export_all_influences': True,
            'export_animations': True,
            'export_def_bones': True
        }
        # Avoid exporting unrelated unused actions
        props = bpy.ops.export_scene.gltf.get_rna_type().properties
        if 'export_animation_mode' in props:
            gltf_kwargs['export_animation_mode'] = 'ACTIVE_ACTIONS'
        bpy.ops.export_scene.gltf(**gltf_kwargs)
    elif fmt == 'fbx':
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            use_armature_deform_only=True,
            add_leaf_bones=False,
            bake_anim=True
        )
    print(f"[+] Successfully exported {filepath}")


def render_poses_grid(output_image_path):
    print(f"[*] Rendering contact sheet grid to '{output_image_path}'...")
    setup_camera_and_lighting()
    bpy.context.scene.render.resolution_x = 600
    bpy.context.scene.render.resolution_y = 600

    temp_frames = []
    for f in [10, 35, 65, 85]:
        bpy.context.scene.frame_set(f)
        temp_path = f"/tmp/rig_pose_f{f:03d}.png"
        bpy.context.scene.render.filepath = temp_path
        bpy.ops.render.render(write_still=True)
        temp_frames.append(temp_path)

    # Attempt 1: ffmpeg hstack filter
    ffmpeg_bin = "/opt/homebrew/bin/ffmpeg" if os.path.exists("/opt/homebrew/bin/ffmpeg") else "ffmpeg"
    try:
        inputs = []
        for p in temp_frames:
            inputs.extend(["-i", p])
        filter_str = "".join([f"[{i}:v]" for i in range(len(temp_frames))]) + f"hstack=inputs={len(temp_frames)}[out]"
        cmd = [ffmpeg_bin, "-y"] + inputs + ["-filter_complex", filter_str, "-map", "[out]", "-update", "1", output_image_path]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[+] Contact sheet saved: {output_image_path}")
        return
    except Exception as e_ffmpeg:
        pass

    # Attempt 2: PIL
    try:
        from PIL import Image
        imgs = [Image.open(p) for p in temp_frames]
        w, h = imgs[0].size
        grid = Image.new('RGBA', (w * len(imgs), h), (18, 18, 18, 255))
        for i, img in enumerate(imgs):
            grid.paste(img, (i * w, 0))
        grid.save(output_image_path)
        print(f"[+] Contact sheet saved: {output_image_path}")
        return
    except Exception as e_pil:
        pass

    # Fallback: Single frame
    import shutil
    if temp_frames:
        shutil.copy(temp_frames[0], output_image_path)
        print(f"[+] Rendered single pose preview: {output_image_path}")


def render_animation_video(output_mp4_path):
    print(f"[*] Rendering full 100-frame animation video to '{output_mp4_path}'...")
    setup_camera_and_lighting()
    bpy.context.scene.render.resolution_x = 640
    bpy.context.scene.render.resolution_y = 640
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.context.scene.render.filepath = '/tmp/rig_anim_frame_'
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 100

    bpy.ops.render.render(animation=True)

    ffmpeg_bin = "/opt/homebrew/bin/ffmpeg" if os.path.exists("/opt/homebrew/bin/ffmpeg") else "ffmpeg"
    cmd = [
        ffmpeg_bin, "-y",
        "-framerate", "25",
        "-i", "/tmp/rig_anim_frame_%04d.png",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        output_mp4_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[+] Video rendered: {output_mp4_path}")
    except Exception as e:
        print(f"[-] Video ffmpeg notice: {e}")


# ---------------------------------------------------------------------------
# Main Engine Entry Point
# ---------------------------------------------------------------------------

def main():
    argv = sys.argv
    args_to_parse = argv[argv.index("--") + 1:] if "--" in argv else []

    parser = argparse.ArgumentParser(description="Universal Rig Binder Engine")
    parser.add_argument("--input", required=True, help="Input model path")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    parser.add_argument("--name", default="model", help="Base name for outputs")
    parser.add_argument("--rig-config", required=True, help="Path to rig preset/custom JSON configuration")
    parser.add_argument("--formats", default="usdz,glb,blend", help="Comma-separated export formats")
    parser.add_argument("--no-anim", action="store_true", help="Skip animation routine")
    parser.add_argument("--no-preview", action="store_true", help="Skip visual previews")
    args = parser.parse_args(args_to_parse)

    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    with open(args.rig_config, 'r', encoding='utf-8') as f:
        rig_config = json.load(f)

    formats = [fmt.strip().lower() for fmt in args.formats.split(",") if fmt.strip()]

    # 1. Pure Rigged Model (Rest Pose)
    print("=" * 60)
    print(f"STEP 1: Generating Pure Rigged Model '{args.name}_rigged' [{rig_config.get('name')}]")
    print("=" * 60)
    mesh_static = import_mesh(args.input)
    builder_static = UniversalArmatureBuilder(mesh_static, rig_config)
    builder_static.build_and_bind()

    for fmt in formats:
        export_file(os.path.join(out_dir, f"{args.name}_rigged.{fmt}"), fmt)

    # 2. Animated Model
    if not args.no_anim:
        print("\n" + "=" * 60)
        print(f"STEP 2: Generating Animated Model '{args.name}_animated' [{rig_config.get('name')}]")
        print("=" * 60)
        mesh_anim = import_mesh(args.input)
        builder_anim = UniversalArmatureBuilder(mesh_anim, rig_config)
        arm_anim = builder_anim.build_and_bind()

        if rig_config.get("type") == "planar_2d":
            apply_shadow_puppet_animation(arm_anim)
        else:
            apply_humanoid_walk_to_run_animation(arm_anim)

        for fmt in formats:
            export_file(os.path.join(out_dir, f"{args.name}_animated.{fmt}"), fmt)

        # 3. Visual Previews
        if not args.no_preview:
            print("\n" + "=" * 60)
            print("STEP 3: Rendering Visual Previews (Contact Sheet & MP4)")
            print("=" * 60)
            render_poses_grid(os.path.join(out_dir, f"{args.name}_preview_grid.png"))
            render_animation_video(os.path.join(out_dir, f"{args.name}_preview_anim.mp4"))

    print("\n" + "=" * 60)
    print("  [SUCCESS] UNIVERSAL RIG BINDING PIPELINE FINISHED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
