<template>
  <div class="app-layout">
    <!-- Top App Bar -->
    <header class="md-top-app-bar">
      <div class="app-brand">
        <span class="material-symbols-rounded brand-icon">auto_stories</span>
        <div class="brand-text">
          <h1 class="brand-title">Storybook Craft</h1>
          <span class="brand-subtitle">Asset & Output Inspector</span>
        </div>
      </div>

      <!-- Workspace Selector in App Bar -->
      <div class="workspace-selector-wrap">
        <label for="workspace-select" class="selector-label">Workspace:</label>
        <div class="select-container">
          <select
            id="workspace-select"
            v-model="selectedStem"
            class="workspace-select"
            :disabled="loading"
            @change="loadCurrentWorkspace"
          >
            <option v-for="ws in workspaces" :key="ws.stem" :value="ws.stem">
              {{ ws.stem }} ({{ ws.charactersCount }} chars, {{ ws.generatedImagesCount + ws.generatedVideosCount }} media)
            </option>
          </select>
          <span class="material-symbols-rounded select-arrow">arrow_drop_down</span>
        </div>
      </div>

      <div class="app-bar-actions">
        <!-- Quick stats -->
        <div v-if="workspaceData" class="quick-stats-bar">
          <span class="stat-pill" title="Characters">
            <span class="material-symbols-rounded">face</span>
            {{ workspaceData.characters?.length || 0 }}
          </span>
          <span class="stat-pill" title="Generated Media">
            <span class="material-symbols-rounded">perm_media</span>
            {{ (workspaceData.generatedImages?.length || 0) + (workspaceData.generatedVideos?.length || 0) }}
          </span>
        </div>

        <!-- Reload Data -->
        <button
          type="button"
          class="md-icon-btn"
          title="Reload workspace"
          :disabled="loading"
          @click="refreshData"
        >
          <span class="material-symbols-rounded" :class="{ 'spin-anim': loading }">refresh</span>
        </button>

        <!-- Theme Toggle -->
        <button
          type="button"
          class="md-icon-btn"
          :title="isDark ? 'Switch to Light theme' : 'Switch to Dark theme'"
          @click="toggleTheme"
        >
          <span class="material-symbols-rounded">
            {{ isDark ? 'light_mode' : 'dark_mode' }}
          </span>
        </button>
      </div>
    </header>

    <div class="app-body">
      <!-- Navigation Rail / Bar -->
      <nav class="md-nav-rail">
        <button
          type="button"
          class="nav-tab-btn"
          :class="{ active: currentTab === 'reader' }"
          @click="currentTab = 'reader'"
        >
          <span class="material-symbols-rounded nav-icon">menu_book</span>
          <span class="nav-label">Reader</span>
        </button>

        <button
          type="button"
          class="nav-tab-btn"
          :class="{ active: currentTab === 'characters' }"
          @click="currentTab = 'characters'"
        >
          <span class="material-symbols-rounded nav-icon">face</span>
          <span class="nav-label">Characters</span>
          <span v-if="workspaceData?.characters?.length" class="nav-badge">
            {{ workspaceData.characters.length }}
          </span>
        </button>

        <button
          type="button"
          class="nav-tab-btn"
          :class="{ active: currentTab === 'style' }"
          @click="currentTab = 'style'"
        >
          <span class="material-symbols-rounded nav-icon">palette</span>
          <span class="nav-label">Style</span>
          <span v-if="workspaceData?.style?.images?.length" class="nav-badge">
            {{ workspaceData.style.images.length }}
          </span>
        </button>

        <button
          type="button"
          class="nav-tab-btn"
          :class="{ active: currentTab === 'media' }"
          @click="currentTab = 'media'"
        >
          <span class="material-symbols-rounded nav-icon">photo_library</span>
          <span class="nav-label">Media</span>
          <span v-if="totalMediaCount" class="nav-badge">
            {{ totalMediaCount }}
          </span>
        </button>

        <button
          type="button"
          class="nav-tab-btn"
          :class="{ active: currentTab === 'breakdown' }"
          @click="currentTab = 'breakdown'"
        >
          <span class="material-symbols-rounded nav-icon">list_alt</span>
          <span class="nav-label">Scenes</span>
          <span v-if="workspaceData?.tags?.length" class="nav-badge">
            {{ workspaceData.tags.length }}
          </span>
        </button>
      </nav>

      <!-- Main Content Stage -->
      <main class="main-content-area">
        <!-- Error Alert -->
        <div v-if="errorMessage" class="error-banner md-card-elevated">
          <span class="material-symbols-rounded error-icon">error</span>
          <div class="error-msg">
            <strong>Failed to load:</strong> {{ errorMessage }}
          </div>
          <button type="button" class="md-btn md-btn-tonal" @click="loadCurrentWorkspace">
            Retry
          </button>
        </div>

        <!-- Loading Skeleton -->
        <div v-if="loading" class="loading-container">
          <div class="loading-spinner"></div>
          <p class="loading-text">Loading workspace <strong>{{ selectedStem }}</strong>...</p>
        </div>

        <!-- Active View -->
        <div v-else-if="workspaceData" class="view-content">
          <!-- 1. Story Reader Tab -->
          <StoryReader
            v-if="currentTab === 'reader'"
            :stem="selectedStem"
            :markdown-content="workspaceData.markdownContent"
            :markdown-type="workspaceData.markdownType"
            :images="workspaceData.generatedImages"
            :videos="workspaceData.generatedVideos"
            :tags="workspaceData.tags"
            @preview="openPreview"
          />

          <!-- 2. Characters Tab -->
          <CharactersGallery
            v-else-if="currentTab === 'characters'"
            :stem="selectedStem"
            :characters="workspaceData.characters"
            @preview="openPreview"
          />

          <!-- 3. Style Tab -->
          <StyleProfile
            v-else-if="currentTab === 'style'"
            :stem="selectedStem"
            :style-data="workspaceData.style"
            @preview="openPreview"
          />

          <!-- 4. Generated Media Tab -->
          <MediaGallery
            v-else-if="currentTab === 'media'"
            :stem="selectedStem"
            :images="workspaceData.generatedImages"
            :videos="workspaceData.generatedVideos"
            :tags="workspaceData.tags"
            @preview="openPreview"
          />

          <!-- 5. Scene Breakdown Tab -->
          <SceneBreakdown
            v-else-if="currentTab === 'breakdown'"
            :stem="selectedStem"
            :tags="workspaceData.tags"
            :images="workspaceData.generatedImages"
            :videos="workspaceData.generatedVideos"
            @preview="openPreview"
          />
        </div>

        <div v-else class="no-workspace-state">
          <span class="material-symbols-rounded empty-icon">folder_off</span>
          <h3>No Workspaces Found in <code>outputs/</code></h3>
          <p>Run storybook commands to generate workspaces and review output results.</p>
        </div>
      </main>
    </div>

    <!-- Global Image / Video Lightbox -->
    <ImageLightbox ref="lightboxRef" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { getWorkspaces, getWorkspace } from './services/api';
