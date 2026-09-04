<template>
  <dialog
    ref="dialogRef"
    class="lightbox-dialog"
    closedby="any"
    aria-label="Media Preview Lightbox"
    @close="onDialogClose"
  >
    <div class="lightbox-card" @click.stop>
      <header class="lightbox-header">
        <div class="lightbox-title-wrap">
          <span class="material-symbols-rounded lightbox-type-icon">
            {{ mediaType === 'video' ? 'videocam' : 'image' }}
          </span>
          <h3 class="lightbox-title">{{ mediaTitle || 'Media Preview' }}</h3>
        </div>
        <button
          type="button"
          class="md-icon-btn"
          aria-label="Close dialog"
          @click="close"
        >
          <span class="material-symbols-rounded">close</span>
        </button>
      </header>

      <div class="lightbox-body">
        <div class="lightbox-media-container">
          <video
            v-if="mediaType === 'video'"
            :src="mediaSrc"
            controls
            autoplay
            class="lightbox-media"
          ></video>
          <img
            v-else
            :src="mediaSrc"
            :alt="mediaTitle"
            class="lightbox-media"
          />
        </div>

        <div v-if="mediaPrompt || mediaDetails" class="lightbox-details">
          <div v-if="mediaDetails" class="lightbox-meta-chips">
            <span v-for="(val, key) in mediaDetails" :key="key" class="md-badge">
              <strong>{{ key }}:</strong> {{ val }}
            </span>
          </div>

          <div v-if="mediaPrompt" class="lightbox-prompt-box">
            <div class="prompt-header">
              <span class="prompt-label">Generation / Visual Prompt</span>
              <button
                type="button"
                class="md-btn md-btn-tonal copy-btn"
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
const mediaType = ref('image'); // 'image' | 'video'
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
  max-width: 90vw;
  max-height: 90vh;
  box-shadow: none;
  overflow: visible;
}

.lightbox-dialog::backdrop {
  background-color: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(10px);
}

.lightbox-card {
  display: flex;
  flex-direction: column;
  background: var(--md-sys-color-surface-container);
  border-radius: var(--shape-corner-extra-large);
  border: 1px solid var(--md-sys-color-outline-variant);
  box-shadow: var(--elevation-4);
  max-width: 1000px;
  width: 90vw;
  max-height: 88vh;
  overflow: hidden;
}

.lightbox-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-high);
}

.lightbox-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.lightbox-type-icon {
  color: var(--md-sys-color-primary);
  font-size: 24px;
}

.lightbox-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.lightbox-body {
  padding: 1.25rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  align-items: center;
}

.lightbox-media-container {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--md-sys-color-surface-container-lowest);
  border-radius: var(--shape-corner-large);
  border: 1px solid var(--md-sys-color-outline-variant);
  width: 100%;
  max-height: 55vh;
  overflow: hidden;
}

.lightbox-media {
  max-width: 100%;
  max-height: 55vh;
  object-fit: contain;
  display: block;
}

.lightbox-details {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.lightbox-meta-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.lightbox-prompt-box {
  background: var(--md-sys-color-surface-container-highest);
  border-radius: var(--shape-corner-medium);
  padding: 0.85rem 1rem;
  border: 1px solid var(--md-sys-color-outline-variant);
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}

.prompt-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
  color: var(--md-sys-color-primary);
}

.copy-btn {
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
  height: 28px;
}

.prompt-text {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--md-sys-color-on-surface);
  white-space: pre-wrap;
  font-family: var(--font-sans);
}
</style>
