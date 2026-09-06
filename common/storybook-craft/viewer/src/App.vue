<template>
  <div class="app-shell">
    <!-- Header -->
    <header class="app-header">
      <div class="header-container">
        <div class="header-left">
          <div class="brand">
            <span class="material-symbols-rounded brand-symbol">menu_book</span>
            <span class="brand-name">Storybook Craft</span>
          </div>

          <!-- Workspace Selector -->
          <div class="workspace-selector">
            <label for="ws-select" class="ws-label">Workspace:</label>
            <div class="select-box">
              <select
                id="ws-select"
                v-model="selectedStem"
                class="clean-select ws-dropdown"
                :disabled="loading"
                @change="onWorkspaceChange"
              >
                <option v-for="ws in workspaces" :key="ws.stem" :value="ws.stem">
                  {{ ws.stem }}
                </option>
              </select>
              <span class="material-symbols-rounded select-arrow">expand_more</span>
            </div>
          </div>
        </div>

        <div class="header-right">
          <!-- Active Generation Indicator Pill -->
          <div
            v-if="activeGenerations.length || runningTasksCount > 0"
            class="gen-progress-pill cursor-pointer"
            title="Click to view generation progress and logs"
            @click="currentTab = 'tasks'"
          >
            <span class="material-symbols-rounded is-spinning">sync</span>
            <span>Generating {{ activeTagNames }}...</span>
          </div>

          <!-- Add Scene Tag Button in App Header -->
          <button
            type="button"
            class="clean-btn clean-btn-sm header-add-btn"
            title="Add a new image or video scene tag into the story"
            :disabled="!selectedStem"
            @click="openAddTagModal()"
          >
            <span class="material-symbols-rounded">add_photo_alternate</span>
            <span>+ Add Scene Tag</span>
          </button>

          <!-- Refresh -->
          <button
            type="button"
            class="clean-icon-btn"
            title="Reload workspace"
            :disabled="loading || isRefreshing"
            @click="refreshData"
          >
            <span class="material-symbols-rounded" :class="{ 'is-spinning': loading || isRefreshing }">refresh</span>
          </button>

          <!-- Generation Settings -->
          <button
            type="button"
            class="clean-icon-btn"
            :class="{ active: currentTab === 'settings' }"
            title="Generation Settings (Ratio, Size, Models & Scene Overrides)"
            @click="currentTab = 'settings'"
          >
            <span class="material-symbols-rounded">tune</span>
          </button>

          <!-- Theme Toggle -->
          <button
            type="button"
            class="clean-icon-btn"
            :title="isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme'"
            @click="toggleTheme"
          >
            <span class="material-symbols-rounded">
              {{ isDark ? 'light_mode' : 'dark_mode' }}
            </span>
          </button>
        </div>
      </div>

      <!-- Segmented Tab Navigation -->
      <nav class="nav-tabs-bar">
        <div class="nav-tabs-container">
          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'reader' }"
            @click="currentTab = 'reader'"
          >
            <span class="material-symbols-rounded tab-icon">auto_stories</span>
            <span>Story Reader</span>
          </button>

          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'tags' }"
            @click="currentTab = 'tags'"
          >
            <span class="material-symbols-rounded tab-icon">local_offer</span>
            <span>Media Tags</span>
            <span v-if="workspaceData?.tags?.length" class="tab-badge">
              {{ workspaceData.tags.length }}
            </span>
          </button>

          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'characters' }"
            @click="currentTab = 'characters'"
          >
            <span class="material-symbols-rounded tab-icon">face</span>
            <span>Characters</span>
            <span v-if="workspaceData?.characters?.length" class="tab-badge">
              {{ workspaceData.characters.length }}
            </span>
          </button>

          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'style' }"
            @click="currentTab = 'style'"
          >
            <span class="material-symbols-rounded tab-icon">palette</span>
            <span>Art Style</span>
            <span v-if="workspaceData?.style?.images?.length" class="tab-badge">
              {{ workspaceData.style.images.length }}
            </span>
          </button>

          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'media' }"
            @click="currentTab = 'media'"
          >
            <span class="material-symbols-rounded tab-icon">photo_library</span>
            <span>Asset Files</span>
            <span v-if="totalMediaCount" class="tab-badge">
              {{ totalMediaCount }}
            </span>
          </button>

          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'tasks' }"
            @click="currentTab = 'tasks'"
          >
            <span class="material-symbols-rounded tab-icon">history_edu</span>
            <span>Generations</span>
            <span v-if="runningTasksCount" class="tab-badge running-badge">
              {{ runningTasksCount }}
            </span>
            <span v-else-if="failedTasksCount" class="tab-badge failed-badge" title="Failed tasks">
              {{ failedTasksCount }}
            </span>
          </button>

          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'settings' }"
            @click="currentTab = 'settings'"
          >
            <span class="material-symbols-rounded tab-icon">tune</span>
            <span>Settings</span>
            <span v-if="overriddenScenesCount" class="tab-badge override-badge" title="Custom scene overrides active">
              {{ overriddenScenesCount }}
            </span>
          </button>
        </div>
      </nav>
    </header>

    <!-- Main Content Area -->
    <main class="app-main">
      <div class="content-container">
        <!-- Error Alert -->
        <div v-if="errorMessage" class="error-banner clean-card">
          <span class="material-symbols-rounded error-icon">error_outline</span>
          <span class="error-text">{{ errorMessage }}</span>
          <button type="button" class="clean-btn clean-btn-sm" @click="loadCurrentWorkspace">
            Retry
          </button>
        </div>

        <!-- Loading State -->
        <div v-if="loading && !workspaceData" class="loading-state">
          <div class="clean-spinner"></div>
          <p class="loading-label">Loading workspace <strong>{{ selectedStem }}</strong>...</p>
        </div>

        <!-- Tab Views -->
        <div v-else-if="workspaceData" class="view-wrapper">
          <!-- 1. Story Reader -->
          <StoryReader
            v-if="currentTab === 'reader'"
            :stem="selectedStem"
            :markdown-content="workspaceData.markdownContent"
            :markdown-type="workspaceData.markdownType"
            :images="workspaceData.generatedImages"
            :videos="workspaceData.generatedVideos"
            :tags="workspaceData.tags"
            @preview="openPreview"
            @open-add-tag="openAddTagModal"
            @refresh="() => loadCurrentWorkspace(true)"
          />

          <!-- 2. Media Tags Review (Image & Video) -->
          <MediaTagsReview
            v-else-if="currentTab === 'tags'"
            :stem="selectedStem"
            :tags="workspaceData.tags"
            :images="workspaceData.generatedImages"
            :videos="workspaceData.generatedVideos"
            @preview="openPreview"
            @open-add-tag="openAddTagModal"
            @refresh="() => loadCurrentWorkspace(true)"
          />

          <!-- 3. Characters -->
          <CharactersGallery
            v-else-if="currentTab === 'characters'"
            :stem="selectedStem"
            :characters="workspaceData.characters"
            @preview="openPreview"
            @refresh="() => loadCurrentWorkspace(true)"
          />

          <!-- 4. Style Profile -->
          <StyleProfile
            v-else-if="currentTab === 'style'"
            :stem="selectedStem"
            :style-data="workspaceData.style"
            @preview="openPreview"
            @refresh="() => loadCurrentWorkspace(true)"
          />

          <!-- 5. Asset Files Gallery -->
          <MediaGallery
            v-else-if="currentTab === 'media'"
            :stem="selectedStem"
            :images="workspaceData.generatedImages"
            :videos="workspaceData.generatedVideos"
            :tags="workspaceData.tags"
            @preview="openPreview"
            @refresh="() => loadCurrentWorkspace(true)"
          />

          <!-- 6. Generations Activity & History -->
          <GenerationTasksTab
            v-else-if="currentTab === 'tasks'"
            :stem="selectedStem"
            @preview="openPreview"
            @switch-tab="(tab) => currentTab = tab"
            @refresh="() => loadCurrentWorkspace(true)"
          />

          <!-- 7. Generation Settings -->
          <GenerationSettingsTab
            v-else-if="currentTab === 'settings'"
            :stem="selectedStem"
            :tags="workspaceData.tags || []"
            :settings="currentWorkspaceSettings"
            @update-settings="onSettingsUpdated"
            @preview="openPreview"
          />
        </div>

        <!-- No Workspaces Found -->
        <div v-else class="empty-state clean-card">
          <span class="material-symbols-rounded empty-icon">folder_open</span>
          <h3>No Workspaces Found</h3>
          <p>Generate workspaces in <code>outputs/</code> to inspect characters, media tags, and stories.</p>
        </div>
      </div>
    </main>

    <!-- Global Image / Video Lightbox -->
    <ImageLightbox
      ref="lightboxRef"
      :stem="selectedStem"
      @refresh="() => loadCurrentWorkspace(true)"
    />

    <!-- Global Add Scene Tag Modal -->
    <AddSceneTagModal
      ref="addTagModalRef"
      :stem="selectedStem"
      :tags="workspaceData?.tags || []"
      @inserted="onTagInserted"
      @refresh="() => loadCurrentWorkspace(true)"
    />

    <!-- Global Generation Settings Dialog -->
    <dialog
      ref="settingsDialogRef"
      class="settings-dialog"
      @click="onSettingsBackdropClick"
    >
      <div class="settings-sheet clean-card" @click.stop>
        <header class="settings-head">
          <div class="settings-title-group">
            <span class="material-symbols-rounded head-icon">tune</span>
            <span class="settings-title">Default Image Generation Settings</span>
          </div>
          <button type="button" class="clean-icon-btn" @click="closeSettings">
            <span class="material-symbols-rounded">close</span>
          </button>
        </header>

        <div class="settings-body">
          <div class="form-group">
            <label class="form-label">
              <span class="material-symbols-rounded">aspect_ratio</span>
              Aspect Ratio
            </label>
            <div class="pill-options">
              <button
                v-for="r in ['16:9', '4:3', '1:1', '3:4', '9:16', '21:9']"
                :key="r"
                type="button"
                class="pill-opt"
                :class="{ active: genSettings.ratio === r }"
                @click="genSettings.ratio = r"
              >
                {{ r }}
              </button>
            </div>
            <span class="form-hint">Controls the default image frame ratio passed to Gemini (default: 16:9).</span>
          </div>

          <div class="form-group">
            <label class="form-label">
              <span class="material-symbols-rounded">photo_size_select_actual</span>
              Resolution Size
            </label>
            <div class="pill-options">
              <button
                v-for="s in ['1K', '2K', '4K']"
                :key="s"
                type="button"
                class="pill-opt"
                :class="{ active: genSettings.size === s }"
                @click="genSettings.size = s"
              >
                {{ s }}
              </button>
            </div>
            <span class="form-hint">Output resolution (1K standard, 2K QHD, 4K Ultra HD).</span>
          </div>

          <div class="form-group">
            <label class="form-label">
              <span class="material-symbols-rounded">neurology</span>
              Image Generation Model
            </label>
            <input
              v-model="genSettings.model"
              type="text"
              class="clean-input"
              placeholder="gemini-3.1-flash-image"
            />
            <span class="form-hint">Model identifier used by Google GenAI SDK.</span>
          </div>

          <div class="form-group">
            <label class="form-label">
              <span class="material-symbols-rounded">key</span>
              Google Gemini API Key
            </label>
            <input
              v-model="apiKeyInput"
              type="password"
              class="clean-input"
              placeholder="Enter GEMINI_API_KEY (AIza...)"
            />
            <span class="form-hint">Used for Gemini 3.1 Flash Image, Veo 2.0 Video, and AI prompt refinement.</span>
          </div>
        </div>

        <footer class="settings-footer">
          <button type="button" class="clean-btn" @click="closeSettings">Cancel</button>
          <button type="button" class="clean-btn clean-btn-primary save-btn" @click="saveAndCloseSettings">
            <span class="material-symbols-rounded">check</span>
            Save Settings
          </button>
        </footer>
      </div>
    </dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue';
