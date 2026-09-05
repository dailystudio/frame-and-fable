<template>
  <div class="story-reader">
    <!-- Toolbar -->
    <div class="reader-toolbar clean-card">
      <div class="toolbar-meta">
        <span class="clean-badge">
          <span class="material-symbols-rounded">menu_book</span>
          {{ markdownType === 'output' ? 'Generated Output' : 'Story Document' }}
        </span>
        <span class="stat-pill">{{ wordCount }} words</span>
        <span class="stat-pill">{{ readTime }} min read</span>
      </div>

      <div class="toolbar-actions">
        <!-- Font Size Controls -->
        <div class="font-stepper">
          <button
            type="button"
            class="stepper-btn"
            title="Smaller text"
            :disabled="fontSizeMultiplier <= 0.85"
            @click="fontSizeMultiplier -= 0.1"
          >
            A-
          </button>
          <button
            type="button"
            class="stepper-btn"
            title="Reset text size"
            @click="fontSizeMultiplier = 1.0"
          >
            A
          </button>
          <button
            type="button"
            class="stepper-btn"
            title="Larger text"
            :disabled="fontSizeMultiplier >= 1.4"
            @click="fontSizeMultiplier += 0.1"
          >
            A+
          </button>
        </div>

        <button
          type="button"
          class="clean-btn clean-btn-sm"
          @click="showRaw = !showRaw"
        >
          <span class="material-symbols-rounded">
            {{ showRaw ? 'menu_book' : 'code' }}
          </span>
          {{ showRaw ? 'Story View' : 'Raw Markdown' }}
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!markdownContent" class="empty-state clean-card">
      <span class="material-symbols-rounded empty-icon">menu_book</span>
      <h3>No Story Text Found</h3>
      <p>Ensure <code>{{ stem }}-output.md</code> exists in <code>outputs/{{ stem }}/</code>.</p>
    </div>

    <!-- Raw Markdown View -->
    <div v-else-if="showRaw" class="raw-box clean-card">
      <div class="raw-top">
        <span class="raw-file-name">{{ stem }}-output.md</span>
        <button type="button" class="clean-btn clean-btn-sm" @click="copyRaw">
          <span class="material-symbols-rounded">
            {{ rawCopied ? 'check' : 'content_copy' }}
          </span>
          {{ rawCopied ? 'Copied' : 'Copy Text' }}
        </button>
      </div>
      <pre><code>{{ markdownContent }}</code></pre>
    </div>

    <!-- Formatted Story Reading View -->
    <div
      v-else
      class="story-sheet clean-card"
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

  // 1. Replace relative image markdown links
  text = text.replace(/!\[([^\]]*)\]\((images\/[^)]+)\)/g, (match, alt, rel) => {
    return `![${alt}](/api/asset/${encodeURIComponent(props.stem)}/${rel})`;
  });

  // 2. Replace relative video markdown links
  text = text.replace(/!\[([^\]]*)\]\((videos\/[^)]+)\)/g, (match, alt, rel) => {
    const videoUrl = `/api/asset/${encodeURIComponent(props.stem)}/${rel}`;
    return `<div class="story-video-wrap"><video src="${videoUrl}" controls poster="" preload="metadata"></video><p class="story-media-caption">${alt}</p></div>`;
  });

  // 3. Process storybook-media tags into embedded interactive cards
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
  gap: 1.25rem;
}

.reader-toolbar {
  padding: 0.6rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.toolbar-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.stat-pill {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.font-stepper {
  display: flex;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.stepper-btn {
  border: none;
  background: transparent;
  padding: 0.25rem 0.55rem;
  font-family: var(--font-sans);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.stepper-btn:hover:not(:disabled) {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.stepper-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.story-sheet {
  padding: 2.5rem 3rem;
  min-height: 500px;
}

@media (max-width: 768px) {
  .story-sheet {
    padding: 1.5rem 1rem;
  }
}

.story-markdown {
  font-size: calc(1.1rem * var(--reader-font-scale, 1));
}

.raw-box {
  overflow: hidden;
}

.raw-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 1rem;
  background: var(--bg-surface-secondary);
  border-bottom: 1px solid var(--border-default);
}

.raw-file-name {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
}

.raw-box pre {
  margin: 0;
  padding: 1.25rem;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  line-height: 1.55;
  background: var(--bg-surface);
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
