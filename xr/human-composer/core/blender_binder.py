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


def isolate_and_rename_textures(body_dir, hair_dir):
    """
    Ensure body and hair textures do not collide with the same name (e.g. shaded.png).
    Returns paths to body texture and hair texture if found.
    """
    body_tex = None
    hair_tex = None

    # Check body texture
    body_tex_dir = os.path.join(body_dir, "textures")
    if os.path.exists(body_tex_dir):
        for fname in os.listdir(body_tex_dir):
            if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                src = os.path.join(body_tex_dir, fname)
                dst = os.path.join(body_tex_dir, f"body_{fname}")
                if os.path.exists(src) and not fname.startswith("body_"):
                    os.rename(src, dst)
                    body_tex = dst
                elif fname.startswith("body_"):
                    body_tex = src
                break

    # Check hair texture
    hair_tex_dir = os.path.join(hair_dir, "textures")
    if os.path.exists(hair_tex_dir):
        for fname in os.listdir(hair_tex_dir):
            if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                src = os.path.join(hair_tex_dir, fname)
                dst = os.path.join(hair_tex_dir, f"hair_{fname}")
                if os.path.exists(src) and not fname.startswith("hair_"):
                    os.rename(src, dst)
                    hair_tex = dst
                elif fname.startswith("hair_"):
                    hair_tex = src
                break

    return body_tex, hair_tex


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
    hair_usdz = config["hair"]
    output_usdz = config["output_usdz"]
    preview_image_path = config.get("preview_image_path")
    preview_video_path = config.get("preview_video_path")
    intermediate_dir = config.get("intermediate_dir")
    render_intermediate = config.get("render_intermediate", False)
    ref_data = config.get("ref_data", {})

    temp_root = tempfile.mkdtemp(prefix="human_composer_")
    body_extract_dir = os.path.join(temp_root, "body_unpacked")
    hair_extract_dir = os.path.join(temp_root, "hair_unpacked")

    try:
        print("[Blender Binder] Unpacking USDZ archives...")
        safe_extract_usdz(body_usdz, body_extract_dir)
        safe_extract_usdz(hair_usdz, hair_extract_dir)

        body_tex, hair_tex = isolate_and_rename_textures(body_extract_dir, hair_extract_dir)
        print(f"[Blender Binder] Body texture: {body_tex}")
        print(f"[Blender Binder] Hair texture: {hair_tex}")

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

        existing_objs = set(bpy.context.scene.objects)

        # 2. Import Hair USDZ
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

        # Detect head bone name from armature or vertex groups
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
            cam_obj = bpy.data.objects.new("PreviewCamera", cam_data)
            bpy.context.scene.collection.objects.link(cam_obj)
            bpy.context.scene.camera = cam_obj

        # 9. Render Static Preview Image
        if preview_image_path:
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

        # 10. Render Intermediate Multi-Angle Images
        if render_intermediate and intermediate_dir:
            print(f"[Blender Binder] Rendering intermediate multi-angle images to {intermediate_dir}...")
            os.makedirs(intermediate_dir, exist_ok=True)
            cam_views = {
                "front": ((0, -5.0, 0.95), (math.radians(90), 0, 0)),
                "left": ((5.0, 0, 0.95), (math.radians(90), 0, math.radians(90))),
                "right": ((-5.0, 0, 0.95), (math.radians(90), 0, math.radians(-90))),
                "back": ((0, 5.0, 0.95), (math.radians(90), 0, math.radians(180))),
            }
            bpy.context.scene.render.resolution_x = 1024
            bpy.context.scene.render.resolution_y = 1024
            bpy.context.scene.render.image_settings.file_format = 'PNG'

            for view_name, (cam_loc, cam_rot) in cam_views.items():
                cam_obj.location = cam_loc
                cam_obj.rotation_euler = cam_rot
                img_path = os.path.join(intermediate_dir, f"render_{view_name}.png")
                bpy.context.scene.render.filepath = img_path
                bpy.ops.render.render(write_still=True)

        # 11. Render Sequenced Preview Animation (MP4)
        if preview_video_path:
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
            head_z_level = head_coords[:, 2].mean() if 'head_coords' in locals() else 1.65
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
