<template>
  <div class="media-gallery">
    <div class="section-header">
      <div>
        <h2 class="section-title">Generated Story Media</h2>
        <p class="section-subtitle">
          High-definition illustrations and video clips produced for storybook scenes and story reader presentation.
        </p>
      </div>

      <div class="filter-controls">
        <button
          type="button"
          class="filter-chip"
          :class="{ active: filterType === 'all' }"
          @click="filterType = 'all'"
        >
          All ({{ allMedia.length }})
        </button>
        <button
          type="button"
          class="filter-chip"
          :class="{ active: filterType === 'image' }"
          @click="filterType = 'image'"
        >
          <span class="material-symbols-rounded">image</span>
          Images ({{ images.length }})
        </button>
        <button
          type="button"
          class="filter-chip"
          :class="{ active: filterType === 'video' }"
          @click="filterType = 'video'"
        >
          <span class="material-symbols-rounded">videocam</span>
          Videos ({{ videos.length }})
        </button>
      </div>
    </div>

    <div v-if="filteredMedia.length === 0" class="empty-state">
      <span class="material-symbols-rounded empty-icon">perm_media</span>
      <p v-if="allMedia.length === 0">No generated scene images or videos in this workspace.</p>
      <p v-else>No items match the current filter.</p>
      <small>Run <code>python storybook.py generate &lt;file.md&gt;</code> to generate scene media.</small>
    </div>

    <div v-else class="media-grid">
      <div
        v-for="item in filteredMedia"
        :key="item.assetUrl"
        class="media-card md-card-elevated"
        @click="previewMedia(item)"
      >
        <div class="media-preview-area">
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

          <span class="type-indicator" :class="item.type">
            <span class="material-symbols-rounded">
              {{ item.type === 'video' ? 'videocam' : 'image' }}
            </span>
            {{ item.type }}
          </span>

          <div v-if="item.type === 'video'" class="play-overlay">
            <span class="material-symbols-rounded play-icon">play_circle</span>
          </div>
        </div>

        <div class="media-info">
          <div class="info-row">
            <span class="media-name" :title="item.name">{{ item.name }}</span>
          </div>
          <div class="meta-row">
            <span class="file-size">{{ formatSize(item.sizeBytes) }}</span>
            <span class="hover-action">
              Inspect
              <span class="material-symbols-rounded" style="font-size: 16px;">open_in_full</span>
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

const filterType = ref('all'); // 'all' | 'image' | 'video'

const allMedia = computed(() => {
  const imgItems = props.images.map(img => ({
    ...img,
    type: 'image'
  }));
  const vidItems = props.videos.map(vid => ({
    ...vid,
    type: 'video'
  }));
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
  // Try to find matching prompt from tags by id or filename
  let prompt = '';
  const matchingTag = props.tags.find(t => t.id === item.id || t.id === item.name || item.name.includes(t.id));
  if (matchingTag) {
    prompt = matchingTag.prompt || matchingTag.description || '';
  }

  emit('preview', {
    src: item.assetUrl,
    title: item.name,
    type: item.type,
    prompt: prompt,
    details: {
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

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}

.media-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.media-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--elevation-3);
}

.media-preview-area {
  position: relative;
  aspect-ratio: 16/9;
  background: var(--md-sys-color-surface-container-lowest);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.media-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.type-indicator {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.2rem 0.5rem;
  border-radius: var(--shape-corner-full);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
  backdrop-filter: blur(6px);
}

.type-indicator.image {
  background: rgba(15, 23, 42, 0.7);
  color: #93c5fd;
}

.type-indicator.video {
  background: rgba(126, 34, 206, 0.75);
  color: #f3e8ff;
}

.type-indicator .material-symbols-rounded {
  font-size: 14px;
}

.play-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.25);
  opacity: 0.8;
  transition: opacity 0.2s;
}

.media-card:hover .play-overlay {
  opacity: 1;
  background: rgba(0, 0, 0, 0.15);
}

.play-icon {
  font-size: 48px;
  color: #ffffff;
  filter: drop-shadow(0 2px 8px rgba(0,0,0,0.5));
}

.media-info {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  background: var(--md-sys-color-surface-container);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.media-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  color: var(--md-sys-color-on-surface-variant);
}

.hover-action {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  color: var(--md-sys-color-primary);
  font-weight: 500;
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
