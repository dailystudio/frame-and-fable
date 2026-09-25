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


def ensure_playwright_browsers_path():
    """Ensure PLAYWRIGHT_BROWSERS_PATH points to the persistent system cache directory.

    When packaged into a standalone binary with PyInstaller, sys.frozen is True.
    Playwright's default behavior for frozen binaries is to force PLAYWRIGHT_BROWSERS_PATH="0",
    which expects browsers to be located inside the temporary _MEIPASS extraction directory.
    Setting this explicitly ensures Playwright accesses the system/user browser cache.
    """
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or os.environ.get("PLAYWRIGHT_BROWSERS_PATH") == "0":
        if sys.platform == "darwin":
            cache_dir = os.path.expanduser("~/Library/Caches/ms-playwright")
        elif sys.platform == "win32":
            cache_dir = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
        else:
            cache_dir = os.path.expanduser("~/.cache/ms-playwright")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = cache_dir


ensure_playwright_browsers_path()


def to_snake_case(text):
    """Convert string to snake_case, stripping leading numeric step prefixes if present."""
    if "/" in text or "\\" in text:
        _, ext = os.path.splitext(text)
        if ext and (os.path.exists(text) or ext.lower() in [".usdz", ".usdc", ".fbx", ".obj", ".blend", ".zip"]):
            text = os.path.splitext(os.path.basename(text))[0]
        else:
            text = text.replace("/", " ").replace("\\", " ")
    else:
        text = os.path.splitext(text)[0]
    # Remove leading numeric step prefixes like '1_model' or '01-mesh', but preserve numbers in titles
    text = re.sub(r"^\d+[_\-]\s*", "", text)
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


def load_mixamo_catalog(custom_path=None):
    """Load Mixamo motion catalog items from JSON.

    Checks:
      1. custom_path (if provided)
      2. MIXAMO_CATALOG_PATH environment variable
      3. ~/aisandbox/mixamo/catalog.json
      4. ./catalog.json in script or working directory
    Returns (items_list, source_path_or_None)
    """
    candidates = []
    if custom_path:
        candidates.append(os.path.abspath(os.path.expanduser(custom_path)))
    env_path = os.environ.get("MIXAMO_CATALOG_PATH")
    if env_path:
        candidates.append(os.path.abspath(os.path.expanduser(env_path)))
    candidates.append(os.path.expanduser("~/aisandbox/mixamo/catalog.json"))
    script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
    candidates.append(os.path.join(script_dir, "catalog.json"))

    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            try:
                import json
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data.get("items", [])
                if items:
                    return items, p
            except Exception:
                pass
    return [], None


def resolve_pose_item(query, items=None):
    """Resolve a user-provided pose query (name, partial name, slug, or motion_id) against catalog.

    Returns dict:
      {"name": <canonical title>, "slug": <snake_case_slug>, "id": <motion_id_or_None>, "match_type": <type>}
    """
    q = query.strip()
    if not q:
        return None
    q_lower = q.lower()
    q_slug = to_snake_case(q)

    if items:
        # 1. Exact name match (case-insensitive)
        for it in items:
            name = (it.get("name") or "").strip()
            if name.lower() == q_lower:
                return {"name": name, "slug": to_snake_case(name), "id": it.get("id"), "match_type": "exact_name"}

        # 2. Exact slug match
        for it in items:
            name = (it.get("name") or "").strip()
            if to_snake_case(name) == q_slug:
                return {"name": name, "slug": to_snake_case(name), "id": it.get("id"), "match_type": "exact_slug"}

        # 3. ID / motion_id match
        for it in items:
            it_id = (it.get("id") or "").lower()
            it_m_id = (it.get("motion_id") or "").lower()
            if q_lower in (it_id, it_m_id):
                name = (it.get("name") or "").strip()
                return {"name": name, "slug": to_snake_case(name), "id": it.get("id"), "match_type": "id"}

        # 4. Prefix match on name
        for it in items:
            name = (it.get("name") or "").strip()
            if name.lower().startswith(q_lower):
                return {"name": name, "slug": to_snake_case(name), "id": it.get("id"), "match_type": "prefix_name"}

        # 5. Substring match on name (prefer shortest name to get closest match)
        sub_matches = [it for it in items if q_lower in (it.get("name") or "").lower()]
        if sub_matches:
            sub_matches.sort(key=lambda x: len(x.get("name") or ""))
            best = sub_matches[0]
            name = best.get("name", "").strip()
            return {"name": name, "slug": to_snake_case(name), "id": best.get("id"), "match_type": "substring_name"}

        # 6. Description match
        desc_matches = [it for it in items if q_lower in (it.get("description") or "").lower()]
        if desc_matches:
            best = desc_matches[0]
            name = best.get("name", "").strip()
            return {"name": name, "slug": to_snake_case(name), "id": best.get("id"), "match_type": "description"}

    # Fallback when not found in catalog or no catalog available
    title = q.title()
    return {"name": title, "slug": to_snake_case(q), "id": None, "match_type": "fallback"}


