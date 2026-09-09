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

        <!-- Add Scene Tag (Edit mode only) -->
        <button
          v-if="readerMode === 'edit'"
          type="button"
          class="clean-btn clean-btn-sm add-scene-toolbar-btn"
          title="Add a new image/video scene tag into the story"
          @click="emit('open-add-tag')"
        >
          <span class="material-symbols-rounded">add_photo_alternate</span>
          <span>+ Add Scene Tag</span>
        </button>

        <button
          type="button"
          class="clean-btn clean-btn-sm"
          @click="toggleRawView"
        >
          <span class="material-symbols-rounded">
            {{ showRaw ? 'menu_book' : 'code' }}
          </span>
          {{ showRaw ? 'Story View' : 'Raw Markdown' }}
        </button>

        <!-- Mode Selection Button (Top Right Corner) -->
        <div class="reader-mode-switch" role="group" aria-label="Reader Mode Selection">
          <button
            type="button"
            class="mode-switch-btn"
            :class="{ active: readerMode === 'edit' }"
            title="Edit Mode: manage tags, prompts, generation"
            @click="setReaderMode('edit')"
          >
            <span class="material-symbols-rounded">edit_note</span>
            <span>Edit Mode</span>
          </button>
          <button
            type="button"
            class="mode-switch-btn"
            :class="{ active: readerMode === 'read' }"
            title="Read Mode: clean article view without editing controls or frames"
            @click="setReaderMode('read')"
          >
            <span class="material-symbols-rounded">auto_stories</span>
            <span>Read Mode</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Reader Guidance Hint Banner (Edit Mode Only) -->
    <div v-if="readerMode === 'edit'" class="reader-hint-banner clean-card">
      <div class="hint-left">
        <span class="material-symbols-rounded hint-icon">tips_and_updates</span>
        <span>
          <strong>Scene Tag Tips:</strong> Hover between any two paragraphs in the story to insert an inline scene tag (<strong>+ Add Scene Tag Here</strong>), or click <strong>+ Add Scene Tag</strong> in the toolbar. Switch to <strong>Read Mode</strong> on the top right for a clean article view.
        </span>
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
      :class="readerMode === 'read' ? 'mode-read' : 'mode-edit'"
      :style="{ '--reader-font-scale': fontSizeMultiplier }"
      @click="handleContentClick"
    >
      <div class="story-markdown" v-html="renderedHtml"></div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { marked } from 'marked';
import { isTagGenerating, runTagGeneration, onGenerationComplete, generationState } from '../services/api';
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

const emit = defineEmits(['preview', 'refresh', 'open-add-tag']);

const readerMode = ref('edit'); // 'edit' | 'read'
const showRaw = ref(false);
const rawCopied = ref(false);
const fontSizeMultiplier = ref(1.0);

function setReaderMode(mode) {
  readerMode.value = mode;
  if (showRaw.value) {
    showRaw.value = false;
  }
}

function toggleRawView() {
  showRaw.value = !showRaw.value;
}

const activeGeneratingTags = ref(new Set());
const generationVersion = ref(0);

let unsubGen = null;
onMounted(() => {
  unsubGen = onGenerationComplete((err, payload) => {
    if (payload?.tagId) {
      activeGeneratingTags.value.delete(payload.tagId);
      generationVersion.value++;
    }
  });
});

onBeforeUnmount(() => {
  if (unsubGen) unsubGen();
});

watch(() => Object.keys(generationState.activeMap).length, () => {
  generationVersion.value++;
});

const wordCount = computed(() => {
  if (!props.markdownContent) return 0;
  return props.markdownContent.trim().split(/\s+/).length;
});

const readTime = computed(() => {
  return Math.max(1, Math.ceil(wordCount.value / 220));
});

