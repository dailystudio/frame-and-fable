<template>
  <div class="story-reader">
    <div class="reader-toolbar">
      <div class="reader-meta">
        <span class="md-badge badge-type">
          <span class="material-symbols-rounded" style="font-size: 14px;">menu_book</span>
          {{ markdownType === 'output' ? 'Generated Output' : 'Source Draft' }}
        </span>
        <span class="read-stat">{{ wordCount }} words</span>
        <span class="read-stat">{{ readTime }} min read</span>
      </div>

      <div class="reader-actions">
        <div class="font-size-control">
          <button
            type="button"
            class="size-btn"
            title="Smaller font"
            :disabled="fontSizeMultiplier <= 0.85"
            @click="fontSizeMultiplier -= 0.1"
          >
            A-
          </button>
          <button
            type="button"
            class="size-btn"
            title="Reset font"
            @click="fontSizeMultiplier = 1.0"
          >
            A
          </button>
          <button
            type="button"
            class="size-btn"
            title="Larger font"
            :disabled="fontSizeMultiplier >= 1.4"
            @click="fontSizeMultiplier += 0.1"
          >
            A+
          </button>
        </div>

        <button
          type="button"
          class="md-btn md-btn-tonal raw-toggle"
          @click="showRaw = !showRaw"
        >
          <span class="material-symbols-rounded">
            {{ showRaw ? 'visibility' : 'code' }}
          </span>
          {{ showRaw ? 'Formatted Story' : 'Raw Markdown' }}
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!markdownContent" class="empty-state">
      <span class="material-symbols-rounded empty-icon">menu_book</span>
      <p>No story markdown found for this workspace.</p>
      <small>Ensure <code>{{ stem }}-output.md</code> exists in <code>outputs/{{ stem }}/</code>.</small>
    </div>

    <!-- Raw Markdown View -->
    <div v-else-if="showRaw" class="raw-markdown-view md-card-elevated">
      <div class="raw-head">
        <span class="raw-title">{{ stem }}-output.md</span>
        <button type="button" class="md-btn md-btn-tonal" @click="copyRaw">
          <span class="material-symbols-rounded">
            {{ rawCopied ? 'check' : 'content_copy' }}
          </span>
          {{ rawCopied ? 'Copied' : 'Copy All' }}
        </button>
      </div>
      <pre><code>{{ markdownContent }}</code></pre>
    </div>

    <!-- Formatted Story Reader View -->
    <div
      v-else
      class="reader-paper md-card-elevated"
      :style="{ '--reader-font-scale': fontSizeMultiplier }"
      @click="handleContentClick"
    >
      <div class="story-markdown" v-html="renderedHtml"></div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { marked } from 'marked';
import '../styles/markdown.css';

const props = defineProps({
  stem: {
    type: String,
    required: true
  },
  markdownContent: {
    type: String,
    default: ''
  },
  markdownType: {
    type: String,
    default: 'output'
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

const showRaw = ref(false);
const rawCopied = ref(false);
const fontSizeMultiplier = ref(1.0);

const wordCount = computed(() => {
  if (!props.markdownContent) return 0;
  return props.markdownContent.trim().split(/\s+/).length;
});

const readTime = computed(() => {
  return Math.max(1, Math.ceil(wordCount.value / 220));
});

const renderedHtml = computed(() => {
  if (!props.markdownContent) return '';

  let text = props.markdownContent;

  // 1. Replace relative image markdown links:
  // e.g. ![alt](images/foo.png) -> !alt](/api/asset/<stem>/images/foo.png)
  text = text.replace(/!\[([^\]]*)\]\((images\/[^)]+)\)/g, (match, alt, rel) => {
    return `![${alt}](/api/asset/${encodeURIComponent(props.stem)}/${rel})`;
  });

  // 2. Replace relative video markdown links or tags
  text = text.replace(/!\[([^\]]*)\]\((videos\/[^)]+)\)/g, (match, alt, rel) => {
    const videoUrl = `/api/asset/${encodeURIComponent(props.stem)}/${rel}`;
    return `<div class="story-video-wrap"><video src="${videoUrl}" controls poster="" preload="metadata"></video><p class="story-media-caption">${alt}</p></div>`;
  });

  // 3. Process storybook-media tags into embedded interactive cards
  // <!-- storybook-media: { "id": "...", ... } -->
  text = text.replace(/<!--\s*storybook-media:\s*(\{.*?\})\s*-->/gs, (match, jsonStr) => {
    try {
      const tagData = JSON.parse(jsonStr);
      const tagId = tagData.id || '';
      const tagType = tagData.type || 'image';

      // Check if generated image/video exists
      let matched = null;
      if (tagType === 'video') {
        matched = props.videos.find(v => v.id === tagId || v.name.includes(tagId));
      } else {
        matched = props.images.find(img => img.id === tagId || img.name.includes(tagId));
      }

      if (matched) {
        if (tagType === 'video') {
          return `
            <div class="embedded-scene-card" data-tag-id="${tagId}">
              <div class="scene-media-box">
                <video src="${matched.assetUrl}" controls class="embedded-video" preload="metadata"></video>
              </div>
              <div class="scene-meta-box">
                <span class="scene-tag-badge">🎬 ${tagId}</span>
                <p class="scene-prompt">${tagData.prompt || ''}</p>
              </div>
            </div>
          `;
        } else {
          return `
            <div class="embedded-scene-card" data-tag-id="${tagId}">
              <div class="scene-media-box">
                <img src="${matched.assetUrl}" alt="${tagId}" class="embedded-img" data-clickable-preview="true" data-src="${matched.assetUrl}" data-prompt="${encodeURIComponent(tagData.prompt || '')}" data-title="${tagId}" />
              </div>
              <div class="scene-meta-box">
                <span class="scene-tag-badge">🖼️ ${tagId}</span>
                <p class="scene-prompt">${tagData.prompt || ''}</p>
              </div>
            </div>
          `;
        }
      } else {
        // Pending placeholder
        return `
          <div class="embedded-pending-scene">
            <div class="pending-header">
              <span class="pending-badge">⏳ Scene Pending: ${tagId}</span>
              <span class="pending-type">${tagType}</span>
            </div>
            <p class="pending-prompt">${tagData.prompt || 'No prompt'}</p>
          </div>
        `;
      }
    } catch (e) {
      return match;
    }
  });

  return marked.parse(text);
});