import StoryReader from './components/StoryReader.vue';
import CharactersGallery from './components/CharactersGallery.vue';
import StyleProfile from './components/StyleProfile.vue';
import MediaGallery from './components/MediaGallery.vue';
import SceneBreakdown from './components/SceneBreakdown.vue';
import ImageLightbox from './components/ImageLightbox.vue';

const workspaces = ref([]);
const selectedStem = ref('');
const workspaceData = ref(null);
const currentTab = ref('reader'); // 'reader' | 'characters' | 'style' | 'media' | 'breakdown'
const loading = ref(true);
const errorMessage = ref('');
const isDark = ref(false);
const lightboxRef = ref(null);

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
      // Pick first or restore from localStorage
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

async function loadCurrentWorkspace() {
  if (!selectedStem.value) return;
  loading.value = true;
  errorMessage.value = '';
  localStorage.setItem('storybook_selected_workspace', selectedStem.value);

  try {
    const data = await getWorkspace(selectedStem.value);
    workspaceData.value = data;
  } catch (err) {
    errorMessage.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function refreshData() {
  await initWorkspaces();
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

onMounted(() => {
  initTheme();
  initWorkspaces();
});
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--md-sys-color-background);
  color: var(--md-sys-color-on-background);
}

/* Top App Bar */
.md-top-app-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 1.5rem;
  background-color: var(--md-sys-color-surface-container);
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: var(--elevation-1);
  gap: 1rem;
}