import {
  getWorkspaces,
  getWorkspace,
  onGenerationComplete,
  generationState,
  tasksState,
  fetchWorkspaceTasks,
  workspaceSettingsCache,
  getGenerationSettings,
  saveGenerationSettings,
  fetchServerApiKeyStatus,
  saveServerApiKey,
  getStoredApiKey,
  runTagGeneration
} from './services/api';
import StoryReader from './components/StoryReader.vue';
import MediaTagsReview from './components/MediaTagsReview.vue';
import CharactersGallery from './components/CharactersGallery.vue';
import StyleProfile from './components/StyleProfile.vue';
import MediaGallery from './components/MediaGallery.vue';
import ImageLightbox from './components/ImageLightbox.vue';
import GenerationSettingsTab from './components/GenerationSettingsTab.vue';
import GenerationTasksTab from './components/GenerationTasksTab.vue';
import AddSceneTagModal from './components/AddSceneTagModal.vue';

const workspaces = ref([]);
const selectedStem = ref('');
const workspaceData = ref(null);
const currentTab = ref(localStorage.getItem('storybook_current_tab') || 'reader');
watch(currentTab, (val) => {
  if (val) localStorage.setItem('storybook_current_tab', val);
});
const loading = ref(true);
const isRefreshing = ref(false);
const errorMessage = ref('');
const isDark = ref(false);
const lightboxRef = ref(null);
const settingsDialogRef = ref(null);
const addTagModalRef = ref(null);
const apiKeyInput = ref(getStoredApiKey());

