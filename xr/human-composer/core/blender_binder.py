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

        head_vg = body_mesh.vertex_groups.get("mixamorig_Head")
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
            target_top = body_z_min + (float(ref_front["char_y_max"] - ref_front["head_y_min"])) * m_per_px + 0.02
        else:
            m_per_px = body_height / 3950.0
            target_width = head_width * 1.14
            target_top = head_z_max + 0.04

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
            target_depth = target_width * (head_depth / head_width) * 1.06
            target_y_center = head_y_center + 0.04

        scale_x = (target_width / hair_width) * 1.025
        scale_y = (target_depth / hair_depth) * 1.04
        scale_z = scale_x * 1.02

        target_y_center = max(target_y_center, head_y_center + 0.038)

        loc_x = head_x_center - (hair_x_center * scale_x)
        loc_y = target_y_center - (hair_y_center * scale_y)
        loc_z = target_top - (hair_z_max * scale_z)

        # Crown coverage check
        scaled_hair_top = hair_z_max * scale_z + loc_z
        if scaled_hair_top < head_z_max + 0.03:
            loc_z += (head_z_max + 0.035 - scaled_hair_top)

        # Rear skull coverage check
        scaled_hair_back = hair_y_max * scale_y + loc_y
        if scaled_hair_back < head_y_max + 0.02:
            loc_y += (head_y_max + 0.025 - scaled_hair_back)

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

        head_bone_name = "mixamorig_Head"
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

        # Setup Camera & Lighting for Previews
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

        # 11. Render 360° Turntable Animation (MP4)
        if preview_video_path:
            print(f"[Blender Binder] Rendering preview animation to {preview_video_path}...")
            os.makedirs(os.path.dirname(os.path.abspath(preview_video_path)), exist_ok=True)

            target_rot_obj = root_empty if root_empty else armature
            target_rot_obj.rotation_mode = 'XYZ'
            target_rot_obj.animation_data_clear()

            total_frames = 48
            bpy.context.scene.frame_start = 1
            bpy.context.scene.frame_end = total_frames
            bpy.context.scene.render.fps = 24

            # Keyframe 360 rotation with linear interpolation
            target_rot_obj.rotation_euler.z = 0.0
            target_rot_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=1)

            # Continuous loop: frame total_frames reaches 2pi * (frames - 1) / frames
            target_rot_obj.rotation_euler.z = 2.0 * math.pi * (total_frames - 1) / total_frames
            target_rot_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=total_frames)

            # Make interpolation linear
            if target_rot_obj.animation_data and target_rot_obj.animation_data.action:
                for fcurve in target_rot_obj.animation_data.action.fcurves:
                    for kf in fcurve.keyframe_points:
                        kf.interpolation = 'LINEAR'

            # Camera pointing front
            cam_obj.location = (0, -5.0, 0.95)
            cam_obj.rotation_euler = (math.radians(90), 0, 0)

            bpy.context.scene.render.resolution_x = 512
            bpy.context.scene.render.resolution_y = 512
            bpy.context.scene.render.image_settings.file_format = 'FFMPEG'
            bpy.context.scene.render.ffmpeg.format = 'MPEG4'
            bpy.context.scene.render.ffmpeg.codec = 'H264'
            bpy.context.scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
            bpy.context.scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
            bpy.context.scene.render.filepath = preview_video_path

            bpy.ops.render.render(animation=True)
            print(f"[Blender Binder] Saved preview animation: {preview_video_path}")

    finally:
        if os.path.exists(temp_root):
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
