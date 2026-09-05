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

    <!-- Character Cards Grid -->
    <div v-else class="character-grid">
      <div
        v-for="char in characters"
        :key="char.name"
        class="char-card clean-card"
      >
        <!-- 1. 16:9 Image Banner at top -->
        <div class="char-banner-wrap" @click="previewBanner(char)">
          <img
            v-if="getFirstImage(char)"
            :src="getFirstImageUrl(char)"
            :alt="char.name"
            class="char-banner-img"
            loading="lazy"
          />
          <div v-else class="char-banner-placeholder">
            <span class="material-symbols-rounded placeholder-symbol">face</span>
          </div>

          <!-- Banner Foreground (Aligned Left Bottom Corner) -->
          <div class="char-banner-overlay">
            <div class="char-banner-foreground">
              <h3 class="char-banner-name">{{ char.name }}</h3>
              <div class="char-banner-meta">
                <span class="banner-pill role-pill">{{ char.role || 'Character' }}</span>
                <span v-if="char.images?.length" class="banner-pill count-pill">
                  <span class="material-symbols-rounded">photo_camera</span>
                  {{ char.images.length }} {{ char.images.length === 1 ? 'photo' : 'photos' }}
                </span>
              </div>
            </div>
          </div>

          <!-- Hover Hint -->
          <div class="banner-zoom-hint">
            <span class="material-symbols-rounded">fullscreen</span>
          </div>
        </div>

        <!-- Card Content Body -->
        <div class="char-card-body">
          <!-- 2. Dual Equal-Height Aligned Paragraph Boxes -->
          <div class="char-dual-boxes">
            <!-- Box 1: Visual DNA -->
            <div class="info-box dna-box">
              <div class="info-box-head">
                <div class="info-box-title">
                  <span class="material-symbols-rounded">fingerprint</span>
                  <span>Visual DNA</span>
                </div>
              </div>

              <div class="info-box-body">
                <p
                  class="info-text"
                  :class="{ 'is-clamped': !isExpanded(char.name, 'dna') && needsClamping(char.visual_dna) }"
                >
                  {{ char.visual_dna || 'No visual DNA recorded yet.' }}
                </p>

                <button
                  v-if="needsClamping(char.visual_dna)"
                  type="button"
                  class="expand-btn"
                  @click="toggleExpand(char.name, 'dna')"
                >
                  <span>{{ isExpanded(char.name, 'dna') ? 'Show Less' : 'Show More' }}</span>
                  <span class="material-symbols-rounded">
                    {{ isExpanded(char.name, 'dna') ? 'expand_less' : 'expand_more' }}
                  </span>
                </button>
              </div>
            </div>

            <!-- Box 2: Portrait Prompt -->
            <div class="info-box prompt-box">
              <div class="info-box-head">
                <div class="info-box-title">
                  <span class="material-symbols-rounded">auto_awesome</span>
                  <span>Portrait Prompt</span>
                </div>
                <button
                  type="button"
                  class="clean-btn clean-btn-sm copy-btn"
                  title="Copy portrait prompt"
                  @click="copyPrompt(char.portrait_prompt, char.name)"
                >
                  <span class="material-symbols-rounded">
                    {{ copiedName === char.name ? 'check' : 'content_copy' }}
                  </span>
                  {{ copiedName === char.name ? 'Copied' : 'Copy' }}
                </button>
              </div>

              <div class="info-box-body">
                <p
                  class="info-text"
                  :class="{ 'is-clamped': !isExpanded(char.name, 'prompt') && needsClamping(char.portrait_prompt) }"
                >
                  {{ char.portrait_prompt || 'No portrait prompt recorded yet.' }}
                </p>

                <button
                  v-if="needsClamping(char.portrait_prompt)"
                  type="button"
                  class="expand-btn"
                  @click="toggleExpand(char.name, 'prompt')"
                >
                  <span>{{ isExpanded(char.name, 'prompt') ? 'Show Less' : 'Show More' }}</span>
                  <span class="material-symbols-rounded">
                    {{ isExpanded(char.name, 'prompt') ? 'expand_less' : 'expand_more' }}
                  </span>
                </button>
              </div>
            </div>
          </div>

          <!-- 3. Reference Portraits Gallery -->
          <div class="photos-section">
            <span class="photos-label">All Reference Photos ({{ char.images?.length || 0 }})</span>
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
const expandedMap = ref({});

const totalRefImages = computed(() => {
  return props.characters.reduce((acc, c) => acc + (c.images?.length || 0), 0);
});