const genSettings = reactive(getGenerationSettings());

function openAddTagModal(options = {}) {
  if (addTagModalRef.value) {
    addTagModalRef.value.open(options);
  }
}

async function onTagInserted(data) {
  await loadCurrentWorkspace(true);
  if (data?.generateNow) {
    setTimeout(() => {
      runTagGeneration(selectedStem.value, {
        tagId: data.tagId,
        section: data.section,
        type: data.type
      });
    }, 300);
  }
}

const currentWorkspaceSettings = computed(() => {
  return workspaceSettingsCache[selectedStem.value] || workspaceData.value?.settings || {
    global: {
      image: { ratio: '16:9', size: '1K', model: 'gemini-3.1-flash-image' },
      video: { ratio: '16:9', model: 'veo-2.0-generate-001', duration: '5s' }
    },
    scenes: {}
  };
});

const overriddenScenesCount = computed(() => {
  const scenes = currentWorkspaceSettings.value?.scenes;
  if (!scenes) return 0;
  return Object.keys(scenes).length;
});

function onSettingsUpdated(newSettings) {
  if (workspaceData.value) {
    workspaceData.value.settings = newSettings;
  }
  workspaceSettingsCache[selectedStem.value] = newSettings;
}

async function openSettings() {
  const current = getGenerationSettings();
  genSettings.ratio = current.ratio || '16:9';
  genSettings.size = current.size || '1K';
  genSettings.model = current.model || 'gemini-3.1-flash-image';
  const status = await fetchServerApiKeyStatus();
  apiKeyInput.value = getStoredApiKey() || (status.has_key ? status.masked_key : '');
  if (settingsDialogRef.value) {
    settingsDialogRef.value.showModal();
  }
}

