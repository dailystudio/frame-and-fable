#!/usr/bin/env bash
# ==============================================================================
# Frame & Fable - System-Wide Craft Skill Installer
# ==============================================================================
# Installs Antigravity / Agent skills and CLI binaries system-wide so agents and
# developers can invoke any craft tool from any directory.
#
# Dependencies are installed into an external system location outside the workspace:
#   ~/.local/share/frame-and-fable/venvs/<craft-name>/
#
# Fully compatible with macOS default bash (3.2+), modern bash (4/5), and zsh.
#
# Supports:
#   - Automated virtual environment creation & dependency installation (via uv or pip)
#   - Interactive menu (install all or select crafts)
#   - Non-interactive CLI flags (--all, specific craft names, or numbers)
#   - Target skill discovery across ~/.gemini/config/skills, ~/.agents/skills, ~/.claude/skills
#   - Global CLI wrappers in ~/.local/bin (pointing to external venvs)
#   - Workspace venv cleanup (--clean-workspace-venvs)
#   - Status inspection (--list) and uninstallation (--uninstall, --uninstall-all)
# ==============================================================================

set -e

# Resolve repository root directory
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for terminal output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

# Default paths
BIN_DIR="${HOME}/.local/bin"
VENVS_BASE_DIR="${HOME}/.local/share/frame-and-fable/venvs"

DEFAULT_SKILL_DIRS=(
  "${HOME}/.gemini/config/skills"
  "${HOME}/.agents/skills"
)

# Optional existing agent skill directories to sync if present
OPTIONAL_SKILL_DIRS=(
  "${HOME}/.gemini/skills"
  "${HOME}/.claude/skills"
)

# Installation modes
INSTALL_MODE="link"
INSTALL_BIN_TYPE="wrapper" # "wrapper" (default shell script) or "binary" (compiled standalone native Mach-O binary via PyInstaller)
SKIP_DEPS=false
REINSTALL_DEPS=false

# Crafts Definition Table
CRAFT_KEYS=(
  "audio-craft"
  "image-craft"
  "storybook-craft"
  "video-craft"
  "human-composer"
  "model-composer"
  "model-creator"
  "pose-binder"
  "rig-binder"
  "asset-generator"
)

get_craft_subdir() {
  case "$1" in
    "audio-craft") echo "common/audio-craft" ;;
    "image-craft") echo "common/image-craft" ;;
    "storybook-craft") echo "common/storybook-craft" ;;
    "video-craft") echo "common/video-craft" ;;
    "human-composer") echo "xr/human-composer" ;;
    "model-composer") echo "xr/model-composer" ;;
    "model-creator") echo "xr/model-creator" ;;
    "pose-binder") echo "xr/pose-binder" ;;
    "rig-binder") echo "xr/rig-binder" ;;
    "asset-generator") echo "xr/asset-generator" ;;
  esac
}

get_craft_script() {
  case "$1" in
    "audio-craft") echo "gemini-audio.py" ;;
    "image-craft") echo "gemini-image.py" ;;
    "storybook-craft") echo "storybook.py" ;;
    "video-craft") echo "gemini-video.py" ;;
    "human-composer") echo "human-composer.py" ;;
    "model-composer") echo "auto_combine_models.py" ;;
    "model-creator") echo "model_creator.py" ;;
    "pose-binder") echo "pose_binder.py" ;;
    "rig-binder") echo "rig_binder.py" ;;
    "asset-generator") echo "asset_generator.py" ;;
  esac
}

get_craft_primary_bin() {
  case "$1" in
    "audio-craft") echo "gemini-audio" ;;
    "image-craft") echo "gemini-image" ;;
    "storybook-craft") echo "storybook" ;;
    "video-craft") echo "gemini-video" ;;
    "human-composer") echo "human-composer" ;;
    "model-composer") echo "model-composer" ;;
    "model-creator") echo "model-creator" ;;
    "pose-binder") echo "pose-binder" ;;
    "rig-binder") echo "rig-binder" ;;
    "asset-generator") echo "asset-generator" ;;
  esac
}

get_craft_aliases() {
  case "$1" in
    "audio-craft") echo "gemini-audio audio-craft" ;;
    "image-craft") echo "gemini-image image-craft" ;;
    "storybook-craft") echo "storybook storybook-craft" ;;
    "video-craft") echo "gemini-video video-craft" ;;
    "human-composer") echo "human-composer" ;;
    "model-composer") echo "model-composer auto_combine_models" ;;
    "model-creator") echo "model-creator model_creator" ;;
    "pose-binder") echo "pose-binder pose_binder" ;;
    "rig-binder") echo "rig-binder rig_binder" ;;
    "asset-generator") echo "asset-generator generate-asset asset-craft character-pipeline" ;;
  esac
}

get_craft_desc() {
  case "$1" in
    "audio-craft") echo "AI voice, speech (Gemini TTS), sound effects, and Lyria music" ;;
    "image-craft") echo "AI image generation & editing (Nano Banana 2 / Pro, Imagen 3, sprites)" ;;
    "storybook-craft") echo "Storybook Markdown media tagging, prompt synthesis & asset pipeline" ;;
    "video-craft") echo "Cinematic video generation & interpolation with synchronized audio (Veo 3.1)" ;;
    "human-composer") echo "Headless Blender 3D character garment & hair USDZ binding & inspection" ;;
    "model-composer") echo "3D character combiner, UsdSkel animation composition & QC verification" ;;
    "model-creator") echo "Generative 3D asset creator from text/images (Hyper3D / Rodin Gen-2.5)" ;;
    "pose-binder") echo "USDZ to Adobe Mixamo auto-rigging & PICO Spatial Editor pipeline" ;;
    "rig-binder") echo "Universal 3D/2D mesh rigging & skinning (Shadow Puppet & Humanoid-65)" ;;
    "asset-generator") echo "End-to-end 3D asset generation (characters, props, 4K textures, rigging)" ;;
  esac
}

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

