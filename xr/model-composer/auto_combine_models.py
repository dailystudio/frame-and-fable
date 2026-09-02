#!/usr/bin/env python3
"""
Automated 3D Model Combiner, Fitter, Rigger & Verification Tool
Supports Modular Garments (Dresses, Tops, Suits, Pants, Skirts), Hair, and 4-View Turnaround References (Front, Left, Right, Back).

Usage:
    python3 auto_combine_models.py \
        --body tests/man_anim_base.usdz \
        --anim tests/man_anim_hip_hop_dancing.usdc \
        --hair tests/man_hair.usdz \
        --cloth tests/man_suit.usdz \
        --bottom tests/man_pants.usdz \
        --ref-front tests/man_ref_front.png \
        --ref-left tests/man_ref_left.png \
        --ref-back tests/man_ref_back.png \
        --output-dir outputs
"""

import os
import sys
import json
import shutil
import zipfile
import argparse
import subprocess
import math


def find_blender():
    """Locate Blender executable across macOS, Linux, and Windows."""
    blender_path = shutil.which("blender")
    if blender_path:
        return blender_path

    candidates = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.4.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.3.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.2.app/Contents/MacOS/Blender",
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe",
        "C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def run_blender_worker(blender_bin, config_json_path):
    worker_script = os.path.abspath(__file__)
    cmd = [blender_bin, "-b", "--python", worker_script, "--", "--config", config_json_path]
    print(f"Executing Blender Worker: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True)
    return result.returncode


# =============================================================================
# BLENDER INTERNAL WORKER LOGIC
# =============================================================================

def execute_in_blender(config):
    import bpy
    import mathutils
    import numpy as np
    from pxr import Usd, UsdSkel, UsdGeom, UsdShade, Sdf, Vt, Gf

    output_dir = os.path.abspath(config["output_dir"])
    renders_dir = os.path.join(output_dir, "renders")
    textures_dir = os.path.join(output_dir, "textures")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(renders_dir, exist_ok=True)
    os.makedirs(textures_dir, exist_ok=True)

    print("\n" + "=" * 65)
    print("BLENDER AUTOMATED GENERALIZED FITTING & RIGGING WORKER RUNNING")
    print("=" * 65)

    def extract_texture(pkg_path, out_name):
        if pkg_path and os.path.exists(pkg_path) and pkg_path.endswith(".usdz"):
            with zipfile.ZipFile(pkg_path, "r") as z:
                img_candidates = [
                    item for item in z.namelist()
                    if item.lower().endswith((".png", ".jpg", ".jpeg", ".tga", ".webp"))
                ]
                if not img_candidates:
                    return None
                
                selected = None
                for item in img_candidates:
                    if any(k in item.lower() for k in ["shaded", "diffuse", "albedo", "basecolor", "color"]):
                        selected = item
                        break
                if not selected:
                    selected = max(img_candidates, key=lambda x: z.getinfo(x).file_size)

                data = z.read(selected)
                dest = os.path.join(textures_dir, out_name)
                with open(dest, "wb") as f:
                    f.write(data)
                print(f"  -> Extracted texture '{selected}' ({len(data)} bytes) to '{out_name}'")
                return dest
        return None

    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 1. Import Base Body
    body_path = config["body"]
    bpy.ops.wm.usd_import(filepath=body_path)
    body_obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
    body_obj.name = "Body"
    body_arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
    body_root = body_arm.parent

    # 2. Import Animation file (if provided), or use Body's own armature
    anim_path = config.get("anim")
    if anim_path and os.path.exists(anim_path):
        bpy.ops.wm.usd_import(filepath=anim_path)
        anim_arm = [o for o in bpy.data.objects if o.type == "ARMATURE" and o != body_arm][0]
        anim_arm.name = "Armature"
        anim_root = anim_arm.parent
        anim_root.name = "Root"
        usdc_body = [o for o in bpy.data.objects if o.type == "MESH" and o != body_obj][0]

        # Re-parent body_obj to anim_root matching the target armature space
        body_obj.parent = anim_root
        body_obj.matrix_local = usdc_body.matrix_local.copy()

        bpy.data.objects.remove(body_arm, do_unlink=True)
        bpy.data.objects.remove(usdc_body, do_unlink=True)
        if body_root and body_root != anim_root:
            bpy.data.objects.remove(body_root, do_unlink=True)
    else:
        anim_arm = body_arm
        anim_arm.name = "Armature"
        anim_root = body_root
        if not anim_root:
            anim_root = bpy.data.objects.new("Root", None)
            bpy.context.scene.collection.objects.link(anim_root)
            anim_arm.parent = anim_root
            body_obj.parent = anim_root

    anim_arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    def make_material(name, tex_path, roughness=0.5):
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if tex_path and os.path.exists(tex_path):
            tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex_node.image = bpy.data.images.load(tex_path)
            mat.node_tree.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = roughness
        return mat

    tex_body = extract_texture(body_path, "body_shaded.png")
    body_obj.data.materials.clear()
    body_obj.data.materials.append(make_material("M_Body", tex_body, 0.5))

    # 3. Extract Body Anatomy Landmarks (in meters)
    bv = np.array([v.co for v in body_obj.data.vertices])
    bones = anim_arm.data.bones

    head_bone = bones.get("mixamorig_Head")
    neck_bone = bones.get("mixamorig_Neck")
    spine2_bone = bones.get("mixamorig_Spine2")
    hips_bone = bones.get("mixamorig_Hips")

    head_z = (head_bone.head_local[1] * 0.01) if head_bone else 1.25
    neck_z = (neck_bone.head_local[1] * 0.01) if neck_bone else 1.23
    hips_z = (hips_bone.head_local[1] * 0.01) if hips_bone else 0.70
    head_top_z = float(bv[:, 2].max())
    feet_z = float(bv[:, 2].min())

    head_v = bv[bv[:, 2] >= head_z]
    head_min, head_max = head_v.min(axis=0), head_v.max(axis=0)
    head_center = (head_min + head_max) / 2
    head_dims = head_max - head_min

    print(f"[Anatomy] Head Top: {head_top_z:.3f}m, Head Center: {head_center[2]:.3f}m, Neck: {neck_z:.3f}m, Hips: {hips_z:.3f}m, Feet: {feet_z:.3f}m")

    # Build KDTree on body mesh for robust, high-fidelity vertex weight transfer
    body_kd = mathutils.kdtree.KDTree(len(body_obj.data.vertices))
    for i, v in enumerate(body_obj.data.vertices):
        body_kd.insert(v.co, i)
    body_kd.balance()

    def transfer_weights_from_body(target_obj, k=4):
        """Transfer skeletal skinning weights from rigged body mesh using inverse-distance KDTree."""
        vg_map = {}
        for vg in body_obj.vertex_groups:
            vg_map[vg.name] = target_obj.vertex_groups.new(name=vg.name)

        for v_idx, v in enumerate(target_obj.data.vertices):
            results = body_kd.find_n(v.co, k)
            weights = {}
            total_inv_d = 0.0
            for n_co, n_idx, d in results:
                inv_d = 1.0 / max(d, 1e-4)
                total_inv_d += inv_d
                b_vert = body_obj.data.vertices[n_idx]
                for g in b_vert.groups:
                    vg_name = body_obj.vertex_groups[g.group].name
                    weights[vg_name] = weights.get(vg_name, 0.0) + g.weight * inv_d

            for vg_name, w in weights.items():
                norm_w = w / total_inv_d
                if norm_w > 0.001:
                    vg_map[vg_name].add([v_idx], norm_w, "REPLACE")

    # 4. Process Hair
    hair_obj = None
    if config.get("hair") and os.path.exists(config["hair"]):
        tex_hair = extract_texture(config["hair"], "hair_shaded.png")
        before_objs = set(bpy.data.objects)
        bpy.ops.wm.usd_import(filepath=config["hair"])
        hair_obj = [o for o in bpy.data.objects if o.type == "MESH" and o not in before_objs][0]
        hair_obj.name = "Hair"
        hair_obj.data.materials.clear()
        hair_obj.data.materials.append(make_material("M_Hair", tex_hair, 0.6))

        hv = np.array([v.co for v in hair_obj.data.vertices])
        h_min, h_max = hv.min(axis=0), hv.max(axis=0)
        h_center = (h_min + h_max) / 2
        h_dims = h_max - h_min

        # Compute adaptive hair scale based on head skull dimensions
        h_scale_x = (head_dims[0] * 1.10) / h_dims[0]
        h_scale_y = (head_dims[1] * 1.15) / h_dims[1]
        h_scale_z = (head_dims[2] * 1.06) / max(h_dims[2], 1e-3) if len(head_v) else h_scale_x

        hair_obj.scale = (h_scale_x, h_scale_y, h_scale_z)
        hair_obj.location = (
            head_center[0] - (h_center[0] * h_scale_x),
            head_center[1] - (h_center[1] * h_scale_y) - 0.015,
            (head_top_z + 0.015) - (h_max[2] * h_scale_z),
        )

        bpy.context.view_layer.objects.active = hair_obj
        hair_obj.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        hair_obj.select_set(False)

        # Hair is 100% bound to head bone
        hair_vg = hair_obj.vertex_groups.new(name="mixamorig_Head")
        hair_vg.add(list(range(len(hair_obj.data.vertices))), 1.0, "REPLACE")
        print(f"  -> Adaptive Hair Fitted: crown at {head_top_z + 0.015:.3f}m")

    # 5. Fit and Skin Garments (Modular Tops, Bottoms, Suits, Pants, Dresses)
    def fit_and_skin_garment(garment_path, g_type, obj_name, mat_name, tex_name):
        tex_g = extract_texture(garment_path, f"{tex_name}.png")
        before_objs = set(bpy.data.objects)
        bpy.ops.wm.usd_import(filepath=garment_path)
        g_obj = [o for o in bpy.data.objects if o.type == "MESH" and o not in before_objs][0]
        g_obj.name = obj_name
        g_obj.data.materials.clear()
        g_obj.data.materials.append(make_material(mat_name, tex_g, 0.4))

        gv = np.array([v.co for v in g_obj.data.vertices])
        g_min, g_max = gv.min(axis=0), gv.max(axis=0)
        g_dims = g_max - g_min

        # Auto-detect garment type if requested
        if g_type == "auto":
            lower_path = garment_path.lower()
            lower_name = obj_name.lower()
            if any(k in lower_path or k in lower_name for k in ["pants", "trouser", "jean", "bottom"]):
                g_type = "pants"
            elif any(k in lower_path or k in lower_name for k in ["suit", "jacket", "shirt", "top", "vest", "coat"]):
                g_type = "top"
            elif any(k in lower_path or k in lower_name for k in ["skirt"]):
                g_type = "skirt"
            elif any(k in lower_path or k in lower_name for k in ["tube", "dress", "gown", "robe"]):
                g_type = "full_dress"
            else:
                # Aspect ratio & height heuristic
                if (config.get("bottom") or config.get("skirt")) and obj_name == "Cloth":
                    g_type = "top"
                elif g_dims[0] / max(g_dims[2], 1e-3) > 0.75:
                    g_type = "top"
                elif g_dims[2] > 1.2:
                    g_type = "full_dress"
                else:
                    g_type = "skirt"

        print(f"  -> Processing garment '{obj_name}' as type '{g_type}'")

        if g_type in ["top", "shirt", "suit", "jacket"]:
            target_top_z = neck_z + 0.12 # collar right under chin
            target_bot_z = hips_z - 0.15 # jacket hem covers waist/hips
            target_h = target_top_z - target_bot_z
            scale = target_h / g_dims[2]
            g_obj.scale = (scale * 1.08, scale * 1.10, scale)
            loc_z = target_top_z - (g_max[2] * scale)
            g_obj.location = (0.0, -0.015, loc_z)

        elif g_type in ["pants", "trousers"]:
            legs_v = bv[bv[:, 2] <= hips_z + 0.15]
            legs_dims = legs_v.max(axis=0) - legs_v.min(axis=0)
            target_top_z = hips_z + 0.12 # waist
            target_bot_z = feet_z + 0.08 # ankles / above shoes
            target_h = target_top_z - target_bot_z
            p_scale_z = target_h / g_dims[2]
            p_scale_x = (legs_dims[0] * 1.08) / g_dims[0]
            p_scale_y = (legs_dims[1] * 1.25) / g_dims[1]
            g_obj.scale = (p_scale_x, p_scale_y, p_scale_z)
            g_obj.location = (0.0, 0.020, target_bot_z - (g_min[2] * p_scale_z))

        elif g_type in ["skirt", "bottom"]:
            target_top_z = hips_z + 0.10
            target_bot_z = feet_z + 0.20
            target_h = target_top_z - target_bot_z
            scale_z = target_h / g_dims[2]
            scale_xy = scale_z * 1.10
            g_obj.scale = (scale_xy, scale_xy, scale_z)
            g_obj.location = (0.0, 0.01, target_bot_z - (g_min[2] * scale_z))

        elif g_type in ["full_dress", "tube"]:
            target_top_z = neck_z - 0.06 # bustline
            target_bot_z = feet_z
            target_h = target_top_z - target_bot_z
            scale_z = target_h / g_dims[2]
            scale_xy = scale_z * 1.10
            g_obj.scale = (scale_xy, scale_xy, scale_z)
            g_obj.location = (0.0, 0.03, feet_z - (g_min[2] * scale_z))

        bpy.context.view_layer.objects.active = g_obj
        g_obj.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        g_obj.select_set(False)

        # High-fidelity weight transfer from body
        transfer_weights_from_body(g_obj, k=4)
        return g_obj, g_type

    garments = []
    if config.get("cloth"):
        g_obj, gt = fit_and_skin_garment(config["cloth"], config.get("cloth_type", "auto"), "Cloth", "M_Cloth", "cloth_shaded")
        garments.append((g_obj, gt, "M_Cloth", "cloth_shaded.png"))
    if config.get("top"):
        g_obj, gt = fit_and_skin_garment(config["top"], "top", "Top", "M_Top", "top_shaded")
        garments.append((g_obj, gt, "M_Top", "top_shaded.png"))
    if config.get("bottom") or config.get("skirt"):
        b_path = config.get("bottom") or config.get("skirt")
        b_type = "pants" if ("pant" in b_path.lower() or "trouser" in b_path.lower()) else "skirt"
        g_obj, gt = fit_and_skin_garment(b_path, b_type, "Bottom", "M_Bottom", "bottom_shaded")
        garments.append((g_obj, gt, "M_Bottom", "bottom_shaded.png"))

    all_meshes = [body_obj] + ([hair_obj] if hair_obj else []) + [g[0] for g in garments]

    for obj in all_meshes:
        obj.modifiers.clear()
        mod = obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = anim_arm
        if obj != body_obj:
            obj.parent = anim_root
            obj.matrix_parent_inverse = anim_root.matrix_world.inverted()

    for o in list(bpy.data.objects):
        if o.type == "EMPTY" and o != anim_root and o != body_root:
            bpy.data.objects.remove(o, do_unlink=True)

    anim_arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()

    # 6. Export Master .blend, .glb, .fbx
    out_blend = os.path.join(output_dir, "combined_character.blend")
    out_glb = os.path.join(output_dir, "combined_character.glb")
    out_fbx = os.path.join(output_dir, "combined_character.fbx")
    out_usdc = os.path.join(output_dir, "combined_character_skel.usdc")
    out_usdz = os.path.join(output_dir, "combined_character.usdz")

    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", export_animations=True)
    bpy.ops.export_scene.fbx(filepath=out_fbx, add_leaf_bones=False, bake_anim=True)

    # 7. Pixar UsdSkel Stage Composition
    source_stage_path = anim_path if (anim_path and os.path.exists(anim_path)) else body_path
    shutil.copy(source_stage_path, out_usdc)
    stage = Usd.Stage.Open(out_usdc)
    skel_prim = stage.GetPrimAtPath("/root/Armature/Armature")
    skel = UsdSkel.Skeleton(skel_prim)
    joints = list(skel.GetJointsAttr().Get())
    skel_path = skel_prim.GetPath()

    # Build dynamic joint name -> index mapping for arbitrary skeleton hierarchies
    joint_map = {}
    for i, jpath in enumerate(joints):
        leaf = jpath.split("/")[-1]
        joint_map[leaf] = i
        joint_map[jpath] = i

    UsdGeom.Scope.Define(stage, "/root/_materials")

    def author_usd_material(mat_path, tex_rel_path):
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

    # Bind Body
    mat_b = author_usd_material("/root/_materials/M_Body", "./textures/body_shaded.png")
    body_pts, body_fc, body_fi, body_uvs = extract_buffers(body_obj)
    body_prim_usd = stage.GetPrimAtPath("/root/Armature/model/model")
    if body_uvs:
        st_b = UsdGeom.PrimvarsAPI(body_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
        st_b.Set(Vt.Vec2fArray(body_uvs))
    UsdShade.MaterialBindingAPI.Apply(body_prim_usd).Bind(mat_b)

    # Bind Hair
    if hair_obj:
        mat_h = author_usd_material("/root/_materials/M_Hair", "./textures/hair_shaded.png")
        hair_pts, hair_fc, hair_fi, hair_uvs = extract_buffers(hair_obj)
        UsdGeom.Xform.Define(stage, "/root/Armature/hair")
        hair_prim_usd = stage.DefinePrim("/root/Armature/hair/hair", "Mesh")
        hair_mesh_usd = UsdGeom.Mesh(hair_prim_usd)
        hair_mesh_usd.CreatePointsAttr(Vt.Vec3fArray(hair_pts))
        hair_mesh_usd.CreateFaceVertexCountsAttr(Vt.IntArray(hair_fc))
        hair_mesh_usd.CreateFaceVertexIndicesAttr(Vt.IntArray(hair_fi))
        if hair_uvs:
            st_h = UsdGeom.PrimvarsAPI(hair_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
            st_h.Set(Vt.Vec2fArray(hair_uvs))
        h_bind = UsdSkel.BindingAPI.Apply(hair_prim_usd)
        h_bind.CreateSkeletonRel().SetTargets([skel_path])
        h_bind.CreateJointsAttr(joints)
        head_idx = joint_map.get("mixamorig_Head", joint_map.get("Head", 5))
        h_ind = [head_idx, 0, 0, 0, 0, 0, 0, 0] * len(hair_pts)
        h_wt = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] * len(hair_pts)
        ji_h = h_bind.CreateJointIndicesPrimvar(False, 8)
        ji_h.SetInterpolation(UsdGeom.Tokens.vertex)
        ji_h.Set(Vt.IntArray(h_ind))
        jw_h = h_bind.CreateJointWeightsPrimvar(False, 8)
        jw_h.SetInterpolation(UsdGeom.Tokens.vertex)
        jw_h.Set(Vt.FloatArray(h_wt))
        UsdShade.MaterialBindingAPI.Apply(hair_prim_usd).Bind(mat_h)

    # Bind Garments dynamically with full joint mapping
    for g_obj, gt, mat_id, tex_file in garments:
        g_name = g_obj.name.lower()
        mat_g = author_usd_material(f"/root/_materials/{mat_id}", f"./textures/{tex_file}")
        g_pts, g_fc, g_fi, g_uvs = extract_buffers(g_obj)

        UsdGeom.Xform.Define(stage, f"/root/Armature/{g_name}")
        g_prim_usd = stage.DefinePrim(f"/root/Armature/{g_name}/{g_name}", "Mesh")
        g_mesh_usd = UsdGeom.Mesh(g_prim_usd)
        g_mesh_usd.CreatePointsAttr(Vt.Vec3fArray(g_pts))
        g_mesh_usd.CreateFaceVertexCountsAttr(Vt.IntArray(g_fc))
        g_mesh_usd.CreateFaceVertexIndicesAttr(Vt.IntArray(g_fi))
        if g_uvs:
            st_g = UsdGeom.PrimvarsAPI(g_prim_usd).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
            st_g.Set(Vt.Vec2fArray(g_uvs))

        g_bind = UsdSkel.BindingAPI.Apply(g_prim_usd)
        g_bind.CreateSkeletonRel().SetTargets([skel_path])
        g_bind.CreateJointsAttr(joints)

        g_indices = []
        g_weights = []
        for v in g_obj.data.vertices:
            influences = []
            for g in v.groups:
                vg_name = g_obj.vertex_groups[g.group].name
                if vg_name in joint_map and g.weight > 0.001:
                    influences.append((joint_map[vg_name], float(g.weight)))

            influences.sort(key=lambda x: x[1], reverse=True)
            influences = influences[:8]
            tot_w = sum(w for _, w in influences) if influences else 0.0
            if tot_w > 0:
                influences = [(idx, w / tot_w) for idx, w in influences]
            else:
                influences = [(0, 1.0)]

            while len(influences) < 8:
                influences.append((0, 0.0))

            for idx, w in influences:
                g_indices.append(idx)
                g_weights.append(w)

        ji_g = g_bind.CreateJointIndicesPrimvar(False, 8)
        ji_g.SetInterpolation(UsdGeom.Tokens.vertex)
        ji_g.Set(Vt.IntArray(g_indices))
        jw_g = g_bind.CreateJointWeightsPrimvar(False, 8)
        jw_g.SetInterpolation(UsdGeom.Tokens.vertex)
        jw_g.Set(Vt.FloatArray(g_weights))
        UsdShade.MaterialBindingAPI.Apply(g_prim_usd).Bind(mat_g)

    stage.GetRootLayer().Save()

    # Package USDZ
    with zipfile.ZipFile(out_usdz, "w", compression=zipfile.ZIP_STORED) as z:
        z.write(out_usdc, arcname="combined_character.usdc")
        for tf in os.listdir(textures_dir):
            if tf.endswith((".png", ".jpg", ".jpeg")):
                z.write(os.path.join(textures_dir, tf), arcname=f"textures/{tf}")

    print(f"Authored USDZ Package: {out_usdz}")

    # 8. 4-View Turnaround & Verification Renders
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024

    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.95, 0.95, 0.97, 1.0)

    l1 = bpy.data.lights.new("KeyLight", type="SUN")
    l1.energy = 2.5
    l1_obj = bpy.data.objects.new("KeyLight", l1)
    scene.collection.objects.link(l1_obj)
    l1_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(-30))

    l2 = bpy.data.lights.new("FillLight", type="SUN")
    l2.energy = 1.2
    l2_obj = bpy.data.objects.new("FillLight", l2)
    scene.collection.objects.link(l2_obj)
    l2_obj.rotation_euler = (math.radians(40), math.radians(-30), math.radians(150))

    cam_data = bpy.data.cameras.new("Cam")
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # 1. Render 4 Turnaround views in REST pose for reference comparison
    anim_arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    turnaround_views = [
        ("render_front.png", (0, -3.2, 0.95), (math.radians(90), 0, 0)),
        ("render_left.png", (-3.2, 0, 0.95), (math.radians(90), 0, math.radians(-90))),
        ("render_right.png", (3.2, 0, 0.95), (math.radians(90), 0, math.radians(90))),
        ("render_back.png", (0, 3.2, 0.95), (math.radians(90), 0, math.radians(180))),
    ]

    for filename, loc, rot in turnaround_views:
        cam_obj.location = loc
        cam_obj.rotation_euler = rot
        bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(renders_dir, filename)
        bpy.ops.render.render(write_still=True)

    # 2. Render Animation Verification in POSE mode
    anim_arm.data.pose_position = "POSE"
    scene.frame_set(70)
    bpy.context.view_layer.update()
    cam_obj.location = (0, -3.2, 0.95)
    cam_obj.rotation_euler = (math.radians(90), 0, 0)
    scene.render.filepath = os.path.join(renders_dir, "render_anim_greeting.png")
    bpy.ops.render.render(write_still=True)

    print("\nALL BLENDER TASKS COMPLETED SUCCESSFULLY!")


