#!/usr/bin/env python3
"""
Model Inspector module for Human Composer.
Extracts 3D model geometry, bounding boxes, vertices, textures, materials,
and skeletal armature information using Blender.
"""

import sys
import os
import json
import zipfile
import subprocess
import tempfile
import numpy as np


def extract_zip_info(file_path):
    """Extract archive-level metadata if the file is a USDZ archive."""
    if not zipfile.is_zipfile(file_path):
        return None

    archive_info = {
        "is_usdz": True,
        "files": [],
        "textures": [],
        "usd_scene": None,
        "total_uncompressed_size": 0,
    }

    with zipfile.ZipFile(file_path, "r") as z:
        for info in z.infolist():
            archive_info["total_uncompressed_size"] += info.file_size
            archive_info["files"].append({
                "filename": info.filename,
                "file_size": info.file_size,
                "compress_size": info.compress_size,
            })
            ext = os.path.splitext(info.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".tga", ".hdr", ".exr"]:
                archive_info["textures"].append({
                    "path": info.filename,
                    "size_bytes": info.file_size
                })
            elif ext in [".usdc", ".usd", ".usda"]:
                archive_info["usd_scene"] = info.filename

    return archive_info


def blender_inspect_worker(input_path, output_json_path):
    """
    Code executed directly inside Blender to parse scene data.
    Note: imports bpy inside the function when executed by Blender.
    """
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(input_path)[1].lower()

    if ext in [".usdz", ".usdc", ".usd", ".usda"]:
        bpy.ops.wm.usd_import(filepath=input_path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=input_path)
    elif ext in [".gltf", ".glb"]:
        bpy.ops.import_scene.gltf(filepath=input_path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=input_path)
    else:
        # Try USD import by default
        bpy.ops.wm.usd_import(filepath=input_path)

    result = {
        "meshes": [],
        "armatures": [],
        "animations": [],
        "materials": [],
        "overall_bounds": None
    }

    # Inspect Animations / Actions
    for act in bpy.data.actions:
        result["animations"].append({
            "name": act.name,
            "frame_start": float(act.frame_range[0]),
            "frame_end": float(act.frame_range[1]),
            "duration_frames": int(round(act.frame_range[1] - act.frame_range[0] + 1)),
        })

    all_world_coords = []

    # 1. Inspect Meshes
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            mesh = obj.data
            if not mesh.vertices:
                continue

            world_coords = np.array([obj.matrix_world @ v.co for v in mesh.vertices])
            all_world_coords.append(world_coords)

            bbox_min = world_coords.min(axis=0).tolist()
            bbox_max = world_coords.max(axis=0).tolist()
            dims = (world_coords.max(axis=0) - world_coords.min(axis=0)).tolist()
            center = ((world_coords.min(axis=0) + world_coords.max(axis=0)) / 2.0).tolist()

            # Local bounding box
            local_coords = np.array([v.co for v in mesh.vertices])
            local_min = local_coords.min(axis=0).tolist()
            local_max = local_coords.max(axis=0).tolist()
            local_dims = (local_coords.max(axis=0) - local_coords.min(axis=0)).tolist()

            # Materials on this mesh
            mesh_materials = []
            for mat in mesh.materials:
                if mat:
                    mesh_materials.append(mat.name)

            # Vertex groups
            vgs = [vg.name for vg in obj.vertex_groups]

            # Modifiers (e.g. Armature modifier)
            modifiers = []
            for mod in obj.modifiers:
                mod_info = {"name": mod.name, "type": mod.type}
                if mod.type == "ARMATURE" and mod.object:
                    mod_info["target_armature"] = mod.object.name
                modifiers.append(mod_info)

            result["meshes"].append({
                "name": obj.name,
                "parent": obj.parent.name if obj.parent else None,
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "bbox_min": bbox_min,
                "bbox_max": bbox_max,
                "dimensions": dims,
                "center": center,
                "local_bbox_min": local_min,
                "local_bbox_max": local_max,
                "local_dimensions": local_dims,
                "materials": mesh_materials,
                "vertex_groups_count": len(vgs),
                "vertex_groups": vgs,
                "modifiers": modifiers,
            })

    # 2. Inspect Armatures (Skeleton)
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            arm = obj.data
            bones = [b.name for b in arm.bones]
            
            # Detect key human bones
            key_bone_indicators = ["head", "neck", "spine", "hips", "arm", "hand", "leg", "foot"]
            key_bones = [b for b in bones if any(k in b.lower() for k in key_bone_indicators)]

            result["armatures"].append({
                "name": obj.name,
                "bone_count": len(bones),
                "bones": bones,
                "key_bones": key_bones[:15],
                "has_head_bone": any("head" in b.lower() for b in bones),
            })

    # 3. Inspect Materials & Textures
    for mat in bpy.data.materials:
        textures = []
        if mat.use_nodes and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    textures.append({
                        "image_name": node.image.name,
                        "filepath": node.image.filepath,
                        "resolution": list(node.image.size),
                    })

        result["materials"].append({
            "name": mat.name,
            "textures": textures
        })

    # 4. Compute Overall Model Bounds
    if all_world_coords:
        total_coords = np.vstack(all_world_coords)
        result["overall_bounds"] = {
            "bbox_min": total_coords.min(axis=0).tolist(),
            "bbox_max": total_coords.max(axis=0).tolist(),
            "dimensions": (total_coords.max(axis=0) - total_coords.min(axis=0)).tolist(),
            "center": ((total_coords.min(axis=0) + total_coords.max(axis=0)) / 2.0).tolist(),
            "total_vertices": sum(m["vertices"] for m in result["meshes"]),
            "total_polygons": sum(m["polygons"] for m in result["meshes"]),
        }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


