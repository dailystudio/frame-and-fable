#!/usr/bin/env python3
"""
Pose Binder (pose-binder): USDZ to Mixamo & Spatial Editor Pipeline

Automates the conversion of an input .usdz character model for Mixamo auto-rigging/animation,
exports the resulting rigged base mesh and animation files back into USD format (.usdz and .usdc),
and optionally imports them into a Spatial Editor project.

Dynamic Naming Conventions:
  xxx = snake_case of input model name (e.g., mrye)
  yyy = snake_case of selected Mixamo animation (e.g., defeated, jab_cross)

Output Files:
  Step 2: {xxx}_upload_to_mixamo/model.fbx & {xxx}_upload_to_mixamo/textures/
  Step 3: {xxx}_upload_to_mixamo.zip
  Step 4: {xxx}_anim_{yyy}.fbx
  Step 5: {xxx}_anim_base.usdz
  Step 6: {xxx}_anim_{yyy}.usdc (with SkelAnimation track name set to Mixamo animation title)
  Step 7: Imports assets into Spatial Editor project at --import-to-se path (scene: --scene <name>)
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile


def to_snake_case(text):
    """Convert string to snake_case, stripping leading numeric step prefixes if present."""
    text = os.path.splitext(os.path.basename(text))[0]
    # Remove leading digits and separators e.g. '1_model_orig' -> 'model_orig'
    text = re.sub(r"^\d+[_\-\s]*", "", text)
    # Convert camelCase / PascalCase to snake_case
    text = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", text)
    # Replace non-alphanumeric characters with underscores
    text = re.sub(r"[\s\-\W]+", "_", text)
    text = text.strip("_").lower()
    return text if text else "model"


def to_pascal_case(text):
    """Convert string to PascalCase format."""
    text = re.sub(r"[\s\-\_]+", " ", text).strip()
    return "".join(word.capitalize() for word in text.split()) if text else "Default"


def find_blender_binary(custom_path=None):
    """Find the Blender executable path."""
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

    raise RuntimeError(
        "Blender executable not found. Please install Blender or pass --blender-path."
    )


def run_blender_script(blender_bin, script_code, args=None):
    """Run inline Python code in Blender background mode."""
    cmd = [blender_bin, "--background", "--python-expr", script_code]
    if args:
        cmd.append("--")
        cmd.extend(args)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("--- Blender Output ---")
        print(result.stdout)
        print("--- Blender Error ---")
        print(result.stderr)
        raise RuntimeError(f"Blender process failed with exit code {result.returncode}")
    return result.stdout


def step2_convert_usdz_to_fbx(blender_bin, usdz_path, output_dir, model_name):
    """
    Step 2: Import USDZ, unpack textures into {xxx}_upload_to_mixamo/textures/, and export FBX.
    """
    os.makedirs(output_dir, exist_ok=True)
    step2_folder = os.path.join(output_dir, f"{model_name}_upload_to_mixamo")
    os.makedirs(step2_folder, exist_ok=True)
    fbx_output = os.path.join(step2_folder, "model.fbx")

    script = """
import bpy
import sys
import os

usdz_input = sys.argv[-2]
fbx_out = sys.argv[-1]
out_dir = os.path.dirname(fbx_out)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=usdz_input)

# Save blend file in target folder so unpack_all places textures in out_dir/textures/
temp_blend = os.path.join(out_dir, 'temp.blend')
bpy.ops.wm.save_as_mainfile(filepath=temp_blend)

# Unpack embedded textures into textures/ subfolder
bpy.ops.file.unpack_all(method='WRITE_LOCAL')

# Clean up temp blend file
if os.path.exists(temp_blend):
    os.remove(temp_blend)