function handleContentClick(event) {
  // Check if click was on an image to trigger lightbox
  const target = event.target;
  if (target.tagName === 'IMG') {
    const src = target.getAttribute('src');
    const alt = target.getAttribute('alt') || 'Scene Illustration';
    const prompt = target.dataset.prompt ? decodeURIComponent(target.dataset.prompt) : '';
    const title = target.dataset.title || alt;

    emit('preview', {
      src,
      title,
      type: 'image',
      prompt,
      details: {
        Workspace: props.stem,
        Context: 'Story Reader'
      }
    });
  }
}

async function copyRaw() {
  if (!props.markdownContent) return;
  try {
    await navigator.clipboard.writeText(props.markdownContent);
    rawCopied.value = true;
    setTimeout(() => {
      rawCopied.value = false;
    }, 2000);
  } catch (e) {
    console.error('Failed to copy markdown:', e);
  }
}
</script>

<style scoped>
.story-reader {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.reader-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  padding: 0.75rem 1.25rem;
  background: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--shape-corner-large);
}

.reader-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.badge-type {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  font-weight: 600;
}

.read-stat {
  font-size: 0.85rem;
  color: var(--md-sys-color-on-surface-variant);
}

.reader-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.font-size-control {
  display: flex;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--shape-corner-full);
  overflow: hidden;
  background: var(--md-sys-color-surface-container-high);
}

.size-btn {
  border: none;
  background: transparent;
  padding: 0.35rem 0.65rem;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
  transition: background-color 0.15s;
}

.size-btn:hover:not(:disabled) {
  background: var(--md-sys-color-surface-container-highest);
}

.size-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.raw-toggle {
  padding: 0.35rem 0.8rem;
  font-size: 0.85rem;
  height: 34px;
}

.reader-paper {
  background: var(--md-sys-color-surface-container-low);
  padding: 3rem 4rem;
  border-radius: var(--shape-corner-extra-large);
  border: 1px solid var(--md-sys-color-outline-variant);
  min-height: 500px;
}

@media (max-width: 768px) {
  .reader-paper {
    padding: 1.5rem 1rem;
  }
}

.story-markdown {
  font-size: calc(1.15rem * var(--reader-font-scale, 1));
}

:deep(.story-video-wrap) {
  margin: 2rem 0;
  border-radius: var(--shape-corner-large);
  overflow: hidden;
  box-shadow: var(--elevation-2);
  background: #000;
}

:deep(.story-video-wrap video) {
  width: 100%;
  max-height: 480px;
  display: block;
}

:deep(.story-media-caption) {
  font-family: var(--font-sans);
  font-size: 0.85rem;
  text-align: center;
  color: var(--md-sys-color-on-surface-variant);
  margin-top: 0.5rem;
  font-style: italic;
}

:deep(.embedded-scene-card) {
  margin: 2.5rem 0;
  border-radius: var(--shape-corner-large);
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container);
  box-shadow: var(--elevation-2);
}

:deep(.embedded-img) {
  width: 100%;
  max-height: 480px;
  object-fit: contain;
  background: var(--md-sys-color-surface-container-lowest);
  display: block;
  cursor: zoom-in;
}

:deep(.embedded-video) {
  width: 100%;
  max-height: 480px;
  display: block;
  background: #000;
}

:deep(.scene-meta-box) {
  padding: 1rem 1.25rem;
  font-family: var(--font-sans);
}

:deep(.scene-tag-badge) {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--md-sys-color-primary);
  margin-bottom: 0.35rem;
}

:deep(.scene-prompt) {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.45;
  color: var(--md-sys-color-on-surface-variant);
}

:deep(.embedded-pending-scene) {
  margin: 2rem 0;
  padding: 1.25rem;
  border: 1px dashed var(--md-sys-color-outline-variant);
  border-radius: var(--shape-corner-medium);
  background: var(--md-sys-color-surface-container);
  font-family: var(--font-sans);
}

:deep(.pending-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

:deep(.pending-badge) {
  font-size: 0.8rem;
  font-weight: 700;
  color: #d97706;
}

:deep(.pending-type) {
  font-size: 0.75rem;
  text-transform: uppercase;
  background: var(--md-sys-color-surface-container-high);
  padding: 0.15rem 0.5rem;
  border-radius: var(--shape-corner-full);
}

:deep(.pending-prompt) {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.45;
  color: var(--md-sys-color-on-surface-variant);
  font-style: italic;
}

.raw-markdown-view {
  background: var(--md-sys-color-surface-container);
  border-radius: var(--shape-corner-large);
  overflow: hidden;
}

.raw-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  background: var(--md-sys-color-surface-container-high);
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.raw-title {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 0.9rem;
}

.raw-markdown-view pre {
  margin: 0;
  padding: 1.25rem;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  line-height: 1.6;
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
