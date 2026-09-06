<template>
  <div class="media-gallery">
    <!-- Header -->
    <div class="gallery-header">
      <div>
        <h2 class="section-title">Generated Story Media Files</h2>
        <p class="section-subtitle">
          Generated illustrations and video clips saved in <code>outputs/{{ stem }}/images/</code> and <code>outputs/{{ stem }}/videos/</code>.
        </p>
      </div>

      <div class="filter-controls">
        <button
          type="button"
          class="filter-pill"
          :class="{ active: filterType === 'all' }"
          @click="filterType = 'all'"
        >
          All ({{ allMedia.length }})
        </button>
        <button
          type="button"
          class="filter-pill"
          :class="{ active: filterType === 'image' }"
          @click="filterType = 'image'"
        >
          <span class="material-symbols-rounded">image</span>
          Images ({{ images.length }})
        </button>
        <button
          type="button"
          class="filter-pill"
          :class="{ active: filterType === 'video' }"
          @click="filterType = 'video'"
        >
          <span class="material-symbols-rounded">videocam</span>
          Videos ({{ videos.length }})
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="filteredMedia.length === 0" class="empty-state clean-card">
      <span class="material-symbols-rounded empty-icon">perm_media</span>
      <h3>No Generated Media Found</h3>
      <p v-if="allMedia.length === 0">
        No generated scene images or videos in this workspace yet.
      </p>
      <p v-else>
        No files match the selected filter.
      </p>
      <small>Run <code>python storybook.py media generate outputs/{{ stem }}/{{ stem }}-output.md</code> to produce assets.</small>
    </div>

    <!-- Media Grid -->
    <div v-else class="media-grid">
      <div
        v-for="item in filteredMedia"
        :key="item.assetUrl"
        class="media-card clean-card"
        @click="previewMedia(item)"
      >
        <div class="preview-box">
          <video
            v-if="item.type === 'video'"
            :src="item.assetUrl"
            class="media-thumb"
            preload="metadata"
            muted
          ></video>
          <img
            v-else
            :src="item.assetUrl"
            :alt="item.name"
            class="media-thumb"
            loading="lazy"
          />

          <span class="type-pill" :class="item.type">
            <span class="material-symbols-rounded">
              {{ item.type === 'video' ? 'videocam' : 'image' }}
            </span>
            {{ item.type }}
          </span>

          <div v-if="item.type === 'video'" class="play-overlay">
            <span class="material-symbols-rounded play-icon">play_circle</span>
          </div>
        </div>

        <div class="card-info">
          <span class="media-title" :title="item.name">{{ item.name }}</span>
          <div class="meta-line">
            <span class="file-size">{{ formatSize(item.sizeBytes) }}</span>
            <span class="open-hint">
              Inspect
              <span class="material-symbols-rounded">fullscreen</span>
            </span>
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
  images: {
    type: Array,
    default: () => []
  },
  videos: {
    type: Array,
    default: () => []
  },
  tags: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['preview']);

const filterType = ref('all');

const allMedia = computed(() => {
  const imgItems = props.images.map(img => ({ ...img, type: 'image' }));
  const vidItems = props.videos.map(vid => ({ ...vid, type: 'video' }));
  return [...imgItems, ...vidItems];
});

const filteredMedia = computed(() => {
  if (filterType.value === 'image') return allMedia.value.filter(m => m.type === 'image');
  if (filterType.value === 'video') return allMedia.value.filter(m => m.type === 'video');
  return allMedia.value;
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

function previewMedia(item) {
  let prompt = '';
  const matchingTag = props.tags.find(t => t.id === item.id || t.id === item.name || item.name.includes(t.id));
  if (matchingTag) {
    prompt = matchingTag.prompt || matchingTag.description || '';
  }

  emit('preview', {
    src: item.assetUrl,
    title: item.name,
    type: item.type,
    id: matchingTag?.id || item.id,
    tagId: matchingTag?.id || item.id,
    stem: props.stem,
    section: matchingTag?.section || '',
    prompt: prompt,
    composedPrompt: matchingTag?.composed_prompt || '',
    styleRef: matchingTag?.style_ref || null,
    characterRefs: matchingTag?.character_refs || [],
    cliCommand: matchingTag?.cli_command || '',
    details: {
      TagID: matchingTag?.id || item.id,
      Workspace: props.stem,
      File: item.name,
      Type: item.type,
      Size: formatSize(item.sizeBytes)
    }
  });
}
</script>

<style scoped>
.media-gallery {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.gallery-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
}

.section-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
}

.section-subtitle {
  margin: 0.25rem 0 0 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.section-subtitle code {
  background: var(--bg-surface-secondary);
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.filter-controls {
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
  padding: 0.35rem 0.7rem;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  transition: all 0.15s;
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

.filter-pill .material-symbols-rounded {
  font-size: 16px;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.25rem;
}

.media-card {
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}

.preview-box {
  position: relative;
  aspect-ratio: 16/9;
  background: #000;
  overflow: hidden;
}

.media-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.type-pill {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-full);
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: capitalize;
  backdrop-filter: blur(8px);
}

.type-pill.image {
  background: rgba(15, 23, 42, 0.75);
  color: #93c5fd;
}

.type-pill.video {
  background: rgba(88, 28, 135, 0.8);
  color: #e9d5ff;
}

.type-pill .material-symbols-rounded {
  font-size: 13px;
}

.play-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.25);
  transition: background-color 0.15s;
}

.media-card:hover .play-overlay {
  background: rgba(0, 0, 0, 0.1);
}

.play-icon {
  font-size: 40px;
  color: #ffffff;
}

.card-info {
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.media-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.open-hint {
  display: flex;
  align-items: center;
  gap: 0.15rem;
  color: var(--accent-primary);
  font-weight: 500;
}

.open-hint .material-symbols-rounded {
  font-size: 15px;
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
</style>
