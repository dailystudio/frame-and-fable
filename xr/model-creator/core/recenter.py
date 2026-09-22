"""
recenter.py
Provides mesh and scene recentering utilities to shift 3D model roots/pivots
to the character's feet (ground plane min Z/Y = 0).
Supports USDZ, USDC, USDA, GLB, GLTF, FBX, OBJ, and STL.
"""

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union


def find_blender_binary(custom_path: Optional[str] = None) -> Optional[str]:
    """Find Blender binary executable."""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    env_blender = os.environ.get("BLENDER_BIN")
    if env_blender and os.path.exists(env_blender):
        return env_blender

    # Check system PATH
    blender_in_path = shutil.which("blender")
    if blender_in_path:
        return blender_in_path

    # Common macOS paths
    mac_paths = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender.app/Contents/MacOS/blender",
    ]
    for path in mac_paths:
        if os.path.exists(path):
            return path

    return None


BLENDER_USD_RECENTER_SCRIPT = """
import sys, os, tempfile, shutil
from pxr import Usd, UsdGeom, Gf, UsdUtils, Sdf

input_path = sys.argv[-2]
output_path = sys.argv[-1]

with tempfile.TemporaryDirectory() as td:
    shutil.unpack_archive(input_path, td, "zip")
    usd_file = None
    for root, _, files in os.walk(td):
        for f in files:
            if f.endswith((".usd", ".usdc", ".usda")):
                usd_file = os.path.join(root, f)
                break
        if usd_file:
            break
            
    if not usd_file:
        sys.exit("Error: No USD file found inside USDZ package")
        
    stage = Usd.Stage.Open(usd_file)
    up_axis = UsdGeom.GetStageUpAxis(stage)
    axis_idx = 2 if up_axis == "Z" else 1
    
    min_val = None
    meshes = []
    for p in stage.Traverse():
        if p.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(p)
            pts = mesh.GetPointsAttr().Get()
            if pts and len(pts) > 0:
                meshes.append(mesh)
                m = min(pt[axis_idx] for pt in pts)
                if min_val is None or m < min_val:
                    min_val = m
                    
    if min_val is not None and abs(min_val) > 1e-4:
        print(f"[recenter] Shifting {len(meshes)} mesh(es) by {-min_val:.5f} along {up_axis}-axis (axis {axis_idx})")
        for mesh in meshes:
            pts = mesh.GetPointsAttr().Get()
            offset = [0.0, 0.0, 0.0]
            offset[axis_idx] = -min_val
            new_pts = [Gf.Vec3f(pt[0] + offset[0], pt[1] + offset[1], pt[2] + offset[2]) for pt in pts]
            mesh.GetPointsAttr().Set(new_pts)
        stage.Save()
        
        tmp_out = os.path.join(td, "reこと.usdz")
        UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(usd_file), tmp_out)
        shutil.copyfile(tmp_out, output_path)
        print(f"[recenter] Successfully saved recentered USDZ to: {output_path}")
    else:
        print("[recenter] Model is already aligned to ground plane.")
        if input_path != output_path:
            shutil.copyfile(input_path, output_path)
"""

BLENDER_GENERIC_RECENTER_SCRIPT = """
import bpy, mathutils, sys, os

input_path = sys.argv[-2]
output_path = sys.argv[-1]
ext = os.path.splitext(input_path)[1].lower()

bpy.ops.wm.read_factory_settings(use_empty=True)

if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=input_path)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=input_path)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=input_path)
elif ext == ".stl":
    bpy.ops.wm.stl_import(filepath=input_path)
else:
    sys.exit(f"Unsupported format for generic recenter: {ext}")

meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if meshes:
    min_z = min(min((obj.matrix_world @ mathutils.Vector(corner)).z for corner in obj.bound_box) for obj in meshes)
    if abs(min_z) > 1e-4:
        print(f"[recenter] Shifting {len(meshes)} mesh(es) by {-min_z:.5f} along Z-axis")
        for obj in meshes:
            obj.location.z -= min_z
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

if ext in (".glb", ".gltf"):
    bpy.ops.export_scene.gltf(filepath=output_path)
elif ext == ".fbx":
    bpy.ops.export_scene.fbx(filepath=output_path)
elif ext == ".obj":
    bpy.ops.wm.obj_export(filepath=output_path)
elif ext == ".stl":
    bpy.ops.wm.stl_export(filepath=output_path)

print(f"[recenter] Successfully saved recentered model to: {output_path}")
"""