print_banner() {
  echo -e "${BOLD}${CYAN}"
  echo "╔══════════════════════════════════════════════════════════════════════╗"
  echo "║          Frame & Fable - System-Wide Craft Skill Installer           ║"
  echo "╚══════════════════════════════════════════════════════════════════════╝"
  echo -e "${RESET}"
}

print_help() {
  print_banner
  echo -e "${BOLD}Usage:${RESET}"
  echo "  ./install-skills.sh [OPTIONS] [CRAFTS...]"
  echo ""
  echo -e "${BOLD}Options:${RESET}"
  echo "  -a, --all               Install all 9 crafts system-wide with external dependencies"
  echo "  -b, --binary            Compile crafts into standalone native binaries (Mach-O) via PyInstaller (tamper-proof against AI modifications)"
  echo "  -s, --select <items>    Install comma- or space-separated list of crafts by name or index"
  echo "  -l, --list              List available crafts and their current installation status"
  echo "  -u, --uninstall [items] Uninstall specified crafts (or all if none specified)"
  echo "  --uninstall-all         Uninstall all crafts, CLI wrappers, and external venvs"
  echo "  --skip-deps             Skip virtual environment dependency setup (link skills/wrappers only)"
  echo "  --reinstall-deps        Force recreation of external virtual environments and re-install packages"
  echo "  --clean-workspace-venvs Remove existing .venv folders located inside workspace craft directories"
  echo "  --copy                  Copy skill files instead of creating symlinks (default: symlink)"
  echo "  --venvs-dir <path>      Directory for external virtual environments (default: ~/.local/share/frame-and-fable/venvs)"
  echo "  --bin-dir <path>        Directory for CLI wrapper binaries (default: ~/.local/bin)"
  echo "  --target <path>         Custom target directory for skills"
  echo "  -h, --help              Show this help documentation"
  echo ""
  echo -e "${BOLD}Examples:${RESET}"
  echo "  ./install-skills.sh --all                        # Install all 9 crafts & dependencies (shell wrappers)"
  echo "  ./install-skills.sh --binary --all               # Install all 9 crafts as compiled native binaries (tamper-proof)"
  echo "  ./install-skills.sh -b audio-craft image-craft   # Install selected crafts as native binaries"
  echo "  ./install-skills.sh audio-craft image-craft      # Install selected crafts by name"
  echo "  ./install-skills.sh 1 2 4                        # Install selected crafts by index"
  echo "  ./install-skills.sh -s 1,2,7,9                   # Comma-separated selection"
  echo "  ./install-skills.sh --clean-workspace-venvs      # Clean .venv folders from workspace"
  echo "  ./install-skills.sh --list                       # Inspect install status"
  echo "  ./install-skills.sh                              # Launch interactive selector menu"
  echo ""
}

# Resolve active skill directories
get_target_skill_dirs() {
  local dirs=()
  for d in "${DEFAULT_SKILL_DIRS[@]}"; do
    dirs+=("$d")
  done
  for d in "${OPTIONAL_SKILL_DIRS[@]}"; do
    if [ -d "$d" ]; then
      dirs+=("$d")
    fi
  done
  if [ -n "$CUSTOM_TARGET_DIR" ]; then
    dirs=("$CUSTOM_TARGET_DIR")
  fi
  echo "${dirs[@]}"
}

# Check if craft skill is installed
is_craft_installed() {
  local craft="$1"
  local primary_dir="${DEFAULT_SKILL_DIRS[0]}/$craft"
  if [ -e "$primary_dir" ]; then
    return 0
  else
    return 1
  fi
}

# Check if craft external venv is installed
is_venv_installed() {
  local craft="$1"
  local venv_python="${VENVS_BASE_DIR}/${craft}/bin/python"
  if [ -f "$venv_python" ]; then
    return 0
  else
    return 1
  fi
}

# Inspect CLI binary type in ~/.local/bin
get_cli_status() {
  local craft="$1"
  local primary_bin=$(get_craft_primary_bin "$craft")
  local target_bin="${BIN_DIR}/${primary_bin}"
  if [ -f "$target_bin" ] || [ -L "$target_bin" ]; then
    local ftype=$(file -b "$target_bin" 2>/dev/null || echo "")
    if [[ "$ftype" =~ Mach-O|ELF|executable[[:space:]]arch|PE32 ]]; then
      echo -e "\033[0;32mBinary   \033[0m"
    elif [[ "$ftype" =~ script|text ]]; then
      echo -e "\033[0;36mWrapper  \033[0m"
    else
      echo -e "\033[0;32mInstalled\033[0m"
    fi
  else
    echo -e "\033[0;33mNot inst.\033[0m"
  fi
}

