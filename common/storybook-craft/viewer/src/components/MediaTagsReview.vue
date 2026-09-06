<template>
  <div class="media-tags-review">
    <!-- Header Metrics Summary -->
    <div class="metrics-row">
      <div class="metric-card clean-card">
        <span class="metric-label">Total Media Tags</span>
        <div class="metric-value-wrap">
          <span class="metric-value">{{ tags.length }}</span>
          <span class="metric-sub">scenes</span>
        </div>
      </div>

      <div class="metric-card clean-card">
        <span class="metric-label">
          <span class="material-symbols-rounded icon-type icon-img">image</span>
          Image Tags
        </span>
        <div class="metric-value-wrap">
          <span class="metric-value">{{ imageTagsCount }}</span>
          <span class="metric-sub">illustrations</span>
        </div>
      </div>

      <div class="metric-card clean-card">
        <span class="metric-label">
          <span class="material-symbols-rounded icon-type icon-vid">videocam</span>
          Video Tags
        </span>
        <div class="metric-value-wrap">
          <span class="metric-value">{{ videoTagsCount }}</span>
          <span class="metric-sub">clips</span>
        </div>
      </div>

      <div class="metric-card clean-card">
        <span class="metric-label">Generation Status</span>
        <div class="status-summary-wrap">
          <div class="status-item generated">
            <span class="status-dot"></span>
            <span class="status-num">{{ generatedCount }}</span>
            <span class="status-txt">Generated</span>
          </div>
          <div class="status-item pending">
            <span class="status-dot"></span>
            <span class="status-num">{{ pendingCount }}</span>
            <span class="status-txt">Pending</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Controls Toolbar -->
    <div class="toolbar-card clean-card">
      <div class="toolbar-left">
        <!-- Search -->
        <div class="search-box">
          <span class="material-symbols-rounded search-icon">search</span>
          <input
            v-model="searchQuery"
            type="text"
            class="clean-input search-input"
            placeholder="Search tags by ID, prompt, or section..."
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

        <!-- Type Filter -->
        <div class="filter-group">
          <button
            type="button"
            class="filter-pill"
            :class="{ active: filterType === 'all' }"
            @click="filterType = 'all'"
          >
            All ({{ tags.length }})
          </button>
          <button
            type="button"
            class="filter-pill"
            :class="{ active: filterType === 'image' }"
            @click="filterType = 'image'"
          >
            <span class="material-symbols-rounded pill-icon">image</span>
            Images ({{ imageTagsCount }})
          </button>
          <button
            type="button"
            class="filter-pill"
            :class="{ active: filterType === 'video' }"
            @click="filterType = 'video'"
          >
            <span class="material-symbols-rounded pill-icon">videocam</span>
            Videos ({{ videoTagsCount }})
          </button>
        </div>

        <!-- Status Filter -->
        <div class="filter-group">
          <button
            type="button"
            class="filter-pill"
            :class="{ active: filterStatus === 'all' }"
            @click="filterStatus = 'all'"
          >
            All Status
          </button>
          <button
            type="button"
            class="filter-pill"
            :class="{ active: filterStatus === 'generated' }"
            @click="filterStatus = 'generated'"
          >
            Generated ({{ generatedCount }})
          </button>
          <button
            type="button"
            class="filter-pill"
            :class="{ active: filterStatus === 'pending' }"
            @click="filterStatus = 'pending'"
          >
            Pending ({{ pendingCount }})
          </button>
        </div>

        <!-- Section Filter Dropdown -->
        <div v-if="uniqueSections.length > 1" class="section-select-wrap">
          <select v-model="selectedSection" class="clean-select section-select">
            <option value="">All Chapters / Sections ({{ uniqueSections.length }})</option>
            <option v-for="sec in uniqueSections" :key="sec" :value="sec">
              {{ sec }}
            </option>
          </select>
        </div>
      </div>

      <div class="toolbar-right">
        <!-- Add Scene Tag Button -->
        <button
          type="button"
          class="clean-btn clean-btn-sm add-scene-tag-btn"
          title="Add a new image or video scene tag into this story"
          @click="emit('open-add-tag')"
        >
          <span class="material-symbols-rounded">add_photo_alternate</span>
          <span>+ Add Scene Tag</span>
        </button>

        <!-- Auto-Generate / Enrich Prompts -->
        <button
          type="button"
          class="clean-btn clean-btn-sm enrich-prompts-btn"
          :disabled="isEnrichingPrompts"
          :title="missingPromptsCount > 0 ? 'Auto-generate prompts for tags that have empty prompts' : 'Enrich / regenerate prompts for all tags'"
          @click="handleEnrichMissingPrompts"
        >
          <span class="material-symbols-rounded" :class="{ 'is-spinning': isEnrichingPrompts }">
            {{ isEnrichingPrompts ? 'sync' : 'auto_awesome' }}
          </span>
          <span>{{ isEnrichingPrompts ? 'Synthesizing...' : (missingPromptsCount > 0 ? `Generate Missing Prompts (${missingPromptsCount})` : '✨ Enrich Prompts') }}</span>
        </button>

        <!-- Copy All Prompts -->
        <button
          type="button"
          class="clean-btn clean-btn-sm"
          title="Copy filtered prompts"
          @click="copyAllPrompts"
        >
          <span class="material-symbols-rounded">
            {{ allCopied ? 'check' : 'content_copy' }}
          </span>
          {{ allCopied ? 'Copied' : 'Copy Prompts' }}
        </button>

        <!-- View Mode Switcher -->
        <div class="view-switch">
          <button
            type="button"
            class="view-btn"
            :class="{ active: viewMode === 'cards' }"
            title="Card View"
            @click="viewMode = 'cards'"
          >
            <span class="material-symbols-rounded">grid_view</span>
          </button>
          <button
            type="button"
            class="view-btn"
            :class="{ active: viewMode === 'table' }"
            title="Compact Table View"
            @click="viewMode = 'table'"
          >
            <span class="material-symbols-rounded">table_rows</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="filteredTags.length === 0" class="empty-state clean-card">
      <span class="material-symbols-rounded empty-icon">filter_alt_off</span>
      <h3>No Media Tags Found</h3>
      <p v-if="searchQuery || filterType !== 'all' || filterStatus !== 'all' || selectedSection">
        No tags match the active filters.
      </p>
      <p v-else>
        This workspace markdown does not contain any <code>&lt;!-- storybook-media --&gt;</code> tags.
      </p>
      <button
        v-if="searchQuery || filterType !== 'all' || filterStatus !== 'all' || selectedSection"
        type="button"
        class="clean-btn"
        @click="resetFilters"
      >
        Reset Filters
      </button>
    </div>

    <!-- 1. Card View -->
    <div v-else-if="viewMode === 'cards'" class="tag-cards-grid">
      <div
        v-for="(tag, idx) in filteredTags"
        :key="tag.id || idx"
        class="tag-card clean-card"
        :class="{ 'is-video': tag.type === 'video' }"
      >
        <div class="tag-card-head">
          <div class="tag-identity">
            <span class="tag-id-badge">{{ tag.id || `scene-${idx + 1}` }}</span>
            <span class="type-pill" :class="tag.type">
              <span class="material-symbols-rounded">
                {{ tag.type === 'video' ? 'videocam' : 'image' }}
              </span>
              {{ tag.type }}
            </span>
            <span v-if="tag.section" class="section-pill" :title="tag.section">
              {{ tag.section }}
            </span>
          </div>

          <div class="tag-status">
            <!-- Explicit Regenerate / Generate Scene Button -->
            <button
              v-if="tag.isGenerated"
              type="button"
              class="clean-btn clean-btn-sm card-regen-btn"
              :class="{ 'is-loading': isTagGenerating(stem, tag.id) }"
              :disabled="isTagGenerating(stem, tag.id)"
              title="Regenerate this scene via Gemini"
              @click.stop="handleDirectGenerate(tag)"
            >
              <span class="material-symbols-rounded" :class="{ 'is-spinning': isTagGenerating(stem, tag.id) }">
                {{ isTagGenerating(stem, tag.id) ? 'sync' : 'refresh' }}
              </span>
              <span>{{ isTagGenerating(stem, tag.id) ? 'Generating...' : 'Regenerate' }}</span>
            </button>
            <button
              v-else
              type="button"
              class="clean-btn clean-btn-sm card-gen-btn"
              :class="{ 'is-loading': isTagGenerating(stem, tag.id) }"
              :disabled="isTagGenerating(stem, tag.id)"
              title="Generate this scene via Gemini"
              @click.stop="handleDirectGenerate(tag)"
            >
              <span class="material-symbols-rounded" :class="{ 'is-spinning': isTagGenerating(stem, tag.id) }">
                {{ isTagGenerating(stem, tag.id) ? 'sync' : 'auto_awesome' }}
              </span>
              <span>{{ isTagGenerating(stem, tag.id) ? 'Generating...' : 'Generate' }}</span>
            </button>

            <button
              type="button"
              class="clean-btn clean-btn-sm card-inspect-btn"
              title="Inspect prompt template, style ref & character ref"
              @click="previewAsset(tag)"
            >
              <span class="material-symbols-rounded">tune</span>
              Inspect
            </button>
            <span v-if="isTagGenerating(stem, tag.id)" class="status-badge status-generating">
              <span class="material-symbols-rounded is-spinning">sync</span>
              Generating...
            </span>
            <span v-else class="status-badge" :class="tag.isGenerated ? 'status-done' : 'status-wait'">
              <span class="material-symbols-rounded">
                {{ tag.isGenerated ? 'check' : 'schedule' }}
              </span>
              {{ tag.isGenerated ? 'Generated' : 'Pending' }}
            </span>
          </div>
        </div>

        <!-- Prompt Section -->
        <div class="prompt-box">
          <div class="prompt-top">
            <span class="prompt-heading">Generation Prompt</span>
            <button
              type="button"
              class="clean-btn clean-btn-sm copy-btn"
              @click="copyPrompt(tag.prompt, tag.id || idx)"
            >
              <span class="material-symbols-rounded">
                {{ copiedId === (tag.id || idx) ? 'check' : 'content_copy' }}
              </span>
              {{ copiedId === (tag.id || idx) ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <p class="prompt-text">{{ tag.prompt || 'No prompt specified in tag.' }}</p>
        </div>

        <!-- References Strip: Style Reference + Character Reference(s) -->
        <div v-if="tag.style_ref || (tag.character_refs && tag.character_refs.length)" class="card-refs-strip" @click="previewAsset(tag)">
          <span class="refs-strip-label">References:</span>
          <div v-if="tag.style_ref" class="ref-mini-chip style-chip" title="Always active style guide">
            <img v-if="tag.style_ref.assetUrl" :src="tag.style_ref.assetUrl" class="mini-ref-img" />
            <span class="mini-ref-name">Style: {{ tag.style_ref.style_name }}</span>
          </div>
          <div v-for="c in (tag.character_refs || [])" :key="c.name" class="ref-mini-chip char-chip" title="Context-matched character reference">
            <img v-if="c.assetUrl" :src="c.assetUrl" class="mini-ref-img" />
            <span class="mini-ref-name">{{ c.name }}</span>
          </div>
          <span class="inspect-click-hint">
            <span class="material-symbols-rounded">visibility</span>
            View Model Prompt
          </span>
        </div>

        <!-- Context Hint (Story Context) -->
        <div v-if="tag.context_hint" class="context-hint-box">
          <span class="context-label">Story Context Hint:</span>
          <p class="context-text">{{ tag.context_hint }}</p>
        </div>

        <!-- Characters in Scene -->
        <div v-if="tag.characters && tag.characters.length" class="characters-line">
          <span class="char-label">Characters:</span>
          <span v-for="char in tag.characters" :key="char" class="clean-badge">
            <span class="material-symbols-rounded">face</span>
            {{ char }}
          </span>
        </div>

        <!-- Matched Generated Asset Preview -->
        <div v-if="tag.matchedAsset" class="matched-preview-card" @click="previewAsset(tag)">
          <div class="matched-media-box">
            <video
              v-if="tag.type === 'video'"
              :src="tag.matchedAsset.assetUrl"
              class="thumb-asset"
              muted
              preload="metadata"
            ></video>
            <img
              v-else
              :src="tag.matchedAsset.assetUrl"
              :alt="tag.id"
              class="thumb-asset"
              loading="lazy"
            />
            <div class="preview-hover-hint">
              <span class="material-symbols-rounded">fullscreen</span>
              <span>Enlarge Preview</span>
            </div>
          </div>
          <div class="matched-meta-row">
            <span class="matched-filename">{{ tag.matchedAsset.name }}</span>
            <span class="matched-filesize">{{ formatSize(tag.matchedAsset.sizeBytes) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. Compact Table View -->
    <div v-else class="table-container clean-card">
      <table class="clean-table">
        <thead>
          <tr>
            <th style="width: 100px;">Tag ID</th>
            <th style="width: 90px;">Type</th>
            <th style="width: 150px;">Section</th>
            <th>Generation Prompt</th>
            <th style="width: 100px;">Status</th>
            <th style="width: 100px;">Asset</th>
            <th style="width: 70px; text-align: center;">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(tag, idx) in filteredTags" :key="tag.id || idx">
            <td>
              <span class="tag-id-mono">{{ tag.id || `#${idx+1}` }}</span>
            </td>
            <td>
              <span class="type-pill" :class="tag.type">
                <span class="material-symbols-rounded">
                  {{ tag.type === 'video' ? 'videocam' : 'image' }}
                </span>
                {{ tag.type }}
              </span>
            </td>
            <td>
              <span class="table-section-text" :title="tag.section">{{ tag.section }}</span>
            </td>
            <td>
              <div class="table-prompt-cell" :title="tag.prompt">
                {{ tag.prompt || 'No prompt specified' }}
              </div>
            </td>
            <td>
              <span v-if="isTagGenerating(stem, tag.id)" class="status-badge status-generating">
                <span class="material-symbols-rounded is-spinning">sync</span>
                Generating
              </span>
              <span v-else class="status-badge" :class="tag.isGenerated ? 'status-done' : 'status-wait'">
                <span class="material-symbols-rounded">
                  {{ tag.isGenerated ? 'check' : 'schedule' }}
                </span>
                {{ tag.isGenerated ? 'Done' : 'Pending' }}
              </span>
            </td>
            <td>
              <div v-if="tag.matchedAsset" class="table-asset-preview" @click="previewAsset(tag)">
                <img
                  v-if="tag.type !== 'video'"
                  :src="tag.matchedAsset.assetUrl"
                  :alt="tag.id"
                  class="table-thumb"
                />
                <span v-else class="table-vid-pill">
                  <span class="material-symbols-rounded">play_circle</span>
                  Video
                </span>
              </div>
              <span v-else class="table-no-asset">-</span>
            </td>
            <td style="text-align: center;">
              <div class="table-actions-cell">
                <button
                  type="button"
                  class="clean-icon-btn gen-icon-btn"
                  :class="[tag.isGenerated ? 'regen' : 'gen', { 'is-loading': isTagGenerating(stem, tag.id) }]"
                  :disabled="isTagGenerating(stem, tag.id)"
                  :title="isTagGenerating(stem, tag.id) ? 'Generating...' : (tag.isGenerated ? 'Regenerate this scene' : 'Generate this scene')"
                  @click.stop="handleDirectGenerate(tag)"
                >
                  <span class="material-symbols-rounded" :class="{ 'is-spinning': isTagGenerating(stem, tag.id) }">
                    {{ isTagGenerating(stem, tag.id) ? 'sync' : (tag.isGenerated ? 'refresh' : 'auto_awesome') }}
                  </span>
                </button>
                <button
                  type="button"
                  class="clean-icon-btn copy-icon-btn"
                  title="Inspect prompt template & reference guides"
                  @click="previewAsset(tag)"
                >
                  <span class="material-symbols-rounded">tune</span>
                </button>
                <button
                  type="button"
                  class="clean-icon-btn copy-icon-btn"
                  title="Copy prompt"
                  @click="copyPrompt(tag.prompt, tag.id || idx)"
                >
                  <span class="material-symbols-rounded">
                    {{ copiedId === (tag.id || idx) ? 'check' : 'content_copy' }}
                  </span>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { isTagGenerating, runTagGeneration, enrichPrompts } from '../services/api';

const props = defineProps({
  stem: {
    type: String,
    required: true
  },
  tags: {
    type: Array,
    default: () => []
  },
  images: {
    type: Array,
    default: () => []
  },
  videos: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['preview', 'refresh', 'open-add-tag']);

const searchQuery = ref('');
const filterType = ref('all'); // 'all' | 'image' | 'video'
const filterStatus = ref('all'); // 'all' | 'generated' | 'pending'
const selectedSection = ref('');
const viewMode = ref('cards'); // 'cards' | 'table'
const copiedId = ref(null);
const allCopied = ref(false);
const isEnrichingPrompts = ref(false);

const missingPromptsCount = computed(() => {
  return (props.tags || []).filter(t => !t.prompt || !t.prompt.trim()).length;
});

async function handleEnrichMissingPrompts() {
  if (isEnrichingPrompts.value) return;
  isEnrichingPrompts.value = true;
  try {
    const force = missingPromptsCount.value === 0;
    await enrichPrompts(props.stem, { force });
    emit('refresh');
  } catch (err) {
    alert(`Failed to enrich prompts: ${err.message}`);
  } finally {
    isEnrichingPrompts.value = false;
  }
}

const imageTagsCount = computed(() => {
  return props.tags.filter(t => t.type !== 'video').length;
});

const videoTagsCount = computed(() => {
  return props.tags.filter(t => t.type === 'video').length;
});

const generatedCount = computed(() => {
  return props.tags.filter(t => t.isGenerated).length;
});

const pendingCount = computed(() => {
  return props.tags.filter(t => !t.isGenerated).length;
});

const uniqueSections = computed(() => {
  const set = new Set();
  props.tags.forEach(t => {
    if (t.section) set.add(t.section);
  });
  return Array.from(set);
});

const filteredTags = computed(() => {
  return props.tags.filter(tag => {
    // 1. Type
    if (filterType.value === 'image' && tag.type === 'video') return false;
    if (filterType.value === 'video' && tag.type !== 'video') return false;

    // 2. Status
    if (filterStatus.value === 'generated' && !tag.isGenerated) return false;
    if (filterStatus.value === 'pending' && tag.isGenerated) return false;

    // 3. Section
    if (selectedSection.value && tag.section !== selectedSection.value) return false;

    // 4. Search Query
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase().trim();
      const idMatch = (tag.id || '').toLowerCase().includes(q);
      const promptMatch = (tag.prompt || '').toLowerCase().includes(q);
      const secMatch = (tag.section || '').toLowerCase().includes(q);
      const hintMatch = (tag.context_hint || '').toLowerCase().includes(q);
      const charMatch = (tag.characters || []).some(c => c.toLowerCase().includes(q));
      if (!idMatch && !promptMatch && !secMatch && !hintMatch && !charMatch) {
        return false;
      }
    }

    return true;
  });
});

function formatSize(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(1)} ${units[i]}`;
}

function resetFilters() {
  searchQuery.value = '';
  filterType.value = 'all';
  filterStatus.value = 'all';
  selectedSection.value = '';
}

async function handleDirectGenerate(tag) {
  if (isTagGenerating(props.stem, tag.id)) return;
  try {
    await runTagGeneration(props.stem, {
      tagId: tag.id,
      section: tag.section,
      type: tag.type || 'image'
    });
  } catch (err) {
    console.error('Direct generation failed:', err);
  }
}

function triggerTagAction(tag, autoGenerate = false) {
  emit('preview', {
    src: tag.matchedAsset ? tag.matchedAsset.assetUrl : '',
    title: `[${(tag.type || 'image').toUpperCase()}] ${tag.id || 'Scene'}${tag.section ? ' - ' + tag.section : ''}`,
    type: tag.type || 'image',
    id: tag.id,
    tagId: tag.id,
    stem: props.stem,
    section: tag.section,
    prompt: tag.prompt || '',
    composedPrompt: tag.composed_prompt || '',
    styleRef: tag.style_ref || null,
    characterRefs: tag.character_refs || [],
    cliCommand: tag.cli_command || '',
    autoGenerate,
    details: {
      TagID: tag.id,
      Type: tag.type === 'video' ? 'Video Scene' : 'Image Scene',
      Section: tag.section || 'N/A',
      Status: tag.isGenerated ? 'Generated' : 'Pending',
      File: tag.matchedAsset ? tag.matchedAsset.name : 'Pending generation'
    }
  });
}

function previewAsset(tag) {
  triggerTagAction(tag, false);
}

async function copyPrompt(prompt, id) {
  if (!prompt) return;
  try {
    await navigator.clipboard.writeText(prompt);
    copiedId.value = id;
    setTimeout(() => {
      copiedId.value = null;
    }, 2000);
  } catch (e) {
    console.error('Clipboard copy failed:', e);
  }
}

async function copyAllPrompts() {
  if (!filteredTags.value.length) return;
  const lines = filteredTags.value.map(t => {
    return `[${t.type.toUpperCase()}] ${t.id} (${t.section}):\n${t.prompt}\n`;
  });
  try {
    await navigator.clipboard.writeText(lines.join('\n'));
    allCopied.value = true;
    setTimeout(() => {
      allCopied.value = false;
    }, 2500);
  } catch (e) {
    console.error('Clipboard copy failed:', e);
  }
}
</script>

<style scoped>
.media-tags-review {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* 1. Metrics Strip */
.metrics-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.metric-card {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.metric-label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.icon-type {
  font-size: 16px;
}
.icon-img { color: #16a34a; }
.icon-vid { color: #7c3aed; }

.metric-value-wrap {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}

.metric-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.metric-sub {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.status-summary-wrap {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.25rem;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-item.generated .status-dot {
  background-color: #10b981;
}

.status-item.pending .status-dot {
  background-color: #f59e0b;
}

.status-num {
  font-weight: 600;
  color: var(--text-primary);
}

.status-txt {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* 2. Toolbar */
.toolbar-card {
  padding: 0.75rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  flex: 1;
}

.search-box {
  position: relative;
  min-width: 240px;
}

.search-icon {
  position: absolute;
  left: 0.6rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 18px;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding-left: 2rem;
  padding-right: 1.75rem;
}

.clear-search-btn {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0;
}
.clear-search-btn .material-symbols-rounded {
  font-size: 16px;
}

.filter-group {
  display: flex;
  gap: 0.25rem;
  background: var(--bg-surface-secondary);
  padding: 0.2rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
}

.filter-pill {
  border: none;
  background: transparent;
  padding: 0.3rem 0.65rem;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.filter-pill:hover {
  color: var(--text-primary);
}

.filter-pill.active {
  background: var(--bg-surface);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
  font-weight: 600;
}

.pill-icon {
  font-size: 15px;
}

.section-select-wrap {
  min-width: 160px;
}

.section-select {
  width: 100%;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.add-scene-tag-btn {
  background: var(--primary, #6750a4);
  color: #ffffff;
  font-weight: 600;
  gap: 0.35rem;
  border-radius: 9999px;
  padding: 0.35rem 0.85rem;
  box-shadow: 0 2px 6px rgba(103, 80, 164, 0.25);
  transition: all 0.2s ease;
}

.add-scene-tag-btn:hover {
  opacity: 0.94;
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(103, 80, 164, 0.35);
}

.add-scene-tag-btn .material-symbols-rounded {
  font-size: 1.1rem;
}

.enrich-prompts-btn {
  background: var(--primary-container, rgba(103, 80, 164, 0.12));
  color: var(--primary-on-container, var(--primary));
  font-weight: 600;
  gap: 0.35rem;
  border-radius: 9999px;
  padding: 0.35rem 0.85rem;
  border: 1px solid rgba(103, 80, 164, 0.25);
  transition: all 0.2s ease;
}

.enrich-prompts-btn:hover:not(:disabled) {
  background: var(--primary, #6750a4);
  color: #ffffff;
}

.enrich-prompts-btn .material-symbols-rounded {
  font-size: 1.1rem;
}

.view-switch {
  display: flex;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 0.2rem;
  gap: 0.2rem;
}

.view-btn {
  border: none;
  background: transparent;
  color: var(--text-muted);
  padding: 0.25rem 0.4rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}

.view-btn:hover {
  color: var(--text-primary);
}

.view-btn.active {
  background: var(--bg-surface);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.view-btn .material-symbols-rounded {
  font-size: 18px;
}

/* 3. Cards Grid */
.tag-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 1rem;
}

@media (max-width: 600px) {
  .tag-cards-grid {
    grid-template-columns: 1fr;
  }
}

.tag-card {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.tag-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tag-identity {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tag-id-badge {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text-primary);
}

.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-full);
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: capitalize;
}

.type-pill.image {
  background: var(--type-image-bg);
  color: var(--type-image-text);
  border: 1px solid var(--type-image-border);
}

.type-pill.video {
  background: var(--type-video-bg);
  color: var(--type-video-text);
  border: 1px solid var(--type-video-border);
}

.type-pill .material-symbols-rounded {
  font-size: 13px;
}

.section-pill {
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: var(--bg-surface-secondary);
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
  max-width: 180px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-regen-btn {
  background: #2563eb;
  color: #ffffff;
  border-color: #1d4ed8;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.card-regen-btn:hover {
  background: #1d4ed8;
  color: #ffffff;
  box-shadow: var(--shadow-sm);
}

.card-gen-btn {
  background: #059669;
  color: #ffffff;
  border-color: #047857;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.card-gen-btn:hover {
  background: #047857;
  color: #ffffff;
  box-shadow: var(--shadow-sm);
}

.clean-icon-btn.gen-icon-btn.regen {
  color: #2563eb;
}

.clean-icon-btn.gen-icon-btn.regen:hover {
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
}

.clean-icon-btn.gen-icon-btn.gen {
  color: #059669;
}

.clean-icon-btn.gen-icon-btn.gen:hover {
  background: rgba(5, 150, 105, 0.1);
  color: #047857;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.15rem 0.55rem;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 600;
}

.status-badge .material-symbols-rounded {
  font-size: 14px;
}

.status-done {
  background: var(--status-success-bg);
  color: var(--status-success-text);
  border: 1px solid var(--status-success-border);
}

.status-wait {
  background: var(--status-pending-bg);
  color: var(--status-pending-text);
  border: 1px solid var(--status-pending-border);
}

.status-generating {
  background: rgba(14, 165, 233, 0.12);
  color: var(--accent-primary);
  border: 1px solid rgba(14, 165, 233, 0.25);
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Prompt Box */
.prompt-box {
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 0.85rem;
}

.prompt-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}

.prompt-heading {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.copy-btn {
  height: 24px;
  padding: 0.15rem 0.45rem;
}
.copy-btn .material-symbols-rounded {
  font-size: 14px;
}

.prompt-text {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
}

/* Context Hint Box */
.context-hint-box {
  border-left: 2px solid var(--border-strong);
  padding-left: 0.75rem;
  margin-top: -0.25rem;
}

.context-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--text-muted);
}

.context-text {
  margin: 0.2rem 0 0 0;
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

/* Characters row */
.characters-line {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.char-label {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
}

/* Matched Asset Preview */
.matched-preview-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.matched-preview-card:hover {
  border-color: var(--accent-primary);
  box-shadow: var(--shadow-sm);
}

.matched-media-box {
  position: relative;
  aspect-ratio: 16/9;
  background: #000;
  overflow: hidden;
}

.thumb-asset {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.preview-hover-hint {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  color: #ffffff;
  font-size: 0.8rem;
  font-weight: 500;
  opacity: 0;
  transition: opacity 0.15s;
}

.matched-preview-card:hover .preview-hover-hint {
  opacity: 1;
}

.matched-meta-row {
  padding: 0.5rem 0.75rem;
  background: var(--bg-surface);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.matched-filename {
  font-family: var(--font-mono);
  font-weight: 500;
}

/* 4. Table View */
.table-container {
  overflow-x: auto;
}

.clean-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.clean-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-surface-secondary);
  border-bottom: 1px solid var(--border-default);
}

.clean-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-default);
  vertical-align: middle;
}

.clean-table tr:hover td {
  background: var(--bg-surface-secondary);
}

.tag-id-mono {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-primary);
}

.table-section-text {
  color: var(--text-secondary);
  max-width: 140px;
  display: inline-block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-prompt-cell {
  max-width: 380px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
}

.table-asset-preview {
  cursor: pointer;
  display: flex;
  align-items: center;
}

.table-thumb {
  width: 48px;
  height: 32px;
  border-radius: var(--radius-xs);
  object-fit: cover;
  border: 1px solid var(--border-default);
}

.table-vid-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.75rem;
  color: var(--type-video-text);
  background: var(--type-video-bg);
  padding: 0.15rem 0.4rem;
  border-radius: var(--radius-xs);
}
.table-vid-pill .material-symbols-rounded {
  font-size: 14px;
}

.table-no-asset {
  color: var(--text-muted);
}

.copy-icon-btn {
  width: 28px;
  height: 28px;
}
.copy-icon-btn .material-symbols-rounded {
  font-size: 15px;
}

.card-inspect-btn {
  padding: 0.2rem 0.55rem;
  font-size: 0.72rem;
  gap: 0.25rem;
  color: var(--text-secondary);
}

.card-inspect-btn .material-symbols-rounded {
  font-size: 14px;
}

.card-inspect-btn:hover {
  color: var(--accent-primary);
  border-color: var(--accent-primary);
}

.card-refs-strip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-wrap: wrap;
  transition: all 0.15s ease;
}

.card-refs-strip:hover {
  background: var(--bg-surface-hover);
  border-color: var(--accent-primary);
}

.refs-strip-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ref-mini-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
}

.style-chip {
  background: rgba(14, 165, 233, 0.1);
  color: #0284c7;
  border: 1px solid rgba(14, 165, 233, 0.2);
}

.char-chip {
  background: rgba(168, 85, 247, 0.1);
  color: #9333ea;
  border: 1px solid rgba(168, 85, 247, 0.2);
}

.mini-ref-img {
  width: 18px;
  height: 18px;
  border-radius: 3px;
  object-fit: cover;
}

.mini-ref-name {
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.inspect-click-hint {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.7rem;
  color: var(--accent-primary);
  font-weight: 500;
}

.inspect-click-hint .material-symbols-rounded {
  font-size: 13px;
}

.table-actions-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
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
  font-weight: 600;
}

.empty-state p {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
}
</style>
