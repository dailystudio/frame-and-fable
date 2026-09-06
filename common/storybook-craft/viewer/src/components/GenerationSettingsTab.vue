<template>
  <div class="generation-settings-tab">
    <!-- Header Banner -->
    <header class="settings-header clean-card">
      <div class="header-left">
        <div class="header-title-row">
          <div class="header-icon-box">
            <span class="material-symbols-rounded">tune</span>
          </div>
          <div>
            <h2 class="header-title">Generation Settings & Inheritance</h2>
            <p class="header-subtitle">
              Configure global defaults for AI image and video generation in <strong>{{ stem }}</strong>.
              All scenes inherit these defaults automatically unless individually overridden below.
            </p>
          </div>
        </div>
      </div>

      <div class="header-right">
        <!-- Save Feedback Banner -->
        <div v-if="saveMsg" class="save-toast" :class="saveStatus">
          <span class="material-symbols-rounded toast-icon">
            {{ saveStatus === 'saved' ? 'check_circle' : (saveStatus === 'saving' ? 'sync' : 'error') }}
          </span>
          <span>{{ saveMsg }}</span>
        </div>

        <button
          v-if="overriddenCount > 0"
          type="button"
          class="clean-btn clean-btn-sm reset-all-btn"
          title="Reset all custom scene overrides back to global defaults"
          @click="resetAllOverrides"
        >
          <span class="material-symbols-rounded">restart_alt</span>
          <span>Reset All Overrides ({{ overriddenCount }})</span>
        </button>

        <button
          type="button"
          class="clean-btn clean-btn-primary clean-btn-sm"
          :disabled="saveStatus === 'saving'"
          @click="manualSave"
        >
          <span class="material-symbols-rounded" :class="{ 'is-spinning': saveStatus === 'saving' }">
            {{ saveStatus === 'saving' ? 'sync' : 'save' }}
          </span>
          <span>{{ saveStatus === 'saving' ? 'Saving...' : 'Save Settings' }}</span>
        </button>
      </div>
    </header>

    <!-- Global Controls Grid (Image & Video) -->
    <div class="global-cards-grid">
      <!-- 1. Global Image Defaults -->
      <div class="global-card clean-card image-card">
        <div class="card-head">
          <div class="card-badge image-badge">
            <span class="material-symbols-rounded">image</span>
            <span>Global Image Defaults</span>
          </div>
          <span class="card-scope-tag">Applies to all non-overridden images</span>
        </div>

        <div class="card-body">
          <!-- Image Aspect Ratio -->
          <div class="setting-group">
            <div class="setting-label-row">
              <label class="setting-label">
                <span class="material-symbols-rounded">aspect_ratio</span>
                Default Aspect Ratio
              </label>
              <span class="active-val-pill">{{ localSettings.global.image.ratio }}</span>
            </div>
            <div class="ratio-options-grid">
              <button
                v-for="r in imageRatioOptions"
                :key="r.value"
                type="button"
                class="ratio-card-btn"
                :class="{ active: localSettings.global.image.ratio === r.value }"
                @click="setGlobalImageRatio(r.value)"
              >
                <div class="ratio-box" :style="{ aspectRatio: r.boxRatio }"></div>
                <span class="ratio-name">{{ r.value }}</span>
                <span class="ratio-desc">{{ r.label }}</span>
              </button>
            </div>
          </div>

          <!-- Image Resolution Size -->
          <div class="setting-group">
            <div class="setting-label-row">
              <label class="setting-label">
                <span class="material-symbols-rounded">photo_size_select_actual</span>
                Default Resolution Size
              </label>
              <span class="active-val-pill">{{ localSettings.global.image.size }}</span>
            </div>
            <div class="size-options-grid">
              <button
                v-for="s in imageSizeOptions"
                :key="s.value"
                type="button"
                class="size-card-btn"
                :class="{ active: localSettings.global.image.size === s.value }"
                @click="setGlobalImageSize(s.value)"
              >
                <span class="size-title">{{ s.value }}</span>
                <span class="size-desc">{{ s.desc }}</span>
              </button>
            </div>
          </div>

          <!-- Image Model -->
          <div class="setting-group">
            <div class="setting-label-row">
              <label class="setting-label">
                <span class="material-symbols-rounded">neurology</span>
                Default Image Model
              </label>
            </div>
            <input
              v-model="localSettings.global.image.model"
              type="text"
              class="clean-input model-input"
              placeholder="gemini-3.1-flash-image"
              @input="onModelInput"
            />
            <div class="model-quick-chips">
              <button
                v-for="m in quickImageModels"
                :key="m"
                type="button"
                class="chip-btn"
                :class="{ active: localSettings.global.image.model === m }"
                @click="setGlobalImageModel(m)"
              >
                {{ m }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Global Video Defaults -->
      <div class="global-card clean-card video-card">
        <div class="card-head">
          <div class="card-badge video-badge">
            <span class="material-symbols-rounded">videocam</span>
            <span>Global Video Defaults</span>
          </div>
          <span class="card-scope-tag">Applies to all non-overridden videos</span>
        </div>

        <div class="card-body">
          <!-- Video Aspect Ratio -->
          <div class="setting-group">
            <div class="setting-label-row">
              <label class="setting-label">
                <span class="material-symbols-rounded">aspect_ratio</span>
                Default Aspect Ratio
              </label>
              <span class="active-val-pill">{{ localSettings.global.video.ratio }}</span>
            </div>
            <div class="ratio-options-grid">
              <button
                v-for="r in videoRatioOptions"
                :key="r.value"
                type="button"
                class="ratio-card-btn"
                :class="{ active: localSettings.global.video.ratio === r.value }"
                @click="setGlobalVideoRatio(r.value)"
              >
                <div class="ratio-box" :style="{ aspectRatio: r.boxRatio }"></div>
                <span class="ratio-name">{{ r.value }}</span>
                <span class="ratio-desc">{{ r.label }}</span>
              </button>
            </div>
          </div>

          <!-- Video Duration -->
          <div class="setting-group">
            <div class="setting-label-row">
              <label class="setting-label">
                <span class="material-symbols-rounded">timelapse</span>
                Default Duration
              </label>
              <span class="active-val-pill">{{ localSettings.global.video.duration || '5s' }}</span>
            </div>
            <div class="size-options-grid">
              <button
                v-for="d in ['5s', '10s']"
                :key="d"
                type="button"
                class="size-card-btn"
                :class="{ active: (localSettings.global.video.duration || '5s') === d }"
                @click="setGlobalVideoDuration(d)"
              >
                <span class="size-title">{{ d }}</span>
                <span class="size-desc">{{ d === '5s' ? 'Standard Clip' : 'Extended Clip' }}</span>
              </button>
            </div>
          </div>

          <!-- Video Model -->
          <div class="setting-group">
            <div class="setting-label-row">
              <label class="setting-label">
                <span class="material-symbols-rounded">neurology</span>
                Default Video Model
              </label>
            </div>
            <input
              v-model="localSettings.global.video.model"
              type="text"
              class="clean-input model-input"
              placeholder="veo-2.0-generate-001"
              @input="onModelInput"
            />
            <div class="model-quick-chips">
              <button
                v-for="m in quickVideoModels"
                :key="m"
                type="button"
                class="chip-btn"
                :class="{ active: localSettings.global.video.model === m }"
                @click="setGlobalVideoModel(m)"
              >
                {{ m }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Scene Overrides Matrix Section -->
    <section class="scenes-matrix-section clean-card">
      <div class="matrix-header">
        <div class="matrix-title-wrap">
          <div class="title-with-pill">
            <h3 class="matrix-title">Scene Overrides & Inheritance Matrix</h3>
            <span class="counter-badge">{{ filteredTags.length }} of {{ tags.length }} scenes</span>
          </div>
          <p class="matrix-sub">
            Scenes set to <strong>Inherit Global</strong> update dynamically whenever you modify the global defaults above.
            Scenes with a <strong>Custom Override</strong> remain fixed to their individual settings.
          </p>
        </div>

        <!-- Filter & Search Toolbar -->
        <div class="matrix-toolbar">
          <!-- Search Box -->
          <div class="search-wrap">
            <span class="material-symbols-rounded search-icon">search</span>
            <input
              v-model="searchQuery"
              type="text"
              class="clean-input search-input"
              placeholder="Search by ID, title, or prompt..."
            />
            <button
              v-if="searchQuery"
              type="button"
              class="clear-search-btn"
              @click="searchQuery = ''"
            >
              <span class="material-symbols-rounded">close</span>
            </button>
          </div>

          <!-- Status Filter Pills -->
          <div class="filter-pills-row">
            <button
              type="button"
              class="filter-pill"
              :class="{ active: filterStatus === 'all' }"
              @click="filterStatus = 'all'"
            >
              All ({{ tags.length }})
            </button>
            <button
              type="button"
              class="filter-pill pill-inherit"
              :class="{ active: filterStatus === 'inherited' }"
              @click="filterStatus = 'inherited'"
            >
              <span class="status-dot dot-inherit"></span>
              Inheriting Global ({{ inheritedCount }})
            </button>
            <button
              type="button"
              class="filter-pill pill-override"
              :class="{ active: filterStatus === 'overridden' }"
              @click="filterStatus = 'overridden'"
            >
              <span class="status-dot dot-override"></span>
              Custom Overrides ({{ overriddenCount }})
            </button>
          </div>

          <!-- Media Type Filter -->
          <div class="media-type-select-wrap">
            <select v-model="filterType" class="clean-select media-select">
              <option value="all">All Media Types</option>
              <option value="image">Images Only</option>
              <option value="video">Videos Only</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Scene Rows Table -->
      <div v-if="filteredTags.length === 0" class="empty-matrix-state">
        <span class="material-symbols-rounded empty-icon">filter_alt_off</span>
        <p>No scenes match the active filter criteria.</p>
        <button type="button" class="clean-btn clean-btn-sm" @click="resetMatrixFilters">
          Reset Filters
        </button>
      </div>

      <div v-else class="matrix-table-wrap">
        <table class="matrix-table">
          <thead>
            <tr>
              <th class="col-scene">Scene ID & Narrative</th>
              <th class="col-type">Type</th>
              <th class="col-status">Inheritance Status</th>
              <th class="col-ratio">Aspect Ratio</th>
              <th class="col-size">Resolution Size</th>
              <th class="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in filteredTags"
              :key="item.id"
              class="matrix-row"
              :class="{ 'is-overridden': item.isOverridden }"
            >
              <!-- 1. Scene ID & Narrative -->
              <td class="col-scene">
                <div class="scene-id-group">
                  <span class="scene-id-pill">{{ item.id }}</span>
                  <span class="scene-section-name">{{ item.section }}</span>
                </div>
                <p class="scene-prompt-snippet" :title="item.prompt">
                  {{ item.prompt || 'No narrative prompt specified.' }}
                </p>
              </td>

              <!-- 2. Type -->
              <td class="col-type">
                <span class="type-pill" :class="item.type === 'video' ? 'type-video' : 'type-image'">
                  <span class="material-symbols-rounded pill-icon">
                    {{ item.type === 'video' ? 'videocam' : 'image' }}
                  </span>
                  {{ item.type === 'video' ? 'Video' : 'Image' }}
                </span>
              </td>

              <!-- 3. Status -->
              <td class="col-status">
                <div v-if="item.isOverridden" class="status-badge-override" title="This scene has explicit custom overrides">
                  <span class="status-dot dot-override"></span>
                  <span>Custom Override</span>
                </div>
                <div v-else class="status-badge-inherit" title="Dynamically inherits current global defaults">
                  <span class="status-dot dot-inherit"></span>
                  <span>Inheriting Global</span>
                </div>
              </td>

              <!-- 4. Aspect Ratio Select -->
              <td class="col-ratio">
                <div class="select-cell-wrap">
                  <select
                    :value="item.overrideRatio"
                    class="clean-select inline-select"
                    :class="{ 'is-custom': item.overrideRatio !== 'inherit' }"
                    @change="onSceneRatioChange(item.id, $event.target.value)"
                  >
                    <option value="inherit">
                      Inherit Global ({{ item.globalRatio }})
                    </option>
                    <option
                      v-for="r in (item.type === 'video' ? videoRatioOptions : imageRatioOptions)"
                      :key="r.value"
                      :value="r.value"
                    >
                      {{ r.value }} ({{ r.label }})
                    </option>
                  </select>
                </div>
              </td>

              <!-- 5. Resolution Size Select -->
              <td class="col-size">
                <div v-if="item.type === 'image'" class="select-cell-wrap">
                  <select
                    :value="item.overrideSize"
                    class="clean-select inline-select"
                    :class="{ 'is-custom': item.overrideSize !== 'inherit' }"
                    @change="onSceneSizeChange(item.id, $event.target.value)"
                  >
                    <option value="inherit">
                      Inherit Global ({{ item.globalSize }})
                    </option>
                    <option v-for="s in imageSizeOptions" :key="s.value" :value="s.value">
                      {{ s.value }} ({{ s.desc }})
                    </option>
                  </select>
                </div>
                <span v-else class="text-muted-dash">—</span>
              </td>

              <!-- 6. Actions -->
              <td class="col-actions">
                <div class="actions-group">
                  <button
                    v-if="item.isOverridden"
                    type="button"
                    class="clean-btn clean-btn-sm reset-row-btn"
                    title="Reset this scene back to inheriting global settings"
                    @click="resetSceneToGlobal(item.id)"
                  >
                    <span class="material-symbols-rounded">undo</span>
                    <span>Reset</span>
                  </button>

                  <button
                    type="button"
                    class="clean-btn clean-btn-sm inspect-row-btn"
                    title="Inspect prompt template, references, and regenerate"
                    @click="inspectScene(item)"
                  >
                    <span class="material-symbols-rounded">visibility</span>
                    <span>Inspect</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { saveWorkspaceSettings, resolveTagSettings } from '../services/api';

const props = defineProps({
  stem: { type: String, required: true },
  tags: { type: Array, default: () => [] },
  settings: {
    type: Object,
    default: () => ({
      global: {
        image: { ratio: '16:9', size: '1K', model: 'gemini-3.1-flash-image' },
        video: { ratio: '16:9', model: 'veo-2.0-generate-001', duration: '5s' }
      },
      scenes: {}
    })
  }
});

const emit = defineEmits(['update-settings', 'preview']);

// Reactive clone of settings
const localSettings = reactive({
  global: {
    image: {
      ratio: props.settings?.global?.image?.ratio || '16:9',
      size: props.settings?.global?.image?.size || '1K',
      model: props.settings?.global?.image?.model || 'gemini-3.1-flash-image'
    },
    video: {
      ratio: props.settings?.global?.video?.ratio || '16:9',
      model: props.settings?.global?.video?.model || 'veo-2.0-generate-001',
      duration: props.settings?.global?.video?.duration || '5s'
    }
  },
  scenes: { ...(props.settings?.scenes || {}) }
});

// Watch props.settings changes from server reload
watch(
  () => props.settings,
  (newVal) => {
    if (!newVal) return;
    if (newVal.global?.image) {
      Object.assign(localSettings.global.image, newVal.global.image);
    }
    if (newVal.global?.video) {
      Object.assign(localSettings.global.video, newVal.global.video);
    }
    if (newVal.scenes) {
      // Clear and reassign
      Object.keys(localSettings.scenes).forEach(k => delete localSettings.scenes[k]);
      Object.assign(localSettings.scenes, newVal.scenes);
    }
  },
  { deep: true }
);

// Options constants
const imageRatioOptions = [
  { value: '16:9', label: 'Landscape', boxRatio: '16/9' },
  { value: '4:3', label: 'Standard', boxRatio: '4/3' },
  { value: '1:1', label: 'Square', boxRatio: '1/1' },
  { value: '3:4', label: 'Portrait', boxRatio: '3/4' },
  { value: '9:16', label: 'Vertical', boxRatio: '9/16' },
  { value: '21:9', label: 'Ultrawide', boxRatio: '21/9' }
];

const videoRatioOptions = [
  { value: '16:9', label: 'Landscape (16:9)', boxRatio: '16/9' },
  { value: '9:16', label: 'Vertical / Reels (9:16)', boxRatio: '9/16' },
  { value: '1:1', label: 'Square (1:1)', boxRatio: '1/1' }
];

const imageSizeOptions = [
  { value: '1K', desc: 'Standard HD (1024px)' },
  { value: '2K', desc: 'QHD High-Res (2048px)' },
  { value: '4K', desc: 'Ultra HD (4096px)' }
];

const quickImageModels = [
  'gemini-3.1-flash-image',
  'imagen-3.0-generate-002',
  'gemini-2.5-flash-image'
];

const quickVideoModels = [
  'veo-2.0-generate-001',
  'veo-3.0-generate-preview'
];

// Matrix filters & search
const searchQuery = ref('');
const filterStatus = ref('all'); // 'all', 'inherited', 'overridden'
const filterType = ref('all');   // 'all', 'image', 'video'

// Toast notifications
const saveStatus = ref('');
const saveMsg = ref('');
let saveTimeout = null;
let debounceTimer = null;

function flashToast(msg, status = 'saved', duration = 3000) {
  saveMsg.value = msg;
  saveStatus.value = status;
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(() => {
    saveMsg.value = '';
    saveStatus.value = '';
  }, duration);
}

// Auto-save debouncer
function triggerAutoSave() {
  if (debounceTimer) clearTimeout(debounceTimer);
  saveStatus.value = 'saving';
  saveMsg.value = 'Saving changes...';

  debounceTimer = setTimeout(async () => {
    await persistSettings();
  }, 400);
}

async function persistSettings() {
  try {
    saveStatus.value = 'saving';
    const payload = JSON.parse(JSON.stringify(localSettings));
    const saved = await saveWorkspaceSettings(props.stem, payload);
    emit('update-settings', saved);
    flashToast('Settings saved to workspace settings.json', 'saved');
  } catch (err) {
    flashToast(`Save error: ${err.message}`, 'error', 5000);
  }
}

async function manualSave() {
  if (debounceTimer) clearTimeout(debounceTimer);
  await persistSettings();
}

// Global Image updates
function setGlobalImageRatio(r) {
  localSettings.global.image.ratio = r;
  triggerAutoSave();
}

function setGlobalImageSize(s) {
  localSettings.global.image.size = s;
  triggerAutoSave();
}

function setGlobalImageModel(m) {
  localSettings.global.image.model = m;
  triggerAutoSave();
}

// Global Video updates
function setGlobalVideoRatio(r) {
  localSettings.global.video.ratio = r;
  triggerAutoSave();
}

function setGlobalVideoDuration(d) {
  localSettings.global.video.duration = d;
  triggerAutoSave();
}

function setGlobalVideoModel(m) {
  localSettings.global.video.model = m;
  triggerAutoSave();
}

function onModelInput() {
  triggerAutoSave();
}

// Scene Overrides Management
function onSceneRatioChange(tagId, val) {
  if (!tagId) return;
  if (!localSettings.scenes[tagId]) {
    localSettings.scenes[tagId] = {};
  }
  if (val === 'inherit') {
    delete localSettings.scenes[tagId].ratio;
    cleanEmptyScene(tagId);
  } else {
    localSettings.scenes[tagId].ratio = val;
  }
  triggerAutoSave();
}

function onSceneSizeChange(tagId, val) {
  if (!tagId) return;
  if (!localSettings.scenes[tagId]) {
    localSettings.scenes[tagId] = {};
  }
  if (val === 'inherit') {
    delete localSettings.scenes[tagId].size;
    cleanEmptyScene(tagId);
  } else {
    localSettings.scenes[tagId].size = val;
  }
  triggerAutoSave();
}

function cleanEmptyScene(tagId) {
  const sc = localSettings.scenes[tagId];
  if (!sc) return;
  const keys = Object.keys(sc);
  if (keys.length === 0 || keys.every(k => !sc[k] || sc[k] === 'inherit')) {
    delete localSettings.scenes[tagId];
  }
}

function resetSceneToGlobal(tagId) {
  if (localSettings.scenes[tagId]) {
    delete localSettings.scenes[tagId];
    triggerAutoSave();
  }
}

function resetAllOverrides() {
  const count = overriddenCount.value;
  if (count === 0) return;
  if (!confirm(`Reset all ${count} scene overrides back to inheriting global settings?`)) return;
  localSettings.scenes = {};
  triggerAutoSave();
}

// Processed tag rows with resolved settings
const processedTags = computed(() => {
  return props.tags.map(t => {
    const resolved = resolveTagSettings(localSettings, t.id, t.type || 'image');
    return {
      ...t,
      isOverridden: resolved.isOverridden,
      overrideRatio: resolved.overrideRatio,
      overrideSize: resolved.overrideSize,
      effectiveRatio: resolved.ratio,
      effectiveSize: resolved.size,
      globalRatio: resolved.globalRatio,
      globalSize: resolved.globalSize
    };
  });
});

const overriddenCount = computed(() => {
  return processedTags.value.filter(t => t.isOverridden).length;
});

const inheritedCount = computed(() => {
  return processedTags.value.filter(t => !t.isOverridden).length;
});

const filteredTags = computed(() => {
  return processedTags.value.filter(item => {
    // 1. Filter Type
    if (filterType.value !== 'all' && item.type !== filterType.value) {
      return false;
    }

    // 2. Filter Status
    if (filterStatus.value === 'inherited' && item.isOverridden) {
      return false;
    }
    if (filterStatus.value === 'overridden' && !item.isOverridden) {
      return false;
    }

    // 3. Search Query
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase().trim();
      const idMatch = (item.id || '').toLowerCase().includes(q);
      const secMatch = (item.section || '').toLowerCase().includes(q);
      const promptMatch = (item.prompt || '').toLowerCase().includes(q);
      if (!idMatch && !secMatch && !promptMatch) {
        return false;
      }
    }

    return true;
  });
});

function resetMatrixFilters() {
  searchQuery.value = '';
  filterStatus.value = 'all';
  filterType.value = 'all';
}

function inspectScene(tag) {
  emit('preview', {
    id: tag.id,
    tagId: tag.id,
    stem: props.stem,
    section: tag.section,
    type: tag.type || 'image',
    prompt: tag.prompt || '',
    composedPrompt: tag.composed_prompt || '',
    styleRef: tag.style_ref || null,
    characterRefs: tag.character_refs || [],
    src: tag.matchedAsset?.assetUrl || (tag.asset ? `/api/asset/${encodeURIComponent(props.stem)}/${tag.asset}` : ''),
    title: `${tag.section || 'Scene'} (${tag.id})`
  });
}
</script>

<style scoped>
.generation-settings-tab {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding-bottom: 3rem;
}

/* Header Banner */
.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.header-left {
  flex: 1;
  min-width: 320px;
}

.header-title-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.header-icon-box {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--accent-primary-subtle);
  color: var(--accent-primary);
  flex-shrink: 0;
}