.app-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.brand-icon {
  font-size: 30px;
  color: var(--md-sys-color-primary);
  background: var(--md-sys-color-primary-container);
  padding: 0.35rem;
  border-radius: var(--shape-corner-medium);
}

.brand-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--md-sys-color-on-surface);
}

.brand-subtitle {
  font-size: 0.75rem;
  color: var(--md-sys-color-on-surface-variant);
}

.workspace-selector-wrap {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex: 1;
  max-width: 480px;
}

.selector-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--md-sys-color-on-surface-variant);
}

.select-container {
  position: relative;
  flex: 1;
}

.workspace-select {
  width: 100%;
  appearance: none;
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
  border: 1px solid var(--md-sys-color-outline);
  border-radius: var(--shape-corner-medium);
  padding: 0.5rem 2.2rem 0.5rem 0.85rem;
  font-family: var(--font-sans);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.workspace-select:focus {
  outline: none;
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 0 0 2px var(--md-sys-color-primary-container);
}

.select-arrow {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--md-sys-color-on-surface-variant);
}

.app-bar-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.quick-stats-bar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  background: var(--md-sys-color-surface-container-highest);
  padding: 0.25rem 0.6rem;
  border-radius: var(--shape-corner-full);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.stat-pill .material-symbols-rounded {
  font-size: 16px;
  color: var(--md-sys-color-primary);
}

.spin-anim {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* App Body */
.app-body {
  display: flex;
  flex: 1;
}

/* Navigation Rail */
.md-nav-rail {
  width: 96px;
  background-color: var(--md-sys-color-surface-container-low);
  border-right: 1px solid var(--md-sys-color-outline-variant);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1rem 0;
  gap: 0.75rem;
  flex-shrink: 0;
}

.nav-tab-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 76px;
  height: 64px;
  border: none;
  background: transparent;
  border-radius: var(--shape-corner-large);
  cursor: pointer;
  position: relative;
  transition: background-color 0.2s, color 0.2s;
  color: var(--md-sys-color-on-surface-variant);
}

.nav-tab-btn:hover {
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
}

.nav-tab-btn.active {
  background-color: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  font-weight: 700;
}

.nav-icon {
  font-size: 24px;
  margin-bottom: 2px;
}

.nav-label {
  font-size: 0.72rem;
  letter-spacing: 0.02em;
}

.nav-badge {
  position: absolute;
  top: 4px;
  right: 8px;
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  border-radius: var(--shape-corner-full);
}

/* Main Content Area */
.main-content-area {
  flex: 1;
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

@media (max-width: 768px) {
  .app-body {
    flex-direction: column;
  }
  .md-nav-rail {
    width: 100%;
    height: auto;
    flex-direction: row;
    justify-content: space-around;
    padding: 0.5rem;
    border-right: none;
    border-bottom: 1px solid var(--md-sys-color-outline-variant);
  }
  .nav-tab-btn {
    width: 60px;
    height: 52px;
  }
  .main-content-area {
    padding: 1rem;
  }
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: #fee2e2;
  color: #991b1b;
  padding: 1rem 1.25rem;
  border-radius: var(--shape-corner-medium);
  margin-bottom: 1.5rem;
}

[data-theme="dark"] .error-banner {
  background: #450a0a;
  color: #fca5a5;
}

.error-icon {
  font-size: 24px;
}

.error-msg {
  flex: 1;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem 1rem;
  gap: 1.25rem;
}

.loading-spinner {
  width: 44px;
  height: 44px;
  border: 4px solid var(--md-sys-color-surface-container-highest);
  border-top-color: var(--md-sys-color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-text {
  font-size: 1rem;
  color: var(--md-sys-color-on-surface-variant);
}

.no-workspace-state {
  text-align: center;
  padding: 6rem 2rem;
  color: var(--md-sys-color-on-surface-variant);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.no-workspace-state code {
  background: var(--md-sys-color-surface-container-high);
  padding: 0.2rem 0.4rem;
  border-radius: var(--shape-corner-small);
}
</style>
