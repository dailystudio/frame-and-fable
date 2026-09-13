#!/usr/bin/env python3
"""
fix_chin_jaw_weights.py

Universal Chin & Jaw Skinning Weight Cleaner for USDZ / USDC character models.

Solves the common "rubber chin / stretched jaw" rigging bug on 3D characters
(typically caused by Mixamo or automatic weight heat/voxel bleeding):
  - Strips stray torso (Spine2/Chest), shoulder, and arm weights from chin, jaw, and head vertices.
  - Reallocates that weight to the Head bone.
  - Clamps influences to 4 per vertex (Apple RealityKit / GPU skinning standard) and renormalizes.
  - Uses anatomical bone hierarchy & 3D joint reference positions, making it universal
    across any character height, scale, or orientation.
"""

import argparse
import os
import shutil
import sys
import tempfile

# If run with standard python3 lacking pxr (USD), re-launch via Blender's Python
try:
    import pxr
except ImportError:
    mac_paths = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender.app/Contents/MacOS/blender",
    ]
    env_blender = os.environ.get("BLENDER_BIN")
    blender_bin = env_blender or shutil.which("blender")
    if not blender_bin:
        for p in mac_paths:
            if os.path.exists(p):
                blender_bin = p
                break

    if blender_bin and os.path.exists(blender_bin):
        cmd = [blender_bin, "-b", "--python", os.path.abspath(__file__), "--"] + sys.argv[1:]
        import subprocess
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    else:
        print("Error: pxr (Universal Scene Description) not found and Blender executable was not located.")
        sys.exit(1)

from pxr import Sdf, Usd, UsdGeom, UsdSkel, UsdUtils
import numpy as np


def find_skeleton_and_meshes(stage):
    """Dynamically finds the Skeleton and all skinned Mesh prims in the USD stage."""
    skel_prim = None
    meshes = []
    for p in stage.Traverse():
        if not skel_prim and p.IsA(UsdSkel.Skeleton):
            skel_prim = p
        if p.IsA(UsdGeom.Mesh) and p.HasAPI(UsdSkel.BindingAPI):
            binding = UsdSkel.BindingAPI(p)
            if binding.GetJointIndicesAttr().HasValue():
                meshes.append(p)
    return skel_prim, meshes


def identify_joints(joints):
    """
    Identifies head, neck, and invalid ancestor/limb joints using standard naming conventions.
    Compatible with Mixamo, Unreal, Unity HumanIK, Blender Rigify, DAZ, CC4, etc.
    """
    head_idx = None
    neck_idx = None
    invalid_for_head = set()

    for idx, j in enumerate(joints):
        name = j.split("/")[-1].lower()
        # Head detection (ignore leaf helper tips like HeadTop_End)
        if "head" in name and not any(x in name for x in ["top", "end", "nub", "tip"]):
            head_idx = idx
        elif "neck" in name:
            neck_idx = idx

        # Bones that should NEVER directly influence the head or chin:
        # Torso (spine, chest, hips, pelvis) and arms/shoulders (clavicle, shoulder, arm, hand)
        if any(token in name for token in ["spine", "chest", "torso", "hip", "pelvis",
                                           "shoulder", "clavicle", "arm", "hand"]):
            invalid_for_head.add(idx)

    return head_idx, neck_idx, invalid_for_head


