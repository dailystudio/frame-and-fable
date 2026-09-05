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
                @change="loadCurrentWorkspace"
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
          <!-- Refresh -->
          <button
            type="button"
            class="clean-icon-btn"
            title="Reload workspace"
            :disabled="loading"
            @click="refreshData"
          >
            <span class="material-symbols-rounded" :class="{ 'is-spinning': loading }">refresh</span>
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
        <div v-if="loading" class="loading-state">
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
          />

          <!-- 2. Media Tags Review (Image & Video) -->
          <MediaTagsReview
            v-else-if="currentTab === 'tags'"
            :stem="selectedStem"
            :tags="workspaceData.tags"
            :images="workspaceData.generatedImages"
            :videos="workspaceData.generatedVideos"
            @preview="openPreview"
          />

          <!-- 3. Characters -->
          <CharactersGallery
            v-else-if="currentTab === 'characters'"
            :stem="selectedStem"
            :characters="workspaceData.characters"
            @preview="openPreview"
          />

          <!-- 4. Style Profile -->
          <StyleProfile
            v-else-if="currentTab === 'style'"
            :stem="selectedStem"
            :style-data="workspaceData.style"
            @preview="openPreview"
          />

          <!-- 5. Asset Files Gallery -->
          <MediaGallery
            v-else-if="currentTab === 'media'"
            :stem="selectedStem"
            :images="workspaceData.generatedImages"
            :videos="workspaceData.generatedVideos"
            :tags="workspaceData.tags"
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
    <ImageLightbox ref="lightboxRef" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { getWorkspaces, getWorkspace } from './services/api';
import StoryReader from './components/StoryReader.vue';
import MediaTagsReview from './components/MediaTagsReview.vue';
import CharactersGallery from './components/CharactersGallery.vue';
import StyleProfile from './components/StyleProfile.vue';
import MediaGallery from './components/MediaGallery.vue';
import ImageLightbox from './components/ImageLightbox.vue';

const workspaces = ref([]);
const selectedStem = ref('');
const workspaceData = ref(null);
const currentTab = ref('tags'); // Default to 'tags' or 'reader' for instant inspection
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
  gap: 0.5rem;
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
</style>
