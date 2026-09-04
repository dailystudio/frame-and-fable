<template>
  <div class="scene-breakdown">
    <div class="section-header">
      <div>
        <h2 class="section-title">Scene Media Breakdown & Tags</h2>
        <p class="section-subtitle">
          Structured inspection of all <code>&lt;!-- storybook-media --&gt;</code> markers embedded in the storybook markdown.
        </p>
      </div>

      <div class="filter-controls">
        <button
          type="button"
          class="filter-chip"
          :class="{ active: filterStatus === 'all' }"
          @click="filterStatus = 'all'"
        >
          All ({{ enrichedTags.length }})
        </button>
        <button
          type="button"
          class="filter-chip"
          :class="{ active: filterStatus === 'generated' }"
          @click="filterStatus = 'generated'"
        >
          <span class="material-symbols-rounded">check_circle</span>
          Generated ({{ generatedCount }})
        </button>
        <button
          type="button"
          class="filter-chip"
          :class="{ active: filterStatus === 'pending' }"
          @click="filterStatus = 'pending'"
        >
          <span class="material-symbols-rounded">pending</span>
          Pending ({{ pendingCount }})
        </button>
      </div>
    </div>

    <div v-if="enrichedTags.length === 0" class="empty-state">
      <span class="material-symbols-rounded empty-icon">label_off</span>
      <p>No storybook-media tags found in this markdown document.</p>
      <small>Tags like <code>&lt;!-- storybook-media: {"id":"scene-01", ...} --&gt;</code> are extracted during processing.</small>
    </div>

    <div v-else class="tags-list">
      <div
        v-for="(tag, idx) in filteredTags"
        :key="tag.id || idx"
        class="tag-card md-card-elevated"
      >
        <div class="tag-top-bar">
          <div class="tag-title-group">
            <span class="tag-index">#{{ idx + 1 }}</span>
            <span class="tag-id">{{ tag.id || `tag-${idx + 1}` }}</span>
            <span class="md-badge" :class="tag.type === 'video' ? 'badge-video' : 'badge-image'">
              <span class="material-symbols-rounded">
                {{ tag.type === 'video' ? 'videocam' : 'image' }}
              </span>
              {{ tag.type || 'image' }}
            </span>
          </div>

          <div class="tag-status-group">
            <span
              class="status-chip"
              :class="tag.isGenerated ? 'status-generated' : 'status-pending'"
            >
              <span class="material-symbols-rounded">
                {{ tag.isGenerated ? 'check_circle' : 'schedule' }}
              </span>
              {{ tag.isGenerated ? 'Generated' : 'Pending' }}
            </span>
          </div>
        </div>

        <div class="tag-body">
          <!-- Characters In Scene -->
          <div v-if="tag.characters && tag.characters.length > 0" class="characters-row">
            <span class="sub-label">Characters:</span>
            <span v-for="c in tag.characters" :key="c" class="char-chip">
              <span class="material-symbols-rounded">face</span>
              {{ c }}
            </span>
          </div>

          <!-- Prompt Box -->
          <div class="prompt-box">
            <div class="prompt-header">
              <span class="sub-label">Generation Prompt</span>
              <button
                type="button"
                class="md-btn md-btn-tonal copy-btn"
                @click="copyPrompt(tag.prompt, tag.id || idx)"
              >
                <span class="material-symbols-rounded">
                  {{ copiedTagId === (tag.id || idx) ? 'check' : 'content_copy' }}
                </span>
                {{ copiedTagId === (tag.id || idx) ? 'Copied' : 'Copy' }}
              </button>
            </div>
            <p class="prompt-text">{{ tag.prompt || 'No explicit prompt text' }}</p>
          </div>

          <!-- Media Match Thumbnail if Generated -->
          <div v-if="tag.matchedAsset" class="matched-asset-preview" @click="previewTagAsset(tag)">
            <img
              v-if="tag.type !== 'video'"
              :src="tag.matchedAsset.assetUrl"
              :alt="tag.id"
              class="matched-thumb"
            />
            <video
              v-else
              :src="tag.matchedAsset.assetUrl"
              class="matched-thumb"
              preload="metadata"
              muted
            ></video>
            <div class="matched-overlay">
              <span class="material-symbols-rounded">zoom_in</span>
              <span>Preview generated output</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

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

const emit = defineEmits(['preview']);

const filterStatus = ref('all'); // 'all' | 'generated' | 'pending'
const copiedTagId = ref(null);