def run_blender_inspector(blender_bin, model_path):
    """Run headless Blender script to inspect model."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        output_json = f.name

    # Create temporary Blender script
    script_content = f"""
import sys
import os
sys.path.insert(0, {repr(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))})
from core.model_inspector import blender_inspect_worker
blender_inspect_worker({repr(os.path.abspath(model_path))}, {repr(output_json)})
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as sf:
        script_path = sf.name
        sf.write(script_content)

    try:
        cmd = [blender_bin, "-b", "-P", script_path]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        with open(output_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)
        if os.path.exists(output_json):
            os.remove(output_json)


def inspect_model(model_path, blender_bin):
    """Primary function to extract full 3D model metadata."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    model_path = os.path.abspath(model_path)
    file_size = os.path.getsize(model_path)

    # Basic file metadata
    meta = {
        "file_path": model_path,
        "file_name": os.path.basename(model_path),
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "archive_info": extract_zip_info(model_path),
    }

    # Blender scene inspection
    blender_data = run_blender_inspector(blender_bin, model_path)
    meta.update(blender_data)

    # Cross-reference textures between materials and meshes
    mat_tex_map = {m["name"]: m["textures"] for m in meta.get("materials", [])}
    for mesh in meta.get("meshes", []):
        mesh_textures = []
        for mat_name in mesh["materials"]:
            if mat_name in mat_tex_map:
                mesh_textures.extend(mat_tex_map[mat_name])
        mesh["textures"] = mesh_textures

    # Determine skeletal information
    armatures = meta.get("armatures", [])
    has_skeleton = len(armatures) > 0
    meta["has_skeleton"] = has_skeleton

    return meta


def format_model_info(data, selected_part=None):
    """Format extracted model metadata into a clean, human-readable report."""
    lines = []
    lines.append("=" * 78)
    lines.append(f"  3D Model Information: {data['file_name']}")
    lines.append("=" * 78)

    # 1. File Summary
    lines.append("\n[File Summary]")
    lines.append(f"  • Path             : {data['file_path']}")
    lines.append(f"  • File Size        : {data['file_size_mb']} MB ({data['file_size_bytes']:,} bytes)")
    arch = data.get("archive_info")
    if arch:
        lines.append(f"  • Format           : USDZ Package")
        if arch.get("usd_scene"):
            lines.append(f"  • Embedded Scene   : {arch['usd_scene']}")
        if arch.get("textures"):
            tex_names = [f"{t['path']} ({t['size_bytes']/1024:.1f} KB)" for t in arch["textures"]]
            lines.append(f"  • Packaged Textures: {', '.join(tex_names)}")
    else:
        ext = os.path.splitext(data["file_name"])[1].upper()
        lines.append(f"  • Format           : {ext} Model")

    # 2. Skeleton / Rigging
    lines.append("\n[Skeleton / Rigging]")
    armatures = data.get("armatures", [])
    if armatures:
        lines.append(f"  • Has Skeleton     : YES ({len(armatures)} Armature{'s' if len(armatures)>1 else ''} found)")
        for arm in armatures:
            lines.append(f"    - Armature Name  : {arm['name']}")
            lines.append(f"    - Total Bones    : {arm['bone_count']}")
            if arm.get("has_head_bone"):
                lines.append(f"    - Head Bone      : Detected (mixamorig_Head / Head)")
            if arm.get("key_bones"):
                lines.append(f"    - Key Bones      : {', '.join(arm['key_bones'][:8])}...")
    else:
        lines.append("  • Has Skeleton     : NO (Static mesh, no armature detected)")

    # 3. Animations / Motion Clips
    lines.append("\n[Animations / Motion Clips]")
    anims = data.get("animations", [])
    if anims:
        lines.append(f"  • Has Animation    : YES ({len(anims)} clip{'s' if len(anims)>1 else ''} found)")
        for a in anims:
            lines.append(f"    - Clip Name      : \"{a['name']}\"")
            lines.append(f"      Frame Range    : Frame {int(a['frame_start'])} to {int(a['frame_end'])} ({a['duration_frames']} frames)")
    else:
        lines.append("  • Has Animation    : NO (No animation actions/tracks found; static/T-pose)")

    # 4. Meshes / Parts
    meshes = data.get("meshes", [])
    lines.append(f"\n[Mesh Parts] (Total Meshes: {len(meshes)})")

    # Filter by selected_part if requested
    target_meshes = meshes
    if selected_part:
        part_query = selected_part.strip().lower()

        # Check if user asked for skeleton / armature specifically
        if part_query in ["skeleton", "armature", "bones", "rig"]:
            lines.append(f"\n[Filtered Component: Skeleton / Armature]")
            if armatures:
                for arm in armatures:
                    lines.append(f"  • Name         : {arm['name']}")
                    lines.append(f"  • Total Bones  : {arm['bone_count']}")
                    lines.append(f"  • Head Bone    : {'Detected (mixamorig_Head / Head)' if arm.get('has_head_bone') else 'Not detected'}")
                    lines.append(f"  • All Bones    : {', '.join(arm['bones'])}")
            else:
                lines.append("  • Has Skeleton : NO (No armature detected)")
            lines.append("=" * 78)
            return "\n".join(lines)

        # Check if user asked for animation / motion clips specifically
        if part_query in ["anim", "animation", "animations", "motion", "action", "actions"]:
            lines.append(f"\n[Filtered Component: Animations / Motion Clips]")
            if anims:
                lines.append(f"  • Total Clips  : {len(anims)}")
                for a in anims:
                    lines.append(f"  • Clip Name    : \"{a['name']}\"")
                    lines.append(f"    Frame Range  : Frame {int(a['frame_start'])} to {int(a['frame_end'])} ({a['duration_frames']} frames)")
            else:
                lines.append("  • Has Animation: NO (No animation actions or keyframes found; static/T-pose)")
            lines.append("=" * 78)
            return "\n".join(lines)

        # Check numeric index (1-based)
        if part_query.isdigit():
            idx = int(part_query) - 1
            if 0 <= idx < len(meshes):
                target_meshes = [meshes[idx]]
            else:
                target_meshes = []
        else:
            # Match against mesh name, material names, or texture names
            matched = []
            for m in meshes:
                m_name = m["name"].lower()
                mats = [mat.lower() for mat in m.get("materials", [])]
                texs = [t["image_name"].lower() for t in m.get("textures", [])]
                vgs = [vg.lower() for vg in m.get("vertex_groups", [])]
                if (part_query in m_name or 
                    any(part_query in mat for mat in mats) or 
                    any(part_query in tex for tex in texs) or
                    any(part_query in vg for vg in vgs)):
                    matched.append(m)
            target_meshes = matched

        if not target_meshes:
            lines.append(f"\n  [Notice] No part found matching query: '{selected_part}'.")
            lines.append(f"  Available mesh names: {', '.join(m['name'] for m in meshes)}")
            if armatures:
                lines.append(f"  Available armatures : {', '.join(a['name'] for a in armatures)}")
            lines.append("=" * 78)
            return "\n".join(lines)

    for i, mesh in enumerate(target_meshes, 1):
        lines.append("  " + "-" * 74)
        lines.append(f"  Part #{i}: \"{mesh['name']}\"")
        lines.append("  " + "-" * 74)
        lines.append(f"  • Geometry         : {mesh['vertices']:,} Vertices | {mesh['polygons']:,} Polygons (Faces) | {mesh['edges']:,} Edges")
        
        # Dimensions & Bounding Box
        dims = mesh["dimensions"]
        bmin = mesh["bbox_min"]
        bmax = mesh["bbox_max"]
        center = mesh["center"]
        lines.append(f"  • Dimensions (Size): Width (X) = {dims[0]:.4f} m | Depth (Y) = {dims[1]:.4f} m | Height (Z) = {dims[2]:.4f} m")
        lines.append(f"  • Bounding Box Min : X = {bmin[0]:+.4f} m, Y = {bmin[1]:+.4f} m, Z = {bmin[2]:+.4f} m")
        lines.append(f"  • Bounding Box Max : X = {bmax[0]:+.4f} m, Y = {bmax[1]:+.4f} m, Z = {bmax[2]:+.4f} m")
        lines.append(f"  • Center Position  : X = {center[0]:+.4f} m, Y = {center[1]:+.4f} m, Z = {center[2]:+.4f} m")

        # Materials & Textures
        mats = mesh.get("materials", [])
        lines.append(f"  • Materials        : {', '.join(mats) if mats else 'None'}")
        textures = mesh.get("textures", [])
        if textures:
            tex_strs = [f"{t['image_name']} ({t['resolution'][0]}x{t['resolution'][1]})" for t in textures]
            lines.append(f"  • Textures         : {', '.join(tex_strs)}")
        else:
            lines.append(f"  • Textures         : None")

        # Vertex Groups & Bone Weights
        vg_count = mesh.get("vertex_groups_count", 0)
        vgs = mesh.get("vertex_groups", [])
        if vg_count > 0:
            lines.append(f"  • Bone Weights     : Rigged ({vg_count} vertex groups)")
            if vg_count <= 8:
                lines.append(f"    - Groups         : {', '.join(vgs)}")
            else:
                lines.append(f"    - Groups         : {', '.join(vgs[:6])}, ... ({vg_count - 6} more)")
        else:
            lines.append(f"  • Bone Weights     : Unrigged (0 vertex groups)")

    # 4. Overall Model Bounds
    ob = data.get("overall_bounds")
    if ob and not selected_part:
        lines.append("\n[Overall Model Dimensions & Bounds]")
        dims = ob["dimensions"]
        bmin = ob["bbox_min"]
        bmax = ob["bbox_max"]
        center = ob["center"]
        lines.append(f"  • Total Size       : Width (X) = {dims[0]:.4f} m, Depth (Y) = {dims[1]:.4f} m, Height (Z) = {dims[2]:.4f} m")
        lines.append(f"  • Combined Bounds  : Min [{bmin[0]:+.4f}, {bmin[1]:+.4f}, {bmin[2]:+.4f}] -> Max [{bmax[0]:+.4f}, {bmax[1]:+.4f}, {bmax[2]:+.4f}] m")
        lines.append(f"  • Center Point     : [{center[0]:+.4f}, {center[1]:+.4f}, {center[2]:+.4f}] m")
        lines.append(f"  • Total Geometry   : {ob['total_vertices']:,} Vertices, {ob['total_polygons']:,} Polygons")

    lines.append("=" * 78)
    return "\n".join(lines)