function closeSettings() {
  if (settingsDialogRef.value) {
    settingsDialogRef.value.close();
  }
}

async function saveAndCloseSettings() {
  saveGenerationSettings({
    ratio: genSettings.ratio,
    size: genSettings.size,
    model: genSettings.model
  });
  if (apiKeyInput.value && !apiKeyInput.value.includes('...')) {
    await saveServerApiKey(apiKeyInput.value.trim());
  }
  closeSettings();
}

function onSettingsBackdropClick(event) {
  if (event.target === settingsDialogRef.value) {
    closeSettings();
  }
}

const activeGenerations = computed(() => {
  return Object.values(generationState.activeMap).filter(item => item.stem === selectedStem.value && item.status === 'generating');
});

const runningTasksCount = computed(() => {
  return tasksState.runningCount || activeGenerations.value.length;
});

const failedTasksCount = computed(() => {
  return tasksState.failedCount || 0;
});

const activeTagNames = computed(() => {
  if (activeGenerations.value.length > 0) {
    return activeGenerations.value.map(g => g.tagId).join(', ');
  }
  const running = (tasksState.tasks || []).filter(t => t.status === 'running');
  if (running.length > 0) {
    return running.map(t => t.tag_id || t.type).join(', ');
  }
  return 'assets';
});