const enrichedTags = computed(() => {
  return props.tags.map(tag => {
    // Check if matching image or video exists
    let matched = null;
    if (tag.type === 'video') {
      matched = props.videos.find(v => v.id === tag.id || v.name.includes(tag.id));
    } else {
      matched = props.images.find(img => img.id === tag.id || img.name.includes(tag.id));
    }

    return {
      ...tag,
      isGenerated: !!matched,
      matchedAsset: matched
    };
  });
});

const generatedCount = computed(() => {
  return enrichedTags.value.filter(t => t.isGenerated).length;
});

const pendingCount = computed(() => {
  return enrichedTags.value.filter(t => !t.isGenerated).length;
});

const filteredTags = computed(() => {
  if (filterStatus.value === 'generated') return enrichedTags.value.filter(t => t.isGenerated);
  if (filterStatus.value === 'pending') return enrichedTags.value.filter(t => !t.isGenerated);
  return enrichedTags.value;
});

function previewTagAsset(tag) {
  if (!tag.matchedAsset) return;
  emit('preview', {
    src: tag.matchedAsset.assetUrl,
    title: tag.id || 'Scene Asset',
    type: tag.type || 'image',
    prompt: tag.prompt || '',
    details: {
      TagID: tag.id,
      Type: tag.type,
      Status: 'Generated',
      Characters: tag.characters ? tag.characters.join(', ') : 'N/A'
    }
  });
}

async function copyPrompt(prompt, id) {
  if (!prompt) return;
  try {
    await navigator.clipboard.writeText(prompt);
    copiedTagId.value = id;
    setTimeout(() => {
      copiedTagId.value = null;
    }, 2000);
  } catch (err) {
    console.error('Failed to copy:', err);
  }
}
</script>

<style scoped>
.scene-breakdown {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
}

.section-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
}

.section-subtitle {
  margin: 0.25rem 0 0 0;
  font-size: 0.95rem;
  color: var(--md-sys-color-on-surface-variant);
}

.filter-controls {
  display: flex;
  gap: 0.5rem;
  background: var(--md-sys-color-surface-container);
  padding: 0.25rem;
  border-radius: var(--shape-corner-full);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.filter-chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  border: none;
  background: transparent;
  padding: 0.45rem 0.9rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--md-sys-color-on-surface-variant);
  border-radius: var(--shape-corner-full);
  cursor: pointer;
  transition: all 0.2s;
}

.filter-chip .material-symbols-rounded {
  font-size: 18px;
}

.filter-chip.active {
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  box-shadow: var(--elevation-1);
}

.tags-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.tag-card {
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.tag-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.tag-title-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.tag-index {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--md-sys-color-primary);
  background: var(--md-sys-color-primary-container);
  padding: 0.2rem 0.5rem;
  border-radius: var(--shape-corner-small);
}

.tag-id {
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--md-sys-color-on-surface);
}

.badge-image {
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
}

.badge-video {
  background: var(--md-sys-color-tertiary-container);
  color: var(--md-sys-color-on-tertiary-container);
}

.status-chip {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.75rem;
  border-radius: var(--shape-corner-full);
  font-size: 0.8rem;
  font-weight: 600;
}

.status-chip .material-symbols-rounded {
  font-size: 16px;
}

.status-generated {
  background: #dcfce7;
  color: #166534;
}

[data-theme="dark"] .status-generated {
  background: #14532d;
  color: #86efac;
}

.status-pending {
  background: #fef3c7;
  color: #92400e;
}

[data-theme="dark"] .status-pending {
  background: #78350f;
  color: #fde68a;
}

.tag-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.sub-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
  color: var(--md-sys-color-on-surface-variant);
}

.characters-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.char-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.2rem 0.5rem;
  border-radius: var(--shape-corner-full);
}

.char-chip .material-symbols-rounded {
  font-size: 14px;
  color: var(--md-sys-color-primary);
}

.prompt-box {
  background: var(--md-sys-color-surface-container);
  border-radius: var(--shape-corner-medium);
  padding: 0.75rem 1rem;
  border: 1px solid var(--md-sys-color-outline-variant);
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
}

.copy-btn {
  padding: 0.15rem 0.5rem;
  font-size: 0.75rem;
  height: 24px;
}

.prompt-text {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--md-sys-color-on-surface);
  white-space: pre-wrap;
}

.matched-asset-preview {
  position: relative;
  max-width: 320px;
  aspect-ratio: 16/9;
  border-radius: var(--shape-corner-medium);
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
}

.matched-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.matched-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 500;
  opacity: 0;
  transition: opacity 0.2s;
}

.matched-asset-preview:hover .matched-overlay {
  opacity: 1;
}

.empty-state {
  text-align: center;
  padding: 4rem 2rem;
  color: var(--md-sys-color-on-surface-variant);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.empty-icon {
  font-size: 48px;
  color: var(--md-sys-color-outline);
}
</style>