def resolve_poses(queries, catalog_path=None):
    """Resolve a list of pose queries against the Mixamo catalog.

    Supports comma-separated strings (e.g. ['walking, defeated']).
    Returns (resolved_pose_dicts, catalog_items, catalog_source_path)
    """
    items, src_path = load_mixamo_catalog(catalog_path)
    resolved = []
    seen_slugs = set()
    raw_list = []
    for q in queries:
        for part in q.split(","):
            part_clean = part.strip()
            if part_clean:
                raw_list.append(part_clean)

    for q in raw_list:
        item = resolve_pose_item(q, items)
        if item and item["slug"] not in seen_slugs:
            seen_slugs.add(item["slug"])
            resolved.append(item)
    return resolved, items, src_path


def auto_select_pose_in_mixamo(page, pose_name):
    """Automate searching, selecting, and clicking DOWNLOAD for pose_name in Mixamo UI.

    Returns True if successfully clicked download trigger.
    """
    try:
        # Dismiss any open modal dialog (e.g. from previous download)
        try:
            cancel_btn = page.query_selector('.asset-download-modal button:has-text("CANCEL"), .modal button:has-text("CANCEL")')
            if cancel_btn and cancel_btn.is_visible():
                cancel_btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        search_input = page.query_selector('input[type="search"], input[placeholder="Search"], input[name="search"]')
        if not search_input or not search_input.is_visible():
            return False

        print(f"🔍 Searching Mixamo catalog for '{pose_name}'...")
        search_input.click()
        search_input.fill("")
        search_input.fill(pose_name)
        search_input.press("Enter")
        page.wait_for_timeout(2000)

        # Collect matching animation cards
        cards = page.query_selector_all(".product.product-animation")
        if not cards:
            print(f"⚠️ No animation cards returned for query '{pose_name}'.")
            return False

        chosen_card = None
        # Priority 1: Exact match on title
        for c in cards:
            try:
                title = c.inner_text().split("\n")[0].strip()
                if title.lower() == pose_name.lower():
                    chosen_card = (c, title)
                    break
            except Exception:
                pass

        # Priority 2: Starts with
        if not chosen_card:
            for c in cards:
                try:
                    title = c.inner_text().split("\n")[0].strip()
                    if title.lower().startswith(pose_name.lower()):
                        chosen_card = (c, title)
                        break
                except Exception:
                    pass

        # Priority 3: First returned card
        if not chosen_card and cards:
            try:
                title = cards[0].inner_text().split("\n")[0].strip()
                chosen_card = (cards[0], title)
            except Exception:
                pass

        if not chosen_card:
            return False

        card_elem, card_title = chosen_card
        print(f"🎯 Selecting animation card: '{card_title}'...")
        card_elem.click()
        page.wait_for_timeout(3000)

        # Click top-level DOWNLOAD button
        dl_btn = page.query_selector("button:has-text('DOWNLOAD')")
        if dl_btn and dl_btn.is_visible():
            print("Clicking 'DOWNLOAD' button on Mixamo...")
            dl_btn.click()
            page.wait_for_timeout(1500)

            # Click modal DOWNLOAD button
            modal_dl = page.query_selector(
                ".asset-download-modal button:has-text('DOWNLOAD'), .modal-footer button.btn-primary:has-text('DOWNLOAD')"
            )
            if modal_dl and modal_dl.is_visible():
                print(f"Clicking modal confirmation DOWNLOAD for '{card_title}'...")
                modal_dl.click()
                return True
    except Exception as e:
        print(f"Notice: Auto-selection for '{pose_name}' had non-fatal error: {e}. Interactive fallback available.")
    return False


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


