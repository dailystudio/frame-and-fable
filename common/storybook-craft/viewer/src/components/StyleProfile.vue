<template>
  <div class="style-profile">
    <div class="profile-header">
      <div>
        <h2 class="section-title">Art & Visual Style Profile</h2>
        <p class="section-subtitle">
          Art direction guidelines, aesthetic prompt modifiers, and reference moodboard maintaining visual consistency across scenes.
        </p>
      </div>

      <div class="header-badges">
        <span class="clean-badge">
          <span class="material-symbols-rounded">palette</span>
          {{ styleData.style_name || 'Art Style' }}
        </span>
        <span class="clean-badge">
          <span class="material-symbols-rounded">image</span>
          {{ styleImages.length }} Style Photos
        </span>
      </div>
    </div>

    <div class="style-grid">
      <!-- Style Details Card -->
      <div class="style-card clean-card">
        <div class="card-head">
          <div class="style-title-group">
            <h3 class="style-name">{{ styleData.style_name || 'Standard Storybook Style' }}</h3>
            <span class="clean-badge">{{ styleData.source || 'workspace style' }}</span>
          </div>
        </div>

        <!-- Style Prompt -->
        <div class="prompt-box">
          <div class="prompt-head">
            <span class="prompt-title">
              <span class="material-symbols-rounded">auto_awesome</span>
              Art Direction & Aesthetic Prompt
            </span>
            <button
              v-if="styleData.style_prompt"
              type="button"
              class="clean-btn clean-btn-sm"
              @click="copyText(styleData.style_prompt, 'style')"
            >
              <span class="material-symbols-rounded">
                {{ copiedKey === 'style' ? 'check' : 'content_copy' }}
              </span>
              {{ copiedKey === 'style' ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <p class="prompt-text">{{ styleData.style_prompt || 'No style prompt specified.' }}</p>
        </div>

        <!-- Reference Environment Prompt -->
        <div v-if="styleData.reference_prompt" class="prompt-box">
          <div class="prompt-head">
            <span class="prompt-title">
              <span class="material-symbols-rounded">landscape</span>
              Environment & Reference Generator Prompt
            </span>
            <button
              type="button"
              class="clean-btn clean-btn-sm"
              @click="copyText(styleData.reference_prompt, 'ref')"
            >
              <span class="material-symbols-rounded">
                {{ copiedKey === 'ref' ? 'check' : 'content_copy' }}
              </span>
              {{ copiedKey === 'ref' ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <p class="prompt-text">{{ styleData.reference_prompt }}</p>
        </div>
      </div>

      <!-- Style Reference Images Card -->
      <div class="style-images-card clean-card">
        <div class="card-head">
          <div>
            <h3 class="card-title">Reference Moodboard</h3>
            <span class="card-sub">Visual references used by image & video generation models</span>
          </div>
          <label class="clean-btn clean-btn-xs upload-photo-btn">
            <span class="material-symbols-rounded">cloud_upload</span>
            <span>Upload Style Image</span>
            <input
              type="file"
              accept="image/*"
              class="sr-only"
              @change="onUploadStyleImage"
            />
          </label>
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
            <button
              type="button"
              class="style-trash-btn"
              title="Delete style reference image"
              @click.stop="onDeleteStyleImage(img)"
            >
              <span class="material-symbols-rounded">delete</span>
            </button>
            <div class="img-overlay">
              <span class="img-name">{{ img }}</span>
              <span class="material-symbols-rounded zoom-icon">fullscreen</span>
            </div>
          </div>
        </div>

        <div v-else class="no-images-box">
          <span class="material-symbols-rounded">image_not_supported</span>
          <span>No style references yet (drop image into <code>outputs/{{ stem }}/style-ref/</code>)</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { getStyleImageUrl, uploadReferenceImage, deleteReferenceImage } from '../services/api';

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

const emit = defineEmits(['preview', 'refresh']);

const copiedKey = ref(null);

async function onUploadStyleImage(event) {
  const file = event.target.files?.[0];
  if (!file || !props.stem) return;

  try {
    const reader = new FileReader();
    reader.onload = async (e) => {
      const dataUrl = e.target.result;
      await uploadReferenceImage(props.stem, {
        type: 'style',
        filename: file.name,
        imageBase64: dataUrl
      });
      emit('refresh');
    };
    reader.readAsDataURL(file);
  } catch (err) {
    console.error('Failed to upload style image:', err);
    alert(`Failed to upload style image: ${err.message}`);
  }
}

async function onDeleteStyleImage(imgName) {
  if (!confirm(`Are you sure you want to delete style reference "${imgName}"?`)) return;
  try {
    await deleteReferenceImage(props.stem, {
      type: 'style',
      filename: imgName
    });
    emit('refresh');
  } catch (err) {
    console.error('Failed to delete style image:', err);
    alert(`Failed to delete style image: ${err.message}`);
  }
}

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
  gap: 1.25rem;
}

.profile-header {
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

.style-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}

@media (max-width: 860px) {
  .style-grid {
    grid-template-columns: 1fr;
  }
}

.style-card,
.style-images-card {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.upload-photo-btn {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  padding: 0.25rem 0.6rem;
  border-radius: 4px;
}

.upload-photo-btn .material-symbols-rounded {
  font-size: 16px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.style-title-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.style-name,
.card-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.card-sub {
  font-size: 0.8rem;
  color: var(--text-secondary);
  display: block;
  margin-top: 0.15rem;
}

.prompt-box {
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.prompt-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.prompt-title .material-symbols-rounded {
  font-size: 15px;
}

.prompt-text {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.style-images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.75rem;
}

.style-image-wrap {
  position: relative;
  aspect-ratio: 4/3;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-default);
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}

.style-image-wrap:hover {
  border-color: var(--accent-primary);
  transform: scale(1.02);
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
  background: linear-gradient(to top, rgba(0, 0, 0, 0.7) 0%, transparent 60%);
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 0.4rem;
  color: #fff;
  opacity: 0.85;
}

.img-name {
  font-size: 0.7rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80%;
}

.zoom-icon {
  font-size: 18px;
}

.style-trash-btn {
  position: absolute;
  top: 0.35rem;
  right: 0.35rem;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-full);
  border: 1px solid rgba(239, 68, 68, 0.4);
  background: rgba(254, 242, 242, 0.95);
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: all 0.15s ease;
  z-index: 2;
  padding: 0;
}

.style-image-wrap:hover .style-trash-btn {
  opacity: 1;
}

.style-trash-btn:hover {
  background: #ef4444;
  color: #ffffff;
  transform: scale(1.1);
}

.style-trash-btn .material-symbols-rounded {
  font-size: 15px;
}

.no-images-box {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 1.5rem;
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-default);
  color: var(--text-muted);
  font-size: 0.85rem;
  justify-content: center;
}
</style>