const renderedHtml = computed(() => {
  if (!props.markdownContent) return '';
  const _v = generationVersion.value;
  const _activeMap = generationState.activeMap;
  const isRead = readerMode.value === 'read';

  let text = props.markdownContent;

  // 1. Strip duplicate markdown image links immediately following a storybook-media tag.
  // MUST RUN FIRST before any link rewriting so raw relative links like ![alt](images/xxx.png) are caught and stripped!
  text = text.replace(/(<!--\s*storybook-media(?::\s*\{.*?\}|\s+[^>]*?)\s*-->)(?:\s*!\[[^\]]*\]\([^)]+\))+/gs, '$1');

  // 2. Fix bold rendering in CJK text:
  // Convert **bold** and __bold__ to <strong> tags so marked/CommonMark delimiter rules
  // don't fail when asterisks are adjacent to CJK characters or punctuation marks (e.g. **“皮拉诺瓦”（Pyranova）**)
  text = text.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/__([^_\n]+?)__/g, '<strong>$1</strong>');

  // 3. Replace relative image markdown links: ![alt](images/xxx.png)
  text = text.replace(/!\[([^\]]*)\]\((images\/[^)]+)\)/g, (match, alt, rel) => {
    return `![${alt}](/api/asset/${encodeURIComponent(props.stem)}/${rel})`;
  });

  // 4. Replace relative video markdown links: ![alt](videos/xxx.mp4)
  text = text.replace(/!\[([^\]]*)\]\((videos\/[^)]+)\)/g, (match, alt, rel) => {
    const videoUrl = `/api/asset/${encodeURIComponent(props.stem)}/${rel}`;
    return `<div class="story-video-wrap"><video src="${videoUrl}" controls preload="metadata"></video><p class="story-media-caption">${alt}</p></div>`;
  });

  // 5. Extract storybook-media tags into clean unique slot tokens before running marked.parse.
  // This completely prevents marked from escaping HTML, breaking indentation, or wrapping cards in <pre><code>!
  const mediaSlots = {};
  let slotCounter = 0;

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

      const enriched = props.tags.find(t => t.id === tagId);

      // Check if generated image/video exists in workspace
      let matched = null;
      if (tagType === 'video') {
        matched = props.videos.find(v => v.id === tagId || v.name.startsWith(tagId + '.') || v.name.includes(tagId));
      } else {
        matched = props.images.find(img => img.id === tagId || img.name.startsWith(tagId + '.') || img.name.includes(tagId));
      }

      // Robust fallback: check if tagData or enriched metadata indicates the asset was generated
      if (!matched) {
        const rawAsset = tagData.asset || enriched?.asset;
        const isStatusGen = tagData.status === 'generated' || enriched?.status === 'generated' || enriched?.isGenerated;
        if (rawAsset && (isStatusGen || rawAsset.startsWith('images/') || rawAsset.startsWith('videos/'))) {
          const assetFile = rawAsset.split('/').pop();
          matched = {
            id: tagId,
            name: assetFile,
            assetUrl: rawAsset.startsWith('/api/') ? rawAsset : `/api/asset/${encodeURIComponent(props.stem)}/${rawAsset}`
          };
        }
      }

      const isGenerated = !!matched;
      const isGeneratingTag = activeGeneratingTags.value.has(tagId) || isTagGenerating(props.stem, tagId);

      // Character chips if characters are matched
      const charChipsHtml = (enriched?.character_refs || []).map(c =>
        `<span class="char-chip"><span class="material-symbols-rounded">face</span>${c.name}</span>`
      ).join(' ');

      let cardHtml = '';

      if (isRead) {
        // READ MODE:
        // Hide control panel and frame of image, just markdown text with images and video like final output
        if (isGenerated) {
          if (tagType === 'video') {
            cardHtml = `<div class="story-video-wrap"><video src="${matched.assetUrl}" controls preload="metadata" class="story-article-video"></video></div>`;
          } else {
            cardHtml = `<div class="story-read-media"><img src="${matched.assetUrl}" alt="${tagSection || tagId}" class="story-article-img" data-tag-id="${tagId}" data-clickable-preview="true" data-src="${matched.assetUrl}" data-prompt="${encodeURIComponent(tagPrompt)}" data-title="${tagId}" loading="lazy" /></div>`;
          }
        } else {
          // In read mode, pending ungenerated scene tags are completely omitted
          cardHtml = '';
        }
      } else {
        // EDIT MODE:
        if (isGenerated) {
          // Embedded visual card with media, prominent Regenerate Scene button, and inspect button
          const mediaHtml = tagType === 'video'
            ? `<video src="${matched.assetUrl}" controls class="embedded-video" preload="metadata" data-tag-id="${tagId}"></video>`
            : `<img src="${matched.assetUrl}" alt="${tagId}" class="embedded-img" data-tag-id="${tagId}" data-clickable-preview="true" data-src="${matched.assetUrl}" data-prompt="${encodeURIComponent(tagPrompt)}" data-title="${tagId}" />`;

          cardHtml = `<div class="embedded-scene-card type-${tagType}" data-tag-id="${tagId}">
  <div class="scene-top-bar">
    <div class="scene-top-row">
      <div class="scene-top-left">
        <span class="type-pill ${tagType}">
          <span class="material-symbols-rounded">${tagType === 'video' ? 'videocam' : 'image'}</span>
          ${tagType === 'video' ? 'Video' : 'Image'}
        </span>
        <span class="scene-id">${tagId}</span>
        ${tagSection ? `<span class="scene-section">${tagSection}</span>` : ''}
      </div>
      <div class="scene-top-right">
        <button type="button" class="scene-action-btn regen-btn" data-tag-id="${tagId}" data-action="regenerate" ${isGeneratingTag ? 'disabled' : ''} title="${isGeneratingTag ? 'Generating in background...' : 'Regenerate this scene via Gemini'}">
          <span class="material-symbols-rounded ${isGeneratingTag ? 'is-spinning' : ''}">${isGeneratingTag ? 'sync' : 'refresh'}</span>
          <span>${isGeneratingTag ? 'Generating...' : 'Regenerate Scene'}</span>
        </button>
        <button type="button" class="inspect-tag-btn" data-tag-id="${tagId}" data-action="inspect" title="Inspect prompt & references">
          <span class="material-symbols-rounded">tune</span>
          <span>Prompt & Refs</span>
        </button>
        <span class="status-badge ${isGeneratingTag ? 'status-generating' : 'status-done'}">
          <span class="material-symbols-rounded ${isGeneratingTag ? 'is-spinning' : ''}">${isGeneratingTag ? 'sync' : 'check'}</span>
          ${isGeneratingTag ? 'Generating...' : 'Generated'}
        </span>
      </div>
    </div>
    ${charChipsHtml ? `
    <div class="scene-chars-strip">
      <span class="chars-strip-label"><span class="material-symbols-rounded">face</span>Characters:</span>
      <div class="chars-strip-list">${charChipsHtml}</div>
    </div>` : ''}
  </div>
  <div class="scene-media-box">
    ${mediaHtml}
  </div>
</div>`;
        } else {
          // Clean, compact placeholder with Generate Scene button and inspect button
          const typeLabel = tagType === 'video' ? 'Video' : 'Image';
          const typeIcon = tagType === 'video' ? 'videocam' : 'image';

          cardHtml = `<div class="story-scene-placeholder type-${tagType}"
     data-tag-id="${tagId}"
     data-tag-type="${tagType}"
     data-tag-section="${tagSection}"
     data-prompt="${encodeURIComponent(tagPrompt)}"
     data-status="Pending"
     title="Click to inspect scene prompt & reference guides">
  <div class="placeholder-top-row">
    <div class="scene-meta-group">
      <span class="type-pill ${tagType}">
        <span class="material-symbols-rounded">${typeIcon}</span>
        ${typeLabel}
      </span>
      <span class="scene-id">${tagId}</span>
      ${tagSection ? `<span class="scene-section">${tagSection}</span>` : ''}
    </div>
    <div class="placeholder-side">
      <button type="button" class="scene-action-btn gen-btn" data-tag-id="${tagId}" data-action="generate" ${isGeneratingTag ? 'disabled' : ''} title="${isGeneratingTag ? 'Generating in background...' : 'Generate this scene via Gemini'}">
        <span class="material-symbols-rounded ${isGeneratingTag ? 'is-spinning' : ''}">${isGeneratingTag ? 'sync' : 'auto_awesome'}</span>
        <span>${isGeneratingTag ? 'Generating...' : 'Generate Scene'}</span>
      </button>
      <button type="button" class="inspect-tag-btn" data-tag-id="${tagId}" data-action="inspect">
        <span class="material-symbols-rounded">tune</span>
        <span>Prompt & Refs</span>
      </button>
      <span class="status-badge ${isGeneratingTag ? 'status-generating' : 'status-wait'}">
        <span class="material-symbols-rounded ${isGeneratingTag ? 'is-spinning' : ''}">${isGeneratingTag ? 'sync' : 'schedule'}</span>
        ${isGeneratingTag ? 'Generating...' : 'Pending'}
      </span>
    </div>
  </div>
  ${charChipsHtml ? `
  <div class="scene-chars-strip">
    <span class="chars-strip-label"><span class="material-symbols-rounded">face</span>Characters:</span>
    <div class="chars-strip-list">${charChipsHtml}</div>
  </div>` : ''}
</div>`;
        }
      }

      if (!cardHtml) {
        return '';
      }

      const slotToken = `%%STORYBOOK_MEDIA_SLOT_${slotCounter++}%%`;
      mediaSlots[slotToken] = cardHtml;
      return `\n\n${slotToken}\n\n`;
    } catch (e) {
      return match;
    }
  });

  // Parse markdown into HTML safely
  let html = marked.parse(text);

  // Substitute media slots back into HTML
  for (const [token, cardHtml] of Object.entries(mediaSlots)) {
    html = html.replace(`<p>${token}</p>`, cardHtml).replace(token, cardHtml);
  }

  // In Edit mode only: Add sleek hover insertion zones after narrative paragraphs
  if (!isRead) {
    html = html.replace(/<\/p>/g, '</p><div class="para-insert-zone"><button type="button" class="para-insert-btn" data-action="insert-tag-here" title="Insert new image/video scene tag here"><span class="material-symbols-rounded">add</span><span>+ Add Scene Tag Here</span></button></div>');
  }

  return html;
});

