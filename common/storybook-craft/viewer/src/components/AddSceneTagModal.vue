<template>
  <dialog
    ref="dialogRef"
    class="add-tag-modal-dialog"
    @click="onBackdropClick"
  >
    <div class="add-tag-modal-sheet clean-card" @click.stop>
      <!-- Header -->
      <header class="modal-header">
        <div class="header-title-group">
          <span class="material-symbols-rounded modal-icon">add_photo_alternate</span>
          <div>
            <h3 class="modal-title">Add New Scene Tag</h3>
            <p class="modal-subtitle">
              Insert a visual scene tag into the story markdown to generate an illustration or video.
            </p>
          </div>
        </div>
        <button type="button" class="clean-icon-btn close-btn" @click="close">
          <span class="material-symbols-rounded">close</span>
        </button>
      </header>

      <!-- Body -->
      <div class="modal-body">
        <!-- Row 1: Type & Tag ID -->
        <div class="form-row-2col">
          <div class="form-group">
            <label class="form-label">
              <span class="material-symbols-rounded">category</span>
              Media Type
            </label>
            <div class="pill-options">
              <button
                type="button"
                class="pill-opt"
                :class="{ active: tagType === 'image' }"
                @click="onTypeChange('image')"
              >
                <span class="material-symbols-rounded">image</span>
                Image
              </button>
              <button
                type="button"
                class="pill-opt"
                :class="{ active: tagType === 'video' }"
                @click="onTypeChange('video')"
              >
                <span class="material-symbols-rounded">videocam</span>
                Video
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              <span class="material-symbols-rounded">tag</span>
              Scene Tag ID
            </label>
            <div class="input-with-action">
              <input
                v-model="tagId"
                type="text"
                class="clean-input"
                placeholder="e.g. img_056"
              />
              <button
                type="button"
                class="clean-btn clean-btn-sm id-suggest-btn"
                title="Auto-suggest next sequential ID"
                @click="tagId = suggestNextTagId(tagType)"
              >
                Suggest
              </button>
            </div>
          </div>
        </div>

        <!-- Row 2: Placement Mode -->
        <div class="form-group">
          <label class="form-label">
            <span class="material-symbols-rounded">place</span>
            Insertion Location in Story
          </label>
          <div class="placement-mode-selector">
            <label class="radio-pill" :class="{ active: placementMode === 'inline' }" v-if="hasInlineContext">
              <input type="radio" v-model="placementMode" value="inline" />
              <span>Inline (Between Selected Paragraphs)</span>
            </label>
            <label class="radio-pill" :class="{ active: placementMode === 'after_tag' }">
              <input type="radio" v-model="placementMode" value="after_tag" />
              <span>After Existing Scene Tag</span>
            </label>
            <label class="radio-pill" :class="{ active: placementMode === 'section' }">
              <input type="radio" v-model="placementMode" value="section" />
              <span>Under Chapter / Section</span>
            </label>
            <label class="radio-pill" :class="{ active: placementMode === 'end' }">
              <input type="radio" v-model="placementMode" value="end" />
              <span>End of Story</span>
            </label>
          </div>
        </div>

        <!-- Dynamic Placement Target Fields -->
        <div v-if="placementMode === 'after_tag'" class="form-group">
          <label class="form-label">
            <span class="material-symbols-rounded">low_priority</span>
            Select Scene Tag to Insert After
          </label>
          <select v-model="selectedAfterTagId" class="clean-select full-width">
            <option value="">-- Choose target tag --</option>
            <option v-for="t in tags" :key="t.id" :value="t.id">
              {{ t.id }} ({{ t.type || 'image' }}) - {{ t.section || 'General' }} - {{ (t.prompt || '').slice(0, 40) }}...
            </option>
          </select>
        </div>

        <!-- Chapter / Section -->
        <div class="form-group">
          <label class="form-label">
            <span class="material-symbols-rounded">bookmark</span>
            Chapter / Section Title
          </label>
          <div class="section-input-row">
            <input
              v-model="section"
              type="text"
              class="clean-input"
              list="section-datalist"
              placeholder="e.g. 序章, 第一章"
            />
            <datalist id="section-datalist">
              <option v-for="s in uniqueSections" :key="s" :value="s" />
            </datalist>
          </div>
        </div>

        <!-- Context Preview (if available) -->
        <div v-if="beforeText || afterText" class="context-preview-box">
          <span class="context-title">
            <span class="material-symbols-rounded">auto_stories</span>
            Surrounding Narrative Context
          </span>
          <p v-if="beforeText" class="context-p">
            <strong>Preceding:</strong> {{ beforeText.slice(0, 140) }}{{ beforeText.length > 140 ? '...' : '' }}
          </p>
          <p v-if="afterText" class="context-p">
            <strong>Following:</strong> {{ afterText.slice(0, 140) }}{{ afterText.length > 140 ? '...' : '' }}
          </p>
        </div>

        <!-- Scene Visual Prompt -->
        <div class="form-group">
          <div class="prompt-header-bar">
            <label class="form-label">
              <span class="material-symbols-rounded">psychology</span>
              Visual Generation Prompt
            </label>
            <button
              type="button"
              class="clean-btn clean-btn-sm auto-prompt-btn"
              :disabled="isGeneratingPrompt"
              title="Automatically synthesize visual prompt using story narrative, character references, and art style"
              @click="handleAutoBuildPrompt"
            >
              <span class="material-symbols-rounded" :class="{ 'is-spinning': isGeneratingPrompt }">
                {{ isGeneratingPrompt ? 'sync' : 'auto_awesome' }}
              </span>
              <span>{{ isGeneratingPrompt ? 'Synthesizing...' : '✨ Auto-Generate Prompt' }}</span>
            </button>
          </div>
          <textarea
            v-model="prompt"
            class="clean-textarea prompt-area"
            rows="4"
            placeholder="Visual generation prompt describing subjects, actions, lighting, camera framing, mood, and art style..."
          ></textarea>
          <div class="prompt-hint-row">
            <span v-if="statusMessage" class="status-msg">{{ statusMessage }}</span>
            <span v-else class="form-hint">
              💡 Tip: Click <strong>Auto-Generate Prompt</strong> to synthesize a rich visual prompt from narrative text, character guides, and art style.
            </span>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <footer class="modal-footer">
        <button type="button" class="clean-btn" @click="close">
          Cancel
        </button>
        <button
          type="button"
          class="clean-btn clean-btn-secondary"
          :disabled="isSubmitting"
          @click="submitTag(false)"
        >
          <span class="material-symbols-rounded">save</span>
          <span>Insert Tag Only</span>
        </button>
        <button
          type="button"
          class="clean-btn clean-btn-primary primary-gen-btn"
          :disabled="isSubmitting"
          @click="submitTag(true)"
        >
          <span class="material-symbols-rounded">auto_awesome</span>
          <span>✨ Insert & Generate Scene</span>
        </button>
      </footer>
    </div>
  </dialog>