# Export FBX
bpy.ops.export_scene.fbx(
    filepath=fbx_out,
    use_selection=False,
    embed_textures=False,
    path_mode='AUTO'
)
print(f"Step 2 completed: Exported FBX to {fbx_out}")
"""
    print(f"Executing Step 2: Converting {usdz_path} to Mixamo-compatible FBX...")
    run_blender_script(blender_bin, script, [usdz_path, fbx_output])

    # Remove temporary blend backup files if created
    temp_blend1 = os.path.join(step2_folder, "temp.blend1")
    if os.path.exists(temp_blend1):
        os.remove(temp_blend1)

    print(f"Step 2 finished. FBX created at: {fbx_output}")
    return step2_folder, fbx_output


def step3_package_for_mixamo(step2_folder, fbx_path, output_dir, model_name):
    """
    Step 3: Zip FBX file and textures/ folder into {xxx}_upload_to_mixamo.zip.
    """
    os.makedirs(output_dir, exist_ok=True)
    zip_path = os.path.join(output_dir, f"{model_name}_upload_to_mixamo.zip")

    print(f"Executing Step 3: Packaging {fbx_path} and textures into {zip_path}...")
    textures_dir = os.path.join(step2_folder, "textures")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        # Add FBX
        z.write(fbx_path, arcname=os.path.basename(fbx_path))
        # Add textures directory if present
        if os.path.exists(textures_dir):
            for root, dirs, files in os.walk(textures_dir):
                for file in files:
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, start=step2_folder)
                    z.write(full_p, arcname=rel_p)

    print(f"Step 3 finished. Mixamo package created at: {zip_path}")
    return zip_path


def step4_launch_interactive_mixamo_browser(zip_path, output_dir, model_name, skip_upload=False):
    """
    Step 4: Launch a headful browser, navigate to Mixamo, auto-upload {xxx}_upload_to_mixamo.zip
    (or reuse existing uploaded session if skip_upload=True), wait for user animation download,
    and save to {xxx}_anim_{yyy}.fbx.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Please install with: pip install playwright && playwright install chromium")
        return None, None, None

    zip_path_abs = os.path.abspath(zip_path) if zip_path else None

    print("\n" + "=" * 70)
    print("Launching interactive browser for Mixamo (Step 4)...")
    if skip_upload:
        print("Reusing existing uploaded Mixamo character session.")
        print("Please pick your desired animation action and click DOWNLOAD in Mixamo.")
    else:
        print("The browser will open https://www.mixamo.com/ and auto-upload your zip file.")
        print("Please complete sign-in (if required), adjust rigging markers, pick an animation,")
        print("and click DOWNLOAD in Mixamo.")
    print("=" * 70 + "\n")

    user_data_dir = os.path.expanduser("~/.mixamo_browser_profile")
    os.makedirs(user_data_dir, exist_ok=True)
    # Remove stale Chrome lock files from previous runs
    for lock in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock_p = os.path.join(user_data_dir, lock)
        if os.path.islink(lock_p) or os.path.exists(lock_p):
            try:
                os.unlink(lock_p)
            except Exception:
                pass

    def wait_for_file_completion(filepath, min_size=50000, stability_sec=1):
        """Wait until a downloading file reaches minimum size, has no temporary extension, and stops changing in size."""
        if not os.path.exists(filepath):
            return False

        lower_path = filepath.lower()
        if any(lower_path.endswith(ext) for ext in [".crdownload", ".tmp", ".part", ".download"]):
            return False

        last_size = -1
        stable_count = 0
        for _ in range(15): # wait up to 15 seconds for file size to stabilize
            if os.path.exists(filepath):
                if any(filepath.lower().endswith(ext) for ext in [".crdownload", ".tmp", ".part", ".download"]):
                    return False
                curr_size = os.path.getsize(filepath)
                if curr_size >= min_size and curr_size == last_size and curr_size > 0:
                    stable_count += 1
                    if stable_count >= stability_sec:
                        return True
                else:
                    stable_count = 0
                last_size = curr_size
            time.sleep(1)
        return os.path.exists(filepath) and os.path.getsize(filepath) >= min_size

    def get_mixamo_animation_title(page_obj):
        """Scrape active Mixamo animation title from page DOM."""
        try:
            js_title = page_obj.evaluate("""() => {
                const nodes = document.querySelectorAll('h1, h2, h3, div');
                for (let n of nodes) {
                    if (n.children.length === 0 && n.innerText) {
                        const t = n.innerText.trim();
                        if (t.length > 2 && t.length < 40 && t === t.toUpperCase() && !t.includes('MIXAMO') && !t.includes('CHARACTER')) {
                            return t;
                        }
                    }
                }
                return null;
            }""")
            if js_title:
                return js_title.title()
        except Exception:
            pass
        return "animation"

    detected_fbx_path = [None]
    detected_anim_raw = ["animation"]

    with sync_playwright() as p:
        # Launch Playwright bundled Chromium with persistent context and stealth args
        launch_kwargs = {
            "user_data_dir": user_data_dir,
            "headless": False,
            "accept_downloads": True,
            "ignore_default_args": ["--enable-automation"],
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-profile-error-dialogs",
                "--start-maximized",
                "--no-sandbox"
            ]
        }

        context = p.chromium.launch_persistent_context(**launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()

        # Mask navigator.webdriver
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        anim_downloaded = [False]

        def on_download(download):
            raw_title = os.path.splitext(download.suggested_filename)[0]
            if not raw_title or len(raw_title) > 20 or "-" in raw_title:
                raw_title = get_mixamo_animation_title(page)
            print("\n" + "=" * 70)
            print(f"📥 [EVENT] Browser download event triggered for: '{download.suggested_filename}' (Animation: '{raw_title}')")
            print("⏳ [DOWNLOAD STREAM] Receiving file from Mixamo server... Please wait...")
            print("=" * 70)
            try:
                # download.path() natively blocks until Playwright finishes downloading the file 100%
                file_path = download.path()
                if file_path and os.path.exists(file_path):
                    final_bytes = os.path.getsize(file_path)
                    final_mb = final_bytes / (1024 * 1024)
                    print(f"✅ [DOWNLOAD COMPLETE] Received {final_bytes:,} bytes ({final_mb:.2f} MB)")
                    anim_slug = to_snake_case(raw_title)
                    target_fbx = os.path.join(output_dir, f"{model_name}_anim_{anim_slug}.fbx")
                    shutil.copy2(file_path, target_fbx)
                    print(f"📁 [SAVED] Successfully exported Mixamo animation FBX to:\n   -> {target_fbx}")
                    detected_fbx_path[0] = target_fbx
                    detected_anim_raw[0] = raw_title
                    print("🚪 [SHUTDOWN] Closing browser window in 3 seconds...\n")
                    time.sleep(3)
                    anim_downloaded[0] = True
            except Exception as e:
                print(f"❌ [DOWNLOAD ERROR] Failed to capture download: {e}")

        page.on("download", on_download)

        print("Navigating to https://www.mixamo.com/...")
        page.goto("https://www.mixamo.com/", wait_until="domcontentloaded")

        uploaded = skip_upload
        print("Waiting for Mixamo interface to load...")

        downloads_dir = os.path.expanduser("~/Downloads")
        initial_fbx_files = set(os.listdir(downloads_dir)) if os.path.exists(downloads_dir) else set()

        start_time = time.time()
        print("\n" + "-" * 70)
        if skip_upload:
            print("⌛ Step 4 Active: Reusing currently uploaded Mixamo character session!")
            print("   1. Pick your desired animation action in Mixamo")
            print("   2. Click the red DOWNLOAD button on Mixamo")
        else:
            print("⌛ Step 4 Active: Please interact with Mixamo in the open browser window:")
            print("   1. Adjust rigging markers (chin, wrists, elbows, knees, groin)")
            print("   2. Click NEXT to complete auto-rigging")
            print("   3. Pick your desired animation")
            print("   4. Click the red DOWNLOAD button on Mixamo")
        print("-" * 70 + "\n")

        while not anim_downloaded[0] and (time.time() - start_time < 600):
            if not uploaded and zip_path_abs:
                try:
                    file_input = page.query_selector("input[type='file']")
                    if file_input:
                        print("Found file input! Auto-uploading character package...")
                        file_input.set_input_files(zip_path_abs)
                        uploaded = True
                        print("Character package uploaded into Mixamo! Waiting for manual rigging & animation download...")
                    else:
                        upload_btn = page.query_selector("button:has-text('Upload Character'), [data-testid='upload-character']")
                        if upload_btn and upload_btn.is_visible():
                            print("Clicking 'Upload Character' button...")
                            upload_btn.click()
                            time.sleep(1)
                except Exception:
                    pass

            # Print periodic status hint every 10 seconds
            elapsed = int(time.time() - start_time)
            if elapsed > 0 and elapsed % 10 == 0:
                if skip_upload:
                    print(f"⌛ [{elapsed}s] Waiting in Mixamo: Pick animation -> Click DOWNLOAD")
                else:
                    print(f"⌛ [{elapsed}s] Waiting in Mixamo: Adjust rigging markers -> Click Next -> Pick animation -> Click DOWNLOAD")

            # 1. Check ~/Downloads for any newly downloaded / recently modified FBX or UUID download file
            if os.path.exists(downloads_dir):
                for f in os.listdir(downloads_dir):
                    if not any(f.lower().endswith(ext) for ext in [".crdownload", ".tmp", ".part", ".download"]):
                        new_path = os.path.join(downloads_dir, f)
                        if os.path.isfile(new_path) and (f not in initial_fbx_files or os.path.getmtime(new_path) >= start_time - 30):
                            if (f.lower().endswith(".fbx") or len(f) > 20) and os.path.getsize(new_path) > 100000:
                                if wait_for_file_completion(new_path, min_size=50000, stability_sec=1):
                                    raw_title = os.path.splitext(f)[0] if f.lower().endswith(".fbx") else get_mixamo_animation_title(page)
                                    anim_slug = to_snake_case(raw_title)
                                    target_fbx = os.path.join(output_dir, f"{model_name}_anim_{anim_slug}.fbx")
                                    print(f"\n📥 [DOWNLOAD DETECTED IN ~/Downloads] File: {f} (Animation: '{raw_title}')")
                                    shutil.copy2(new_path, target_fbx)
                                    print(f"Copied {f} ({os.path.getsize(target_fbx):,} bytes) to {target_fbx}")
                                    detected_fbx_path[0] = target_fbx
                                    detected_anim_raw[0] = raw_title
                                    print("Download 100% complete! Closing browser in 3 seconds...")
                                    time.sleep(3)
                                    anim_downloaded[0] = True
                                    break

            # 2. Check Playwright temporary download artifacts directory for blob downloads (UUID files)
            import tempfile
            temp_sys_dir = tempfile.gettempdir()
            try:
                for root_dir, _, files_list in os.walk(temp_sys_dir):
                    if "playwright-artifacts-" in root_dir:
                        for file_name in files_list:
                            full_artifact_path = os.path.join(root_dir, file_name)
                            if os.path.isfile(full_artifact_path) and os.path.getmtime(full_artifact_path) >= start_time - 30:
                                if not any(file_name.lower().endswith(ext) for ext in [".crdownload", ".tmp", ".part", ".download"]):
                                    if os.path.getsize(full_artifact_path) > 100000 and wait_for_file_completion(full_artifact_path, min_size=50000, stability_sec=1):
                                        raw_title = detected_anim_raw[0] if detected_anim_raw[0] and detected_anim_raw[0] != "animation" else get_mixamo_animation_title(page)
                                        anim_slug = to_snake_case(raw_title)
                                        target_fbx = os.path.join(output_dir, f"{model_name}_anim_{anim_slug}.fbx")
                                        print(f"\n📥 [DOWNLOAD DETECTED IN PLAYWRIGHT ARTIFACTS] File: {file_name} (Animation: '{raw_title}')")
                                        shutil.copy2(full_artifact_path, target_fbx)
                                        print(f"Copied artifact ({os.path.getsize(target_fbx):,} bytes) to {target_fbx}")
                                        detected_fbx_path[0] = target_fbx
                                        detected_anim_raw[0] = raw_title
                                        print("Download 100% complete! Closing browser in 3 seconds...")
                                        time.sleep(3)
                                        anim_downloaded[0] = True
                                        break
                    if anim_downloaded[0]:
                        break
            except Exception:
                pass

            # 3. Check output_dir for any newly created animated FBX file
            if os.path.exists(output_dir):
                for f in os.listdir(output_dir):
                    if f.lower().endswith(".fbx") and ("_anim_" in f or "4_model_anim" in f):
                        cand_path = os.path.join(output_dir, f)
                        if os.path.isfile(cand_path) and os.path.getsize(cand_path) > 50000 and os.path.getmtime(cand_path) >= start_time - 30:
                            cand_model, anim_slug, anim_raw_name = parse_anim_info_from_fbx(cand_path, model_name)
                            print(f"\n📥 [ANIMATED FBX DETECTED IN OUTPUT DIR] File: {f}")
                            detected_fbx_path[0] = cand_path
                            detected_anim_raw[0] = anim_raw_name
                            anim_downloaded[0] = True
                            break

            time.sleep(1)

        context.close()

    if detected_fbx_path[0] and os.path.exists(detected_fbx_path[0]):
        anim_slug = to_snake_case(detected_anim_raw[0])
        return detected_fbx_path[0], anim_slug, detected_anim_raw[0]
    return None, None, None


def step5_export_anim_base_usdz(blender_bin, anim_fbx_path, output_dir, model_name):
    """
    Step 5: Process Base Mesh & Shader setup, export to {xxx}_anim_base.usdz.
    - Clear active animation track strip data on armature, reset pose to T-pose
    - Material setup: Link texture to Base Color (instead of Emission), set Emission to 0
    - USD Export: Include Mesh, Animation, Geometry, Armatures, Materials; Exclude Lights, Cameras
    """
    os.makedirs(output_dir, exist_ok=True)
    out_usdz = os.path.join(output_dir, f"{model_name}_anim_base.usdz")

    script = """
import bpy
import sys
import os

fbx_input = sys.argv[-2]
usdz_out = sys.argv[-1]
out_dir = os.path.dirname(usdz_out)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx_input)

# Save temp blend file so texture unpack works relative to working directory
temp_blend = os.path.join(out_dir, 'temp.blend')
bpy.ops.wm.save_as_mainfile(filepath=temp_blend)
bpy.ops.file.unpack_all(method='WRITE_LOCAL')

if os.path.exists(temp_blend):
    os.remove(temp_blend)

# 1. Animation Setup: Set action name, clear active action & NLA tracks, and reset transforms to rest pose (T-pose)
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        if obj.animation_data:
            if obj.animation_data.action:
                obj.animation_data.action.name = "Action_SkeletonAnimation"
            obj.animation_data.action = None
            for track in list(obj.animation_data.nla_tracks):
                obj.animation_data.nla_tracks.remove(track)
        # Reset all pose bone transforms to rest position (T-pose)
        for pbone in obj.pose.bones:
            pbone.location = (0.0, 0.0, 0.0)
            pbone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pbone.rotation_euler = (0.0, 0.0, 0.0)
            pbone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
            pbone.scale = (1.0, 1.0, 1.0)
if bpy.context.view_layer:
    bpy.context.view_layer.update()

# 2. Material Setup:
# Link texture map to Base Color (instead of Emission), set Emission color/strength to 0
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    nt = mat.node_tree
    principled = None
    tex_node = None
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            principled = n
        elif n.type == 'TEX_IMAGE':
            tex_node = n

    if principled:
        emission_input = principled.inputs.get('Emission Color') or principled.inputs.get('Emission')
        base_color_input = principled.inputs.get('Base Color')
        emission_strength_input = principled.inputs.get('Emission Strength')

        if tex_node and emission_input:
            for link in list(nt.links):
                if link.to_socket == emission_input:
                    from_sock = link.from_socket
                    nt.links.remove(link)
                    if base_color_input:
                        nt.links.new(from_sock, base_color_input)

        if emission_input and hasattr(emission_input, 'default_value'):
            if len(emission_input.default_value) == 4:
                emission_input.default_value = (0.0, 0.0, 0.0, 1.0)
            elif len(emission_input.default_value) == 3:
                emission_input.default_value = (0.0, 0.0, 0.0)
        if emission_strength_input:
            emission_strength_input.default_value = 0.0

# 3. USD Export Settings: Include Mesh, Animation, Geometry, Armatures, Materials; Exclude Lights, Cameras
bpy.ops.wm.usd_export(
    filepath=usdz_out,
    export_meshes=True,
    export_animation=True,
    export_armatures=True,
    export_materials=True,
    export_lights=False,
    export_cameras=False
)
print(f"Step 5 completed: Exported USDZ base mesh to {usdz_out}")
"""
    print(f"Executing Step 5: Exporting base mesh USDZ from {anim_fbx_path}...")
    run_blender_script(blender_bin, script, [anim_fbx_path, out_usdz])

    # Clean up temp blend backup
    temp_blend1 = os.path.join(output_dir, "temp.blend1")
    if os.path.exists(temp_blend1):
        os.remove(temp_blend1)

    print(f"Step 5 finished. USDZ created at: {out_usdz}")
    return out_usdz


def step6_export_anim_usdc(blender_bin, anim_fbx_path, output_dir, model_name, anim_slug, anim_raw_name):
    """
    Step 6: Export Animation Data Only to {xxx}_anim_{yyy}.usdc.
    - USD Export Settings: Include Mesh (skeleton topology), Animation, Armatures; Exclude Geometry (normals/uvmaps/colors), Materials, Lights, Cameras
    - SkelAnimation track name set to Mixamo animation title with _SkeletonAnimation suffix
    - Timeline frame_start and frame_end adjusted to match action frame range
    """
    os.makedirs(output_dir, exist_ok=True)
    out_usdc = os.path.join(output_dir, f"{model_name}_anim_{anim_slug}.usdc")

    usd_prim_name = re.sub(r"[\s\-\W]+", "_", anim_raw_name).strip("_")
    action_skel_name = f"{usd_prim_name}_SkeletonAnimation"

    script = """
import bpy
import sys
import os

fbx_input = sys.argv[-3]
usdc_out = sys.argv[-2]
action_name = sys.argv[-1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx_input)

# Set action name to match Mixamo animation title with _SkeletonAnimation suffix, and set scene frame range
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.action:
        act = obj.animation_data.action
        act.name = action_name
        if hasattr(act, 'frame_range'):
            bpy.context.scene.frame_start = int(act.frame_range[0])
            bpy.context.scene.frame_end = int(act.frame_range[1])

# USD Export Settings: Include Mesh, Animation, Armatures; Exclude Geometry attributes, Materials, Lights, Cameras
bpy.ops.wm.usd_export(
    filepath=usdc_out,
    export_meshes=True,
    export_animation=True,
    export_armatures=True,
    export_materials=False,
    export_normals=False,
    export_uvmaps=False,
    export_mesh_colors=False,
    export_lights=False,
    export_cameras=False
)
print(f"Step 6 completed: Exported USDC animation data to {usdc_out}")
"""
    print(f"Executing Step 6: Exporting animation USDC to {out_usdc} with animation track '{action_skel_name}'...")
    run_blender_script(blender_bin, script, [anim_fbx_path, out_usdc, action_skel_name])

    print(f"Step 6 finished. USDC created at: {out_usdc}")
    return out_usdc


def get_skel_anim_path(blender_bin, usdc_path, fallback_name="Action"):
    """Inspect USDC or USDZ file using Blender USD API to get the exact SkelAnimation prim path."""
    clean_fallback = re.sub(r"[\s\-\W]+", "_", fallback_name).strip("_")
    if not usdc_path or not os.path.exists(usdc_path) or not blender_bin:
        return f"/root/Armature/Armature/{clean_fallback}_SkeletonAnimation"

    script = """
import sys
from pxr import Usd, UsdSkel

usdc_file = sys.argv[-1]
stage = Usd.Stage.Open(usdc_file)
found = False
for prim in stage.Traverse():
    if prim.IsA(UsdSkel.Animation) or prim.GetTypeName() == 'SkelAnimation':
        print(f"SKEL_ANIM_PATH:{prim.GetPath()}")
        found = True
        break
if not found:
    print("SKEL_ANIM_PATH:NONE")
"""
    try:
        out = run_blender_script(blender_bin, script, [usdc_path])
        for line in out.splitlines():
            if line.startswith("SKEL_ANIM_PATH:"):
                p = line.split("SKEL_ANIM_PATH:")[1].strip()
                if p and p != "NONE":
                    return p
    except Exception:
        pass

    return f"/root/Armature/Armature/{clean_fallback}_SkeletonAnimation"


def step7_import_to_spatial_editor(se_project_dir, scene_name, model_name, anim_slug, anim_raw_name, base_usdz_path, anim_usdc_path, blender_bin=None):
    """
    Step 7: Import base mesh USDZ and animation USDC into Spatial Editor project.
    - Base model saved as Sources/Assets/{xxx}_without_anim.usdz
    - Animation USDC saved as Sources/Assets/anims/{yyy}.usdc
    - Scene USDA created/updated under Sources/Scenes/{SceneNamePascal}.usda
    """
    se_project_dir = os.path.abspath(os.path.expanduser(se_project_dir))
    scene_name_pascal = to_pascal_case(scene_name)

    print(f"\nExecuting Step 7: Importing assets to Spatial Editor project at '{se_project_dir}' (Scene: {scene_name_pascal})...")

    assets_dir = os.path.join(se_project_dir, "Sources", "Assets")
    anims_dir = os.path.join(assets_dir, "anims")
    scenes_dir = os.path.join(se_project_dir, "Sources", "Scenes")

    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(anims_dir, exist_ok=True)
    os.makedirs(scenes_dir, exist_ok=True)

    dest_base_usdz = os.path.join(assets_dir, f"{model_name}_without_anim.usdz")
    dest_anim_usdc = os.path.join(anims_dir, f"{anim_slug}.usdc")

    if base_usdz_path and os.path.exists(base_usdz_path):
        shutil.copy2(base_usdz_path, dest_base_usdz)
        print(f"Copied base mesh to SE Assets: {dest_base_usdz}")

    if anim_usdc_path and os.path.exists(anim_usdc_path):
        shutil.copy2(anim_usdc_path, dest_anim_usdc)
        print(f"Copied animation to SE Assets anims: {dest_anim_usdc}")

    scene_file = os.path.join(scenes_dir, f"{scene_name_pascal}.usda")

    usd_prim_name = re.sub(r"[\s\-\W]+", "_", anim_raw_name).strip("_")
    anim_struct_code = f"""                def SpatialStruct "{anim_slug}"
                {{
                    custom string[] clipNames = []
                    custom uniform asset file = @../Assets/anims/{anim_slug}.usdc@
                    custom bool isDefault = 0
                    custom string path = "/root/Armature/Armature/{usd_prim_name}_SkeletonAnimation_SkeletonAnimation"
                }}"""

    if not os.path.exists(scene_file):
        scene_content = f"""#usda 1.0
(
    customLayerData = {{
        string Copyright = "Copyright 2022 - 2024 PICO. All rights reserved."
        string RuntimeVersion = "Runtime V6.0.0.0.alpha.0"
        string Version = "Spatial Editor V6.0.1"
    }}
    defaultPrim = "Root"
    metersPerUnit = 1
    upAxis = "Y"
)

def Xform "Root"
{{
    def "{model_name}" (
        prepend references = @../Assets/{model_name}_without_anim.usdz@
    )
    {{
        quatf xformOp:orient = (0.7071068, -0.7071067, 0, 0)
        float3 xformOp:scale = (1, 0.99999994, 0.99999994)
        float3 xformOp:translate = (0, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:orient", "xformOp:scale"]

        over "Armature"
        {{
            def SpatialComponent "AnimationResourceLibraryComponent"
            {{
                uniform token info:id = "AnimationResourceLibraryComponent"

                def SpatialStruct "default_animation"
                {{
                    custom string[] clipNames = []
                    custom bool isDefault = 1
                    custom string path = "/Root/{model_name}/Armature/Armature/Action_SkeletonAnimation"
                }}

{anim_struct_code}
            }}
        }}
    }}
}}
"""
        with open(scene_file, "w") as f:
            f.write(scene_content)
        print(f"Step 7 finished: Created new scene USDA at {scene_file}")
    else:
        with open(scene_file, "r") as f:
            content = f.read()

        model_prim_str = f'def "{model_name}"'
        if model_prim_str not in content:
            root_end = content.rfind("}")
            model_block = f"""    def "{model_name}" (
        prepend references = @../Assets/{model_name}_without_anim.usdz@
    )
    {{
        quatf xformOp:orient = (0.7071068, -0.7071067, 0, 0)
        float3 xformOp:scale = (1, 0.99999994, 0.99999994)
        float3 xformOp:translate = (0, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:orient", "xformOp:scale"]

        over "Armature"
        {{
            def SpatialComponent "AnimationResourceLibraryComponent"
            {{
                uniform token info:id = "AnimationResourceLibraryComponent"

                def SpatialStruct "default_animation"
                {{
                    custom string[] clipNames = []
                    custom bool isDefault = 1
                    custom string path = "/Root/{model_name}/Armature/Armature/Action_SkeletonAnimation"
                }}

{anim_struct_code}
            }}
        }}
    }}
"""
            new_content = content[:root_end] + model_block + content[root_end:]
            with open(scene_file, "w") as f:
                f.write(new_content)
            print(f"Step 7 finished: Added model prim and animation to existing scene USDA at {scene_file}")
        else:
            struct_str = f'def SpatialStruct "{anim_slug}"'
            if struct_str in content:
                pattern = rf'def SpatialStruct "{anim_slug}"[\s\S]*?\n\s*\}}'
                new_content = re.sub(pattern, anim_struct_code.strip(), content)
                with open(scene_file, "w") as f:
                    f.write(new_content)
                print(f"Step 7 finished: Updated animation struct in existing scene USDA at {scene_file}")
            else:
                anim_comp_idx = content.find("AnimationResourceLibraryComponent")
                if anim_comp_idx != -1:
                    idx = content.find("{", anim_comp_idx)
                    depth = 1
                    closing_idx = -1
                    for i in range(idx + 1, len(content)):
                        if content[i] == "{":
                            depth += 1
                        elif content[i] == "}":
                            depth -= 1
                            if depth == 0:
                                closing_idx = i
                                break
                    if closing_idx != -1:
                        new_content = content[:closing_idx] + anim_struct_code + "\n" + content[closing_idx:]
                        with open(scene_file, "w") as f:
                            f.write(new_content)
                        print(f"Step 7 finished: Inserted animation struct into scene USDA at {scene_file}")


def parse_anim_info_from_fbx(anim_fbx_path, model_name=None):
    """
    Extract model_name, anim_slug, and anim_raw_name from FBX filename or path.
    Uses '_anim_' as separator if present in the filename.
    """
    base_stem = os.path.splitext(os.path.basename(anim_fbx_path))[0]
    match = re.match(r"^(.*?)_anim_(.+)$", base_stem, re.IGNORECASE)
    if match:
        extracted_model_name = to_snake_case(match.group(1))
        anim_slug = to_snake_case(match.group(2))
        anim_raw_name = anim_slug.replace("_", " ").strip().title()
        final_model_name = model_name if model_name and model_name not in ["model", "character"] else extracted_model_name
        return final_model_name, anim_slug, anim_raw_name

    anim_slug = to_snake_case(base_stem)
    anim_raw_name = anim_slug.replace("_", " ").strip().title()
    final_model_name = model_name if model_name else anim_slug
    return final_model_name, anim_slug, anim_raw_name


def check_existing_anim_fbx(output_dir, model_name, custom_anim_fbx=None):
    """Find candidate {model_name}_anim_*.fbx files in output_dir or custom_anim_fbx."""
    if custom_anim_fbx and os.path.exists(custom_anim_fbx):
        return [os.path.abspath(custom_anim_fbx)]

    candidates = []
    if os.path.exists(output_dir):
        for f in os.listdir(output_dir):
            if f.lower().endswith(".fbx") and ("_anim_" in f or "4_model_anim" in f):
                p = os.path.abspath(os.path.join(output_dir, f))
                if os.path.isfile(p) and os.path.getsize(p) > 50000:
                    candidates.append(p)
    candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return candidates


def main():
    parser = argparse.ArgumentParser(
        description="Pose Binder (pose-binder): USDZ to Mixamo & Spatial Editor Pipeline"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to input USDZ file (runs full pipeline: Steps 1-6)",
    )
    parser.add_argument(
        "--input-anim",
        type=str,
        default=None,
        help="Path to Mixamo animated FBX file (skips Steps 1-4, runs Steps 5-6)",
    )
    parser.add_argument(
        "--input-mixamo",
        nargs="?",
        const=True,
        default=False,
        help="Reuse existing Mixamo.com character session to select a new animation action (skips Steps 1-3, runs Steps 4-6)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs",
        help="Output directory for generated pipeline artifacts (default: outputs/)",
    )
    parser.add_argument(
        "--import-to-se",
        type=str,
        default=None,
        help="Target Spatial Editor project path (runs Step 7)",
    )
    parser.add_argument(
        "--scene",
        type=str,
        default="Default",
        help="Scene name for Spatial Editor import (converted to PascalCase, default: Default)",
    )
    parser.add_argument(
        "--blender-path",
        type=str,
        default=None,
        help="Path to Blender binary (optional)",
    )
    parser.add_argument(
        "--auto-browser",
        action="store_true",
        default=True,
        help="Automatically open headful browser for Mixamo in Step 4 (default: True)",
    )
    parser.add_argument(
        "--no-auto-browser",
        action="store_false",
        dest="auto_browser",
        help="Disable automatic headful browser for Step 4",
    )

    args = parser.parse_args()

    blender_bin = find_blender_binary(args.blender_path)
    print(f"Using Blender binary at: {blender_bin}")

    out_dir = os.path.abspath(args.output)
    os.makedirs(out_dir, exist_ok=True)

    # Workflow 1: --input-anim (Process provided Mixamo animation FBX directly: Steps 5-6)
    if args.input_anim:
        anim_fbx_path = os.path.abspath(args.input_anim)
        if not os.path.exists(anim_fbx_path):
            sys.exit(f"Error: Animated FBX file '{args.input_anim}' not found.")

        given_model = to_snake_case(args.input) if args.input else None
        model_name, anim_slug, anim_raw_name = parse_anim_info_from_fbx(anim_fbx_path, given_model)

        print(f"Pipeline target model name: '{model_name}'")
        print(f"\nProcessing provided Mixamo animation FBX: {anim_fbx_path}")
        print(f"Detected animation slug: '{anim_slug}', title: '{anim_raw_name}'")

        base_usdz_path = step5_export_anim_base_usdz(blender_bin, anim_fbx_path, out_dir, model_name)
        anim_usdc_path = step6_export_anim_usdc(blender_bin, anim_fbx_path, out_dir, model_name, anim_slug, anim_raw_name)

        if args.import_to_se:
            step7_import_to_spatial_editor(
                se_project_dir=args.import_to_se,
                scene_name=args.scene,
                model_name=model_name,
                anim_slug=anim_slug,
                anim_raw_name=anim_raw_name,
                base_usdz_path=base_usdz_path,
                anim_usdc_path=anim_usdc_path,
                blender_bin=blender_bin,
            )
        print("\nPipeline execution finished successfully!")
        return

    # Workflow 2: --input-mixamo (Reuse uploaded Mixamo character session: Steps 4-6)
    if args.input_mixamo:
        if args.input:
            model_name = to_snake_case(args.input)
        elif isinstance(args.input_mixamo, str):
            model_name = to_snake_case(args.input_mixamo)
        else:
            candidates = check_existing_anim_fbx(out_dir, "model", None)
            if candidates:
                model_name = parse_anim_info_from_fbx(candidates[0])[0]
            else:
                model_name = "character"

        print(f"Pipeline target model name: '{model_name}'")
        anim_fbx_path, anim_slug, anim_raw_name = step4_launch_interactive_mixamo_browser(
            zip_path=None, output_dir=out_dir, model_name=model_name, skip_upload=True
        )
        if not anim_fbx_path:
            sys.exit("Error: Failed to capture Mixamo animation download.")

        base_usdz_path = step5_export_anim_base_usdz(blender_bin, anim_fbx_path, out_dir, model_name)
        anim_usdc_path = step6_export_anim_usdc(blender_bin, anim_fbx_path, out_dir, model_name, anim_slug, anim_raw_name)

        if args.import_to_se:
            step7_import_to_spatial_editor(
                se_project_dir=args.import_to_se,
                scene_name=args.scene,
                model_name=model_name,
                anim_slug=anim_slug,
                anim_raw_name=anim_raw_name,
                base_usdz_path=base_usdz_path,
                anim_usdc_path=anim_usdc_path,
                blender_bin=blender_bin,
            )
        print("\nPipeline execution finished successfully!")
        return

    # Workflow 3: --input (Full USDZ -> Mixamo -> USD -> SE pipeline: Steps 1-6)
    if args.input:
        usdz_path = os.path.abspath(args.input)
        if not os.path.exists(usdz_path):
            sys.exit(f"Error: Input USDZ file '{args.input}' not found.")

        model_name = to_snake_case(usdz_path)
        print(f"Pipeline target model name: '{model_name}'")

        step2_folder, fbx_out = step2_convert_usdz_to_fbx(blender_bin, usdz_path, out_dir, model_name)
        zip_path = step3_package_for_mixamo(step2_folder, fbx_out, out_dir, model_name)

        anim_fbx_path = None
        if args.auto_browser and os.path.exists(zip_path):
            anim_fbx_path, anim_slug, anim_raw_name = step4_launch_interactive_mixamo_browser(zip_path, out_dir, model_name)

        if not anim_fbx_path:
            sys.exit("Error: Failed to capture Mixamo animation download.")

        base_usdz_path = step5_export_anim_base_usdz(blender_bin, anim_fbx_path, out_dir, model_name)
        anim_usdc_path = step6_export_anim_usdc(blender_bin, anim_fbx_path, out_dir, model_name, anim_slug, anim_raw_name)

        if args.import_to_se:
            step7_import_to_spatial_editor(
                se_project_dir=args.import_to_se,
                scene_name=args.scene,
                model_name=model_name,
                anim_slug=anim_slug,
                anim_raw_name=anim_raw_name,
                base_usdz_path=base_usdz_path,
                anim_usdc_path=anim_usdc_path,
                blender_bin=blender_bin,
            )
        print("\nPipeline execution finished successfully!")
        return

    sys.exit(
        "Error: Please specify one of the input flags:\n"
        "  --input <usdz_file>     : Convert USDZ, upload to Mixamo, and export USD/SE assets\n"
        "  --input-anim <fbx_file> : Process existing Mixamo FBX and export USD/SE assets\n"
        "  --input-mixamo          : Select new action for already-uploaded Mixamo character"
    )


if __name__ == "__main__":
    main()