def clean_chin_jaw_weights(stage, skel_prim, mesh_prim):
    """
    Cleans up contaminated vertex weights on the chin, jaw, and head vertices:
      1. Uses joint reference positions and skeletal topology.
      2. Strips torso/shoulder weights from head and jawline vertices.
      3. Clamps influences to 4 per vertex and normalizes all weights.
    """
    mesh = UsdGeom.Mesh(mesh_prim)
    points = np.array(mesh.GetPointsAttr().Get())
    binding = UsdSkel.BindingAPI(mesh_prim)

    weights_attr = binding.GetJointWeightsAttr()
    indices_attr = binding.GetJointIndicesAttr()
    orig_elem_size = binding.GetJointIndicesPrimvar().GetElementSize()

    weights = np.array(weights_attr.Get()).reshape(-1, orig_elem_size)
    indices = np.array(indices_attr.Get()).reshape(-1, orig_elem_size)

    skel = UsdSkel.Skeleton(skel_prim)
    joints = list(skel.GetJointsAttr().Get())
    bind_xforms = skel.GetBindTransformsAttr().Get()

    head_idx, neck_idx, invalid_for_head = identify_joints(joints)
    if head_idx is None:
        print(f"[-] Warning: Head bone not found in skeleton '{skel_prim.GetPath()}'. Skipping.")
        return 0

    # Transform mesh points to skeleton space using geomBindTransform
    gbt = binding.GetGeomBindTransformAttr().Get()
    if gbt:
        M = np.array([[gbt[i][j] for j in range(4)] for i in range(4)])
        pts_h = np.hstack([points, np.ones((len(points), 1))])
        skel_pts = (pts_h @ M)[:, :3]
    else:
        skel_pts = points

    # Calculate joint reference positions in skeleton space
    p_head = np.array(bind_xforms[head_idx].ExtractTranslation())
    if neck_idx is not None:
        p_neck = np.array(bind_xforms[neck_idx].ExtractTranslation())
        d_head_neck = np.linalg.norm(p_head - p_neck)
    else:
        p_neck = p_head
        d_head_neck = 10.0

    d_head = np.linalg.norm(skel_pts - p_head, axis=1)
    d_neck = np.linalg.norm(skel_pts - p_neck, axis=1)

    print(f"[*] Scanning mesh '{mesh_prim.GetPath()}' ({len(points)} vertices)...")
    print(f"    Head joint: [{head_idx}] {joints[head_idx]}")
    if neck_idx is not None:
        print(f"    Neck joint: [{neck_idx}] {joints[neck_idx]}")

    new_indices = []
    new_weights = []
    fixed_count = 0

    for i in range(len(points)):
        row_ind = indices[i]
        row_wt = weights[i]

        w_dict = {}
        for j_idx, w in zip(row_ind, row_wt):
            if w > 1e-5:
                w_dict[int(j_idx)] = w_dict.get(int(j_idx), 0.0) + float(w)

        # Topological & geometric head/jaw vertex detection:
        # 1. Influenced by Head (> 2%)
        # OR 2. Geometrically closer to Head than Neck and within head scale
        is_head_vertex = (w_dict.get(head_idx, 0.0) > 0.02) or (
            d_head[i] < d_neck[i] and d_head[i] < (d_head_neck * 6.0)
        )

        modified = False
        if is_head_vertex:
            bad_w = 0.0
            for k in list(w_dict.keys()):
                if k in invalid_for_head:
                    bad_w += w_dict.pop(k)
                    modified = True
            if bad_w > 0:
                w_dict[head_idx] = w_dict.get(head_idx, 0.0) + bad_w

        if modified:
            fixed_count += 1

        # Keep top 4 influences and normalize
        sorted_items = sorted(w_dict.items(), key=lambda x: -x[1])[:4]
        total_w = sum(x[1] for x in sorted_items)
        if total_w > 0:
            norm_items = [(x[0], x[1] / total_w) for x in sorted_items]
        else:
            norm_items = [(head_idx, 1.0)]

        while len(norm_items) < 4:
            norm_items.append((0, 0.0))

        new_indices.append([x[0] for x in norm_items])
        new_weights.append([x[1] for x in norm_items])

    new_indices_flat = np.array(new_indices, dtype=np.int32).flatten()
    new_weights_flat = np.array(new_weights, dtype=np.float32).flatten()

    binding.GetJointIndicesPrimvar().SetElementSize(4)
    binding.GetJointWeightsPrimvar().SetElementSize(4)
    indices_attr.Set(new_indices_flat)
    weights_attr.Set(new_weights_flat)

    print(f"[✓] Fixed {fixed_count} chin/head vertices on '{mesh_prim.GetName()}'. ElementSize clamped to 4.")
    return fixed_count