def step4_launch_interactive_mixamo_browser(
    zip_path,
    output_dir,
    model_name,
    skip_upload=False,
    target_poses=None,
    catalog_path=None,
):
    """
    Step 4: Launch a headful browser, navigate to Mixamo, auto-upload {xxx}_upload_to_mixamo.zip
    (or reuse existing uploaded session if skip_upload=True), select and download requested animation(s),
    and save to {xxx}_anim_{yyy}.fbx.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Please install with: pip install playwright && playwright install chromium")
        return (None, None, None) if target_poses is None else []

    zip_path_abs = os.path.abspath(zip_path) if zip_path else None

    print("\n" + "=" * 70)
    print("Launching interactive browser for Mixamo (Step 4)...")
    if target_poses:
        print(f"Target poses to bind ({len(target_poses)}):")
        for i, tp in enumerate(target_poses):
            print(f"  [{i + 1}] {tp['name']} (slug: {tp['slug']})")
    elif skip_upload:
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

    downloaded_results = []
    current_pose_idx = [0]
    current_download_finished = [False]
    last_downloaded_fbx = [None]

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

        try:
            context = p.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as exc:
            err_text = str(exc)
            if "Executable doesn't exist" in err_text or "playwright install" in err_text:
                print("⚠️ Playwright Chromium browser missing or path changed. Automatically installing...")
                installed = False
                try:
                    from playwright._impl._driver import compute_driver_executable
                    driver_exec, driver_cli = compute_driver_executable()
                    res = subprocess.run([driver_exec, driver_cli, "install", "chromium"], env=os.environ)
                    if res.returncode == 0:
                        installed = True
                except Exception:
                    pass
                if not installed:
                    try:
                        res = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], env=os.environ)
                        if res.returncode == 0:
                            installed = True
                    except Exception:
                        pass
                if installed:
                    print("✅ Playwright Chromium downloaded successfully. Retrying browser launch...")
                    context = p.chromium.launch_persistent_context(**launch_kwargs)
                else:
                    raise
            else:
                raise
        page = context.pages[0] if context.pages else context.new_page()

        # Mask navigator.webdriver
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        def on_download(download):
            idx = current_pose_idx[0]
            curr_pose = target_poses[idx] if (target_poses and idx < len(target_poses)) else None
            sugg_name = download.suggested_filename
            if curr_pose:
                raw_title = curr_pose["name"]
                anim_slug = curr_pose["slug"]
            else:
                raw_title = os.path.splitext(sugg_name)[0]
                if not raw_title or len(raw_title) > 20 or "-" in raw_title:
                    raw_title = get_mixamo_animation_title(page)
                anim_slug = to_snake_case(raw_title)

            print("\n" + "=" * 70)
            print(f"📥 [EVENT] Browser download event triggered for: '{sugg_name}' (Animation: '{raw_title}')")
            print("⏳ [DOWNLOAD STREAM] Receiving file from Mixamo server... Please wait...")
            print("=" * 70)
            try:
                # download.path() natively blocks until Playwright finishes downloading the file 100%
                file_path = download.path()
                if file_path and os.path.exists(file_path):
                    final_bytes = os.path.getsize(file_path)
                    final_mb = final_bytes / (1024 * 1024)
                    print(f"✅ [DOWNLOAD COMPLETE] Received {final_bytes:,} bytes ({final_mb:.2f} MB)")
                    target_fbx = os.path.join(output_dir, f"{model_name}_anim_{anim_slug}.fbx")
                    shutil.copy2(file_path, target_fbx)
                    print(f"📁 [SAVED] Successfully exported Mixamo animation FBX to:\n   -> {target_fbx}")
                    last_downloaded_fbx[0] = (target_fbx, anim_slug, raw_title)
                    current_download_finished[0] = True
            except Exception as e:
                print(f"❌ [DOWNLOAD ERROR] Failed to capture download: {e}")

        page.on("download", on_download)

        print("Navigating to https://www.mixamo.com/...")
        page.goto("https://www.mixamo.com/", wait_until="domcontentloaded")

        uploaded = skip_upload
        print("Waiting for Mixamo interface to load...")

        downloads_dir = os.path.expanduser("~/Downloads")
        initial_fbx_files = set(os.listdir(downloads_dir)) if os.path.exists(downloads_dir) else set()

        total_poses = len(target_poses) if target_poses else 1

        for p_idx in range(total_poses):
            current_pose_idx[0] = p_idx
            current_download_finished[0] = False
            last_downloaded_fbx[0] = None
            curr_pose = target_poses[p_idx] if target_poses else None
            pose_name = curr_pose["name"] if curr_pose else "Animation"
            pose_selected = False

            print("\n" + "-" * 70)
            if target_poses:
                print(f"🎯 Step 4 Active [{p_idx + 1}/{total_poses}]: Binding pose '{pose_name}'")
                if p_idx > 0:
                    print("   Reusing currently uploaded & rigged character on Mixamo (skipping upload).")
            elif skip_upload:
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

            start_time = time.time()
            pose_timeout = 600 if (p_idx == 0 and not skip_upload) else 180

            while not current_download_finished[0] and (time.time() - start_time < pose_timeout):
                if not uploaded and zip_path_abs:
                    try:
                        file_input = page.query_selector("input[type='file']")
                        if file_input:
                            print("Found file input! Auto-uploading character package...")
                            file_input.set_input_files(zip_path_abs)
                            uploaded = True
                            print("Character package uploaded into Mixamo! Waiting for manual rigging & animation selection...")
                        else:
                            upload_btn = page.query_selector("button:has-text('Upload Character'), [data-testid='upload-character']")
                            if upload_btn and upload_btn.is_visible():
                                print("Clicking 'Upload Character' button...")
                                upload_btn.click()
                                time.sleep(1)
                    except Exception:
                        pass

                # If target pose is specified and not selected yet, check if search bar is visible
                if curr_pose and not pose_selected:
                    try:
                        search_input = page.query_selector('input[type="search"], input[placeholder="Search"], input[name="search"]')
                        ar_modal = page.query_selector('.autorigger-modal, [class*="autorigger"]')
                        if search_input and search_input.is_visible() and not ar_modal:
                            if auto_select_pose_in_mixamo(page, curr_pose["name"]):
                                pose_selected = True
                    except Exception:
                        pass

                # Print periodic status hint every 10 seconds
                elapsed = int(time.time() - start_time)
                if elapsed > 0 and elapsed % 10 == 0:
                    if curr_pose:
                        print(f"⌛ [{elapsed}s] Processing pose [{p_idx + 1}/{total_poses}] '{pose_name}'...")
                    elif skip_upload:
                        print(f"⌛ [{elapsed}s] Waiting in Mixamo: Pick animation -> Click DOWNLOAD")
                    else:
                        print(f"⌛ [{elapsed}s] Waiting in Mixamo: Adjust rigging markers -> Click Next -> Pick animation -> Click DOWNLOAD")

                # 1. Check ~/Downloads for newly downloaded file
                if os.path.exists(downloads_dir):
                    for f in os.listdir(downloads_dir):
                        if not any(f.lower().endswith(ext) for ext in [".crdownload", ".tmp", ".part", ".download"]):
                            new_path = os.path.join(downloads_dir, f)
                            if os.path.isfile(new_path) and (f not in initial_fbx_files or os.path.getmtime(new_path) >= start_time - 30):
                                if (f.lower().endswith(".fbx") or len(f) > 20) and os.path.getsize(new_path) > 100000:
                                    if wait_for_file_completion(new_path, min_size=50000, stability_sec=1):
                                        if curr_pose:
                                            raw_title = curr_pose["name"]
                                            anim_slug = curr_pose["slug"]
                                        else:
                                            raw_title = os.path.splitext(f)[0] if f.lower().endswith(".fbx") else get_mixamo_animation_title(page)
                                            anim_slug = to_snake_case(raw_title)
                                        target_fbx = os.path.join(output_dir, f"{model_name}_anim_{anim_slug}.fbx")
                                        print(f"\n📥 [DOWNLOAD DETECTED IN ~/Downloads] File: {f} (Animation: '{raw_title}')")
                                        shutil.copy2(new_path, target_fbx)
                                        print(f"Copied {f} ({os.path.getsize(target_fbx):,} bytes) to {target_fbx}")
                                        last_downloaded_fbx[0] = (target_fbx, anim_slug, raw_title)
                                        current_download_finished[0] = True
                                        break

                if current_download_finished[0]:
                    break

                # 2. Check Playwright temporary download artifacts directory
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
                                            if curr_pose:
                                                raw_title = curr_pose["name"]
                                                anim_slug = curr_pose["slug"]
                                            else:
                                                raw_title = get_mixamo_animation_title(page)
                                                anim_slug = to_snake_case(raw_title)
                                            target_fbx = os.path.join(output_dir, f"{model_name}_anim_{anim_slug}.fbx")
                                            print(f"\n📥 [DOWNLOAD DETECTED IN PLAYWRIGHT ARTIFACTS] File: {file_name} (Animation: '{raw_title}')")
                                            shutil.copy2(full_artifact_path, target_fbx)
                                            print(f"Copied artifact ({os.path.getsize(target_fbx):,} bytes) to {target_fbx}")
                                            last_downloaded_fbx[0] = (target_fbx, anim_slug, raw_title)
                                            current_download_finished[0] = True
                                            break
                            if current_download_finished[0]:
                                break
                except Exception:
                    pass

                if current_download_finished[0]:
                    break

                # 3. Check output_dir for any newly created animated FBX file
                if os.path.exists(output_dir):
                    for f in os.listdir(output_dir):
                        if f.lower().endswith(".fbx") and ("_anim_" in f or "4_model_anim" in f):
                            cand_path = os.path.join(output_dir, f)
                            if os.path.isfile(cand_path) and os.path.getsize(cand_path) > 50000 and os.path.getmtime(cand_path) >= start_time - 30:
                                cand_model, anim_slug, anim_raw_name = parse_anim_info_from_fbx(cand_path, model_name)
                                if curr_pose:
                                    anim_slug = curr_pose["slug"]
                                    anim_raw_name = curr_pose["name"]
                                print(f"\n📥 [ANIMATED FBX DETECTED IN OUTPUT DIR] File: {f}")
                                last_downloaded_fbx[0] = (cand_path, anim_slug, anim_raw_name)
                                current_download_finished[0] = True
                                break

                time.sleep(1)

            if current_download_finished[0] and last_downloaded_fbx[0]:
                downloaded_results.append(last_downloaded_fbx[0])
                print(f"✅ Pose [{p_idx + 1}/{total_poses}] ('{pose_name}') completed.")
                if p_idx + 1 < total_poses:
                    print(f"⏳ Waiting 3 seconds before next pose...\n")
                    time.sleep(3)
                    # Close any leftover modal dialog before next pose
                    try:
                        modal_cancel = page.query_selector('.modal button:has-text("CANCEL"), .modal button.close')
                        if modal_cancel and modal_cancel.is_visible():
                            modal_cancel.click()
                    except Exception:
                        pass
            else:
                print(f"⚠️ Pose [{p_idx + 1}/{total_poses}] ('{pose_name}') download timed out.")

        print("🚪 Closing browser window in 2 seconds...\n")
        time.sleep(2)
        context.close()

    if target_poses is None:
        return downloaded_results[0] if downloaded_results else (None, None, None)
    return downloaded_results


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
    skel_anim_path = get_skel_anim_path(blender_bin, anim_usdc_path, fallback_name=usd_prim_name)
    anim_struct_code = f"""                def SpatialStruct "{anim_slug}"
                {{
                    custom string[] clipNames = []
                    custom uniform asset file = @../Assets/anims/{anim_slug}.usdc@
                    custom bool isDefault = 0
                    custom string path = "{skel_anim_path}"
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


def process_downloaded_animations(downloaded, blender_bin, out_dir, model_name, se_project_dir, scene_name):
    """
    Process downloaded Mixamo FBX file(s):
    - Export base mesh USDZ only once (Step 5) -> {model_name}_anim_base.usdz
    - Export animation USDC for each downloaded motion (Step 6) -> {model_name}_anim_{slug}.usdc
    - Deploy base mesh and all motion tracks to Spatial Editor (Step 7)
    """
    if not downloaded:
        sys.exit("Error: Failed to capture Mixamo animation download.")

    print(f"\n" + "=" * 70)
    print(f"Processing {len(downloaded)} animation(s) for model '{model_name}'...")
    print("=" * 70)

    # Step 5: Export base USDZ only once
    base_usdz_path = None
    existing_base_usdz = os.path.join(out_dir, f"{model_name}_anim_base.usdz")
    if os.path.exists(existing_base_usdz):
        print(f"\nReusing existing base mesh USDZ: {existing_base_usdz}")
        base_usdz_path = existing_base_usdz
    else:
        first_fbx = downloaded[0][0]
        base_usdz_path = step5_export_anim_base_usdz(blender_bin, first_fbx, out_dir, model_name)

    # Step 6: Export USDC animation tracks for each downloaded pose
    usdc_paths = []
    for idx, (anim_fbx_path, anim_slug, anim_raw_name) in enumerate(downloaded):
        print(f"\n[{idx + 1}/{len(downloaded)}] Processing animation: '{anim_raw_name}' ({anim_slug})")
        anim_usdc_path = step6_export_anim_usdc(
            blender_bin, anim_fbx_path, out_dir, model_name, anim_slug, anim_raw_name
        )
        usdc_paths.append(anim_usdc_path)

        if se_project_dir:
            step7_import_to_spatial_editor(
                se_project_dir=se_project_dir,
                scene_name=scene_name,
                model_name=model_name,
                anim_slug=anim_slug,
                anim_raw_name=anim_raw_name,
                base_usdz_path=base_usdz_path if idx == 0 else None,
                anim_usdc_path=anim_usdc_path,
                blender_bin=blender_bin,
            )

    print(f"\n" + "=" * 70)
    print(f"🎉 Pipeline execution finished successfully!")
    print(f"Summary:")
    print(f"  • Base Mesh USDZ (1): {base_usdz_path}")
    print(f"  • Motion Tracks USDC ({len(usdc_paths)}):")
    for up in usdc_paths:
        print(f"     - {up}")
    if se_project_dir:
        print(f"  • Deployed to Spatial Editor project: {se_project_dir}")
    print("=" * 70 + "\n")


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
        "--poses",
        "--pose",
        nargs="+",
        type=str,
        default=None,
        help="One or more Mixamo pose/animation names or IDs to bind (e.g. --poses walking punching 'jab cross')",
    )
    parser.add_argument(
        "--catalog",
        type=str,
        default=None,
        help="Custom path to Mixamo catalog.json (default: ~/aisandbox/mixamo/catalog.json)",
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

    # Resolve requested poses from catalog if specified
    resolved_poses = None
    if args.poses:
        raw_queries = []
        for p in args.poses:
            for part in p.split(","):
                part_clean = part.strip()
                if part_clean:
                    raw_queries.append(part_clean)

        resolved_poses, catalog_items, catalog_src = resolve_poses(raw_queries, args.catalog)
        if catalog_items:
            print(f"Loaded {len(catalog_items)} motions from Mixamo catalog at: {catalog_src}")
        else:
            print("Notice: Mixamo catalog not found. Will use input pose names directly.")

        print(f"\nResolved {len(resolved_poses)} target pose(s) to bind:")
        for idx, rp in enumerate(resolved_poses):
            match_str = f" [Catalog ID: {rp['id']}]" if rp.get("id") else ""
            print(f"  {idx + 1}. '{rp['name']}' (slug: {rp['slug']}){match_str}")
        print()

        # If --poses is specified without --input or --input-anim, assume --input-mixamo to reuse existing character
        if not args.input and not args.input_anim and not args.input_mixamo:
            print("Notice: --poses specified without --input. Enabling --input-mixamo to reuse existing Mixamo session.")
            args.input_mixamo = True

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

        downloaded = [(anim_fbx_path, anim_slug, anim_raw_name)]
        process_downloaded_animations(downloaded, blender_bin, out_dir, model_name, args.import_to_se, args.scene)
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
        res = step4_launch_interactive_mixamo_browser(
            zip_path=None,
            output_dir=out_dir,
            model_name=model_name,
            skip_upload=True,
            target_poses=resolved_poses,
            catalog_path=args.catalog,
        )
        downloaded = res if isinstance(res, list) else ([res] if res and res[0] else [])
        process_downloaded_animations(downloaded, blender_bin, out_dir, model_name, args.import_to_se, args.scene)
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

        downloaded = []
        if args.auto_browser and os.path.exists(zip_path):
            res = step4_launch_interactive_mixamo_browser(
                zip_path=zip_path,
                output_dir=out_dir,
                model_name=model_name,
                skip_upload=False,
                target_poses=resolved_poses,
                catalog_path=args.catalog,
            )
            downloaded = res if isinstance(res, list) else ([res] if res and res[0] else [])

        process_downloaded_animations(downloaded, blender_bin, out_dir, model_name, args.import_to_se, args.scene)
        return

    sys.exit(
        "Error: Please specify one of the input flags:\n"
        "  --input <usdz_file>     : Convert USDZ, upload to Mixamo, and export USD/SE assets\n"
        "  --input-anim <fbx_file> : Process existing Mixamo FBX and export USD/SE assets\n"
        "  --input-mixamo          : Select new action for already-uploaded Mixamo character\n"
        "  --poses <p1> [p2...]    : Specify Mixamo poses to bind (auto-matches catalog at ~/aisandbox/mixamo/)"
    )


if __name__ == "__main__":
    main()
