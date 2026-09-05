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

  // 1. Fix bold rendering in CJK text:
  // Convert **bold** and __bold__ to <strong> tags so marked/CommonMark delimiter rules
  // don't fail when asterisks are adjacent to CJK characters or punctuation marks (e.g. **“皮拉诺瓦”（Pyranova）**)
  text = text.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/__([^_\n]+?)__/g, '<strong>$1</strong>');

  // 2. Replace relative image markdown links: ![alt](images/xxx.png)
  text = text.replace(/!\[([^\]]*)\]\((images\/[^)]+)\)/g, (match, alt, rel) => {
    return `![${alt}](/api/asset/${encodeURIComponent(props.stem)}/${rel})`;
  });

  // 3. Replace relative video markdown links: ![alt](videos/xxx.mp4)
  text = text.replace(/!\[([^\]]*)\]\((videos\/[^)]+)\)/g, (match, alt, rel) => {
    const videoUrl = `/api/asset/${encodeURIComponent(props.stem)}/${rel}`;
    return `<div class="story-video-wrap"><video src="${videoUrl}" controls preload="metadata"></video><p class="story-media-caption">${alt}</p></div>`;
  });

  // 4. Process storybook-media tags into clean placeholders or generated embeds
  // Matches both JSON format <!-- storybook-media: { ... } --> and KV format <!-- storybook-media type="..." ... -->
  text = text.replace(/<!--\s*storybook-media(?::\s*(\{.*?\})|\s+([^>]*?))\s*-->/gs, (match, jsonStr, kvStr) => {
    try {
      let tagData = {};
      if (jsonStr) {
        tagData = JSON.parse(jsonStr);
      } else if (kvStr) {
        const attrRegex = /(\w+)=["'](.*?)["']/g;
        let am;
        while ((am = attrRegex.exec(kvStr)) !== null) {
          tagData[am[1]] = am[2];
        }
      }

      const tagId = tagData.id || '';
      const tagType = (tagData.type || 'image').toLowerCase();
      const tagSection = tagData.section || tagData.title || '';
      const tagPrompt = tagData.prompt || tagData.description || '';

      // Check if generated image/video exists in workspace
      let matched = null;
      if (tagType === 'video') {
        matched = props.videos.find(v => v.id === tagId || v.name.startsWith(tagId + '.') || v.name.includes(tagId));
      } else {
        matched = props.images.find(img => img.id === tagId || img.name.startsWith(tagId + '.') || img.name.includes(tagId));
      }

      const isGenerated = !!matched;

      if (isGenerated) {
        // If generated asset exists: show embedded visual card with media and clean header
        const mediaHtml = tagType === 'video'
          ? `<video src="${matched.assetUrl}" controls class="embedded-video" preload="metadata"></video>`
          : `<img src="${matched.assetUrl}" alt="${tagId}" class="embedded-img" data-clickable-preview="true" data-src="${matched.assetUrl}" data-prompt="${encodeURIComponent(tagPrompt)}" data-title="${tagId}" />`;

        return `\n\n<div class="embedded-scene-card type-${tagType}" data-tag-id="${tagId}">
  <div class="scene-top-bar">
    <div class="scene-top-left">
      <span class="type-pill ${tagType}">
        <span class="material-symbols-rounded">${tagType === 'video' ? 'videocam' : 'image'}</span>
        ${tagType === 'video' ? 'Video' : 'Image'}
      </span>
      <span class="scene-id">${tagId}</span>
      ${tagSection ? `<span class="scene-section">${tagSection}</span>` : ''}
    </div>
    <span class="status-badge status-done">
      <span class="material-symbols-rounded">check</span>
      Generated
    </span>
  </div>
  <div class="scene-media-box">
    ${mediaHtml}
  </div>
</div>\n\n`;
      } else {
        // When pending: render as a clean, compact placeholder with critical info (type, id, section, status)
        // without cluttering the reading flow with raw prompt text. Clicking placeholder allows inspecting the prompt.
        const typeLabel = tagType === 'video' ? 'Video' : 'Image';
        const typeIcon = tagType === 'video' ? 'videocam' : 'image';

        return `\n\n<div class="story-scene-placeholder type-${tagType}"
     data-tag-id="${tagId}"
     data-tag-type="${tagType}"
     data-tag-section="${tagSection}"
     data-prompt="${encodeURIComponent(tagPrompt)}"
     data-status="Pending"
     title="Click to inspect scene prompt">
  <div class="placeholder-main">
    <span class="type-pill ${tagType}">
      <span class="material-symbols-rounded">${typeIcon}</span>
      ${typeLabel}
    </span>
    <span class="scene-id">${tagId}</span>
    ${tagSection ? `<span class="scene-section">${tagSection}</span>` : ''}
  </div>
  <div class="placeholder-side">
    <span class="status-badge status-wait">
      <span class="material-symbols-rounded">schedule</span>
      Pending
    </span>
  </div>
</div>\n\n`;
      }
    } catch (e) {
      return match;
    }
  });

  return marked.parse(text);
});

function handleContentClick(event) {
  // 1. Clicked on an image to preview
  const imgTarget = event.target.closest('img');
  if (imgTarget) {
    const src = imgTarget.getAttribute('src');
    const alt = imgTarget.getAttribute('alt') || 'Scene Illustration';
    const prompt = imgTarget.dataset.prompt ? decodeURIComponent(imgTarget.dataset.prompt) : '';
    const title = imgTarget.dataset.title || alt;

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
    return;
  }

  // 2. Clicked on a scene placeholder to inspect critical info and prompt
  const placeholderTarget = event.target.closest('.story-scene-placeholder');
  if (placeholderTarget) {
    const tagId = placeholderTarget.dataset.tagId || '';
    const tagType = placeholderTarget.dataset.tagType || 'image';
    const tagSection = placeholderTarget.dataset.tagSection || '';
    const prompt = placeholderTarget.dataset.prompt ? decodeURIComponent(placeholderTarget.dataset.prompt) : '';
    const status = placeholderTarget.dataset.status || 'Pending';

    let matched = null;
    if (tagType === 'video') {
      matched = props.videos.find(v => v.id === tagId || v.name.startsWith(tagId + '.') || v.name.includes(tagId));
    } else {
      matched = props.images.find(img => img.id === tagId || img.name.startsWith(tagId + '.') || img.name.includes(tagId));
    }

    emit('preview', {
      src: matched ? matched.assetUrl : '',
      title: `[${tagType.toUpperCase()}] ${tagId}${tagSection ? ' - ' + tagSection : ''}`,
      type: tagType,
      prompt,
      details: {
        TagID: tagId,
        Type: tagType === 'video' ? 'Video Scene' : 'Image Scene',
        Section: tagSection || 'N/A',
        Status: status,
        Asset: matched ? matched.name : 'Pending generation'
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