list_crafts() {
  print_banner
  echo -e "${BOLD}Available Crafts in Frame & Fable:${RESET}"
  echo "──────────────────────────────────────────────────────────────────────────────────────────"
  printf " %-3s | %-16s | %-9s | %-9s | %-9s | %s\n" "#" "Craft Name" "Skill" "Venv" "CLI Mode" "Description"
  echo "──────────────────────────────────────────────────────────────────────────────────────────"
  local i=1
  for key in "${CRAFT_KEYS[@]}"; do
    local desc=$(get_craft_desc "$key")
    local skill_status="\033[0;33mNot inst.\033[0m"
    local venv_status="\033[0;33mNot inst.\033[0m"
    local cli_status=$(get_cli_status "$key")

    if is_craft_installed "$key"; then
      skill_status="\033[0;32mInstalled\033[0m"
    fi
    if is_venv_installed "$key"; then
      venv_status="\033[0;32mReady    \033[0m"
    fi

    printf " [%d] | %-16s | %-19b | %-19b | %-19b | %s\n" "$i" "$key" "$skill_status" "$venv_status" "$cli_status" "$desc"
    i=$((i + 1))
  done
  echo "──────────────────────────────────────────────────────────────────────────────────────────"
  echo ""
  echo -e "Skills target locations:"
  local target_dirs=($(get_target_skill_dirs))
  for td in "${target_dirs[@]}"; do
    echo "  - $td"
  done
  echo -e "External venvs directory: ${VENVS_BASE_DIR}"
  echo -e "CLI Binaries directory:   ${BIN_DIR}"
  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "  ${YELLOW}Warning: $BIN_DIR is not currently in your \$PATH.${RESET}"
  else
    echo -e "  ${GREEN}✓ $BIN_DIR is present in your \$PATH.${RESET}"
  fi
  echo ""
}

# Setup dedicated external virtual environment and install dependencies
setup_craft_venv() {
  local craft="$1"
  local craft_subdir=$(get_craft_subdir "$craft")
  local craft_path="${REPO_DIR}/${craft_subdir}"
  local req_file="${craft_path}/requirements.txt"
  local venv_dir="${VENVS_BASE_DIR}/${craft}"
  local venv_python="${venv_dir}/bin/python"

  if [ "$SKIP_DEPS" = true ] && [ -f "$venv_python" ]; then
    echo -e "  ${CYAN}ℹ${RESET} Skipping dependency setup (--skip-deps specified)."
    return 0
  fi

  if [ "$REINSTALL_DEPS" = true ] && [ -d "$venv_dir" ]; then
    echo -e "  ${YELLOW}↻${RESET} Removing existing venv for re-installation..."
    rm -rf "$venv_dir"
  fi

  mkdir -p "${VENVS_BASE_DIR}"

  # Create virtualenv if not exists
  if [ ! -f "$venv_python" ]; then
    echo -e "  ${CYAN}⚙${RESET} Creating external virtualenv at: ${venv_dir}"
    if command -v uv >/dev/null 2>&1; then
      uv venv "${venv_dir}" --python python3 --quiet
    else
      python3 -m venv "${venv_dir}"
    fi
  fi

  # Install requirements
  if [ -f "$req_file" ] && [ -s "$req_file" ]; then
    echo -e "  ${CYAN}📦${RESET} Installing dependencies from: ${craft_subdir}/requirements.txt"
    if command -v uv >/dev/null 2>&1; then
      uv pip install --python "${venv_python}" -r "${req_file}" --quiet
    else
      "${venv_python}" -m pip install -q --upgrade pip
      "${venv_python}" -m pip install -q -r "${req_file}"
    fi
    echo -e "  ${GREEN}✓${RESET} Dependencies installed successfully."
  fi

  # Specific post-install steps
  if [ "$craft" = "pose-binder" ] || [ "$craft" = "asset-generator" ]; then
    echo -e "  ${CYAN}🎭${RESET} Configuring & verifying Playwright Chromium browser..."
    local browsers_cache_dir
    if [[ "$OSTYPE" == "darwin"* ]]; then
      browsers_cache_dir="${HOME}/Library/Caches/ms-playwright"
    elif [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "win32"* ]]; then
      browsers_cache_dir="${LOCALAPPDATA:-$HOME/AppData/Local}/ms-playwright"
    else
      browsers_cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/ms-playwright"
    fi
    export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$browsers_cache_dir}"
    mkdir -p "${PLAYWRIGHT_BROWSERS_PATH}"

    local pb_python="${VENVS_BASE_DIR}/pose-binder/bin/python"
    local runner_python="${venv_python}"
    if [ "$craft" = "asset-generator" ] && [ -f "${pb_python}" ]; then
      runner_python="${pb_python}"
    fi

    if "${runner_python}" -m playwright --version >/dev/null 2>&1; then
      echo -e "  ${CYAN}⬇${RESET} Installing Chromium browser into: ${PLAYWRIGHT_BROWSERS_PATH}..."
      if PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH}" "${runner_python}" -m playwright install chromium; then
        echo -e "  ${GREEN}✓${RESET} Playwright Chromium browser successfully installed and verified."
      else
        echo -e "  ${YELLOW}⚠${RESET} Playwright standard install returned non-zero, trying with system dependencies..."
        PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH}" "${runner_python}" -m playwright install --with-deps chromium || true
      fi
    fi
  fi
}