.header-icon-box .material-symbols-rounded {
  font-size: 24px;
}

.header-title {
  margin: 0 0 0.25rem 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.header-subtitle {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.save-toast {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-full);
}

.save-toast.saved {
  background: var(--status-success-bg);
  color: var(--status-success-text);
  border: 1px solid var(--status-success-border);
}

.save-toast.saving {
  background: var(--accent-primary-subtle);
  color: var(--accent-primary-text);
}

.save-toast.error {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}

.toast-icon {
  font-size: 16px;
}

.reset-all-btn {
  color: #b91c1c;
  border-color: #fecaca;
  background: #fff5f5;
}

.reset-all-btn:hover {
  background: #fee2e2;
  border-color: #fca5a5;
}

/* Global Cards Grid */
.global-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 1.25rem;
}

.global-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface-secondary);
}

.card-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.92rem;
  font-weight: 700;
}

.card-badge .material-symbols-rounded {
  font-size: 20px;
}

.image-badge {
  color: var(--type-image-text);
}

.video-badge {
  color: var(--type-video-text);
}

.card-scope-tag {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.card-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.setting-group {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.setting-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.setting-label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.setting-label .material-symbols-rounded {
  font-size: 18px;
  color: var(--text-secondary);
}

.active-val-pill {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.15rem 0.55rem;
  border-radius: var(--radius-full);
  background: var(--badge-bg);
  color: var(--badge-text);
  border: 1px solid var(--badge-border);
}

/* Ratio Options Grid */
.ratio-options-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(95px, 1fr));
  gap: 0.5rem;
}