const totalMediaCount = computed(() => {
  if (!workspaceData.value) return 0;
  return (workspaceData.value.generatedImages?.length || 0) + (workspaceData.value.generatedVideos?.length || 0);
});

async function initWorkspaces() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const list = await getWorkspaces();
    workspaces.value = list;
    if (list.length > 0) {
      const savedStem = localStorage.getItem('storybook_selected_workspace');
      const found = list.find(w => w.stem === savedStem);
      selectedStem.value = found ? found.stem : list[0].stem;
      await loadCurrentWorkspace();
    } else {
      loading.value = false;
    }
  } catch (err) {
    errorMessage.value = err.message;
    loading.value = false;
  }
}

async function onWorkspaceChange() {
  workspaceData.value = null;
  await loadCurrentWorkspace(false);
}

let isLoadingWorkspace = false;
let loadDebounceTimer = null;

async function loadCurrentWorkspace(silent = false) {
  if (!selectedStem.value || isLoadingWorkspace) return;
  isLoadingWorkspace = true;

  if (!silent && !workspaceData.value) {
    loading.value = true;
  }
  isRefreshing.value = true;
  errorMessage.value = '';
  localStorage.setItem('storybook_selected_workspace', selectedStem.value);

  try {
    const data = await getWorkspace(selectedStem.value);
    workspaceData.value = data;
  } catch (err) {
    errorMessage.value = err.message;
  } finally {
    loading.value = false;
    isRefreshing.value = false;
    isLoadingWorkspace = false;
  }
}

async function refreshData() {
  await loadCurrentWorkspace(true);
}

function openPreview(item) {
  if (lightboxRef.value) {
    lightboxRef.value.open(item);
  }
}

function initTheme() {
  const saved = localStorage.getItem('storybook_theme');
  if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDark.value = true;
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    isDark.value = false;
    document.documentElement.setAttribute('data-theme', 'light');
  }
}

function toggleTheme() {
  isDark.value = !isDark.value;
  const theme = isDark.value ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('storybook_theme', theme);
}

watch(() => tasksState.runningCount, (newVal, oldVal) => {
  if (oldVal > 0 && newVal === 0) {
    if (loadDebounceTimer) clearTimeout(loadDebounceTimer);
    loadDebounceTimer = setTimeout(() => {
      loadDebounceTimer = null;
      loadCurrentWorkspace(true);
    }, 300);
  }
});

onMounted(() => {
  initTheme();
  initWorkspaces();
  onGenerationComplete((err, payload) => {
    if (!err && (payload?.allFinished || payload?.stem === selectedStem.value)) {
      if (loadDebounceTimer) clearTimeout(loadDebounceTimer);
      loadDebounceTimer = setTimeout(() => {
        loadDebounceTimer = null;
        loadCurrentWorkspace(true);
      }, 300);
    }
  });
});
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-app);
  color: var(--text-primary);
}

/* Header */
.app-header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-default);
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: var(--shadow-xs);
}