function handleContentClick(event) {
  // In Read Mode: allow clicking on images to preview lightbox, but ignore edit actions
  if (readerMode.value === 'read') {
    const imgTarget = event.target.closest('img');
    if (imgTarget) {
      const src = imgTarget.getAttribute('src') || '';
      const alt = imgTarget.getAttribute('alt') || 'Scene Illustration';
      const tagId = imgTarget.dataset.tagId || '';

      const filename = src.split('/').pop().split('?')[0];
      const baseName = filename.replace(/\.[^/.]+$/, "");
      const enriched = (props.tags || []).find(t =>
        (tagId && t.id === tagId) ||
        t.id === baseName ||
        filename.includes(t.id) ||
        t.id === alt
      );

      const resolvedTagId = enriched?.id || tagId || baseName;
      const resolvedPrompt = enriched?.prompt || (imgTarget.dataset.prompt ? decodeURIComponent(imgTarget.dataset.prompt) : alt);

      emit('preview', {
        src,
        title: enriched ? `[${(enriched.type || 'image').toUpperCase()}] ${enriched.id}${enriched.section ? ' - ' + enriched.section : ''}` : alt,
        type: enriched?.type || 'image',
        id: resolvedTagId,
        tagId: resolvedTagId,
        stem: props.stem,
        section: enriched?.section || '',
        prompt: resolvedPrompt,
        composedPrompt: enriched?.composed_prompt || '',
        styleRef: enriched?.style_ref || null,
        characterRefs: enriched?.character_refs || [],
        cliCommand: enriched?.cli_command || '',
        details: {
          TagID: resolvedTagId,
          Type: (enriched?.type || 'image') === 'video' ? 'Video Scene' : 'Image Scene',
          Section: enriched?.section || 'N/A',
          Workspace: props.stem,
          Context: 'Story Reader (Read Mode)'
        }
      });
    }
    return;
  }

  // 0. Clicked on insert scene tag trigger between paragraphs
  const insertBtn = event.target.closest('[data-action="insert-tag-here"]');
  if (insertBtn) {
    const zone = insertBtn.closest('.para-insert-zone');
    
    // Walk backwards to find preceding narrative paragraph in this section
    let beforeText = '';
    let section = '';
    let el = zone?.previousElementSibling;
    while (el) {
      if (/^H[1-6]$/i.test(el.tagName)) {
        section = el.innerText.trim();
        break;
      }
      if (el.tagName === 'P' && !beforeText) {
        beforeText = el.innerText.trim();
      }
      el = el.previousElementSibling;
    }

    // Walk forward to find following narrative paragraph in this section
    let afterText = '';
    let nextEl = zone?.nextElementSibling;
    while (nextEl) {
      if (/^H[1-6]$/i.test(nextEl.tagName)) {
        // Next element is the next section heading: this is the last paragraph of the section!
        afterText = '';
        break;
      }
      if (nextEl.tagName === 'P') {
        afterText = nextEl.innerText.trim();
        break;
      }
      nextEl = nextEl.nextElementSibling;
    }

    emit('open-add-tag', {
      section,
      beforeText,
      afterText
    });
    return;
  }

  // 1. Clicked on any element with data-tag-id (placeholder, card, inspect button, action button, embedded media)
  const tagTarget = event.target.closest('[data-tag-id]');
  if (tagTarget) {
    const actionTarget = event.target.closest('[data-action]');
    const isAutoGenerate = actionTarget && (actionTarget.dataset.action === 'regenerate' || actionTarget.dataset.action === 'generate');

    const tagId = tagTarget.dataset.tagId;
    const enriched = props.tags.find(t => t.id === tagId);

    const tagType = (enriched?.type || tagTarget.dataset.tagType || 'image').toLowerCase();
    const tagSection = enriched?.section || tagTarget.dataset.tagSection || '';
    const tagPrompt = enriched?.prompt || (tagTarget.dataset.prompt ? decodeURIComponent(tagTarget.dataset.prompt) : '');

    let matched = null;
    if (tagType === 'video') {
      matched = props.videos.find(v => v.id === tagId || v.name.startsWith(tagId + '.') || v.name.includes(tagId));
    } else {
      matched = props.images.find(img => img.id === tagId || img.name.startsWith(tagId + '.') || img.name.includes(tagId));
    }

    // Direct inline button action (Generate Scene or Regenerate Scene)
    if (isAutoGenerate) {
      actionTarget.disabled = true;
      const spanText = actionTarget.querySelector('span:not(.material-symbols-rounded)');
      const icon = actionTarget.querySelector('.material-symbols-rounded');
      if (spanText) spanText.textContent = 'Generating...';
      if (icon) {
        icon.textContent = 'sync';
        icon.classList.add('is-spinning');
      }
      const sideGroup = actionTarget.closest('.scene-top-right, .placeholder-side');
      const statusBadge = sideGroup?.querySelector('.status-badge');
      if (statusBadge) {
        statusBadge.className = 'status-badge status-generating';
        statusBadge.innerHTML = '<span class="material-symbols-rounded is-spinning">sync</span> Generating...';
      }

      activeGeneratingTags.value.add(tagId);
      generationVersion.value++;

      runTagGeneration(props.stem, { tagId, section: tagSection, type: tagType });
      return;
    }

    // Clicking "Prompt & Refs" or clicking the card/media opens the Lightbox inspector
    emit('preview', {
      src: matched ? matched.assetUrl : '',
      title: `[${tagType.toUpperCase()}] ${tagId}${tagSection ? ' - ' + tagSection : ''}`,
      type: tagType,
      id: tagId,
      tagId: tagId,
      stem: props.stem,
      section: tagSection,
      prompt: tagPrompt,
      composedPrompt: enriched?.composed_prompt || '',
      styleRef: enriched?.style_ref || null,
      characterRefs: enriched?.character_refs || [],
      cliCommand: enriched?.cli_command || '',
      autoGenerate: false,
      details: {
        TagID: tagId,
        Type: tagType === 'video' ? 'Video Scene' : 'Image Scene',
        Section: tagSection || 'N/A',
        Status: matched ? 'Generated' : 'Pending',
        Asset: matched ? matched.name : 'Pending generation'
      }
    });
    return;
  }

  // 2. Clicked on a standalone markdown image
  const imgTarget = event.target.closest('img');
  if (imgTarget) {
    const src = imgTarget.getAttribute('src') || '';
    const alt = imgTarget.getAttribute('alt') || 'Scene Illustration';
    const tagId = imgTarget.dataset.tagId || '';

    // Match against tags by data-tag-id, filename, or alt text
    const filename = src.split('/').pop().split('?')[0];
    const baseName = filename.replace(/\.[^/.]+$/, "");
    const enriched = (props.tags || []).find(t =>
      (tagId && t.id === tagId) ||
      t.id === baseName ||
      filename.includes(t.id) ||
      t.id === alt
    );

    const resolvedTagId = enriched?.id || tagId || baseName;
    const resolvedPrompt = enriched?.prompt || (imgTarget.dataset.prompt ? decodeURIComponent(imgTarget.dataset.prompt) : alt);

    emit('preview', {
      src,
      title: enriched ? `[${(enriched.type || 'image').toUpperCase()}] ${enriched.id}${enriched.section ? ' - ' + enriched.section : ''}` : alt,
      type: enriched?.type || 'image',
      id: resolvedTagId,
      tagId: resolvedTagId,
      stem: props.stem,
      section: enriched?.section || '',
      prompt: resolvedPrompt,
      composedPrompt: enriched?.composed_prompt || '',
      styleRef: enriched?.style_ref || null,
      characterRefs: enriched?.character_refs || [],
      cliCommand: enriched?.cli_command || '',
      details: {
        TagID: resolvedTagId,
        Type: (enriched?.type || 'image') === 'video' ? 'Video Scene' : 'Image Scene',
        Section: enriched?.section || 'N/A',
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

/* Inline Paragraph Insertion Zone */
:deep(.para-insert-zone) {
  height: 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  margin: 4px 0;
  z-index: 2;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s ease;
}

:deep(.para-insert-zone)::before {
  content: '';
  position: absolute;
  left: 6%;
  right: 6%;
  top: 50%;
  height: 1px;
  background: var(--primary, #6750a4);
  opacity: 0;
  transition: opacity 0.2s ease;
}

:deep(.para-insert-zone:hover)::before {
  opacity: 0.4;
}

:deep(.para-insert-btn) {
  opacity: 0;
  transform: scale(0.92);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  background: var(--bg-surface, #ffffff);
  color: var(--primary, #6750a4);
  border: 1px solid var(--primary, #6750a4);
  border-radius: 9999px;
  padding: 0.25rem 0.85rem;
  font-size: 0.8rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(103, 80, 164, 0.18);
  pointer-events: none;
  z-index: 3;
}

:deep(.para-insert-zone:hover .para-insert-btn) {
  opacity: 1;
  transform: scale(1);
  pointer-events: auto;
  background: var(--primary-container, #eaddff);
  color: var(--primary-on-container, #21005d);
}

:deep(.para-insert-btn .material-symbols-rounded) {
  font-size: 1.1rem;
}

.add-scene-toolbar-btn {
  background: var(--primary, #6750a4);
  color: #ffffff;
  font-weight: 600;
  gap: 0.35rem;
  border-radius: 9999px;
  padding: 0.35rem 0.85rem;
  box-shadow: 0 2px 6px rgba(103, 80, 164, 0.25);
  transition: all 0.2s ease;
}

.add-scene-toolbar-btn:hover {
  opacity: 0.94;
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(103, 80, 164, 0.35);
}

.add-scene-toolbar-btn .material-symbols-rounded {
  font-size: 1.1rem;
}

.reader-hint-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 1.25rem;
  background: var(--primary-container, rgba(103, 80, 164, 0.08));
  border: 1px solid rgba(103, 80, 164, 0.2);
  border-radius: var(--radius-md);
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.hint-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.hint-icon {
  font-size: 1.2rem;
  color: var(--primary, #6750a4);
}

/* Mode Selection Button Group (Top Right Corner) */
.reader-mode-switch {
  display: inline-flex;
  align-items: center;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  padding: 3px;
  gap: 2px;
}

.mode-switch-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: none;
  background: transparent;
  padding: 0.28rem 0.75rem;
  font-family: var(--font-sans);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
  line-height: 1.2;
}

.mode-switch-btn .material-symbols-rounded {
  font-size: 16px;
}

.mode-switch-btn:hover:not(.active) {
  color: var(--text-primary);
  background: rgba(0, 0, 0, 0.05);
}

[data-theme="dark"] .mode-switch-btn:hover:not(.active) {
  background: rgba(255, 255, 255, 0.08);
}

.mode-switch-btn.active {
  background: var(--accent-primary);
  color: #ffffff;
  box-shadow: 0 1px 4px rgba(37, 99, 235, 0.25);
}

.read-mode-badge {
  background: rgba(37, 99, 235, 0.1);
  color: var(--accent-primary);
  border-color: rgba(37, 99, 235, 0.25);
}

/* Pure Read Mode Styling */
.story-sheet.mode-read {
  border-color: var(--border-subtle);
}

:deep(.story-read-media) {
  margin: 2.2rem auto;
  text-align: center;
  line-height: 0;
}

:deep(.story-read-media .story-article-img) {
  max-width: 100% !important;
  height: auto !important;
  border-radius: var(--radius-md) !important;
  box-shadow: var(--shadow-sm) !important;
  display: block !important;
  margin: 0 auto !important;
  cursor: zoom-in !important;
  transition: opacity 0.15s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

:deep(.story-read-media .story-article-img:hover) {
  opacity: 0.97;
  box-shadow: var(--shadow-md) !important;
}

:deep(.story-article-video) {
  width: 100%;
  max-height: 520px;
  display: block;
  border-radius: var(--radius-md);
}

/* Read Mode safety hiding rules */
.story-sheet.mode-read :deep(.para-insert-zone),
.story-sheet.mode-read :deep(.story-scene-placeholder),
.story-sheet.mode-read :deep(.scene-top-bar) {
  display: none !important;
}

.story-sheet.mode-read :deep(.embedded-scene-card) {
  margin: 2.2rem 0 !important;
  border: none !important;
  border-left: none !important;
  background: transparent !important;
  box-shadow: none !important;
  border-radius: 0 !important;
}

.story-sheet.mode-read :deep(.embedded-scene-card .scene-media-box) {
  background: transparent !important;
  border-radius: var(--radius-md) !important;
}

.story-sheet.mode-read :deep(.embedded-scene-card .embedded-img) {
  border-radius: var(--radius-md) !important;
  box-shadow: var(--shadow-sm) !important;
}
</style>
