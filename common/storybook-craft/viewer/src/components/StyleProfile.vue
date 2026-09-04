<template>
  <div class="style-profile">
    <div class="section-header">
      <div>
        <h2 class="section-title">Art & Visual Style Profile</h2>
        <p class="section-subtitle">
          Aesthetic guidelines, prompt modifiers, and visual moodboard references maintaining consistent rendering across all scenes.
        </p>
      </div>
      <div class="header-badges">
        <span class="md-badge badge-primary">
          <span class="material-symbols-rounded" style="font-size: 14px;">palette</span>
          {{ styleData.style_name || 'Custom Style' }}
        </span>
        <span class="md-badge">
          <span class="material-symbols-rounded" style="font-size: 14px;">image</span>
          {{ styleImages.length }} Style Images
        </span>
      </div>
    </div>

    <div class="style-content-grid">
      <!-- Style Overview Card -->
      <div class="style-card md-card-elevated">
        <div class="card-head">
          <span class="material-symbols-rounded head-icon">brush</span>
          <div>
            <h3 class="style-name">{{ styleData.style_name || 'Standard Storybook Style' }}</h3>
            <span class="md-badge badge-source">{{ styleData.source || 'workspace style' }}</span>
          </div>
        </div>

        <!-- Style Prompt Section -->
        <div class="prompt-section">
          <div class="prompt-bar">
            <span class="prompt-title">
              <span class="material-symbols-rounded">magic_button</span>
              Art Direction & Aesthetic Prompt
            </span>
            <button
              v-if="styleData.style_prompt"
              type="button"
              class="md-btn md-btn-tonal copy-btn"
              @click="copyText(styleData.style_prompt, 'style')"
            >
              <span class="material-symbols-rounded">
                {{ copiedKey === 'style' ? 'check' : 'content_copy' }}
              </span>
              {{ copiedKey === 'style' ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <div class="prompt-container">
            <p v-if="styleData.style_prompt" class="prompt-text">
              {{ styleData.style_prompt }}
            </p>
            <p v-else class="prompt-empty">
              No style prompt specified yet.
            </p>
          </div>
        </div>

        <!-- Reference Prompt Section -->
        <div v-if="styleData.reference_prompt" class="prompt-section">
          <div class="prompt-bar">
            <span class="prompt-title">
              <span class="material-symbols-rounded">landscape</span>
              Environment & Reference Generator Prompt
            </span>
            <button
              type="button"
              class="md-btn md-btn-tonal copy-btn"
              @click="copyText(styleData.reference_prompt, 'ref')"
            >
              <span class="material-symbols-rounded">
                {{ copiedKey === 'ref' ? 'check' : 'content_copy' }}
              </span>
              {{ copiedKey === 'ref' ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <div class="prompt-container">
            <p class="prompt-text">
              {{ styleData.reference_prompt }}
            </p>
          </div>
        </div>
      </div>

      <!-- Style Reference Images Card -->
      <div class="style-images-card md-card-elevated">
        <div class="card-head">
          <span class="material-symbols-rounded head-icon">collections</span>
          <div>
            <h3 class="card-title">Style Reference Gallery</h3>
            <p class="card-desc">Visual moodboard for the image & video generators</p>
          </div>
        </div>

        <div v-if="styleImages.length > 0" class="style-images-grid">
          <div
            v-for="img in styleImages"
            :key="img"
            class="style-image-wrap"
            @click="previewImage(img)"
          >
            <img
              :src="getImageUrl(img)"
              :alt="`Style reference ${img}`"
              class="style-img"
              loading="lazy"
            />
            <div class="img-overlay">
              <span class="img-name">{{ img }}</span>
              <span class="material-symbols-rounded zoom-icon">zoom_in</span>
            </div>
          </div>
        </div>

        <div v-else class="no-images-placeholder">
          <span class="material-symbols-rounded">image_not_supported</span>
          <span>No style references yet (drop reference images into <code>outputs/{{ stem }}/style-ref/</code>)</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { getStyleImageUrl } from '../services/api';

const props = defineProps({
  stem: {
    type: String,
    required: true
  },
  styleData: {
    type: Object,
    default: () => ({})
  }
});

const emit = defineEmits(['preview']);

const copiedKey = ref(null);

const styleImages = computed(() => {
  return props.styleData.images || [];
});

function getImageUrl(imgName) {
  return getStyleImageUrl(props.stem, imgName);
}

function previewImage(img) {
  emit('preview', {
    src: getImageUrl(img),
    title: `Style Reference - ${img}`,
    type: 'image',
    prompt: props.styleData.style_prompt || props.styleData.reference_prompt || '',
    details: {
      Style: props.styleData.style_name || 'Art Style',
      File: img
    }
  });
}

async function copyText(text, key) {
  try {
    await navigator.clipboard.writeText(text);
    copiedKey.value = key;
    setTimeout(() => {
      copiedKey.value = null;
    }, 2000);
  } catch (err) {
    console.error('Failed to copy:', err);
  }
}
</script>

<style scoped>
.style-profile {
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

.header-badges {
  display: flex;
  gap: 0.5rem;
}

.badge-primary {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.style-content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 900px) {
  .style-content-grid {
    grid-template-columns: 1fr;
  }
}

.style-card,
.style-images-card {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.head-icon {
  font-size: 28px;
  color: var(--md-sys-color-primary);
  background: var(--md-sys-color-primary-container);
  padding: 0.5rem;
  border-radius: var(--shape-corner-medium);
}

.style-name {
  margin: 0 0 0.25rem 0;
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
}

.card-title {
  margin: 0 0 0.2rem 0;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
}

.card-desc {
  margin: 0;
  font-size: 0.85rem;
  color: var(--md-sys-color-on-surface-variant);
}

.badge-source {
  background: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-on-surface-variant);
}

.prompt-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.prompt-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.prompt-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--md-sys-color-primary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.prompt-title .material-symbols-rounded {
  font-size: 18px;
}

.copy-btn {
  padding: 0.2rem 0.6rem;
  font-size: 0.75rem;
  height: 26px;
}

.prompt-container {
  background: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--shape-corner-medium);
  padding: 1rem;
}

.prompt-text {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--md-sys-color-on-surface);
  white-space: pre-wrap;
}

.prompt-empty {
  margin: 0;
  font-size: 0.85rem;
  font-style: italic;
  color: var(--md-sys-color-on-surface-variant);
}

.style-images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 1rem;
}

.style-image-wrap {
  position: relative;
  aspect-ratio: 4/3;
  border-radius: var(--shape-corner-medium);
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.style-image-wrap:hover {
  transform: scale(1.03);
  box-shadow: var(--elevation-2);
}

.style-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.img-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 60%);
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 0.5rem;
  color: #fff;
  opacity: 0.85;
  transition: opacity 0.2s;
}

.style-image-wrap:hover .img-overlay {
  opacity: 1;
}

.img-name {
  font-size: 0.75rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80%;
}

.zoom-icon {
  font-size: 20px;
}

.no-images-placeholder {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 2rem 1rem;
  border-radius: var(--shape-corner-medium);
  border: 1px dashed var(--md-sys-color-outline-variant);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 0.85rem;
  justify-content: center;
}
</style>