.ratio-card-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.6rem 0.4rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.ratio-card-btn:hover {
  border-color: var(--border-strong);
  background: var(--bg-surface-secondary);
}

.ratio-card-btn.active {
  border-color: var(--accent-primary);
  background: var(--accent-primary-subtle);
  box-shadow: 0 0 0 1px var(--accent-primary);
}

.ratio-box {
  width: 24px;
  max-height: 20px;
  background: var(--text-muted);
  border-radius: 2px;
  margin-bottom: 0.35rem;
  opacity: 0.6;
}

.ratio-card-btn.active .ratio-box {
  background: var(--accent-primary);
  opacity: 1;
}

.ratio-name {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.ratio-desc {
  font-size: 0.68rem;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Size Options Grid */
.size-options-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 0.5rem;
}

.size-card-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.65rem 0.5rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  cursor: pointer;
  transition: all 0.15s ease;
}

.size-card-btn:hover {
  border-color: var(--border-strong);
  background: var(--bg-surface-secondary);
}

.size-card-btn.active {
  border-color: var(--accent-primary);
  background: var(--accent-primary-subtle);
  box-shadow: 0 0 0 1px var(--accent-primary);
}

.size-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
}

.size-desc {
  font-size: 0.68rem;
  color: var(--text-muted);
  text-align: center;
  margin-top: 2px;
}