# =============================================================================
# CLI & REFERENCE COMPARISON
# =============================================================================

def build_comparison_sheet(render_img, ref_img, output_sheet):
    """Combine rendered output and reference image side-by-side."""
    try:
        from PIL import Image
        if not (os.path.exists(render_img) and os.path.exists(ref_img)):
            return
        im_render = Image.open(render_img)
        im_ref = Image.open(ref_img)

        target_h = im_render.height
        target_w = int(im_ref.width * (target_h / im_ref.height))
        im_ref_resized = im_ref.resize((target_w, target_h), Image.Resampling.LANCZOS)

        combined = Image.new("RGB", (im_render.width + target_w, target_h), (255, 255, 255))
        combined.paste(im_render, (0, 0))
        combined.paste(im_ref_resized, (im_render.width, 0))
        combined.save(output_sheet)
        print(f"Generated comparison sheet: {output_sheet}")
    except Exception as e:
        print(f"Note: Could not build comparison sheet ({e})")


def main():
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", required=True)
        args, _ = parser.parse_known_args(sys.argv[idx + 1:])
        with open(args.config, "r") as f:
            config = json.load(f)
        execute_in_blender(config)
        return

    parser = argparse.ArgumentParser(description="Automated Modular 3D Model Combiner, Fitter & Rigger")
    parser.add_argument("--body", required=True, help="Base textured character body model (e.g. tests/man_anim_base.usdz)")
    parser.add_argument("--anim", default=None, help="Optional skeletal animation file (e.g. tests/man_anim_hip_hop_dancing.usdc)")
    parser.add_argument("--hair", default=None, help="Hair model (e.g. tests/man_hair.usdz)")
    parser.add_argument("--cloth", default=None, help="Garment model (e.g. tests/man_suit.usdz or tests/woman_tube.usdz)")
    parser.add_argument("--cloth-type", default="auto", choices=["auto", "full_dress", "tube", "top", "shirt", "suit", "skirt", "bottom", "pants"], help="Garment type")
    parser.add_argument("--top", default=None, help="Upper garment model (for two-piece outfits)")
    parser.add_argument("--bottom", default=None, help="Lower garment model (for two-piece outfits, or alias --skirt)")
    parser.add_argument("--skirt", default=None, help="Alias for --bottom")
    parser.add_argument("--ref-front", default=None, help="Optional front reference image")
    parser.add_argument("--ref-left", default=None, help="Optional left side reference image")
    parser.add_argument("--ref-right", default=None, help="Optional right side reference image")
    parser.add_argument("--ref-back", default=None, help="Optional back reference image")
    parser.add_argument("--output-dir", default="./outputs", help="Directory for deliverables & renders (default: ./outputs)")
    parser.add_argument("--blender-path", default=None, help="Custom path to Blender binary")

    # Backward compatibility alias
    parser.add_argument("--body-base", default=None, help="Legacy alias for --body")

    args = parser.parse_args()

    blender_bin = args.blender_path or find_blender()
    if not blender_bin:
        print("ERROR: Blender executable not found. Please install Blender or pass --blender-path.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    body_input = args.body or args.body_base
    config = {
        "body": os.path.abspath(body_input),
        "anim": os.path.abspath(args.anim) if args.anim else None,
        "hair": os.path.abspath(args.hair) if args.hair else None,
        "cloth": os.path.abspath(args.cloth) if args.cloth else None,
        "cloth_type": args.cloth_type,
        "top": os.path.abspath(args.top) if args.top else None,
        "bottom": os.path.abspath(args.bottom or args.skirt) if (args.bottom or args.skirt) else None,
        "output_dir": os.path.abspath(args.output_dir),
    }

    config_path = os.path.join(args.output_dir, "pipeline_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # 1. Run Blender Worker
    run_blender_worker(blender_bin, config_path)

    # 2. Build Side-by-Side Comparison Sheets if reference images are provided
    renders_dir = os.path.join(args.output_dir, "renders")
    if args.ref_front and os.path.exists(args.ref_front):
        build_comparison_sheet(os.path.join(renders_dir, "render_front.png"), os.path.abspath(args.ref_front), os.path.join(renders_dir, "compare_front.png"))
    if args.ref_right and os.path.exists(args.ref_right):
        build_comparison_sheet(os.path.join(renders_dir, "render_right.png"), os.path.abspath(args.ref_right), os.path.join(renders_dir, "compare_right.png"))
    if args.ref_left and os.path.exists(args.ref_left):
        build_comparison_sheet(os.path.join(renders_dir, "render_left.png"), os.path.abspath(args.ref_left), os.path.join(renders_dir, "compare_left.png"))
    if args.ref_back and os.path.exists(args.ref_back):
        build_comparison_sheet(os.path.join(renders_dir, "render_back.png"), os.path.abspath(args.ref_back), os.path.join(renders_dir, "compare_back.png"))

    print("\n" + "=" * 65)
    print(f"ALL DELIVERABLES GENERATED IN: {os.path.abspath(args.output_dir)}")
    print(f"  - Master Blend: {os.path.join(args.output_dir, 'combined_character.blend')}")
    print(f"  - Animated USDZ: {os.path.join(args.output_dir, 'combined_character.usdz')}")
    print(f"  - GLB: {os.path.join(args.output_dir, 'combined_character.glb')}")
    print(f"  - FBX: {os.path.join(args.output_dir, 'combined_character.fbx')}")
    print(f"  - Renders & Comparison Sheets: {renders_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()
