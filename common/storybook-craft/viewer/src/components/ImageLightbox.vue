<template>
  <dialog
    ref="dialogRef"
    class="lightbox-dialog"
    closedby="any"
    aria-label="Media Preview Lightbox"
    @close="onDialogClose"
  >
    <div class="lightbox-sheet clean-card" @click.stop>
      <!-- Header -->
      <header class="sheet-head">
        <div class="sheet-title-group">
          <span class="material-symbols-rounded head-icon">
            {{ mediaType === 'video' ? 'videocam' : 'image' }}
          </span>
          <span class="sheet-title">{{ mediaTitle || 'Media Preview' }}</span>
        </div>
        <button
          type="button"
          class="clean-icon-btn close-btn"
          aria-label="Close dialog"
          @click="close"
        >
          <span class="material-symbols-rounded">close</span>
        </button>
      </header>

      <!-- Media Content Area -->
      <div class="sheet-body">
        <div class="media-viewport">
          <video
            v-if="mediaType === 'video'"
            :src="mediaSrc"
            controls
            autoplay
            class="media-elem"
          ></video>
          <img
            v-else
            :src="mediaSrc"
            :alt="mediaTitle"
            class="media-elem"
          />
        </div>

        <!-- Details & Prompt -->
        <div v-if="mediaPrompt || mediaDetails" class="details-section">
          <div v-if="mediaDetails" class="meta-pills">
            <span v-for="(val, key) in mediaDetails" :key="key" class="clean-badge">
              <strong>{{ key }}:</strong> {{ val }}
            </span>
          </div>

          <div v-if="mediaPrompt" class="lightbox-prompt-box">
            <div class="prompt-header">
              <span class="prompt-label">Generation / Scene Prompt</span>
              <button
                type="button"
                class="clean-btn clean-btn-sm"
                @click="copyPrompt"
              >
                <span class="material-symbols-rounded">
                  {{ copied ? 'check' : 'content_copy' }}
                </span>
                {{ copied ? 'Copied' : 'Copy' }}
              </button>
            </div>
            <p class="prompt-text">{{ mediaPrompt }}</p>
          </div>
        </div>
      </div>
    </div>
  </dialog>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';

const dialogRef = ref(null);
const isOpen = ref(false);
const mediaSrc = ref('');
const mediaTitle = ref('');
const mediaType = ref('image');
const mediaPrompt = ref('');
const mediaDetails = ref(null);
const copied = ref(false);

function open({ src, title = '', type = 'image', prompt = '', details = null }) {
  mediaSrc.value = src;
  mediaTitle.value = title;
  mediaType.value = type;
  mediaPrompt.value = prompt;
  mediaDetails.value = details;
  copied.value = false;

  if (dialogRef.value && !dialogRef.value.open) {
    dialogRef.value.showModal();
    isOpen.value = true;
  }
}

function close() {
  if (dialogRef.value && dialogRef.value.open) {
    dialogRef.value.close();
  }
  isOpen.value = false;
}

function onDialogClose() {
  isOpen.value = false;
}

async function copyPrompt() {
  if (!mediaPrompt.value) return;
  try {
    await navigator.clipboard.writeText(mediaPrompt.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch (e) {
    console.error('Clipboard copy failed:', e);
  }
}

// Fallback for browsers without native <dialog closedby> support
function handleBackdropClick(event) {
  const dialog = dialogRef.value;
  if (!dialog || !dialog.open) return;
  if (event.target !== dialog) return;

  const rect = dialog.getBoundingClientRect();
  const isDialogContent = (
    rect.top <= event.clientY &&
    event.clientY <= rect.top + rect.height &&
    rect.left <= event.clientX &&
    event.clientX <= rect.left + rect.width
  );

  if (!isDialogContent) {
    close();
  }
}

onMounted(() => {
  const dialog = dialogRef.value;
  if (dialog && !('closedBy' in HTMLDialogElement.prototype)) {
    dialog.addEventListener('click', handleBackdropClick);
  }
});

onBeforeUnmount(() => {
  const dialog = dialogRef.value;
  if (dialog && !('closedBy' in HTMLDialogElement.prototype)) {
    dialog.removeEventListener('click', handleBackdropClick);
  }
});

defineExpose({
  open,
  close
});
</script>

<style scoped>
.lightbox-dialog {
  border: none;
  background: transparent;
  padding: 0;
  margin: auto;
  max-width: 92vw;
  max-height: 92vh;
  box-shadow: none;
  overflow: visible;
}

.lightbox-dialog::backdrop {
  background-color: rgba(9, 9, 11, 0.7);
  backdrop-filter: blur(8px);
}

.lightbox-sheet {
  display: flex;
  flex-direction: column;
  max-width: 960px;
  width: 92vw;
  max-height: 88vh;
  overflow: hidden;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}

.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface);
}

.sheet-title-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.head-icon {
  font-size: 20px;
  color: var(--accent-primary);
}

.sheet-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.sheet-body {
  padding: 1rem 1.25rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.media-viewport {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  border-radius: var(--radius-md);
  overflow: hidden;
  max-height: 52vh;
}

.media-elem {
  max-width: 100%;
  max-height: 52vh;
  object-fit: contain;
  display: block;
}

.details-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.meta-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.lightbox-prompt-box {
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
}

.prompt-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--text-muted);
}

.prompt-text {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
}
</style>