function getFirstImage(char) {
  return char.images && char.images.length > 0 ? char.images[0] : null;
}

function getFirstImageUrl(char) {
  const first = getFirstImage(char);
  return first ? getImageUrl(char.name, first) : '';
}

function getImageUrl(charName, imgName) {
  return getCharImageUrl(props.stem, charName, imgName);
}

function isExpanded(charName, field) {
  return !!expandedMap.value[`${charName}_${field}`];
}

function toggleExpand(charName, field) {
  const key = `${charName}_${field}`;
  expandedMap.value[key] = !expandedMap.value[key];
}

function needsClamping(text) {
  if (!text) return false;
  // If text is longer than ~130 characters, it typically exceeds 3-4 lines
  return text.length > 130;
}

function previewBanner(char) {
  const first = getFirstImage(char);
  if (first) {
    previewImage(char, first);
  }
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

/* Character Cards Grid */
.character-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(540px, 1fr));
  gap: 1.5rem;
}

@media (max-width: 640px) {
  .character-grid {
    grid-template-columns: 1fr;
  }
}

.char-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: var(--radius-lg);
}

/* 1. 16:9 Image Banner */
.char-banner-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background-color: #09090b;
  overflow: hidden;
  cursor: pointer;
}

.char-banner-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center top;
  display: block;
  transition: transform 0.3s ease;
}

.char-banner-wrap:hover .char-banner-img {
  transform: scale(1.02);
}

.char-banner-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-surface-secondary);
}

.placeholder-symbol {
  font-size: 64px;
  color: var(--text-muted);
}

.char-banner-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to top,
    rgba(0, 0, 0, 0.88) 0%,
    rgba(0, 0, 0, 0.55) 40%,
    rgba(0, 0, 0, 0.1) 75%,
    transparent 100%
  );
  display: flex;
  align-items: flex-end;
  padding: 1.25rem 1.4rem;
  pointer-events: none;
}

.char-banner-foreground {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.char-banner-name {
  margin: 0;
  font-size: 1.6rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
  line-height: 1.2;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.75);
}

.char-banner-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.banner-pill {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.18rem 0.6rem;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  backdrop-filter: blur(8px);
}

.banner-pill.role-pill {
  background: rgba(255, 255, 255, 0.22);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.35);
}

.banner-pill.count-pill {
  background: rgba(0, 0, 0, 0.5);
  color: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.banner-pill .material-symbols-rounded {
  font-size: 13px;
}

.banner-zoom-hint {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(6px);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.75;
  transition: opacity 0.2s, background-color 0.2s;
}

.char-banner-wrap:hover .banner-zoom-hint {
  opacity: 1;
  background: rgba(0, 0, 0, 0.8);
}

.banner-zoom-hint .material-symbols-rounded {
  font-size: 18px;
}

/* Card Body */
.char-card-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

/* 2. Dual Equal-Height Aligned Boxes */
.char-dual-boxes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: stretch;
}

@media (max-width: 680px) {
  .char-dual-boxes {
    grid-template-columns: 1fr;
  }
}

.info-box {
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 0.9rem 1rem;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
}

.info-box.dna-box {
  border-left: 3px solid var(--accent-primary);
}

.info-box.prompt-box {
  border-left: 3px solid #8b5cf6;
}

.info-box-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  flex-shrink: 0;
  min-height: 26px;
}

.info-box-title {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}

.info-box.dna-box .info-box-title .material-symbols-rounded {
  color: var(--accent-primary);
  font-size: 16px;
}

.info-box.prompt-box .info-box-title .material-symbols-rounded {
  color: #8b5cf6;
  font-size: 16px;
}

.copy-btn {
  height: 24px;
  padding: 0.15rem 0.5rem;
  font-size: 0.75rem;
}

.copy-btn .material-symbols-rounded {
  font-size: 13px;
}

.info-box-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.info-text {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.info-text.is-clamped {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.expand-btn {
  align-self: flex-start;
  margin-top: 0.5rem;
  background: none;
  border: none;
  padding: 0;
  font-family: var(--font-sans);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--accent-primary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  transition: color 0.15s;
}

.expand-btn:hover {
  color: var(--accent-primary-hover);
  text-decoration: underline;
}

.expand-btn .material-symbols-rounded {
  font-size: 16px;
}

/* 3. Reference Portraits */
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
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 0.6rem;
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
  background: rgba(0, 0, 0, 0.72);
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