/* Model input & chips */
.model-input {
  width: 100%;
}

.model-quick-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.25rem;
}

.chip-btn {
  padding: 0.2rem 0.55rem;
  font-size: 0.72rem;
  font-family: var(--font-mono);
  border-radius: var(--radius-full);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.chip-btn:hover {
  background: var(--bg-surface-secondary);
  color: var(--text-primary);
}

.chip-btn.active {
  background: var(--accent-primary);
  color: #fff;
  border-color: var(--accent-primary);
}

/* Scene Overrides Matrix */
.scenes-matrix-section {
  display: flex;
  flex-direction: column;
}

.matrix-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-default);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.matrix-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.title-with-pill {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.matrix-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.counter-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.55rem;
  border-radius: var(--radius-full);
  background: var(--badge-bg);
  color: var(--badge-text);
  border: 1px solid var(--badge-border);
}

.matrix-sub {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.matrix-toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.search-wrap {
  position: relative;
  flex: 1;
  min-width: 240px;
}

.search-icon {
  position: absolute;
  left: 0.65rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 18px;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding-left: 2.2rem;
  padding-right: 2rem;
}

.clear-search-btn {
  position: absolute;
  right: 0.4rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  padding: 2px;
}

.clear-search-btn:hover {
  color: var(--text-primary);
}

.filter-pills-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.filter-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.65rem;
  border-radius: var(--radius-full);
  font-size: 0.78rem;
  font-weight: 500;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.filter-pill:hover {
  background: var(--bg-surface-secondary);
  color: var(--text-primary);
}

.filter-pill.active {
  background: var(--text-primary);
  color: var(--bg-surface);
  border-color: var(--text-primary);
}

.filter-pill.pill-inherit.active {
  background: #047857;
  color: #fff;
  border-color: #047857;
}

.filter-pill.pill-override.active {
  background: #6d28d9;
  color: #fff;
  border-color: #6d28d9;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot-inherit {
  background: #10b981;
}

.dot-override {
  background: #8b5cf6;
}

.media-type-select-wrap {
  min-width: 140px;
}

.media-select {
  width: 100%;
}

/* Empty State */
.empty-matrix-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1.5rem;
  gap: 0.75rem;
  color: var(--text-muted);
}