</template>

<script setup>
import { ref, computed } from 'vue';
import { buildPrompt, insertTag } from '../services/api';

const props = defineProps({
  stem: {
    type: String,
    required: true
  },
  tags: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['close', 'inserted', 'refresh']);

const dialogRef = ref(null);
const tagType = ref('image');
const tagId = ref('');
const section = ref('');
const prompt = ref('');
const beforeText = ref('');
const afterText = ref('');
const selectedAfterTagId = ref('');
const placementMode = ref('inline');
const hasInlineContext = ref(false);

const isGeneratingPrompt = ref(false);
const isSubmitting = ref(false);
const statusMessage = ref('');

const uniqueSections = computed(() => {
  const set = new Set();
  for (const t of props.tags) {
    if (t.section) set.add(t.section);
  }
  return Array.from(set);
});

function suggestNextTagId(type = 'image') {
  const prefix = type === 'video' ? 'vid_' : 'img_';
  let maxNum = 0;
  for (const t of props.tags) {
    if (t.id && t.id.startsWith(prefix)) {
      const numPart = parseInt(t.id.slice(prefix.length), 10);
      if (!isNaN(numPart) && numPart > maxNum) {
        maxNum = numPart;
      }
    }
  }
  return `${prefix}${String(maxNum + 1).padStart(3, '0')}`;
}

function onTypeChange(newType) {
  tagType.value = newType;
  if (!tagId.value || tagId.value.startsWith('img_') || tagId.value.startsWith('vid_')) {
    tagId.value = suggestNextTagId(newType);
  }
}

function open(options = {}) {
  statusMessage.value = '';
  tagType.value = options.defaultType || 'image';
  tagId.value = options.suggestedId || suggestNextTagId(tagType.value);
  section.value = options.section || '';
  prompt.value = options.prompt || '';
  beforeText.value = options.beforeText || '';
  afterText.value = options.afterText || '';
  selectedAfterTagId.value = options.afterTagId || '';

  if (options.beforeText || options.afterText) {
    hasInlineContext.value = true;
    placementMode.value = 'inline';
  } else if (options.afterTagId) {
    hasInlineContext.value = false;
    placementMode.value = 'after_tag';
  } else if (options.section) {
    hasInlineContext.value = false;
    placementMode.value = 'section';
  } else {
    hasInlineContext.value = false;
    placementMode.value = 'end';
  }

  if (dialogRef.value) {
    dialogRef.value.showModal();
  }
}

function close() {
  if (dialogRef.value) {
    dialogRef.value.close();
  }
  emit('close');
}

function onBackdropClick(e) {
  if (e.target === dialogRef.value) {
    close();
  }
}

async function handleAutoBuildPrompt() {
  isGeneratingPrompt.value = true;
  statusMessage.value = '';
  try {
    let ctxBefore = beforeText.value;
    let ctxAfter = afterText.value;

    // If no context was passed inline but a tag was selected to insert after, find tag's prompt or context hint
    if (!ctxBefore && selectedAfterTagId.value) {
      const prevTag = props.tags.find(t => t.id === selectedAfterTagId.value);
      if (prevTag) {
        ctxBefore = prevTag.prompt || prevTag.context_hint || '';
      }
    }

    const res = await buildPrompt(props.stem, {
      type: tagType.value,
      section: section.value,
      beforeText: ctxBefore,
      afterText: ctxAfter,
      tagId: tagId.value
    });

    if (res.prompt) {
      prompt.value = res.prompt;
      statusMessage.value = '✨ Successfully synthesized prompt from narrative context & art style!';
    }
  } catch (err) {
    statusMessage.value = `Failed to generate prompt: ${err.message}`;
  } finally {
    isGeneratingPrompt.value = false;
  }
}

async function submitTag(generateNow = false) {
  const cleanId = (tagId.value || '').trim();
  if (!cleanId) {
    alert('Please enter a Scene Tag ID (e.g. img_056)');
    return;
  }

  isSubmitting.value = true;
  try {
    let insertAfterTextVal = '';
    let afterTagIdVal = '';

    if (placementMode.value === 'inline' && beforeText.value) {
      insertAfterTextVal = beforeText.value;
    } else if (placementMode.value === 'after_tag' && selectedAfterTagId.value) {
      afterTagIdVal = selectedAfterTagId.value;
    }

    await insertTag(props.stem, {
      tagId: cleanId,
      type: tagType.value,
      section: section.value,
      prompt: prompt.value,
      insertAfterText: insertAfterTextVal,
      afterTagId: afterTagIdVal
    });

    const insertedData = {
      tagId: cleanId,
      type: tagType.value,
      section: section.value,
      prompt: prompt.value,
      generateNow
    };

    close();
    emit('inserted', insertedData);
    emit('refresh');
  } catch (err) {
    alert(`Failed to insert tag: ${err.message}`);
  } finally {
    isSubmitting.value = false;
  }
}

defineExpose({
  open,
  close
});
</script>

<style scoped>
.add-tag-modal-dialog {
  border: none;
  background: transparent;
  padding: 0;
  max-width: 680px;
  width: 92vw;
  margin: auto;
}

.add-tag-modal-dialog::backdrop {
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
}

.add-tag-modal-sheet {
  background: var(--bg-surface, #ffffff);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.28);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border-default);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.25rem 1.5rem 1rem;
  border-bottom: 1px solid var(--border-default);
}

.header-title-group {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
}

.modal-icon {
  font-size: 1.75rem;
  color: var(--primary, #6750a4);
  background: var(--primary-container, rgba(103, 80, 164, 0.12));
  padding: 0.5rem;
  border-radius: 12px;
}

.modal-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.modal-subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.modal-body {
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 68vh;
  overflow-y: auto;
}

.form-row-2col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 600px) {
  .form-row-2col {
    grid-template-columns: 1fr;
  }
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.form-label .material-symbols-rounded {
  font-size: 1.05rem;
  color: var(--primary);
}

.pill-options {
  display: flex;
  gap: 0.5rem;
}

.pill-opt {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.85rem;
  border-radius: 9999px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface-secondary);
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.pill-opt:hover {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.pill-opt.active {
  background: var(--primary, #6750a4);
  color: #ffffff;
  border-color: var(--primary, #6750a4);
}

.pill-opt .material-symbols-rounded {
  font-size: 1.05rem;
}

.input-with-action {
  display: flex;
  gap: 0.5rem;
}

.id-suggest-btn {
  white-space: nowrap;
}

.placement-mode-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.radio-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  font-size: 0.78rem;
  cursor: pointer;
  user-select: none;
  transition: all 0.15s;
}

.radio-pill.active {
  background: var(--primary-container, rgba(103, 80, 164, 0.15));
  border-color: var(--primary, #6750a4);
  color: var(--primary-on-container, var(--primary));
  font-weight: 600;
}

.radio-pill input[type="radio"] {
  accent-color: var(--primary);
  margin: 0;
}

.full-width {
  width: 100%;
}

.section-input-row {
  display: flex;
  gap: 0.5rem;
}

.section-input-row .clean-input {
  flex: 1;
}

.context-preview-box {
  background: var(--bg-surface-secondary);
  padding: 0.85rem 1rem;
  border-radius: 8px;
  font-size: 0.82rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  border: 1px solid var(--border-default);
}

.context-title {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-weight: 600;
  color: var(--text-primary);
}

.context-title .material-symbols-rounded {
  font-size: 1.05rem;
  color: var(--primary);
}

.context-p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.45;
}

.prompt-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.auto-prompt-btn {
  background: var(--primary-container, rgba(103, 80, 164, 0.15));
  color: var(--primary-on-container, var(--primary));
  font-weight: 600;
  gap: 0.35rem;
  font-size: 0.8rem;
  padding: 0.3rem 0.85rem;
  border-radius: 9999px;
  border: 1px solid rgba(103, 80, 164, 0.3);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  transition: all 0.15s;
}

.auto-prompt-btn:hover:not(:disabled) {
  background: var(--primary, #6750a4);
  color: #ffffff;
}

.prompt-area {
  width: 100%;
  box-sizing: border-box;
  font-family: inherit;
  font-size: 0.88rem;
  line-height: 1.5;
  resize: vertical;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-primary);
}

.prompt-hint-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-hint {
  font-size: 0.76rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.status-msg {
  font-size: 0.8rem;
  color: var(--primary);
  font-weight: 600;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-default);
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  background: var(--bg-surface-secondary);
}

.primary-gen-btn {
  background: var(--primary, #6750a4);
  color: #ffffff;
  font-weight: 600;
}
</style>