# Create wrapper script in ~/.local/bin pointing to external venv
install_cli_wrapper() {
  local craft="$1"
  local bin_name="$2"
  local craft_subdir=$(get_craft_subdir "$craft")
  local script_file=$(get_craft_script "$craft")
  local target_bin="${BIN_DIR}/${bin_name}"
  local venv_python="${VENVS_BASE_DIR}/${craft}/bin/python"

  mkdir -p "${BIN_DIR}"
  rm -f "${target_bin}"

  local extra_env=""
  if [ "$craft" = "pose-binder" ] || [ "$craft" = "asset-generator" ]; then
    extra_env=$(cat <<'ENV_EOF'
# Ensure Playwright browser cache location is preserved
if [ -z "${PLAYWRIGHT_BROWSERS_PATH}" ] || [ "${PLAYWRIGHT_BROWSERS_PATH}" = "0" ]; then
  if [[ "$OSTYPE" == "darwin"* ]]; then
    export PLAYWRIGHT_BROWSERS_PATH="${HOME}/Library/Caches/ms-playwright"
  elif [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "win32"* ]]; then
    export PLAYWRIGHT_BROWSERS_PATH="${LOCALAPPDATA:-$HOME/AppData/Local}/ms-playwright"
  else
    export PLAYWRIGHT_BROWSERS_PATH="${XDG_CACHE_HOME:-$HOME/.cache}/ms-playwright"
  fi
fi
ENV_EOF
)
  fi

  cat <<EOF > "${target_bin}"
#!/usr/bin/env bash
# Auto-generated CLI wrapper for Frame & Fable craft: ${craft} (${bin_name})
REPO_DIR="${REPO_DIR}"
CRAFT_DIR="\${REPO_DIR}/${craft_subdir}"
VENV_PYTHON="${venv_python}"
SCRIPT="\${CRAFT_DIR}/${script_file}"

${extra_env}

if [ ! -f "\${VENV_PYTHON}" ]; then
  echo "[Error] External virtual environment for ${craft} not found at: \${VENV_PYTHON}" >&2
  echo "Please install dependencies by running:" >&2
  echo "  \${REPO_DIR}/install-skills.sh ${craft}" >&2
  exit 1
fi

if [ ! -f "\${SCRIPT}" ]; then
  echo "[Error] Craft script not found at: \${SCRIPT}" >&2
  exit 1
fi

exec "\${VENV_PYTHON}" "\${SCRIPT}" "\$@"
EOF

  chmod +x "${target_bin}"
}

# Compile craft script into standalone native Mach-O binary using PyInstaller
compile_craft_binary() {
  local craft="$1"
  local craft_subdir=$(get_craft_subdir "$craft")
  local craft_path="${REPO_DIR}/${craft_subdir}"
  local script_file=$(get_craft_script "$craft")
  local primary_bin=$(get_craft_primary_bin "$craft")
  local venv_dir="${VENVS_BASE_DIR}/${craft}"
  local venv_pyinstaller="${venv_dir}/bin/pyinstaller"
  local venv_python="${venv_dir}/bin/python"
  local dist_dir="${venv_dir}/dist"
  local build_dir="${venv_dir}/build"

  # Ensure virtualenv exists
  if [ ! -f "${venv_python}" ]; then
    echo -e "  ${RED}[Error] Virtual environment not found for ${craft} at: ${venv_dir}${RESET}" >&2
    return 1
  fi

  # Ensure PyInstaller is installed in the craft's virtual environment
  if [ ! -f "${venv_pyinstaller}" ]; then
    echo -e "  ${CYAN}⚙${RESET} Installing PyInstaller in ${craft} external virtualenv..."
    if command -v uv >/dev/null 2>&1; then
      uv pip install --python "${venv_python}" pyinstaller --quiet
    else
      "${venv_python}" -m pip install -q pyinstaller
    fi
  fi

  echo -e "  ${CYAN}🔨${RESET} Compiling standalone native binary: ${BOLD}${primary_bin}${RESET}..."
  mkdir -p "${dist_dir}" "${build_dir}"

  local pyi_args=(
    "--onefile"
    "--clean"
    "--paths" "${craft_path}"
    "--distpath" "${dist_dir}"
    "--workpath" "${build_dir}"
    "--specpath" "${build_dir}"
    "--name" "${primary_bin}"
  )

  # Craft-specific inclusions
  case "$craft" in
    "human-composer")
      if [ -d "${craft_path}/core" ]; then
        pyi_args+=("--add-data" "${craft_path}/core:core")
      fi
      ;;
    "model-creator")
      if [ -d "${craft_path}/core" ]; then
        pyi_args+=("--add-data" "${craft_path}/core:core")
      fi
      if [ -d "${craft_path}/providers" ]; then
        pyi_args+=("--add-data" "${craft_path}/providers:providers")
      fi
      ;;
    "rig-binder")
      if [ -f "${craft_path}/rig_engine.py" ]; then
        pyi_args+=("--add-data" "${craft_path}/rig_engine.py:.")
      fi
      if [ -d "${craft_path}/presets" ]; then
        pyi_args+=("--add-data" "${craft_path}/presets:presets")
      fi
      ;;
    "model-composer")
      if [ -f "${craft_path}/auto_combine_models.py" ]; then
        pyi_args+=("--add-data" "${craft_path}/auto_combine_models.py:.")
      fi
      if [ -f "${craft_path}/combine_character_pipeline.py" ]; then
        pyi_args+=("--add-data" "${craft_path}/combine_character_pipeline.py:.")
      fi
      ;;
    "pose-binder")
      pyi_args+=("--collect-all" "playwright")
      ;;
  esac

  local log_file="${build_dir}/pyinstaller.log"
  if ! "${venv_pyinstaller}" "${pyi_args[@]}" "${craft_path}/${script_file}" > "${log_file}" 2>&1; then
    echo -e "  ${RED}✗ Failed to compile binary for ${craft}. See log: ${log_file}${RESET}" >&2
    return 1
  fi

  if [ ! -f "${dist_dir}/${primary_bin}" ]; then
    echo -e "  ${RED}✗ Binary output not found at: ${dist_dir}/${primary_bin}${RESET}" >&2
    return 1
  fi

  # Copy to BIN_DIR
  mkdir -p "${BIN_DIR}"
  rm -f "${BIN_DIR}/${primary_bin}"
  cp -f "${dist_dir}/${primary_bin}" "${BIN_DIR}/${primary_bin}"
  chmod 555 "${BIN_DIR}/${primary_bin}" # Read-only & executable: immune to AI file modifications

  # Setup alias symlinks
  local aliases=($(get_craft_aliases "$craft"))
  for alias_name in "${aliases[@]}"; do
    if [ "$alias_name" != "$primary_bin" ]; then
      rm -f "${BIN_DIR}/${alias_name}"
      ln -sf "${primary_bin}" "${BIN_DIR}/${alias_name}"
      echo -e "  ${GREEN}✓${RESET} Linked alias binary: ${BIN_DIR}/${alias_name} -> ${primary_bin}"
    fi
  done

  # Clean build artifacts to save disk space
  rm -rf "${build_dir}"

  echo -e "  ${GREEN}✓${RESET} Installed native binary: ${BIN_DIR}/${primary_bin} (read-only/tamper-proof)"
}