.empty-icon {
  font-size: 40px;
}

/* Matrix Table */
.matrix-table-wrap {
  overflow-x: auto;
}

.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.matrix-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  background: var(--bg-surface-secondary);
  color: var(--text-secondary);
  font-weight: 600;
  border-bottom: 1px solid var(--border-default);
  white-space: nowrap;
}

.matrix-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: middle;
}

.matrix-row:hover {
  background: var(--bg-surface-secondary);
}

.matrix-row.is-overridden {
  background: rgba(139, 92, 246, 0.03);
}

.matrix-row.is-overridden:hover {
  background: rgba(139, 92, 246, 0.07);
}

/* Columns */
.col-scene {
  min-width: 260px;
  max-width: 340px;
}

.scene-id-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.scene-id-pill {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: var(--radius-xs);
  background: var(--bg-surface-tertiary);
  color: var(--text-primary);
}

.scene-section-name {
  font-weight: 600;
  color: var(--text-primary);
}

.scene-prompt-snippet {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}

.col-type {
  width: 100px;
  white-space: nowrap;
}

.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-full);
  font-size: 0.72rem;
  font-weight: 600;
}

.type-pill .pill-icon {
  font-size: 14px;
}

.type-image {
  background: var(--type-image-bg);
  color: var(--type-image-text);
  border: 1px solid var(--type-image-border);
}

