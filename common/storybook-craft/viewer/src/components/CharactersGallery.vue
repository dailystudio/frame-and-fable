<template>
  <div class="characters-gallery">
    <div class="section-header">
      <div>
        <h2 class="section-title">Character Visual References</h2>
        <p class="section-subtitle">
          Visual DNA, portrait prompts, and multi-angle reference portraits for consistent multi-shot generation.
        </p>
      </div>
      <div class="header-badges">
        <span class="md-badge badge-primary">
          <span class="material-symbols-rounded" style="font-size: 14px;">face</span>
          {{ characters.length }} Characters
        </span>
        <span class="md-badge">
          <span class="material-symbols-rounded" style="font-size: 14px;">photo_library</span>
          {{ totalRefImages }} Reference Images
        </span>
      </div>
    </div>

    <div v-if="characters.length === 0" class="empty-state">
      <span class="material-symbols-rounded empty-icon">person_off</span>
      <p>No character references found in this workspace.</p>
      <small>Run <code>python storybook.py assets &lt;file.md&gt;</code> to extract characters.</small>
    </div>

    <div v-else class="character-grid">
      <div
        v-for="char in characters"
        :key="char.name"
        class="char-card md-card-elevated"
      >
        <div class="char-header">
          <div class="char-title-wrap">
            <h3 class="char-name">{{ char.name }}</h3>
            <div class="char-chips">
              <span class="md-badge badge-role">{{ char.role || 'Character' }}</span>
              <span v-if="char.source" class="md-badge badge-source">{{ char.source }}</span>
            </div>
          </div>
          <span class="char-ref-count">
            {{ char.images?.length || 0 }} images
          </span>
        </div>

        <!-- Visual DNA Section -->
        <div v-if="char.visual_dna" class="char-dna-block">
          <div class="dna-label">
            <span class="material-symbols-rounded icon-dna">fingerprint</span>
            Visual DNA
          </div>
          <p class="dna-text">{{ char.visual_dna }}</p>
        </div>

        <!-- Portrait Prompt Section -->
        <div v-if="char.portrait_prompt" class="char-prompt-block">
          <div class="prompt-head">
            <span class="prompt-title">
              <span class="material-symbols-rounded icon-prompt">auto_awesome</span>
              Portrait Prompt
            </span>
            <button
              type="button"
              class="md-btn md-btn-tonal copy-btn"
              @click="copyText(char.portrait_prompt, char.name)"
            >
              <span class="material-symbols-rounded">
                {{ copiedChar === char.name ? 'check' : 'content_copy' }}
              </span>
              {{ copiedChar === char.name ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <p class="prompt-content">{{ char.portrait_prompt }}</p>
        </div>

        <!-- Reference Images Gallery -->
        <div class="char-images-section">
          <h4 class="images-heading">Reference Photos</h4>
          <div v-if="char.images && char.images.length > 0" class="images-strip">
            <div
              v-for="img in char.images"
              :key="img"
              class="image-thumb-wrap"
              @click="previewImage(char, img)"
            >
              <img
                :src="getImageUrl(char.name, img)"
                :alt="`${char.name} - ${img}`"
                class="image-thumb"
                loading="lazy"
              />
              <span class="image-label">{{ img }}</span>
            </div>
          </div>
          <div v-else class="no-images-placeholder">
            <span class="material-symbols-rounded">image_not_supported</span>
            <span>No reference images yet (add ref_001.png to char-ref/{{ char.name }}/)</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { getCharImageUrl } from '../services/api';

const props = defineProps({
  stem: {
    type: String,
    required: true
  },
  characters: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['preview']);

const copiedChar = ref(null);

const totalRefImages = computed(() => {
  return props.characters.reduce((acc, c) => acc + (c.images?.length || 0), 0);
});

function getImageUrl(charName, imgName) {
  return getCharImageUrl(props.stem, charName, imgName);
}

function previewImage(char, img) {
  emit('preview', {
    src: getImageUrl(char.name, img),
    title: `${char.name} (${img})`,
    type: 'image',
    prompt: char.portrait_prompt || char.visual_dna || '',
    details: {
      Character: char.name,
      Role: char.role || 'Character',
      File: img
    }
  });
}

async function copyText(text, charName) {
  try {
    await navigator.clipboard.writeText(text);
    copiedChar.value = charName;
    setTimeout(() => {
      copiedChar.value = null;
    }, 2000);
  } catch (err) {
    console.error('Failed to copy:', err);
  }
}
</script>

<style scoped>
.characters-gallery {
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

.character-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 1.5rem;
}

.char-card {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.char-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--elevation-3);
}

.char-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.char-name {
  margin: 0 0 0.4rem 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--md-sys-color-primary);
}

.char-chips {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.badge-role {
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  font-weight: 600;
}

.badge-source {
  background: var(--md-sys-color-surface-variant);
  color: var(--md-sys-color-on-surface-variant);
}

.char-ref-count {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--md-sys-color-on-surface-variant);
  background: var(--md-sys-color-surface-container-high);
  padding: 0.25rem 0.6rem;
  border-radius: var(--shape-corner-full);
}

.char-dna-block {
  background: var(--md-sys-color-surface-container);
  padding: 0.85rem 1rem;
  border-radius: var(--shape-corner-medium);
  border-left: 3px solid var(--md-sys-color-primary);
}

.dna-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
  color: var(--md-sys-color-primary);
  margin-bottom: 0.35rem;
}

.icon-dna {
  font-size: 16px;
}

.dna-text {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--md-sys-color-on-surface);
}

.char-prompt-block {
  background: var(--md-sys-color-surface-container-high);
  padding: 0.85rem 1rem;
  border-radius: var(--shape-corner-medium);
}

.prompt-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}

.prompt-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
  color: var(--md-sys-color-secondary);
}

.icon-prompt {
  font-size: 16px;
}

.copy-btn {
  padding: 0.2rem 0.5rem;
  font-size: 0.75rem;
  height: 26px;
}

.prompt-content {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.45;
  color: var(--md-sys-color-on-surface);
  white-space: pre-wrap;
  font-family: var(--font-sans);
}

.char-images-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.images-heading {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--md-sys-color-on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.images-strip {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 0.75rem;
}

.image-thumb-wrap {
  position: relative;
  border-radius: var(--shape-corner-medium);
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
  aspect-ratio: 1;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.image-thumb-wrap:hover {
  transform: scale(1.04);
  box-shadow: var(--elevation-2);
}

.image-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-label {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.65);
  color: #ffffff;
  font-size: 0.7rem;
  padding: 0.2rem 0.35rem;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  backdrop-filter: blur(4px);
}

.no-images-placeholder {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  border-radius: var(--shape-corner-medium);
  border: 1px dashed var(--md-sys-color-outline-variant);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 0.85rem;
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