# Install single craft
install_single_craft() {
  local craft="$1"
  local craft_subdir=$(get_craft_subdir "$craft")
  local craft_path="${REPO_DIR}/${craft_subdir}"
  local skill_md="${craft_path}/SKILL.md"

  if [ ! -f "$skill_md" ]; then
    echo -e "${RED}[Error] SKILL.md not found for ${craft} at: ${skill_md}${RESET}" >&2
    return 1
  fi

  local install_type_label="CLI wrappers"
  if [ "$INSTALL_BIN_TYPE" = "binary" ]; then
    install_type_label="standalone native binary"
  fi

  echo -e "${BOLD}${BLUE}▸ Installing craft:${RESET} ${BOLD}${craft}${RESET} (${install_type_label})"
  echo -e "  Source: ${craft_path}"

  # 1. Setup external virtual environment & dependencies
  setup_craft_venv "$craft"

  # 2. Link or copy skill files into system agent directories
  local target_dirs=($(get_target_skill_dirs))
  for target_dir in "${target_dirs[@]}"; do
    mkdir -p "${target_dir}"
    local dest="${target_dir}/${craft}"

    if [ "$INSTALL_BIN_TYPE" = "binary" ]; then
      # Binary mode: copy ONLY SKILL.md and documentation. Never expose Python source files to AI!
      rm -rf "${dest}"
      mkdir -p "${dest}"
      cp "${skill_md}" "${dest}/SKILL.md"
      if [ -f "${craft_path}/README.md" ]; then
        cp "${craft_path}/README.md" "${dest}/README.md"
      fi
      chmod 444 "${dest}/SKILL.md" 2>/dev/null || true
      echo -e "  ${GREEN}✓${RESET} Installed protected skill (SKILL.md only) to: ${dest}"
    elif [ "$INSTALL_MODE" = "copy" ]; then
      rm -rf "${dest}"
      mkdir -p "${dest}"
      cp -R "${craft_path}"/* "${dest}"/ 2>/dev/null || cp "${skill_md}" "${dest}"/
      echo -e "  ${GREEN}✓${RESET} Copied skill to: ${dest}"
    else
      # Symlink (default)
      ln -sfn "${craft_path}" "${dest}"
      echo -e "  ${GREEN}✓${RESET} Linked skill to: ${dest}"
    fi
  done

  # 3. Install CLI binary or wrapper
  if [ "$INSTALL_BIN_TYPE" = "binary" ]; then
    compile_craft_binary "$craft"
  else
    local aliases=($(get_craft_aliases "$craft"))
    for alias_name in "${aliases[@]}"; do
      install_cli_wrapper "$craft" "$alias_name"
      echo -e "  ${GREEN}✓${RESET} Created CLI wrapper: ${BIN_DIR}/${alias_name}"
    done
  fi

  # 4. Install preset tools (e.g. image-craft multiviews)
  install_craft_presets "$craft"

  echo ""
}

# Install companion preset CLI tools (e.g., image-craft multi-view generators, pose-binder fix-chin-jaw)
install_craft_presets() {
  local craft="$1"
  local craft_subdir=$(get_craft_subdir "$craft")
  local craft_path="${REPO_DIR}/${craft_subdir}"
  local presets_dir="${craft_path}/presets"

  case "$craft" in
    "image-craft")
      if [ -d "$presets_dir" ]; then
        local preset_scripts=(
          "model-multiviews.sh:model-multiviews"
          "t-pose-multiviews.sh:t-pose-multiviews"
          "garment-multiviews.sh:garment-multiviews"
        )
        for item in "${preset_scripts[@]}"; do
          local src_file="${presets_dir}/${item%%:*}"
          local bin_name="${item##*:}"
          local target_bin="${BIN_DIR}/${bin_name}"

          if [ -f "$src_file" ]; then
            mkdir -p "${BIN_DIR}"
            rm -f "$target_bin"
            cp -f "$src_file" "$target_bin"
            chmod 555 "$target_bin" # Read-only & executable (tamper-proof against AI)
            echo -e "  ${GREEN}✓${RESET} Installed preset tool: ${BIN_DIR}/${bin_name} (read-only)"
          fi
        done
      fi
      ;;
    "pose-binder")
      local src_script="${craft_path}/fix_chin_jaw_weights.py"
      local target_bin="${BIN_DIR}/fix-chin-jaw"
      local venv_python="${VENVS_BASE_DIR}/${craft}/bin/python"

      if [ -f "$src_script" ]; then
        mkdir -p "${BIN_DIR}"
        if [ "$INSTALL_MODE" = "binary" ]; then
          local dist_dir="${craft_path}/dist"
          local build_dir="${craft_path}/build"
          local venv_pyinstaller="${VENVS_BASE_DIR}/${craft}/bin/pyinstaller"
          if [ -x "$venv_pyinstaller" ]; then
            echo -e "  ${CYAN}🔨${RESET} Compiling companion native binary: ${BOLD}fix-chin-jaw${RESET}..."
            local pyi_args=(
              "--onefile"
              "--clean"
              "--collect-all" "pxr"
              "--distpath" "${dist_dir}"
              "--workpath" "${build_dir}/fix-chin-jaw"
              "--specpath" "${build_dir}/fix-chin-jaw"
              "--name" "fix-chin-jaw"
            )
            "${venv_pyinstaller}" "${pyi_args[@]}" "${src_script}" > "${build_dir}/pyi_fcj.log" 2>&1 || true
            if [ -f "${dist_dir}/fix-chin-jaw" ]; then
              rm -f "${target_bin}"
              cp -f "${dist_dir}/fix-chin-jaw" "${target_bin}"
              chmod 555 "${target_bin}"
              rm -rf "${build_dir}/fix-chin-jaw" "${dist_dir}/fix-chin-jaw"
              echo -e "  ${GREEN}✓${RESET} Installed native companion binary: ${target_bin} (read-only)"
            fi
          fi
        fi

        # Fallback to CLI wrapper if binary mode was not requested or failed
        if [ ! -f "${target_bin}" ]; then
          cat <<EOF > "$target_bin"
#!/usr/bin/env bash
# Auto-generated CLI wrapper for Frame & Fable companion tool: fix-chin-jaw
VENV_PYTHON="${venv_python}"
SCRIPT="${src_script}"

if [ -x "\${VENV_PYTHON}" ]; then
  exec "\${VENV_PYTHON}" "\${SCRIPT}" "\$@"
else
  exec python3 "\${SCRIPT}" "\$@"
fi
EOF
          chmod 555 "$target_bin"
          echo -e "  ${GREEN}✓${RESET} Installed companion CLI wrapper: ${target_bin} (read-only)"
        fi
      fi
      ;;
  esac
}

uninstall_craft_presets() {
  local craft="$1"
  case "$craft" in
    "image-craft")
      local preset_bins=("model-multiviews" "t-pose-multiviews" "garment-multiviews")
      for pb in "${preset_bins[@]}"; do
        local target_bin="${BIN_DIR}/${pb}"
        if [ -f "$target_bin" ] || [ -L "$target_bin" ]; then
          rm -f "$target_bin"
          echo -e "  ${GREEN}✓${RESET} Removed preset tool: ${target_bin}"
        fi
      done
      ;;
    "pose-binder")
      local target_bin="${BIN_DIR}/fix-chin-jaw"
      if [ -f "$target_bin" ] || [ -L "$target_bin" ]; then
        rm -f "$target_bin"
        echo -e "  ${GREEN}✓${RESET} Removed companion tool: ${target_bin}"
      fi
      ;;
  esac
}

# Uninstall craft
uninstall_single_craft() {
  local craft="$1"
  echo -e "${YELLOW}▸ Uninstalling craft: ${craft}${RESET}"

  # Remove skill links/copies
  local target_dirs=($(get_target_skill_dirs))
  for target_dir in "${target_dirs[@]}"; do
    local dest="${target_dir}/${craft}"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
      rm -rf "$dest"
      echo -e "  ${GREEN}✓${RESET} Removed skill from: ${dest}"
    fi
  done

  # Remove CLI binaries
  local aliases=($(get_craft_aliases "$craft"))
  for alias_name in "${aliases[@]}"; do
    local target_bin="${BIN_DIR}/${alias_name}"
    if [ -f "$target_bin" ] || [ -L "$target_bin" ]; then
      rm -f "$target_bin"
      echo -e "  ${GREEN}✓${RESET} Removed CLI binary: ${target_bin}"
    fi
  done

  # Remove preset tools
  uninstall_craft_presets "$craft"

  # Remove external venv
  local venv_dir="${VENVS_BASE_DIR}/${craft}"
  if [ -d "$venv_dir" ]; then
    rm -rf "$venv_dir"
    echo -e "  ${GREEN}✓${RESET} Removed external virtualenv: ${venv_dir}"
  fi

  echo ""
}

# Clean workspace .venv directories
clean_workspace_venvs() {
  print_banner
  echo -e "${BOLD}${YELLOW}Cleaning workspace .venv directories...${RESET}"
  echo ""
  local count=0
  for key in "${CRAFT_KEYS[@]}"; do
    local subdir=$(get_craft_subdir "$key")
    local local_venv="${REPO_DIR}/${subdir}/.venv"
    if [ -d "$local_venv" ]; then
      echo -e "  Removing: ${subdir}/.venv"
      rm -rf "$local_venv"
      count=$((count + 1))
    fi
  done
  echo ""
  echo -e "${GREEN}✓ Cleaned ${count} workspace .venv directories.${RESET}"
  echo "Workspace is now decoupled from virtual environments."
  echo ""
}

# Resolve input string (e.g., "1", "audio-craft", "1,2", "1 3") into craft keys
resolve_craft_selection() {
  local input="$*"
  # Replace commas with spaces
  input="${input//,/ }"
  local selected=()

  for item in $input; do
    if [[ "$item" =~ ^[0-9]+$ ]]; then
      local idx=$((item - 1))
      if [ "$idx" -ge 0 ] && [ "$idx" -lt "${#CRAFT_KEYS[@]}" ]; then
        selected+=("${CRAFT_KEYS[$idx]}")
      else
        echo -e "${RED}Invalid index: $item (must be between 1 and ${#CRAFT_KEYS[@]})${RESET}" >&2
      fi
    else
      # Check by name
      local matched=false
      for key in "${CRAFT_KEYS[@]}"; do
        if [ "$item" = "$key" ]; then
          selected+=("$key")
          matched=true
          break
        fi
      done
      if [ "$matched" = false ]; then
        echo -e "${RED}Unknown craft name: $item${RESET}" >&2
      fi
    fi
  done

  # Deduplicate
  local unique=()
  for val in "${selected[@]}"; do
    local already=false
    for u in "${unique[@]}"; do
      if [ "$u" = "$val" ]; then
        already=true
        break
      fi
    done
    if [ "$already" = false ]; then
      unique+=("$val")
    fi
  done

  echo "${unique[@]}"
}

# Interactive Selection Menu
interactive_menu() {
  print_banner
  echo -e "${BOLD}Select crafts to install system-wide:${RESET}"
  echo "──────────────────────────────────────────────────────────────────────────────────"
  local i=1
  for key in "${CRAFT_KEYS[@]}"; do
    local desc=$(get_craft_desc "$key")
    local status="\033[0;33m[ ]\033[0m"
    if is_craft_installed "$key" && is_venv_installed "$key"; then
      status="\033[0;32m[✓]\033[0m"
    fi
    printf "  ${BOLD}[%d]${RESET} %-16s %b %s\n" "$i" "$key" "$status" "${desc}"
    i=$((i + 1))
  done
  echo "──────────────────────────────────────────────────────────────────────────────────"
  echo -e "  ${BOLD}[A]${RESET} Install ${BOLD}All Crafts${RESET} (CLI shell wrappers)"
  echo -e "  ${BOLD}[B]${RESET} Install ${BOLD}All Crafts as Compiled Native Binaries${RESET} (Mach-O via PyInstaller)"
  echo -e "  ${BOLD}[C]${RESET} Clean workspace ${BOLD}.venv${RESET} folders"
  echo -e "  ${BOLD}[U]${RESET} Uninstall Crafts"
  echo -e "  ${BOLD}[Q]${RESET} Quit"
  echo "──────────────────────────────────────────────────────────────────────────────────"
  echo ""
  echo -ne "${BOLD}Enter choice (e.g. 'A' for wrappers, 'B' for binaries, '1 2' or 'B 1 2'): ${RESET}"
  read -r user_choice

  case "$user_choice" in
    [Aa]*|"all"|"ALL")
      INSTALL_BIN_TYPE="wrapper"
      execute_install "${CRAFT_KEYS[@]}"
      ;;
    [Bb]*|"binary"|"BINARY")
      if [[ "$user_choice" =~ ^[Bb](inary)?[[:space:]]+(.+)$ ]]; then
        local remainder="${BASH_REMATCH[2]}"
        local resolved=($(resolve_craft_selection "$remainder"))
        if [ "${#resolved[@]}" -eq 0 ]; then
          echo "No valid crafts chosen. Exiting."
          exit 1
        fi
        INSTALL_BIN_TYPE="binary"
        execute_install "${resolved[@]}"
      else
        INSTALL_BIN_TYPE="binary"
        execute_install "${CRAFT_KEYS[@]}"
      fi
      ;;
    [Cc]*|"clean")
      clean_workspace_venvs
      ;;
    [Qq]*|"quit"|"exit")
      echo "Installation cancelled."
      exit 0
      ;;
    [Uu]*|"uninstall")
      echo -ne "${BOLD}Enter numbers/names to uninstall (or 'ALL' to uninstall everything): ${RESET}"
      read -r uninst_choice
      if [[ "$uninst_choice" =~ ^([Aa][Ll][Ll]|A)$ ]]; then
        execute_uninstall "${CRAFT_KEYS[@]}"
      else
        local resolved=($(resolve_craft_selection "$uninst_choice"))
        execute_uninstall "${resolved[@]}"
      fi
      ;;
    *)
      if [ -z "$user_choice" ]; then
        echo "No craft selected. Exiting."
        exit 0
      fi
      local chosen_type="wrapper"
      if [[ "$user_choice" =~ ^[Bb](inary)?[[:space:]]+(.+)$ ]]; then
        chosen_type="binary"
        user_choice="${BASH_REMATCH[2]}"
      fi
      INSTALL_BIN_TYPE="$chosen_type"
      local resolved=($(resolve_craft_selection "$user_choice"))
      if [ "${#resolved[@]}" -eq 0 ]; then
        echo "No valid crafts chosen. Exiting."
        exit 1
      fi
      execute_install "${resolved[@]}"
      ;;
  esac
}

execute_install() {
  local crafts=("$@")
  print_banner
  local mode_desc="CLI shell wrappers"
  if [ "$INSTALL_BIN_TYPE" = "binary" ]; then
    mode_desc="compiled native Mach-O binaries (tamper-proof)"
  fi
  echo -e "${BOLD}${GREEN}Starting installation of ${#crafts[@]} craft(s) as ${mode_desc}...${RESET}"
  echo -e "External virtual environment root: ${CYAN}${VENVS_BASE_DIR}${RESET}"
  echo ""

  for c in "${crafts[@]}"; do
    install_single_craft "$c"
  done

  echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}${GREEN}✔ Installation Completed Successfully!${RESET}"
  echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════════════════${RESET}"
  echo ""
  echo -e "All virtual environments are stored externally in: ${CYAN}${VENVS_BASE_DIR}${RESET}"
  echo -e "The workspace directory is completely free of .venv dependencies."
  echo ""
  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "${YELLOW}Important Notice: ${BIN_DIR} is not in your \$PATH.${RESET}"
    echo -e "Add this line to your shell configuration file (~/.zshrc or ~/.bashrc):"
    echo -e "  ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
  else
    echo -e "${GREEN}✓ ${BIN_DIR} is active in your \$PATH. All CLI commands are directly callable!${RESET}"
  fi
  echo ""
  echo -e "${BOLD}Try running:${RESET}"
  echo "  gemini-audio --help"
  echo "  gemini-image --help"
  echo "  model-multiviews --help"
  echo "  t-pose-multiviews --help"
  echo "  garment-multiviews --help"
  echo "  storybook --help"
  echo "  gemini-video --help"
  echo "  human-composer --help"
  echo "  model-composer --help"
  echo "  model-creator --help"
  echo "  pose-binder --help"
  echo "  fix-chin-jaw --help"
  echo "  rig-binder --help"
  echo "  asset-generator --help"
  echo "  generate-asset --help"
  echo ""
}

execute_uninstall() {
  local crafts=("$@")
  print_banner
  echo -e "${BOLD}${YELLOW}Uninstalling ${#crafts[@]} craft(s)...${RESET}"
  echo ""
  for c in "${crafts[@]}"; do
    uninstall_single_craft "$c"
  done
  echo -e "${BOLD}${GREEN}✔ Uninstallation complete.${RESET}"
  echo ""
}

# ------------------------------------------------------------------------------
# Main Entry Point & Argument Parsing
# ------------------------------------------------------------------------------

TARGET_CRAFTS=()
CUSTOM_TARGET_DIR=""
ACTION="install"

while [ $# -gt 0 ]; do
  case "$1" in
    -a|--all)
      TARGET_CRAFTS=("${CRAFT_KEYS[@]}")
      shift
      ;;
    -b|--binary)
      INSTALL_BIN_TYPE="binary"
      shift
      ;;
    -s|--select)
      shift
      if [ -n "$1" ]; then
        RESOLVED=($(resolve_craft_selection "$1"))
        TARGET_CRAFTS+=("${RESOLVED[@]}")
        shift
      fi
      ;;
    -l|--list)
      list_crafts
      exit 0
      ;;
    -u|--uninstall)
      ACTION="uninstall"
      shift
      if [ $# -gt 0 ] && [[ ! "$1" =~ ^- ]]; then
        RESOLVED=($(resolve_craft_selection "$@"))
        TARGET_CRAFTS+=("${RESOLVED[@]}")
        break
      fi
      ;;
    --uninstall-all)
      ACTION="uninstall"
      TARGET_CRAFTS=("${CRAFT_KEYS[@]}")
      shift
      ;;
    --skip-deps)
      SKIP_DEPS=true
      shift
      ;;
    --reinstall-deps)
      REINSTALL_DEPS=true
      shift
      ;;
    --clean-workspace-venvs)
      clean_workspace_venvs
      exit 0
      ;;
    --copy)
      INSTALL_MODE="copy"
      shift
      ;;
    --link)
      INSTALL_MODE="link"
      shift
      ;;
    --venvs-dir)
      shift
      VENVS_BASE_DIR="$1"
      shift
      ;;
    --bin-dir)
      shift
      BIN_DIR="$1"
      shift
      ;;
    --target)
      shift
      CUSTOM_TARGET_DIR="$1"
      shift
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      # Treat positional args as craft names or numbers
      RESOLVED=($(resolve_craft_selection "$1"))
      TARGET_CRAFTS+=("${RESOLVED[@]}")
      shift
      ;;
  esac
done

if [ "$ACTION" = "uninstall" ]; then
  if [ "${#TARGET_CRAFTS[@]}" -eq 0 ]; then
    TARGET_CRAFTS=("${CRAFT_KEYS[@]}")
  fi
  execute_uninstall "${TARGET_CRAFTS[@]}"
  exit 0
fi

if [ "${#TARGET_CRAFTS[@]}" -gt 0 ]; then
  execute_install "${TARGET_CRAFTS[@]}"
else
  # If no args and running interactively, open interactive menu
  if [ -t 0 ]; then
    interactive_menu
  else
    # Non-interactive without arguments: show help
    print_help
  fi
fi