.type-video {
  background: var(--type-video-bg);
  color: var(--type-video-text);
  border: 1px solid var(--type-video-border);
}

.col-status {
  width: 150px;
  white-space: nowrap;
}

.status-badge-override {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.74rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-full);
  background: rgba(139, 92, 246, 0.12);
  color: #7c3aed;
  border: 1px solid rgba(139, 92, 246, 0.25);
}

.status-badge-inherit {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.74rem;
  font-weight: 500;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-full);
  background: var(--status-success-bg);
  color: var(--status-success-text);
  border: 1px solid var(--status-success-border);
}

.col-ratio,
.col-size {
  min-width: 170px;
}

.select-cell-wrap {
  width: 100%;
}

.inline-select {
  width: 100%;
  padding: 0.35rem 0.55rem;
  font-size: 0.8rem;
}

.inline-select.is-custom {
  font-weight: 600;
  border-color: #8b5cf6;
  background-color: rgba(139, 92, 246, 0.06);
  color: #6d28d9;
}

.text-muted-dash {
  color: var(--text-muted);
  padding-left: 0.5rem;
}

.col-actions {
  width: 150px;
  white-space: nowrap;
}

.actions-group {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.reset-row-btn {
  color: #6d28d9;
  border-color: #ddd6fe;
  background: #f5f3ff;
}

.reset-row-btn:hover {
  background: #ede9fe;
}

.inspect-row-btn {
  color: var(--text-secondary);
}

.inspect-row-btn:hover {
  color: var(--text-primary);
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
