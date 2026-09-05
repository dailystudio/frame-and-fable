<template>
  <div class="characters-gallery">
    <!-- Header -->
    <div class="gallery-header">
      <div>
        <h2 class="section-title">Character Visual References</h2>
        <p class="section-subtitle">
          Visual DNA, portrait prompts, and multi-angle reference photos ensuring character consistency across storybook scenes.
        </p>
      </div>

      <div class="header-badges">
        <span class="clean-badge">
          <span class="material-symbols-rounded">face</span>
          {{ characters.length }} Characters
        </span>
        <span class="clean-badge">
          <span class="material-symbols-rounded">photo_library</span>
          {{ totalRefImages }} Reference Photos
        </span>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="characters.length === 0" class="empty-state clean-card">
      <span class="material-symbols-rounded empty-icon">person_off</span>
      <h3>No Characters Extracted</h3>
      <p>Run <code>python storybook.py assets &lt;story.md&gt;</code> to extract characters into this workspace.</p>
    </div>

    <!-- Grid -->
    <div v-else class="character-grid">
      <div
        v-for="char in characters"
        :key="char.name"
        class="char-card clean-card"
      >
        <div class="char-top">
          <div class="char-title-group">
            <h3 class="char-name">{{ char.name }}</h3>
            <div class="char-chips">
              <span class="clean-badge role-badge">{{ char.role || 'Character' }}</span>
              <span v-if="char.source" class="clean-badge source-badge">{{ char.source }}</span>
            </div>
          </div>
          <span class="photo-count-pill">
            {{ char.images?.length || 0 }} photos
          </span>
        </div>

        <!-- Visual DNA -->
        <div v-if="char.visual_dna" class="dna-box">
          <div class="dna-head">
            <span class="material-symbols-rounded dna-icon">fingerprint</span>
            <span>Visual DNA</span>
          </div>
          <p class="dna-content">{{ char.visual_dna }}</p>
        </div>

        <!-- Portrait Prompt -->
        <div v-if="char.portrait_prompt" class="prompt-box">
          <div class="prompt-head">
            <div class="prompt-title">
              <span class="material-symbols-rounded prompt-icon">auto_awesome</span>
              <span>Portrait Prompt</span>
            </div>
            <button
              type="button"
              class="clean-btn clean-btn-sm"
              @click="copyPrompt(char.portrait_prompt, char.name)"
            >
              <span class="material-symbols-rounded">
                {{ copiedName === char.name ? 'check' : 'content_copy' }}
              </span>
              {{ copiedName === char.name ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <p class="prompt-text">{{ char.portrait_prompt }}</p>
        </div>

        <!-- Photos -->
        <div class="photos-section">
          <span class="photos-label">Reference Portraits</span>
          <div v-if="char.images && char.images.length" class="photos-grid">
            <div
              v-for="img in char.images"
              :key="img"
              class="photo-wrap"
              @click="previewImage(char, img)"
            >
              <img
                :src="getImageUrl(char.name, img)"
                :alt="`${char.name} - ${img}`"
                class="photo-img"
                loading="lazy"
              />
              <span class="photo-name">{{ img }}</span>
            </div>
          </div>
          <div v-else class="no-photos-box">
            <span class="material-symbols-rounded">image_not_supported</span>
            <span>No reference images yet (place in <code>char-ref/{{ char.name }}/</code>)</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
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

const copiedName = ref(null);

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

async function copyPrompt(prompt, name) {
  if (!prompt) return;
  try {
    await navigator.clipboard.writeText(prompt);
    copiedName.value = name;
    setTimeout(() => {
      copiedName.value = null;
    }, 2000);
  } catch (e) {
    console.error('Clipboard copy failed:', e);
  }
}
</script>

<style scoped>
.characters-gallery {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.gallery-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
}

.section-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
}

.section-subtitle {
  margin: 0.25rem 0 0 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.header-badges {
  display: flex;
  gap: 0.5rem;
}

.character-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 1.25rem;
}

.char-card {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.char-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.char-name {
  margin: 0 0 0.35rem 0;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-primary);
}

.char-chips {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.role-badge {
  background: var(--bg-surface-secondary);
  color: var(--text-primary);
  font-weight: 600;
}

.photo-count-pill {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-full);
}

.dna-box {
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-left: 3px solid var(--accent-primary);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.dna-head {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--accent-primary);
  margin-bottom: 0.3rem;
}

.dna-icon {
  font-size: 15px;
}

.dna-content {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--text-primary);
}

.prompt-box {
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.prompt-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
}

.prompt-title {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.prompt-icon {
  font-size: 15px;
}

.prompt-text {
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.45;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.photos-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.photos-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted);
}

.photos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 0.5rem;
}

.photo-wrap {
  position: relative;
  aspect-ratio: 1;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-default);
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}

.photo-wrap:hover {
  border-color: var(--accent-primary);
  transform: scale(1.03);
}

.photo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.photo-name {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 0.65rem;
  padding: 0.15rem 0.3rem;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.no-photos-box {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.75rem;
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-default);
  color: var(--text-muted);
  font-size: 0.8rem;
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