def recenter_model_to_foot(
    model_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    blender_bin: Optional[str] = None,
) -> Path:
    """
    Shifts a 3D model so that its root pivot is located at the character's feet
    (ground plane: min bounding box value = 0.0 on vertical axis).

    Supports: .usdz, .usdc, .usda, .glb, .gltf, .fbx, .obj, .stl.
    """
    in_file = Path(model_path).resolve()
    if not in_file.is_file():
        raise FileNotFoundError(f"3D model file not found: {in_file}")

    out_file = Path(output_path).resolve() if output_path else in_file
    ext = in_file.suffix.lower()

    # Check if pxr is available directly in python
    pxr_available = False
    try:
        from pxr import Usd, UsdGeom, Gf, UsdUtils, Sdf
        pxr_available = True
    except ImportError:
        pass

    if ext == ".usdz" and pxr_available:
        with tempfile.TemporaryDirectory() as td:
            shutil.unpack_archive(str(in_file), td, "zip")
            usd_file = None
            for root, _, files in os.walk(td):
                for f in files:
                    if f.endswith((".usd", ".usdc", ".usda")):
                        usd_file = os.path.join(root, f)
                        break
                if usd_file:
                    break

            if not usd_file:
                raise RuntimeError(f"No USD file found inside USDZ: {in_file}")

            stage = Usd.Stage.Open(usd_file)
            up_axis = UsdGeom.GetStageUpAxis(stage)
            axis_idx = 2 if up_axis == "Z" else 1

            min_val = None
            meshes = []
            for p in stage.Traverse():
                if p.IsA(UsdGeom.Mesh):
                    mesh = UsdGeom.Mesh(p)
                    pts = mesh.GetPointsAttr().Get()
                    if pts and len(pts) > 0:
                        meshes.append(mesh)
                        m = min(pt[axis_idx] for pt in pts)
                        if min_val is None or m < min_val:
                            min_val = m

            if min_val is not None and abs(min_val) > 1e-4:
                print(f"[recenter] Shifting {len(meshes)} mesh(es) by {-min_val:.5f} along {up_axis}-axis")
                for mesh in meshes:
                    pts = mesh.GetPointsAttr().Get()
                    offset = [0.0, 0.0, 0.0]
                    offset[axis_idx] = -min_val
                    new_pts = [Gf.Vec3f(pt[0] + offset[0], pt[1] + offset[1], pt[2] + offset[2]) for pt in pts]
                    mesh.GetPointsAttr().Set(new_pts)
                stage.Save()

                tmp_out = os.path.join(td, "shifted.usdz")
                UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(usd_file), tmp_out)
                shutil.copyfile(tmp_out, str(out_file))
                print(f"[recenter] Successfully saved recentered USDZ to: {out_file}")
                return out_file
            else:
                if in_file != out_file:
                    shutil.copyfile(str(in_file), str(out_file))
                return out_file

    # Fallback to Blender
    blender = find_blender_binary(blender_bin)
    if not blender:
        print("[recenter] Warning: Blender executable not found. Model recentering skipped.", file=sys.stderr)
        return in_file

    script_code = BLENDER_USD_RECENTER_SCRIPT if ext in (".usdz", ".usdc", ".usda") else BLENDER_GENERIC_RECENTER_SCRIPT

    cmd = [
        blender,
        "-b",
        "--python-expr",
        script_code,
        "--",
        str(in_file),
        str(out_file),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[recenter] Warning: Blender recentering failed (exit code {res.returncode}):\n{res.stderr}", file=sys.stderr)
    else:
        for line in res.stdout.splitlines():
            if "[recenter]" in line:
                print(line)

    return out_file
