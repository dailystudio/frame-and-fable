#!/usr/bin/env python3
"""
Automated Pipeline: Character, Hair, and Cloth (Tube Dress) Combination & Rigging

This script automates the entire process of:
1. Extracting and deduplicating textures from USDZ packages.
2. Calibrating, scaling, and fitting Hair and Tube Dress geometry to the body anatomy.
3. Generating smooth skeletal weights for body, hair, and cloth.
4. Integrating the Standing Greeting skeletal animation using Pixar USD (pxr.UsdSkel).
5. Generating production-ready outputs: .blend, .usdz, .glb, and .fbx.

Usage:
    /Applications/Blender.app/Contents/MacOS/Blender -b --python combine_character_pipeline.py
"""

import os
import sys
import math
import shutil
import zipfile
import numpy as np

try:
    import bpy
    from pxr import Usd, UsdSkel, UsdGeom, UsdShade, Sdf, Vt, Gf
except ImportError as e:
    print(f"Error importing required libraries: {e}")
    print("Please run this script using Blender's Python environment, e.g.:")
    print("  /Applications/Blender.app/Contents/MacOS/Blender -b --python combine_character_pipeline.py")
    sys.exit(1)


def run_pipeline(workspace_dir):
    print("=" * 70)
    print("STARTING AUTOMATED CHARACTER COMBINATION PIPELINE")
    print("=" * 70)

    # ---------------------------------------------------------
    # 0. File Paths Setup
    # ---------------------------------------------------------
    body_base_usdz = os.path.join(workspace_dir, "body_anim_base.usdz")
    body_anim_usdc = os.path.join(workspace_dir, "body_anim_standing_greeting.usdc")
    hair_usdz = os.path.join(workspace_dir, "hair.usdz")
    tube_usdz = os.path.join(workspace_dir, "tube.usdz")

    textures_dir = os.path.join(workspace_dir, "textures")
    os.makedirs(textures_dir, exist_ok=True)

    out_blend = os.path.join(workspace_dir, "combined_character.blend")
    out_usdc = os.path.join(workspace_dir, "combined_character_skel.usdc")
    out_usdz = os.path.join(workspace_dir, "combined_character.usdz")
    out_glb = os.path.join(workspace_dir, "combined_character.glb")
    out_fbx = os.path.join(workspace_dir, "combined_character.fbx")

    # ---------------------------------------------------------
    # 1. Texture Extraction & Deduplication
    # ---------------------------------------------------------
    print("\n[Step 1/5] Extracting textures from source packages...")
    
    def extract_texture(usdz_path, dest_filename):
        with zipfile.ZipFile(usdz_path, "r") as z:
            for item in z.namelist():
                if item.endswith("shaded.png"):
                    data = z.read(item)
                    dest_path = os.path.join(textures_dir, dest_filename)
                    with open(dest_path, "wb") as f:
                        f.write(data)
                    print(f"  -> Extracted {dest_filename} ({len(data)} bytes)")
                    return dest_path
        return None

    tex_body = extract_texture(body_base_usdz, "body_shaded.png")
    tex_hair = extract_texture(hair_usdz, "hair_shaded.png")
    tex_tube = extract_texture(tube_usdz, "tube_shaded.png")

    # ---------------------------------------------------------
    # 2. Blender Stage: Geometric Alignment, Materials & Weights
    # ---------------------------------------------------------
    print("\n[Step 2/5] Calibrating meshes, materials, and skeletal weights in Blender...")
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 2.1 Import Body with UVs & Materials
    bpy.ops.wm.usd_import(filepath=body_base_usdz)
    body_obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
    body_obj.name = "Body"
    base_arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
    base_root = base_arm.parent

    # 2.2 Import Animated Armature
    bpy.ops.wm.usd_import(filepath=body_anim_usdc)
    anim_arm = [o for o in bpy.data.objects if o.type == "ARMATURE" and o != base_arm][0]
    anim_arm.name = "Armature"
    anim_root = anim_arm.parent
    anim_root.name = "Root"
    usdc_body = [o for o in bpy.data.objects if o.type == "MESH" and o != body_obj][0]

    # Clean redundant objects
    bpy.data.objects.remove(base_arm, do_unlink=True)
    bpy.data.objects.remove(usdc_body, do_unlink=True)
    if base_root and base_root != anim_root:
        bpy.data.objects.remove(base_root, do_unlink=True)

    # Rest pose during binding
    anim_arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    # 2.3 Setup Body Material
    body_mat = bpy.data.materials.new(name="M_Body")
    body_mat.use_nodes = True
    bsdf_body = body_mat.node_tree.nodes.get("Principled BSDF")
    tex_node_body = body_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex_node_body.image = bpy.data.images.load(tex_body)
    body_mat.node_tree.links.new(tex_node_body.outputs["Color"], bsdf_body.inputs["Base Color"])
    bsdf_body.inputs["Roughness"].default_value = 0.5
    body_obj.data.materials.clear()
    body_obj.data.materials.append(body_mat)

    # 2.4 Import Hair
    bpy.ops.wm.usd_import(filepath=hair_usdz)
    hair_obj = [o for o in bpy.data.objects if o.type == "MESH" and o != body_obj][0]
    hair_obj.name = "Hair"
    hair_mat = bpy.data.materials.new(name="M_Hair")
    hair_mat.use_nodes = True
    bsdf_hair = hair_mat.node_tree.nodes.get("Principled BSDF")
    tex_node_hair = hair_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex_node_hair.image = bpy.data.images.load(tex_hair)
    hair_mat.node_tree.links.new(tex_node_hair.outputs["Color"], bsdf_hair.inputs["Base Color"])
    bsdf_hair.inputs["Roughness"].default_value = 0.6
    hair_obj.data.materials.clear()
    hair_obj.data.materials.append(hair_mat)

    # 2.5 Import Tube Dress
    bpy.ops.wm.usd_import(filepath=tube_usdz)
    tube_obj = [o for o in bpy.data.objects if o.type == "MESH" and o not in [body_obj, hair_obj]][0]
    tube_obj.name = "Tube"
    tube_mat = bpy.data.materials.new(name="M_Tube")
    tube_mat.use_nodes = True
    bsdf_tube = tube_mat.node_tree.nodes.get("Principled BSDF")
    tex_node_tube = tube_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex_node_tube.image = bpy.data.images.load(tex_tube)
    tube_mat.node_tree.links.new(tex_node_tube.outputs["Color"], bsdf_tube.inputs["Base Color"])
    bsdf_tube.inputs["Roughness"].default_value = 0.4
    tube_obj.data.materials.clear()
    tube_obj.data.materials.append(tube_mat)

    # 2.6 Geometric Transformations (Calibrated Scale, Rotation & Placement)
    print("  -> Applying calibrated Hair transformation...")
    hair_obj.rotation_euler = (math.radians(-2.5), 0, 0)
    hair_obj.scale = (0.595, 0.615, 0.595)
    hair_obj.location = (0.003, 0.002, 0.812)

    print("  -> Applying calibrated Tube Dress transformation (Breast mid-line alignment)...")
    tube_obj.scale = (0.835, 0.895, 0.760)
    tube_obj.location = (-0.002, 0.068, 0.005)

    # Apply transforms into world rest space
    for obj in [hair_obj, tube_obj]:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj.select_set(False)

    # 2.7 Hair Skinning (100% Head influence)
    hair_vg = hair_obj.vertex_groups.new(name="mixamorig_Head")
    hair_vg.add(list(range(len(hair_obj.data.vertices))), 1.0, "REPLACE")

    # 2.8 Tube Dress Smooth Skinning
    vg_spine2 = tube_obj.vertex_groups.new(name="mixamorig_Spine2")
    vg_spine1 = tube_obj.vertex_groups.new(name="mixamorig_Spine1")
    vg_spine = tube_obj.vertex_groups.new(name="mixamorig_Spine")
    vg_hips = tube_obj.vertex_groups.new(name="mixamorig_Hips")
    vg_l_leg = tube_obj.vertex_groups.new(name="mixamorig_LeftUpLeg")
    vg_r_leg = tube_obj.vertex_groups.new(name="mixamorig_RightUpLeg")

    for v_idx, v in enumerate(tube_obj.data.vertices):
        z = v.co.z
        x = v.co.x
        if z >= 1.13:
            w_spine2, w_spine1, w_spine, w_hips, w_ll, w_rl = 1.0, 0.0, 0.0, 0.0, 0.0, 0.0
        elif z >= 1.05:
            t = (z - 1.05) / (1.13 - 1.05)
            w_spine2, w_spine1, w_spine, w_hips, w_ll, w_rl = t, 1.0 - t, 0.0, 0.0, 0.0, 0.0
        elif z >= 0.98:
            t = (z - 0.98) / (1.05 - 0.98)
            w_spine2, w_spine1, w_spine, w_hips, w_ll, w_rl = 0.0, t, 1.0 - t, 0.0, 0.0, 0.0
        elif z >= 0.88:
            t = (z - 0.88) / (0.98 - 0.88)
            w_spine2, w_spine1, w_spine, w_hips, w_ll, w_rl = 0.0, 0.0, t, 1.0 - t, 0.0, 0.0
        elif z >= 0.65:
            t = (z - 0.65) / (0.88 - 0.65)
            w_spine2, w_spine1, w_spine = 0.0, 0.0, 0.0
            w_hips = 0.80 + 0.20 * t
            share = 1.0 - w_hips
            w_ll = share if x > 0 else 0.0
            w_rl = share if x <= 0 else 0.0
        else:
            w_spine2, w_spine1, w_spine = 0.0, 0.0, 0.0
            w_hips = 0.75
            share = 0.25
            if x > 0.02:
                w_ll, w_rl = share, 0.0
            elif x < -0.02:
                w_ll, w_rl = 0.0, share
            else:
                w_ll, w_rl = share * 0.5, share * 0.5

        if w_spine2 > 0: vg_spine2.add([v_idx], w_spine2, "REPLACE")
        if w_spine1 > 0: vg_spine1.add([v_idx], w_spine1, "REPLACE")
        if w_spine > 0: vg_spine.add([v_idx], w_spine, "REPLACE")
        if w_hips > 0: vg_hips.add([v_idx], w_hips, "REPLACE")
        if w_ll > 0: vg_l_leg.add([v_idx], w_ll, "REPLACE")
        if w_rl > 0: vg_r_leg.add([v_idx], w_rl, "REPLACE")

    # Bind all meshes to Armature
    for obj in [body_obj, hair_obj, tube_obj]:
        obj.modifiers.clear()
        mod = obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = anim_arm
        obj.parent = anim_root
        obj.matrix_parent_inverse = anim_root.matrix_world.inverted()

    # Clean unneeded helper empties
    for o in list(bpy.data.objects):
        if o.type == "EMPTY" and o != anim_root:
            bpy.data.objects.remove(o, do_unlink=True)

    # Switch to POSE mode
    anim_arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()

    # ---------------------------------------------------------
    # 3. Export Formats: .blend, .glb, .fbx
    # ---------------------------------------------------------
    print("\n[Step 3/5] Exporting Blender, GLB, and FBX files...")
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print(f"  -> Saved master .blend: {out_blend}")

    bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", export_animations=True)
    print(f"  -> Exported .glb: {out_glb}")

    bpy.ops.export_scene.fbx(filepath=out_fbx, add_leaf_bones=False, bake_anim=True)
    print(f"  -> Exported .fbx: {out_fbx}")

    # Extract mesh vertex buffers for USD authoring
    def extract_buffers(obj):
        mesh = obj.data
        pts = [Gf.Vec3f(float(v.co.x * 100.0), float(v.co.z * 100.0), float(-v.co.y * 100.0)) for v in mesh.vertices]
        fc = [len(p.vertices) for p in mesh.polygons]
        fi = []
        for p in mesh.polygons:
            fi.extend(p.vertices)
        uvs = []
        if mesh.uv_layers.active:
            for l in mesh.loops:
                uv = mesh.uv_layers.active.data[l.index].uv
                uvs.append(Gf.Vec2f(float(uv.x), float(uv.y)))
        return pts, fc, fi, uvs

    hair_pts, hair_fc, hair_fi, hair_uvs = extract_buffers(hair_obj)
    tube_pts, tube_fc, tube_fi, tube_uvs = extract_buffers(tube_obj)
    body_pts, body_fc, body_fi, body_uvs = extract_buffers(body_obj)

    # ---------------------------------------------------------
    # 4. Pixar USD Authoring (UsdSkel Native Animation & Skinning)
    # ---------------------------------------------------------
    print("\n[Step 4/5] Authoring native UsdSkel animation into USD stage...")
    shutil.copy(body_anim_usdc, out_usdc)
    stage = Usd.Stage.Open(out_usdc)

    skel_prim = stage.GetPrimAtPath("/root/Armature/Armature")
    skel = UsdSkel.Skeleton(skel_prim)
    joints = skel.GetJointsAttr().Get()
    skel_path = skel_prim.GetPath()

    # Materials scope
    UsdGeom.Scope.Define(stage, "/root/_materials")

    def author_material(mat_path, tex_rel_path):
        mat = UsdShade.Material.Define(stage, mat_path)
        pbr = UsdShade.Shader.Define(stage, f"{mat_path}/PBRShader")
        pbr.CreateIdAttr("UsdPreviewSurface")
        pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
        pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

        tex = UsdShade.Shader.Define(stage, f"{mat_path}/DiffuseTexture")
        tex.CreateIdAttr("UsdUVTexture")
        tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(tex_rel_path)
        tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
        tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")

        st_reader = UsdShade.Shader.Define(stage, f"{mat_path}/stReader")
        st_reader.CreateIdAttr("UsdPrimvarReader_float2")
        st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

        tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_reader.ConnectableAPI(), "result")
        pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), "rgb")
        mat.CreateSurfaceOutput().ConnectToSource(pbr.ConnectableAPI(), "surface")
        return mat

    mat_b = author_material("/root/_materials/M_Body", "./textures/body_shaded.png")
    mat_h = author_material("/root/_materials/M_Hair", "./textures/hair_shaded.png")
    mat_t = author_material("/root/_materials/M_Tube", "./textures/tube_shaded.png")

    # Body Binding & Primvars
    body_prim_usd = stage.GetPrimAtPath("/root/Armature/model/model")
    if body_uvs:
        st_b = UsdGeom.PrimvarsAPI(body_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
        st_b.Set(Vt.Vec2fArray(body_uvs))
    UsdShade.MaterialBindingAPI.Apply(body_prim_usd).Bind(mat_b)

    # Hair Mesh & UsdSkel Binding
    UsdGeom.Xform.Define(stage, "/root/Armature/hair")
    hair_prim_usd = stage.DefinePrim("/root/Armature/hair/hair", "Mesh")
    hair_mesh_usd = UsdGeom.Mesh(hair_prim_usd)
    hair_mesh_usd.CreatePointsAttr(Vt.Vec3fArray(hair_pts))
    hair_mesh_usd.CreateFaceVertexCountsAttr(Vt.IntArray(hair_fc))
    hair_mesh_usd.CreateFaceVertexIndicesAttr(Vt.IntArray(hair_fi))
    if hair_uvs:
        st_h = UsdGeom.PrimvarsAPI(hair_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
        st_h.Set(Vt.Vec2fArray(hair_uvs))

    h_binding = UsdSkel.BindingAPI.Apply(hair_prim_usd)
    h_binding.CreateSkeletonRel().SetTargets([skel_path])
    h_binding.CreateJointsAttr(joints)

    h_indices = []
    h_weights = []
    for _ in range(len(hair_pts)):
        h_indices.extend([5, 0, 0, 0, 0, 0, 0, 0])
        h_weights.extend([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    ji_h = h_binding.CreateJointIndicesPrimvar(False, 8)
    ji_h.SetInterpolation(UsdGeom.Tokens.vertex)
    ji_h.Set(Vt.IntArray(h_indices))

    jw_h = h_binding.CreateJointWeightsPrimvar(False, 8)
    jw_h.SetInterpolation(UsdGeom.Tokens.vertex)
    jw_h.Set(Vt.FloatArray(h_weights))
    UsdShade.MaterialBindingAPI.Apply(hair_prim_usd).Bind(mat_h)

    # Tube Mesh & UsdSkel Binding
    UsdGeom.Xform.Define(stage, "/root/Armature/tube")
    tube_prim_usd = stage.DefinePrim("/root/Armature/tube/tube", "Mesh")
    tube_mesh_usd = UsdGeom.Mesh(tube_prim_usd)
    tube_mesh_usd.CreatePointsAttr(Vt.Vec3fArray(tube_pts))
    tube_mesh_usd.CreateFaceVertexCountsAttr(Vt.IntArray(tube_fc))
    tube_mesh_usd.CreateFaceVertexIndicesAttr(Vt.IntArray(tube_fi))
    if tube_uvs:
        st_t = UsdGeom.PrimvarsAPI(tube_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
        st_t.Set(Vt.Vec2fArray(tube_uvs))

    t_binding = UsdSkel.BindingAPI.Apply(tube_prim_usd)
    t_binding.CreateSkeletonRel().SetTargets([skel_path])
    t_binding.CreateJointsAttr(joints)

    t_indices = []
    t_weights = []
    for v in tube_obj.data.vertices:
        z = v.co.z
        x = v.co.x
        if z >= 1.13:
            w_sp2, w_sp1, w_sp, w_hp, w_ll, w_rl = 1.0, 0.0, 0.0, 0.0, 0.0, 0.0
        elif z >= 1.05:
            t = (z - 1.05) / (1.13 - 1.05)
            w_sp2, w_sp1, w_sp, w_hp, w_ll, w_rl = t, 1.0 - t, 0.0, 0.0, 0.0, 0.0
        elif z >= 0.98:
            t = (z - 0.98) / (1.05 - 0.98)
            w_sp2, w_sp1, w_sp, w_hp, w_ll, w_rl = 0.0, t, 1.0 - t, 0.0, 0.0, 0.0
        elif z >= 0.88:
            t = (z - 0.88) / (0.98 - 0.88)
            w_sp2, w_sp1, w_sp, w_hp, w_ll, w_rl = 0.0, 0.0, t, 1.0 - t, 0.0, 0.0
        elif z >= 0.65:
            t = (z - 0.65) / (0.88 - 0.65)
            w_sp2, w_sp1, w_sp = 0.0, 0.0, 0.0
            w_hp = 0.80 + 0.20 * t
            share = 1.0 - w_hp
            w_ll = share if x > 0 else 0.0
            w_rl = share if x <= 0 else 0.0
        else:
            w_sp2, w_sp1, w_sp = 0.0, 0.0, 0.0
            w_hp = 0.75
            share = 0.25
            if x > 0.02:
                w_ll, w_rl = share, 0.0
            elif x < -0.02:
                w_ll, w_rl = 0.0, share
            else:
                w_ll, w_rl = share * 0.5, share * 0.5

        t_indices.extend([3, 2, 1, 0, 55, 60, 0, 0])
        t_weights.extend([float(w_sp2), float(w_sp1), float(w_sp), float(w_hp), float(w_ll), float(w_rl), 0.0, 0.0])

    ji_t = t_binding.CreateJointIndicesPrimvar(False, 8)
    ji_t.SetInterpolation(UsdGeom.Tokens.vertex)
    ji_t.Set(Vt.IntArray(t_indices))

    jw_t = t_binding.CreateJointWeightsPrimvar(False, 8)
    jw_t.SetInterpolation(UsdGeom.Tokens.vertex)
    jw_t.Set(Vt.FloatArray(t_weights))
    UsdShade.MaterialBindingAPI.Apply(tube_prim_usd).Bind(mat_t)

    # Save and package USDZ
    stage.GetRootLayer().Save()

    print("\n[Step 5/5] Packaging uncompressed USDZ archive...")
    with zipfile.ZipFile(out_usdz, "w", compression=zipfile.ZIP_STORED) as z:
        z.write(out_usdc, arcname="combined_character.usdc")
        for tf in ["body_shaded.png", "hair_shaded.png", "tube_shaded.png"]:
            z.write(os.path.join(textures_dir, tf), arcname=f"textures/{tf}")

    print(f"  -> Generated USDZ package: {out_usdz} ({os.path.getsize(out_usdz)} bytes)")
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    workspace = os.path.dirname(os.path.abspath(__file__))
    run_pipeline(workspace)