def fix_usdz_file(input_file, output_file=None, in_place=False):
    """Processes a .usdz (or .usdc) file and cleans all chin/jaw skinning weights."""
    abs_input = os.path.abspath(input_file)
    if not os.path.exists(abs_input):
        print(f"Error: File not found: {abs_input}")
        return False

    is_usdz = abs_input.lower().endswith(".usdz")
    if in_place:
        abs_output = abs_input
    elif output_file:
        abs_output = os.path.abspath(output_file)
    else:
        suffix = "_fixed.usdz" if is_usdz else "_fixed.usdc"
        abs_output = os.path.splitext(abs_input)[0] + suffix

    print(f"\n==========================================")
    print(f"Processing: {os.path.basename(abs_input)}")
    print(f"Output:     {os.path.basename(abs_output)}")
    print(f"==========================================")

    if is_usdz:
        with tempfile.TemporaryDirectory() as tmpdir:
            shutil.unpack_archive(abs_input, tmpdir, "zip")
            base_usd = None
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith(".usdc") or f.endswith(".usd"):
                        base_usd = os.path.join(root, f)
                        break
                if base_usd:
                    break

            if not base_usd:
                print(f"Error: No USD file found inside {abs_input}")
                return False

            stage = Usd.Stage.Open(base_usd)
            skel_prim, meshes = find_skeleton_and_meshes(stage)
            if not skel_prim or not meshes:
                print("Error: Could not find Skeleton or Skinned Mesh in stage.")
                return False

            for mesh_prim in meshes:
                clean_chin_jaw_weights(stage, skel_prim, mesh_prim)

            stage.Save()

            if in_place:
                backup = os.path.splitext(abs_input)[0] + "_backup.usdz"
                if not os.path.exists(backup):
                    shutil.copyfile(abs_input, backup)
                    print(f"[✓] Backup created at: {backup}")

            if os.path.exists(abs_output):
                os.remove(abs_output)

            success = UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(base_usd), abs_output)
            if not success:
                success = UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(base_usd), abs_output)

            if success:
                print(f"[✓] Successfully saved: {abs_output}")
                return True
            else:
                print(f"Error: Failed to package USDZ at: {abs_output}")
                return False
    else:
        stage = Usd.Stage.Open(abs_input)
        skel_prim, meshes = find_skeleton_and_meshes(stage)
        if not skel_prim or not meshes:
            print("Error: Could not find Skeleton or Skinned Mesh in stage.")
            return False

        for mesh_prim in meshes:
            clean_chin_jaw_weights(stage, skel_prim, mesh_prim)

        if in_place:
            backup = os.path.splitext(abs_input)[0] + "_backup.usdc"
            if not os.path.exists(backup):
                shutil.copyfile(abs_input, backup)
                print(f"[✓] Backup created at: {backup}")
            stage.Save()
            print(f"[✓] Successfully updated in-place: {abs_input}")
        else:
            stage.GetRootLayer().Export(abs_output)
            print(f"[✓] Successfully exported: {abs_output}")
        return True


def main():
    args_list = sys.argv[1:]
    if "--" in args_list:
        args_list = args_list[args_list.index("--") + 1:]

    parser = argparse.ArgumentParser(
        description="Fix chin and jaw skinning stretch on rigged USDZ/USDC characters."
    )
    parser.add_argument(
        "inputs", nargs="*", help="Path(s) to .usdz or .usdc files to clean."
    )
    parser.add_argument(
        "-o", "--output", help="Output file path (only when processing a single input file)."
    )
    parser.add_argument(
        "--in-place", action="store_true", help="Overwrite the input file in place (creates a _backup file)."
    )

    args = parser.parse_args(args_list)

    if not args.inputs:
        parser.print_help()
        sys.exit(0)

    if args.output and len(args.inputs) > 1:
        print("Error: --output can only be specified when processing a single input file.")
        sys.exit(1)

    for f in args.inputs:
        fix_usdz_file(f, output_file=args.output, in_place=args.in_place)


if __name__ == "__main__":
    main()