.header-container {
  max-width: 1320px;
  margin: 0 auto;
  padding: 0.75rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.brand-symbol {
  font-size: 22px;
  color: var(--accent-primary);
}

.brand-name {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.workspace-selector {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.ws-label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.select-box {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.ws-dropdown {
  appearance: none;
  padding-right: 2rem;
  font-weight: 600;
  height: 32px;
  padding-top: 0;
  padding-bottom: 0;
  min-width: 200px;
}

.select-arrow {
  position: absolute;
  right: 0.4rem;
  pointer-events: none;
  font-size: 18px;
  color: var(--text-muted);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.gen-progress-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: #0284c7;
  background: rgba(14, 165, 233, 0.1);
  border: 1px solid rgba(14, 165, 233, 0.25);
  padding: 0.25rem 0.65rem;
  border-radius: var(--radius-full);
}

.gen-progress-pill .is-spinning {
  font-size: 15px;
}

.header-add-btn {
  background: var(--primary, #6750a4);
  color: #ffffff;
  font-weight: 600;
  border-radius: 9999px;
  padding: 0.35rem 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  box-shadow: 0 2px 6px rgba(103, 80, 164, 0.25);
  transition: all 0.2s ease;
  font-size: 0.82rem;
}

.header-add-btn:hover:not(:disabled) {
  opacity: 0.94;
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(103, 80, 164, 0.35);
}

.header-add-btn .material-symbols-rounded {
  font-size: 1.15rem;
}

/* Segmented Tabs Bar */
.nav-tabs-bar {
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-surface);
}

.nav-tabs-container {
  max-width: 1320px;
  margin: 0 auto;
  padding: 0 1.5rem;
  display: flex;
  gap: 0.25rem;
  overflow-x: auto;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.65rem 0.9rem;
  border: none;
  background: transparent;
  font-family: var(--font-sans);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--accent-primary);
  border-bottom-color: var(--accent-primary);
  font-weight: 600;
}

.tab-icon {
  font-size: 17px;
}

.tab-badge {
  font-size: 0.7rem;
  font-weight: 600;
  background: var(--badge-bg);
  color: var(--badge-text);
  border: 1px solid var(--badge-border);
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-full);
}

.tab-btn.active .tab-badge {
  background: var(--accent-primary-subtle);
  color: var(--accent-primary-text);
  border-color: transparent;
}

.tab-badge.override-badge {
  background: rgba(139, 92, 246, 0.14);
  color: #7c3aed;
  border-color: rgba(139, 92, 246, 0.3);
}

.tab-badge.running-badge {
  background: #fbc02d;
  color: #5d4037;
  border-color: #f57f17;
}

.tab-badge.failed-badge {
  background: #ef5350;
  color: #ffffff;
  border-color: #d32f2f;
}

.cursor-pointer {
  cursor: pointer;
}

.tab-btn.active .tab-badge.override-badge {
  background: #7c3aed;
  color: #ffffff;
}

/* Main Area */
.app-main {
  flex: 1;
  padding: 1.75rem 0;
}

.content-container {
  max-width: 1320px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border-color: #fecaca;
  color: #991b1b;
  margin-bottom: 1.25rem;
  font-size: 0.85rem;
}

[data-theme="dark"] .error-banner {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.25);
  color: #fca5a5;
}

.error-icon {
  font-size: 20px;
}

.error-text {
  flex: 1;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 6rem 1rem;
  gap: 1rem;
}

.clean-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-default);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-label {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.is-spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 4rem 2rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.empty-icon {
  font-size: 40px;
  color: var(--text-muted);
}

.empty-state h3 {
  margin: 0;
  font-size: 1.15rem;
}

.empty-state p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

/* Settings Dialog */
.settings-dialog {
  border: none;
  background: transparent;
  padding: 0;
  margin: auto;
  max-width: 90vw;
  box-shadow: none;
  overflow: visible;
}

.settings-dialog::backdrop {
  background-color: rgba(9, 9, 11, 0.72);
  backdrop-filter: blur(8px);
}

.settings-sheet {
  width: 520px;
  max-width: 90vw;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.settings-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface);
}

.settings-title-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.settings-title-group .head-icon {
  font-size: 20px;
  color: var(--accent-primary);
}

.settings-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.settings-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.form-label .material-symbols-rounded {
  font-size: 16px;
  color: var(--text-muted);
}

.pill-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.pill-opt {
  border: 1px solid var(--border-default);
  background: var(--bg-surface-secondary);
  color: var(--text-secondary);
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  font-weight: 500;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.pill-opt:hover {
  background: var(--bg-surface-hover);
  color: var(--text-primary);
}

.pill-opt.active {
  background: var(--accent-primary);
  color: white;
  border-color: var(--accent-primary);
  font-weight: 600;
}

.form-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.settings-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1.25rem;
  border-top: 1px solid var(--border-default);
  background: var(--bg-surface-secondary);
}

.save-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--accent-primary);
  color: white;
  border: none;
  font-weight: 600;
  padding: 0.4rem 0.9rem;
  border-radius: var(--radius-sm);
}

.save-btn:hover {
  opacity: 0.92;
}
</style>
