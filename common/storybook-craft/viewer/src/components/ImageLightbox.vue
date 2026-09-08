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
          <span class="sheet-title">{{ mediaTitle || 'Scene Inspector' }}</span>
        </div>
        <div class="head-actions">
          <button
            type="button"
            class="clean-btn clean-btn-xs jump-prompt-head-btn"
            title="Focus prompt inspector"
            @click="scrollToPrompt"
          >
            <span class="material-symbols-rounded">psychology</span>
            <span>Prompt</span>
          </button>
          <button
            type="button"
            class="clean-icon-btn close-btn"
            aria-label="Close dialog"
            @click="close"
          >
            <span class="material-symbols-rounded">close</span>
          </button>
        </div>
      </header>

      <!-- Modal Body (Two columns on desktop, single column on narrow screens) -->
      <div ref="sheetBodyRef" class="sheet-body">
        <div class="lightbox-grid">
          <!-- Left Column: Visual Media & Reference Showcase -->
          <div class="lightbox-col-visuals">
            <!-- 1. Generated Asset Viewport (if generated) -->
            <div v-if="mediaSrc" class="media-viewport">
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

            <!-- 2. Pending Hero Banner (if not yet generated) -->
            <div v-else class="pending-hero clean-card">
              <div class="pending-hero-left">
                <span class="material-symbols-rounded pending-hero-icon">schedule</span>
                <div>
                  <h4 class="pending-hero-title">Scene Pending Generation</h4>
                  <p class="pending-hero-sub">Review prompt directives and references before generating.</p>
                </div>
              </div>
            </div>

            <!-- 3. Reference Guides Showcase (Style Ref & Character Ref(s)) -->
            <div v-if="styleRef || (characterRefs && characterRefs.length)" class="refs-section clean-card">
              <div class="refs-header">
                <span class="material-symbols-rounded refs-icon">collections</span>
                <span class="refs-title">Reference Guides</span>
                <span class="refs-subtitle">Visual reference images guiding aesthetics and characters.</span>
              </div>

              <div class="refs-grid">
                <!-- Style Reference Card -->
                <div v-if="styleRef" class="ref-card style-ref-card">
                  <div class="ref-thumb-wrap">
                    <img v-if="styleRef.assetUrl" :src="styleRef.assetUrl" :alt="styleRef.style_name" class="ref-thumb" />
                    <div v-else class="ref-thumb-ph">
                      <span class="material-symbols-rounded">palette</span>
                    </div>
                  </div>
                  <div class="ref-info">
                    <div class="ref-tag-row">
                      <span class="badge-role style-role">Style Reference</span>
                      <span class="badge-always">Always Active</span>
                      <span v-if="styleRef.override_scope === 'tag'" class="badge-override badge-override-tag" title="This reference applies specifically to this tag">Tag Override</span>
                      <span v-else-if="styleRef.override_scope === 'scene'" class="badge-override badge-override-scene" title="This reference applies to this entire scene">Scene Override</span>
                      <span v-else-if="styleRef.is_scene_override" class="badge-override badge-override-tag" title="This reference applies specifically to this tag">Tag Override</span>
                    </div>
                    <h5 class="ref-name">{{ styleRef.style_name || styleRef.name }}</h5>
                    <p class="ref-desc">Guides artistic medium, textures, palette & lighting.</p>
                    <div class="ref-upload-row">
                      <button
                        type="button"
                        class="clean-btn clean-btn-xs change-ref-btn"
                        :disabled="isUploadingRef || isSelectingRef"
                        title="Change style reference by selecting from workspace assets"
                        @click="openAssetPicker('style')"
                      >
                        <span class="material-symbols-rounded">photo_library</span>
                        <span>Change</span>
                      </button>
                      <button
                        v-if="styleRef.override_scope || styleRef.is_scene_override"
                        type="button"
                        class="clean-btn clean-btn-xs reset-ref-btn"
                        :disabled="isUploadingRef || isSelectingRef"
                        title="Reset style reference override back to workspace default"
                        @click="onResetRef('style', '', styleRef.override_scope)"
                      >
                        <span class="material-symbols-rounded">restart_alt</span>
                        <span>Reset</span>
                      </button>
                      <button
                        v-if="styleRef.assetUrl"
                        type="button"
                        class="clean-btn clean-btn-xs delete-ref-btn"
                        :disabled="isUploadingRef || isSelectingRef"
                        title="Delete this style reference image"
                        @click="onDeleteStyleRef"
                      >
                        <span class="material-symbols-rounded">delete</span>
                        <span>Delete</span>
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Character Reference Card(s) -->
                <template v-if="characterRefs && characterRefs.length">
                  <div v-for="c in characterRefs" :key="c.name" class="ref-card char-ref-card">
                    <div class="ref-thumb-wrap">
                      <img v-if="c.assetUrl" :src="c.assetUrl" :alt="c.name" class="ref-thumb" />
                      <div v-else class="ref-thumb-ph">
                        <span class="material-symbols-rounded">face</span>
                      </div>
                    </div>
                    <div class="ref-info">
                      <div class="ref-tag-row">
                        <span class="badge-role" :class="`role-${c.category || 'hero'}`">
                          {{ c.category === 'boss' ? 'Boss Titan' : (c.category === 'enemy' ? 'Enemy / Monster' : 'Character Reference') }}
                        </span>
                        <span class="badge-matched">Matched</span>
                        <span v-if="c.override_scope === 'tag'" class="badge-override badge-override-tag" title="This reference photo applies specifically to this tag">Tag Override</span>
                        <span v-else-if="c.override_scope === 'scene'" class="badge-override badge-override-scene" title="This reference photo applies to this entire scene">Scene Override</span>
                        <span v-else-if="c.is_scene_override" class="badge-override badge-override-tag" title="This reference photo applies specifically to this tag">Tag Override</span>
                      </div>
                      <h5 class="ref-name">{{ c.name }}</h5>
                      <p class="ref-desc">Preserves visual identity, features & costume.</p>
                      <div class="ref-upload-row">
                        <button
                          type="button"
                          class="clean-btn clean-btn-xs change-ref-btn"
                          :disabled="isUploadingRef || isSelectingRef"
                          title="Change character reference by selecting from workspace assets"
                          @click="openAssetPicker('character', c.name)"
                        >
                          <span class="material-symbols-rounded">photo_library</span>
                          <span>Change</span>
                        </button>
                        <button
                          v-if="c.override_scope || c.is_scene_override"
                          type="button"
                          class="clean-btn clean-btn-xs reset-ref-btn"
                          :disabled="isUploadingRef || isSelectingRef"
                          title="Reset reference photo back to default"
                          @click="onResetRef('character', c.name, c.override_scope)"
                        >
                          <span class="material-symbols-rounded">restart_alt</span>
                          <span>Reset</span>
                        </button>
                        <button
                          v-if="c.assetUrl"
                          type="button"
                          class="clean-btn clean-btn-xs delete-ref-btn"
                          :disabled="isUploadingRef || isSelectingRef"
                          title="Delete this character reference photo"
                          @click="onDeleteCharRef(c.name, c.assetUrl)"
                        >
                          <span class="material-symbols-rounded">delete</span>
                          <span>Delete</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </template>

                <!-- No Character Matched Notice -->
                <div v-else class="ref-card empty-char-card">
                  <div class="ref-thumb-ph">
                    <span class="material-symbols-rounded empty-ref-icon">landscape</span>
                  </div>
                  <div class="ref-info">
                    <span class="badge-role generic-role">Environment Scene</span>
                    <p class="ref-desc">No character references attached. Pure environment composition.</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- 4. Meta Tags Pill Row -->
            <div v-if="mediaDetails" class="meta-pills">
              <span v-for="(val, key) in mediaDetails" :key="key" class="clean-badge">
                <strong>{{ key }}:</strong> {{ val }}
              </span>
            </div>
          </div>

          <!-- Right Column: Generation Controls, Extra Prompt & Prompt Inspector -->
          <div class="lightbox-col-controls">
            <!-- 1. Action Bar: Generate / Regenerate Asset & Settings -->
            <div v-if="tagId" class="lightbox-action-bar clean-card">
              <div class="action-bar-left">
                <div class="status-indicator" :class="{ 'is-generated': !!mediaSrc, 'is-pending': !mediaSrc }">
                  <span class="status-dot"></span>
                  <strong>{{ mediaSrc ? 'Generated Scene' : 'Pending Generation' }}</strong>
                  <span class="action-tag-id">({{ tagId }})</span>
                </div>

                <!-- Settings: Aspect Ratio & Resolution -->
                <div class="gen-config-group">
                  <div class="config-item" title="Output Aspect Ratio">
                    <span class="material-symbols-rounded config-icon">aspect_ratio</span>
                    <select
                      v-model="selectedRatio"
                      class="config-select"
                      :class="{ 'is-custom-select': selectedRatio !== 'inherit' }"
                      @change="onConfigChange"
                    >
                      <option value="inherit">Ratio: Inherit ({{ currentGlobalRatio }})</option>
                      <option value="16:9">16:9 (Landscape)</option>
                      <option value="4:3">4:3 (Standard)</option>
                      <option value="1:1">1:1 (Square)</option>
                      <option value="3:4">3:4 (Portrait)</option>
                      <option value="9:16">9:16 (Story)</option>
                      <option value="21:9">21:9 (Ultrawide)</option>
                    </select>
                  </div>

                  <div v-if="mediaType === 'image'" class="config-item" title="Output Resolution Size">
                    <span class="material-symbols-rounded config-icon">photo_size_select_actual</span>
                    <select
                      v-model="selectedSize"
                      class="config-select"
                      :class="{ 'is-custom-select': selectedSize !== 'inherit' }"
                      @change="onConfigChange"
                    >
                      <option value="inherit">Size: Inherit ({{ currentGlobalSize }})</option>
                      <option value="1K">1K (HD)</option>
                      <option value="2K">2K (QHD)</option>
                      <option value="4K">4K (UHD)</option>
                    </select>
                  </div>

                  <div v-if="isSceneOverridden" class="lightbox-override-pill" title="Custom override active for this scene">
                    <span class="status-dot dot-override"></span>
                    <span>Custom Override</span>
                    <button type="button" class="clean-btn-xs reset-pill-btn" @click="resetToGlobal">Reset</button>
                  </div>
                  <div v-else class="lightbox-inherit-pill" title="Inheriting workspace global defaults">
                    <span class="status-dot dot-inherit"></span>
                    <span>Inheriting Global</span>
                  </div>
                </div>
              </div>

              <div class="action-bar-right">
                <button
                  type="button"
                  class="clean-btn clean-btn-sm generate-action-btn"
                  :class="{ 'is-loading': isGenerating }"
                  :disabled="isGenerating"
                  @click="triggerGeneration"
                >
                  <span class="material-symbols-rounded" :class="{ 'is-spinning': isGenerating }">
                    {{ isGenerating ? 'sync' : (mediaSrc ? 'refresh' : 'auto_awesome') }}
                  </span>
                  <span>{{ isGenerating ? 'Generating...' : (mediaSrc ? 'Regenerate Scene' : 'Generate Asset Now') }}</span>
                </button>
              </div>
            </div>

            <span v-if="generationStatusMsg" class="generation-status-text">
              {{ generationStatusMsg }}
            </span>

            <!-- 2. Extra Prompt Directives Card -->
            <div v-if="tagId" class="extra-prompt-card clean-card">
              <div class="extra-prompt-head">
                <div class="extra-prompt-title-group">
                  <span class="material-symbols-rounded extra-icon">add_task</span>
                  <span class="extra-title">Extra Prompt Directives</span>
                  <span class="extra-hint">Appended to final prompt for this scene</span>
                </div>
                <span v-if="extraPromptSavedMsg" class="extra-saved-indicator">
                  <span class="material-symbols-rounded">check</span>
                  {{ extraPromptSavedMsg }}
                </span>
              </div>
              <div class="extra-prompt-body">
                <div class="extra-input-wrap">
                  <input
                    v-model="extraPrompt"
                    type="text"
                    class="clean-input extra-prompt-input"
                    placeholder="Add custom modifiers: e.g. cinematic rim lighting, volumetric fog, ethereal 8k..."
                    @input="onExtraPromptInput"
                    @change="saveExtraPrompt"
                  />
                  <button
                    v-if="extraPrompt"
                    type="button"
                    class="clear-extra-btn"
                    title="Clear extra prompt"
                    @click="clearExtraPrompt"
                  >
                    <span class="material-symbols-rounded">close</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- 3. Prompt Inspector with Tabs -->
            <div ref="promptInspectorRef" class="prompt-inspector clean-card">
              <div class="inspector-tabs-bar">
                <div class="inspector-tabs">
                  <button
                    type="button"
                    class="inspector-tab-btn"
                    :class="{ active: activePromptTab === 'composed' }"
                    @click="activePromptTab = 'composed'"
                  >
                    <span class="material-symbols-rounded tab-i">neurology</span>
                    <span>Composed Prompt (Model Input)</span>
                  </button>
                  <button
                    type="button"
                    class="inspector-tab-btn"
                    :class="{ active: activePromptTab === 'narrative' }"
                    @click="activePromptTab = 'narrative'"
                  >
                    <span class="material-symbols-rounded tab-i">auto_stories</span>
                    <span>Scene Context Prompt</span>
                  </button>
                  <button
                    v-if="cliCommand || dynamicCliCommand"
                    type="button"
                    class="inspector-tab-btn"
                    :class="{ active: activePromptTab === 'cli' }"
                    @click="activePromptTab = 'cli'"
                  >
                    <span class="material-symbols-rounded tab-i">terminal</span>
                    <span>CLI Command</span>
                  </button>
                </div>

                <!-- Copy button for active tab -->
                <button
                  type="button"
                  class="clean-btn clean-btn-sm copy-active-btn"
                  @click="copyActiveTabContent"
                >
                  <span class="material-symbols-rounded">
                    {{ isCopied ? 'check' : 'content_copy' }}
                  </span>
                  {{ isCopied ? 'Copied' : 'Copy' }}
                </button>
              </div>

              <!-- Tab Content 1: Composed Model Prompt -->
              <div v-if="activePromptTab === 'composed'" class="prompt-panel">
                <div class="panel-hint">
                  <span class="material-symbols-rounded hint-icon">verified_user</span>
                  <span>Strict prompt passed to Gemini. Isolates reference image roles to create an original scene.</span>
                </div>
                <div v-if="displayComposedPrompt" class="prompt-code-wrap">
                  <pre class="code-box"><code>{{ displayComposedPrompt }}</code></pre>
                </div>
                <div v-else class="empty-prompt-state">
                  <span class="material-symbols-rounded empty-prompt-icon">edit_note</span>
                  <p class="empty-prompt-title">No prompt specified for this scene yet.</p>
                  <p class="empty-prompt-desc">Auto-generate a rich visual prompt from the narrative using Gemini, or write one manually.</p>
                  <button
                    type="button"
                    class="clean-btn clean-btn-sm auto-gen-primary-btn"
                    :disabled="isRegeneratingPrompt"
                    @click="onAutoGeneratePrompt"
                  >
                    <span class="material-symbols-rounded" :class="{ 'is-spinning': isRegeneratingPrompt }">
                      {{ isRegeneratingPrompt ? 'sync' : 'auto_awesome' }}
                    </span>
                    <span>{{ isRegeneratingPrompt ? 'Generating Prompt...' : '✨ Auto-Generate Prompt with AI' }}</span>
                  </button>
                </div>
              </div>

              <!-- Tab Content 2: Narrative Scene Prompt -->
              <div v-else-if="activePromptTab === 'narrative'" class="prompt-panel">
                <div class="panel-hint">
                  <div class="hint-left">
                    <span class="material-symbols-rounded hint-icon">info</span>
                    <span>Scene description extracted from the Markdown narrative context.</span>
                  </div>
                  <div class="hint-actions">
                    <button
                      type="button"
                      class="clean-btn clean-btn-xs auto-gen-btn"
                      :disabled="isRegeneratingPrompt"
                      title="Generate or re-synthesize prompt from narrative context"
                      @click="onAutoGeneratePrompt"
                    >
                      <span class="material-symbols-rounded" :class="{ 'is-spinning': isRegeneratingPrompt }">
                        {{ isRegeneratingPrompt ? 'sync' : 'auto_awesome' }}
                      </span>
                      <span>{{ isRegeneratingPrompt ? 'Generating...' : '✨ Auto-Generate' }}</span>
                    </button>
                    <button
                      v-if="!isEditingPrompt"
                      type="button"
                      class="clean-btn clean-btn-xs edit-btn"
                      title="Edit prompt text"
                      @click="startEditPrompt"
                    >
                      <span class="material-symbols-rounded">edit</span>
                      <span>Edit</span>
                    </button>
                    <button
                      v-else
                      type="button"
                      class="clean-btn clean-btn-xs save-btn"
                      title="Save prompt changes to markdown"
                      @click="saveEditedPrompt"
                    >
                      <span class="material-symbols-rounded">check</span>
                      <span>Save</span>
                    </button>
                  </div>
                </div>
                <textarea
                  v-if="isEditingPrompt"
                  v-model="editingPromptText"
                  class="clean-textarea edit-prompt-textarea"
                  rows="6"
                  placeholder="Enter scene prompt..."
                ></textarea>
                <p v-else-if="mediaPrompt" class="narrative-box">{{ mediaPrompt }}</p>
                <div v-else class="empty-prompt-state">
                  <span class="material-symbols-rounded empty-prompt-icon">edit_note</span>
                  <p class="empty-prompt-title">No prompt specified for this scene yet.</p>
                  <div class="empty-actions">
                    <button
                      type="button"
                      class="clean-btn clean-btn-sm auto-gen-primary-btn"
                      :disabled="isRegeneratingPrompt"
                      @click="onAutoGeneratePrompt"
                    >
                      <span class="material-symbols-rounded" :class="{ 'is-spinning': isRegeneratingPrompt }">
                        {{ isRegeneratingPrompt ? 'sync' : 'auto_awesome' }}
                      </span>
                      <span>{{ isRegeneratingPrompt ? 'Generating...' : '✨ Auto-Generate Prompt' }}</span>
                    </button>
                    <button
                      type="button"
                      class="clean-btn clean-btn-sm"
                      @click="startEditPrompt"
                    >
                      <span class="material-symbols-rounded">edit</span>
                      <span>Write Manually</span>
                    </button>
                  </div>
                </div>
              </div>

              <!-- Tab Content 3: CLI Command -->
              <div v-else-if="activePromptTab === 'cli'" class="prompt-panel">
                <div class="panel-hint">
                  <span class="material-symbols-rounded hint-icon">terminal</span>
                  <span>Run this command in terminal to generate the image asset with storybook:</span>
                </div>
                <pre class="code-box cli-box"><code>{{ dynamicCliCommand }}</code></pre>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- Reference Guide Picker Modal Overlay (Nested Modal) -->
      <div v-if="showAssetPicker" class="asset-picker-overlay" @click.self="closeAssetPicker">
        <div class="asset-picker-modal clean-card" @click.stop>
          <div class="picker-header">
            <div class="picker-title-group">
              <span class="material-symbols-rounded picker-title-icon">
                {{ pickerType === 'style' ? 'palette' : 'face' }}
              </span>
              <div>
                <h4 class="picker-title">
                  {{ pickerType === 'style' ? 'Select Style Reference Image' : `Select Reference Photo for ${pickerTargetName}` }}
                </h4>
                <p class="picker-subtitle">
                  {{ pickerType === 'style'
                    ? 'Choose an active guide from existing style reference images, or upload a new one.'
                    : `Choose from existing reference photos for ${pickerTargetName}, or upload a new one.`
                  }}
                </p>
              </div>
            </div>
            <button type="button" class="clean-icon-btn picker-close-btn" @click="closeAssetPicker">
              <span class="material-symbols-rounded">close</span>
            </button>
          </div>

          <!-- Application Scope Selector -->
          <div class="picker-scope-card">
            <div class="picker-scope-label">
              <span class="material-symbols-rounded scope-icon">tune</span>
              <span>Apply Selection Scope:</span>
            </div>
            <div class="picker-scope-options">
              <label class="scope-radio-label" :class="{ selected: pickerScope === 'tag' }">
                <input type="radio" v-model="pickerScope" value="tag" />
                <span class="scope-radio-custom"></span>
                <span class="scope-text">
                  <strong>Only this tag</strong>
                  <span class="scope-hint">Isolated override for {{ tagId || 'current tag' }}</span>
                </span>
              </label>
              <label class="scope-radio-label" :class="{ selected: pickerScope === 'scene' }">
                <input type="radio" v-model="pickerScope" value="scene" />
                <span class="scope-radio-custom"></span>
                <span class="scope-text">
                  <strong>This Scene</strong>
                  <span class="scope-hint">Apply to all tags in scene "{{ section || 'current scene' }}"</span>
                </span>
              </label>
              <label class="scope-radio-label" :class="{ selected: pickerScope === 'global' }">
                <input type="radio" v-model="pickerScope" value="global" />
                <span class="scope-radio-custom"></span>
                <span class="scope-text">
                  <strong>All Scenes</strong>
                  <span class="scope-hint">Update workspace default (all tags)</span>
                </span>
              </label>
            </div>
          </div>

          <!-- Filter Tabs & Tools -->
          <div class="picker-toolbar">
            <div v-if="pickerType === 'character'" class="picker-tabs">
              <button
                type="button"
                class="picker-tab-btn"
                :class="{ active: pickerTab === 'current' }"
                @click="pickerTab = 'current'"
              >
                {{ pickerTargetName }} ({{ currentCharAssetsCount }})
              </button>
              <button
                type="button"
                class="picker-tab-btn"
                :class="{ active: pickerTab === 'all' }"
                @click="pickerTab = 'all'"
              >
                All Characters ({{ allCharAssetsCount }})
              </button>
            </div>
            <div v-else class="picker-style-indicator">
              <span class="material-symbols-rounded style-ind-icon">collections</span>
              <span>Available Style Images ({{ filteredRefImages.length }})</span>
            </div>

            <div class="picker-tools">
              <div class="picker-search-wrap">
                <span class="material-symbols-rounded search-icon">search</span>
                <input
                  v-model="pickerSearch"
                  type="text"
                  placeholder="Search photos..."
                  class="picker-search-input"
                />
                <button
                  v-if="pickerSearch"
                  type="button"
                  class="search-clear-btn"
                  @click="pickerSearch = ''"
                >
                  <span class="material-symbols-rounded">close</span>
                </button>
              </div>

              <label class="clean-btn clean-btn-xs picker-upload-btn" :class="{ disabled: isUploadingRef || isSelectingRef }">
                <span class="material-symbols-rounded">cloud_upload</span>
                <span>{{ isUploadingRef ? 'Uploading...' : (pickerType === 'style' ? 'Upload Style Image' : 'Upload Photo') }}</span>
                <input
                  type="file"
                  accept="image/*"
                  class="sr-only"
                  :disabled="isUploadingRef || isSelectingRef"
                  @change="onUploadViaPicker"
                />
              </label>
            </div>
          </div>

          <!-- Images Grid -->
          <div class="picker-body">
            <div v-if="filteredRefImages.length === 0" class="picker-empty-state">
              <span class="material-symbols-rounded">image_not_supported</span>
              <p>No existing reference images found.</p>
              <small>Click "Upload Photo" above to add a reference image.</small>
            </div>
            <div v-else class="picker-grid">
              <div
                v-for="item in filteredRefImages"
                :key="item.id"
                class="picker-card"
                :class="{ 'is-selected': isAssetCurrentlyActive(item), 'is-busy': isSelectingRef }"
                @click="onSelectAsset(item)"
              >
                <div class="picker-thumb-wrap">
                  <img :src="item.assetUrl" :alt="item.name" class="picker-thumb" loading="lazy" />
                  <span v-if="isAssetCurrentlyActive(item)" class="picker-active-badge">
                    <span class="material-symbols-rounded">check_circle</span>
                    Active
                  </span>
                </div>
                <div class="picker-info">
                  <div class="picker-name" :title="item.displayName || item.name">{{ item.displayName || item.name }}</div>
                  <div class="picker-badge-row">
                    <span class="picker-cat-badge" :class="item.category">{{ item.categoryLabel }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </dialog>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import {
  uploadReferenceImage,
  deleteReferenceImage,
  selectReferenceImage,
  resetReferenceImage,
  getWorkspace,
  isTagGenerating,
  getGenerationStatus,
  runTagGeneration,
  onGenerationComplete,
  workspaceSettingsCache,
  saveWorkspaceSettings,
  resolveTagSettings,
  getGenerationSettings,
  buildPrompt,
  updateTagPrompt
} from '../services/api';

const props = defineProps({
  stem: { type: String, default: '' },
  workspaceData: { type: Object, default: () => null }
});
const emit = defineEmits(['refresh']);

const dialogRef = ref(null);
const isOpen = ref(false);
const tagId = ref('');
const workspaceStem = ref('');
const section = ref('');
const mediaSrc = ref('');
const mediaTitle = ref('');
const mediaType = ref('image');
const mediaPrompt = ref('');
const composedPrompt = ref('');
const styleRef = ref(null);
const characterRefs = ref([]);
const cliCommand = ref('');
const mediaDetails = ref(null);
const activePromptTab = ref('composed');
const copiedKey = ref('');

const isUploadingRef = ref(false);
const localStatusMsg = ref('');

// Reference Guide Picker State
const showAssetPicker = ref(false);
const pickerType = ref('style'); // 'style' | 'character'
const pickerTargetName = ref('');
const pickerScope = ref('tag'); // 'tag' | 'scene' | 'global'
const pickerTab = ref('current'); // for character: 'current' | 'all'
const pickerSearch = ref('');
const isSelectingRef = ref(false);
const fallbackWsData = ref(null);

const availableRefImages = computed(() => {
  const ws = props.workspaceData || fallbackWsData.value;
  const currentStem = activeStem.value;
  if (!currentStem || !ws) return [];

  if (pickerType.value === 'style') {
    const styleImgs = ws.style?.images || [];
    return styleImgs.map(imgName => ({
      id: `style_${imgName}`,
      name: imgName,
      filename: imgName,
      category: 'style',
      categoryLabel: ws.style?.style_name || 'Art Style',
      path: `style-ref/${imgName}`,
      assetUrl: `/api/asset/${encodeURIComponent(currentStem)}/style-ref/${encodeURIComponent(imgName)}`
    }));
  }

  if (pickerType.value === 'character') {
    const list = [];
    const targetName = pickerTargetName.value;
    const characters = ws.characters || [];

    // Target character's reference photos
    const targetChar = characters.find(c => c.name === targetName);
    if (targetChar && Array.isArray(targetChar.images)) {
      for (const imgName of targetChar.images) {
        list.push({
          id: `char_${targetName}_${imgName}`,
          name: imgName,
          displayName: `${targetName} / ${imgName}`,
          filename: imgName,
          characterName: targetName,
          isTargetChar: true,
          category: 'character',
          categoryLabel: targetName,
          path: `char-ref/${targetName}/${imgName}`,
          assetUrl: `/api/asset/${encodeURIComponent(currentStem)}/char-ref/${encodeURIComponent(targetName)}/${encodeURIComponent(imgName)}`
        });
      }
    }

    // Other characters' reference photos
    for (const ch of characters) {
      if (ch.name === targetName) continue;
      if (Array.isArray(ch.images)) {
        for (const imgName of ch.images) {
          list.push({
            id: `char_${ch.name}_${imgName}`,
            name: imgName,
            displayName: `${ch.name} / ${imgName}`,
            filename: imgName,
            characterName: ch.name,
            isTargetChar: false,
            category: 'character',
            categoryLabel: ch.name,
            path: `char-ref/${ch.name}/${imgName}`,
            assetUrl: `/api/asset/${encodeURIComponent(currentStem)}/char-ref/${encodeURIComponent(ch.name)}/${encodeURIComponent(imgName)}`
          });
        }
      }
    }

    return list;
  }

  return [];
});

const currentCharAssetsCount = computed(() => {
  return availableRefImages.value.filter(a => a.isTargetChar).length;
});

const allCharAssetsCount = computed(() => {
  return availableRefImages.value.length;
});

const filteredRefImages = computed(() => {
  let list = availableRefImages.value;

  if (pickerType.value === 'character' && pickerTab.value === 'current') {
    list = list.filter(a => a.isTargetChar);
  }

  if (pickerSearch.value.trim()) {
    const q = pickerSearch.value.trim().toLowerCase();
    list = list.filter(a =>
      a.name.toLowerCase().includes(q) ||
      (a.displayName && a.displayName.toLowerCase().includes(q)) ||
      (a.categoryLabel && a.categoryLabel.toLowerCase().includes(q))
    );
  }

  return list;
});

function isAssetCurrentlyActive(item) {
  if (pickerType.value === 'style') {
    if (!styleRef.value) return false;
    return styleRef.value.name === item.filename ||
           (styleRef.value.assetUrl && styleRef.value.assetUrl.includes(item.filename));
  }
  if (pickerType.value === 'character') {
    if (item.characterName && item.characterName !== pickerTargetName.value) {
      return false;
    }
    const targetChar = (characterRefs.value || []).find(c => c.name === pickerTargetName.value);
    if (!targetChar) return false;
    if (targetChar.image && targetChar.image === item.filename) return true;
    if (targetChar.assetUrl) {
      return targetChar.assetUrl.includes(`/${encodeURIComponent(item.characterName || pickerTargetName.value)}/${item.filename}`) ||
             targetChar.assetUrl.endsWith(`/${item.filename}`);
    }
    return false;
  }
  return false;
}

async function openAssetPicker(type, targetName = '') {
  pickerType.value = type;
  pickerTargetName.value = targetName;
  pickerSearch.value = '';
  pickerTab.value = 'current';
  pickerScope.value = 'tag';
  showAssetPicker.value = true;

  const currentStem = activeStem.value;
  if (currentStem && (!props.workspaceData || !props.workspaceData.characters)) {
    try {
      const data = await getWorkspace(currentStem);
      fallbackWsData.value = data;
    } catch (e) {
      console.warn('Could not load workspace references for picker:', e);
    }
  }
}

function closeAssetPicker() {
  showAssetPicker.value = false;
}

async function onSelectAsset(item) {
  const currentStem = activeStem.value;
  if (!currentStem || isSelectingRef.value) return;

  isSelectingRef.value = true;
  localStatusMsg.value = `Setting '${item.filename}' as ${pickerType.value} reference guide...`;

  try {
    const res = await selectReferenceImage(currentStem, {
      type: pickerType.value,
      characterName: pickerTargetName.value,
      assetPath: item.path,
      filename: item.filename,
      tagId: tagId.value,
      section: section.value,
      scope: pickerScope.value
    });

    const isOverride = pickerScope.value !== 'global';
    const scopeLabel = pickerScope.value === 'tag'
      ? `Tag ${tagId.value || 'Override'}`
      : (pickerScope.value === 'scene' ? `Scene '${section.value || 'Override'}'` : 'Global Default');

    if (pickerType.value === 'style') {
      if (styleRef.value) {
        styleRef.value.assetUrl = `${res.assetUrl}?t=${Date.now()}`;
        styleRef.value.name = res.filename;
        styleRef.value.override_scope = isOverride ? pickerScope.value : null;
        styleRef.value.is_scene_override = isOverride;
      } else {
        styleRef.value = {
          name: res.filename,
          assetUrl: `${res.assetUrl}?t=${Date.now()}`,
          style_name: res.filename,
          override_scope: isOverride ? pickerScope.value : null,
          is_scene_override: isOverride,
          role: 'Style Reference (Always Active)'
        };
      }
      localStatusMsg.value = `✨ Style reference updated to '${res.filename}' (${scopeLabel})! Click 'Regenerate Scene' to re-render.`;
    } else if (pickerType.value === 'character') {
      const targetChar = (characterRefs.value || []).find(c => c.name === pickerTargetName.value);
      if (targetChar) {
        targetChar.image = res.filename;
        targetChar.assetUrl = `${res.assetUrl}?t=${Date.now()}`;
        targetChar.override_scope = isOverride ? pickerScope.value : null;
        targetChar.is_scene_override = isOverride;
      }
      localStatusMsg.value = `✨ Reference photo for '${pickerTargetName.value}' updated to '${res.filename}' (${scopeLabel})! Click 'Regenerate Scene' to re-render.`;
    }

    emit('refresh');
    showAssetPicker.value = false;
  } catch (err) {
    localStatusMsg.value = `❌ Failed to select reference: ${err.message}`;
    alert(`Failed to set reference asset: ${err.message}`);
  } finally {
    isSelectingRef.value = false;
  }
}

async function onResetRef(type, targetName = '', overrideScope = null) {
  const currentStem = activeStem.value;
  if (!currentStem || isSelectingRef.value) return;

  isSelectingRef.value = true;
  localStatusMsg.value = `Resetting reference override for ${targetName || 'style'}...`;

  try {
    await resetReferenceImage(currentStem, {
      type,
      characterName: targetName,
      tagId: tagId.value,
      section: section.value,
      scope: overrideScope || 'tag'
    });

    if (type === 'style') {
      if (styleRef.value) {
        styleRef.value.override_scope = null;
        styleRef.value.is_scene_override = false;
      }
    } else if (type === 'character') {
      const targetChar = (characterRefs.value || []).find(c => c.name === targetName);
      if (targetChar) {
        targetChar.override_scope = null;
        targetChar.is_scene_override = false;
      }
    }

    localStatusMsg.value = `✨ Reset reference override for ${targetName || 'style'}!`;
    emit('refresh');
  } catch (err) {
    localStatusMsg.value = `❌ Failed to reset reference override: ${err.message}`;
    alert(`Failed to reset reference override: ${err.message}`);
  } finally {
    isSelectingRef.value = false;
  }
}

watch(() => props.workspaceData, (newData) => {
  if (!isOpen.value || !tagId.value || !newData?.tags) return;
  const currentTag = newData.tags.find(t => t.id === tagId.value);
  if (currentTag) {
    if (currentTag.style_ref !== undefined) {
      styleRef.value = currentTag.style_ref;
    }
    if (currentTag.character_refs) {
      characterRefs.value = currentTag.character_refs;
    }
    if (currentTag.composed_prompt) {
      composedPrompt.value = currentTag.composed_prompt;
    }
    if (currentTag.prompt) {
      mediaPrompt.value = currentTag.prompt;
    }
    if (currentTag.cli_command) {
      cliCommand.value = currentTag.cli_command;
    }
  }
}, { deep: true });

async function onUploadViaPicker(event) {
  if (pickerType.value === 'style') {
    await onUploadStyleRef(event);
  } else if (pickerType.value === 'character') {
    await onUploadCharRef(event, pickerTargetName.value);
  }
  showAssetPicker.value = false;
}

const isRegeneratingPrompt = ref(false);
const isEditingPrompt = ref(false);
const editingPromptText = ref('');

function startEditPrompt() {
  editingPromptText.value = mediaPrompt.value;
  isEditingPrompt.value = true;
}

async function saveEditedPrompt() {
  const currentStem = activeStem.value;
  if (!currentStem || !tagId.value) return;
  try {
    await updateTagPrompt(currentStem, {
      tagId: tagId.value,
      prompt: editingPromptText.value
    });
    mediaPrompt.value = editingPromptText.value;
    isEditingPrompt.value = false;
    localStatusMsg.value = '✨ Prompt saved to markdown file!';
    emit('refresh');
  } catch (err) {
    alert(`Failed to save prompt: ${err.message}`);
  }
}

async function onAutoGeneratePrompt() {
  const currentStem = activeStem.value;
  if (!currentStem || !tagId.value) return;
  isRegeneratingPrompt.value = true;
  localStatusMsg.value = 'Synthesizing visual prompt from story context...';
  try {
    const res = await buildPrompt(currentStem, {
      tagId: tagId.value,
      type: mediaType.value,
      section: section.value,
      useAi: true
    });
    if (res && res.prompt) {
      mediaPrompt.value = res.prompt;
      editingPromptText.value = res.prompt;
      await updateTagPrompt(currentStem, {
        tagId: tagId.value,
        prompt: res.prompt
      });
      localStatusMsg.value = '✨ Prompt generated and saved!';
      emit('refresh');
    }
  } catch (err) {
    localStatusMsg.value = `❌ Failed to build prompt: ${err.message}`;
  } finally {
    isRegeneratingPrompt.value = false;
  }
}

const selectedRatio = ref('inherit');
const selectedSize = ref('inherit');
const extraPrompt = ref('');
const extraPromptSavedMsg = ref('');
const promptInspectorRef = ref(null);
const sheetBodyRef = ref(null);
let extraPromptSaveTimeout = null;
let extraPromptDebounce = null;

function lockBodyScroll() {
  try {
    document.body.style.overflow = 'hidden';
  } catch (e) {}
}

function unlockBodyScroll() {
  try {
    document.body.style.overflow = '';
  } catch (e) {}
}

function scrollToPrompt() {
  if (promptInspectorRef.value) {
    promptInspectorRef.value.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } else if (sheetBodyRef.value) {
    sheetBodyRef.value.scrollTo({ top: sheetBodyRef.value.scrollHeight, behavior: 'smooth' });
  }
}

async function saveExtraPrompt() {
  const currentStem = activeStem.value;
  if (!currentStem || !tagId.value) return;

  const wsSettings = workspaceSettingsCache[currentStem] || {
    global: {
      image: { ratio: '16:9', size: '1K', model: 'gemini-3.1-flash-image' },
      video: { ratio: '16:9', model: 'veo-2.0-generate-001', duration: '5s' }
    },
    scenes: {}
  };

  if (!wsSettings.scenes) wsSettings.scenes = {};
  if (!wsSettings.scenes[tagId.value]) {
    wsSettings.scenes[tagId.value] = {};
  }

  const cleanVal = (extraPrompt.value || '').trim();
  if (cleanVal) {
    wsSettings.scenes[tagId.value].extra_prompt = cleanVal;
  } else {
    delete wsSettings.scenes[tagId.value].extra_prompt;
  }

  const keys = Object.keys(wsSettings.scenes[tagId.value]);
  if (keys.length === 0 || keys.every(k => !wsSettings.scenes[tagId.value][k] || wsSettings.scenes[tagId.value][k] === 'inherit')) {
    delete wsSettings.scenes[tagId.value];
  }

  try {
    await saveWorkspaceSettings(currentStem, wsSettings);
    extraPromptSavedMsg.value = 'Saved';
    if (extraPromptSaveTimeout) clearTimeout(extraPromptSaveTimeout);
    extraPromptSaveTimeout = setTimeout(() => {
      extraPromptSavedMsg.value = '';
    }, 2500);
    emit('refresh');
  } catch (e) {
    console.error('Failed to save extra prompt:', e);
  }
}

function onExtraPromptInput() {
  if (extraPromptDebounce) clearTimeout(extraPromptDebounce);
  extraPromptDebounce = setTimeout(() => {
    saveExtraPrompt();
  }, 500);
}

function clearExtraPrompt() {
  extraPrompt.value = '';
  saveExtraPrompt();
}

const activeStem = computed(() => props.stem || workspaceStem.value);

const currentWsSettings = computed(() => {
  return workspaceSettingsCache[activeStem.value] || null;
});

const currentGlobalRatio = computed(() => {
  if (mediaType.value === 'video') {
    return currentWsSettings.value?.global?.video?.ratio || '16:9';
  }
  return currentWsSettings.value?.global?.image?.ratio || '16:9';
});

const currentGlobalSize = computed(() => {
  return currentWsSettings.value?.global?.image?.size || '1K';
});

const isSceneOverridden = computed(() => {
  return (selectedRatio.value && selectedRatio.value !== 'inherit') ||
         (selectedSize.value && selectedSize.value !== 'inherit') ||
         Boolean(extraPrompt.value && extraPrompt.value.trim());
});

async function onConfigChange() {
  const currentStem = activeStem.value;
  if (!currentStem || !tagId.value) return;

  const wsSettings = workspaceSettingsCache[currentStem] || {
    global: {
      image: { ratio: '16:9', size: '1K', model: 'gemini-3.1-flash-image' },
      video: { ratio: '16:9', model: 'veo-2.0-generate-001', duration: '5s' }
    },
    scenes: {}
  };

  if (!wsSettings.scenes) wsSettings.scenes = {};

  if (!wsSettings.scenes[tagId.value]) {
    wsSettings.scenes[tagId.value] = {};
  }

  if (selectedRatio.value === 'inherit') {
    delete wsSettings.scenes[tagId.value].ratio;
  } else {
    wsSettings.scenes[tagId.value].ratio = selectedRatio.value;
  }

  if (selectedSize.value === 'inherit') {
    delete wsSettings.scenes[tagId.value].size;
  } else {
    wsSettings.scenes[tagId.value].size = selectedSize.value;
  }

  const keys = Object.keys(wsSettings.scenes[tagId.value]);
  if (keys.length === 0 || keys.every(k => !wsSettings.scenes[tagId.value][k] || wsSettings.scenes[tagId.value][k] === 'inherit')) {
    delete wsSettings.scenes[tagId.value];
  }

  try {
    await saveWorkspaceSettings(currentStem, wsSettings);
    emit('refresh');
  } catch (e) {
    console.error('Failed to save scene override:', e);
  }
}

async function resetToGlobal() {
  selectedRatio.value = 'inherit';
  selectedSize.value = 'inherit';
  extraPrompt.value = '';
  await onConfigChange();
  await saveExtraPrompt();
}

const currentGenStatus = computed(() => {
  return getGenerationStatus(activeStem.value, tagId.value);
});

const localIsGenerating = ref(false);

const isGenerating = computed(() => {
  return localIsGenerating.value || isTagGenerating(activeStem.value, tagId.value);
});

const generationStatusMsg = computed(() => {
  if (currentGenStatus.value?.message) {
    return currentGenStatus.value.message;
  }
  return localStatusMsg.value;
});

const displayComposedPrompt = computed(() => {
  let base = composedPrompt.value;
  if (!base) {
    if (mediaPrompt.value && mediaPrompt.value.trim()) {
      const sections = [
        '[TASK: BRAND-NEW SCENE ILLUSTRATION FROM SCRATCH]\nGenerate a completely new, original standalone illustration strictly depicting the SCENE DESCRIPTION below.\nCRITICAL CONSTRAINTS:\n- DO NOT edit, inpaint, crop, or modify the provided reference image(s).\n- DO NOT copy the compositions, backgrounds, camera perspectives, or poses from the reference image(s).\n- The environment, action, composition, and physical staging must originate 100% from the SCENE DESCRIPTION.'
      ];
      if (styleRef.value || (characterRefs.value && characterRefs.value.length)) {
        const roles = ['[REFERENCE IMAGE ROLES]'];
        let idx = 1;
        if (styleRef.value) {
          roles.push(`- Reference Image ${idx} (Artistic Style Reference: ${styleRef.value.style_name || 'Art Style'}):\n  * Adopt ONLY the artistic medium, sculpted/painterly textures, color palette, lighting atmosphere, and visual aesthetic shown in Image ${idx}.\n  * Do NOT copy the specific objects, buildings, or layout of Image ${idx}.`);
          idx++;
        }
        for (const c of characterRefs.value) {
          roles.push(`- Reference Image ${idx} (Character Identity Reference: ${c.name}):\n  * Maintain the exact character visual identity, facial features, hairstyle, clothing design, colors, and proportions of ${c.name} from Image ${idx}.\n  * Place ${c.name} naturally into this new scene, dynamically adopting the action, pose, and emotion specified in the SCENE DESCRIPTION.\n  * Do NOT replicate the pose, camera framing, or background of Image ${idx}.`);
          idx++;
        }
        sections.push(roles.join('\n'));
      }
      sections.push(`[SCENE DESCRIPTION & ACTION]\n${mediaPrompt.value.trim()}`);
      base = sections.join('\n\n');
    } else {
      base = '';
    }
  }
  if (extraPrompt.value && extraPrompt.value.trim()) {
    const trimmed = extraPrompt.value.trim();
    if (base && !base.includes('[ADDITIONAL SCENE DIRECTIVES')) {
      base = `${base}\n\n[ADDITIONAL SCENE DIRECTIVES & CUSTOM PROMPT]\n${trimmed}`;
    } else if (!base) {
      base = `[ADDITIONAL SCENE DIRECTIVES & CUSTOM PROMPT]\n${trimmed}`;
    }
  }
  return base;
});

const dynamicCliCommand = computed(() => {
  const currentStem = activeStem.value;
  let base = `python3 storybook.py media generate outputs/${currentStem}/${currentStem}-output.md`;
  if (tagId.value) {
    base += ` --id ${tagId.value}`;
  }
  if (mediaType.value) {
    base += ` --type ${mediaType.value}`;
  }
  const effRatio = selectedRatio.value === 'inherit' ? currentGlobalRatio.value : selectedRatio.value;
  const effSize = selectedSize.value === 'inherit' ? currentGlobalSize.value : selectedSize.value;
  if (effRatio) {
    base += ` --ratio ${effRatio}`;
  }
  if (effSize && mediaType.value === 'image') {
    base += ` --size ${effSize}`;
  }
  if (extraPrompt.value && extraPrompt.value.trim()) {
    base += ` --extra-prompt "${extraPrompt.value.trim()}"`;
  }
  return base;
});

const isCopied = computed(() => copiedKey.value === activePromptTab.value);

function open({
  id = '',
  tagId: explicitTagId = '',
  stem: explicitStem = '',
  section: explicitSection = '',
  src = '',
  title = '',
  type = 'image',
  prompt = '',
  composedPrompt: comp = '',
  styleRef: sRef = null,
  characterRefs: cRefs = [],
  cliCommand: cmd = '',
  details = null,
  autoGenerate = false
}) {
  tagId.value = explicitTagId || id || (details && details.TagID) || '';
  workspaceStem.value = explicitStem || props.stem || '';
  section.value = explicitSection || (details && details.Section) || '';
  mediaSrc.value = src || '';
  mediaTitle.value = title;
  mediaType.value = type;
  mediaPrompt.value = prompt;
  composedPrompt.value = comp;
  styleRef.value = sRef;
  characterRefs.value = cRefs || [];
  cliCommand.value = cmd;
  mediaDetails.value = details;
  activePromptTab.value = (comp || prompt) ? 'composed' : 'narrative';
  copiedKey.value = '';
  localStatusMsg.value = '';
  isUploadingRef.value = false;

  const currentStem = activeStem.value;
  const wsSettings = workspaceSettingsCache[currentStem];
  const tagOverride = wsSettings?.scenes?.[tagId.value] || {};
  selectedRatio.value = tagOverride.ratio || 'inherit';
  selectedSize.value = tagOverride.size || 'inherit';
  extraPrompt.value = tagOverride.extra_prompt || '';
  extraPromptSavedMsg.value = '';

  if (dialogRef.value && !dialogRef.value.open) {
    dialogRef.value.showModal();
    isOpen.value = true;
    lockBodyScroll();
  }

  if (autoGenerate && tagId.value && !isGenerating.value) {
    setTimeout(() => {
      triggerGeneration();
    }, 150);
  }
}

async function onDeleteStyleRef() {
  const currentStem = activeStem.value;
  const filename = styleRef.value?.filename || (styleRef.value?.assetUrl ? styleRef.value.assetUrl.split('/').pop() : 'ref_001.png');
  if (!confirm(`Delete style reference image "${filename}"?`)) return;

  isUploadingRef.value = true;
  try {
    await deleteReferenceImage(currentStem, {
      type: 'style',
      filename
    });
    styleRef.value = null;
    emit('refresh');
  } catch (err) {
    alert(`Failed to delete style reference: ${err.message}`);
  } finally {
    isUploadingRef.value = false;
  }
}

async function onDeleteCharRef(charName, assetUrlOrFilename) {
  const currentStem = activeStem.value;
  const filename = assetUrlOrFilename.includes('/') ? assetUrlOrFilename.split('/').pop() : assetUrlOrFilename;
  if (!confirm(`Delete character reference image "${filename}" for "${charName}"?`)) return;

  isUploadingRef.value = true;
  try {
    await deleteReferenceImage(currentStem, {
      type: 'character',
      characterName: charName,
      filename
    });
    characterRefs.value = characterRefs.value.filter(c => c.name !== charName);
    emit('refresh');
  } catch (err) {
    alert(`Failed to delete character reference: ${err.message}`);
  } finally {
    isUploadingRef.value = false;
  }
}

async function triggerGeneration() {
  if (!tagId.value || isGenerating.value) return;
  const currentStem = activeStem.value;
  if (!currentStem) return;

  localIsGenerating.value = true;
  localStatusMsg.value = `Invoking generation for ${tagId.value}...`;

  try {
    const res = await runTagGeneration(currentStem, {
      tagId: tagId.value,
      section: section.value,
      type: mediaType.value,
      ratio: selectedRatio.value,
      size: selectedSize.value,
      extraPrompt: extraPrompt.value
    });
    if (res && res.success) {
      if (mediaType.value === 'image') {
        mediaSrc.value = `/api/asset/${encodeURIComponent(currentStem)}/images/${tagId.value}.png?t=${Date.now()}`;
      }
      emit('refresh');
    }
  } catch (err) {
    localStatusMsg.value = `❌ Error: ${err.message}`;
  } finally {
    localIsGenerating.value = false;
  }
}

async function onUploadStyleRef(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const currentStem = activeStem.value;
  if (!currentStem) return;

  isUploadingRef.value = true;
  localStatusMsg.value = `Uploading new style reference photo (${file.name})...`;

  try {
    const reader = new FileReader();
    reader.onload = async (e) => {
      const dataUrl = e.target.result;
      const res = await uploadReferenceImage(currentStem, {
        type: 'style',
        filename: file.name,
        imageBase64: dataUrl
      });
      if (styleRef.value) {
        styleRef.value.assetUrl = `${res.assetUrl}?t=${Date.now()}`;
        styleRef.value.name = res.filename;
      }
      localStatusMsg.value = `✨ Style reference updated to '${res.filename}'! Click 'Regenerate Scene' to re-render.`;
      emit('refresh');
      isUploadingRef.value = false;
    };
    reader.readAsDataURL(file);
  } catch (err) {
    localStatusMsg.value = `❌ Style upload failed: ${err.message}`;
    isUploadingRef.value = false;
  }
}

async function onUploadCharRef(event, charName) {
  const file = event.target.files?.[0];
  if (!file) return;
  const currentStem = activeStem.value;
  if (!currentStem) return;

  isUploadingRef.value = true;
  localStatusMsg.value = `Uploading new reference photo for '${charName}' (${file.name})...`;

  try {
    const reader = new FileReader();
    reader.onload = async (e) => {
      const dataUrl = e.target.result;
      const res = await uploadReferenceImage(currentStem, {
        type: 'character',
        characterName: charName,
        filename: file.name,
        imageBase64: dataUrl
      });
      const targetChar = (characterRefs.value || []).find(c => c.name === charName);
      if (targetChar) {
        targetChar.assetUrl = `${res.assetUrl}?t=${Date.now()}`;
      }
      localStatusMsg.value = `✨ Reference photo for '${charName}' updated! Click 'Regenerate Scene' to re-render.`;
      emit('refresh');
      isUploadingRef.value = false;
    };
    reader.readAsDataURL(file);
  } catch (err) {
    localStatusMsg.value = `❌ Photo upload failed: ${err.message}`;
    isUploadingRef.value = false;
  }
}


function close() {
  if (dialogRef.value && dialogRef.value.open) {
    dialogRef.value.close();
  }
  isOpen.value = false;
  unlockBodyScroll();
}

function onDialogClose() {
  isOpen.value = false;
  unlockBodyScroll();
}

async function copyText(text, key) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    copiedKey.value = key;
    setTimeout(() => {
      if (copiedKey.value === key) {
        copiedKey.value = '';
      }
    }, 2000);
  } catch (e) {
    console.error('Clipboard copy failed:', e);
  }
}

function copyActiveTabContent() {
  if (activePromptTab.value === 'composed') {
    copyText(displayComposedPrompt.value || mediaPrompt.value, 'composed');
  } else if (activePromptTab.value === 'narrative') {
    copyText(mediaPrompt.value, 'narrative');
  } else if (activePromptTab.value === 'cli') {
    copyText(dynamicCliCommand.value || cliCommand.value, 'cli');
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

let unsubGen = null;

onMounted(() => {
  const dialog = dialogRef.value;
  if (dialog && !('closedBy' in HTMLDialogElement.prototype)) {
    dialog.addEventListener('click', handleBackdropClick);
  }

  unsubGen = onGenerationComplete((err, payload) => {
    if (!err && payload?.tagId === tagId.value && payload?.stem === activeStem.value) {
      if (mediaType.value === 'image') {
        mediaSrc.value = `/api/asset/${encodeURIComponent(payload.stem)}/images/${payload.tagId}.png?t=${Date.now()}`;
      }
    }
  });
});

onBeforeUnmount(() => {
  unlockBodyScroll();
  const dialog = dialogRef.value;
  if (dialog && !('closedBy' in HTMLDialogElement.prototype)) {
    dialog.removeEventListener('click', handleBackdropClick);
  }
  if (unsubGen) {
    unsubGen();
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
  max-width: 96vw;
  max-height: 94vh;
  box-shadow: none;
  overflow: hidden;
}

.lightbox-dialog::backdrop {
  background-color: rgba(9, 9, 11, 0.78);
}

.lightbox-sheet {
  display: flex;
  flex-direction: column;
  max-width: 1240px;
  width: 94vw;
  height: 92vh;
  max-height: 92vh;
  overflow: hidden;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  background: var(--bg-surface);
}

.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface);
  flex-shrink: 0;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.jump-prompt-head-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.6rem;
  font-size: 0.78rem;
  border-radius: var(--radius-full);
  background: var(--accent-primary-subtle);
  color: var(--accent-primary-text);
  border: 1px solid var(--accent-primary);
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
  flex: 1 1 auto;
  min-height: 0;
  padding: 1.25rem;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--border-strong) transparent;
}

.lightbox-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.25rem;
}

@media (min-width: 860px) {
  .lightbox-grid {
    grid-template-columns: 440px 1fr;
    align-items: start;
  }
}

.lightbox-col-visuals {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.lightbox-col-controls {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.sheet-body::-webkit-scrollbar {
  width: 8px;
}

.sheet-body::-webkit-scrollbar-track {
  background: transparent;
}

.sheet-body::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 4px;
}

.sheet-body::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.media-viewport {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  border-radius: var(--radius-md);
  overflow: hidden;
  max-height: 48vh;
  flex-shrink: 0;
}

.media-elem {
  max-width: 100%;
  max-height: 48vh;
  object-fit: contain;
  display: block;
}

.jump-prompt-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  color: var(--text-primary);
  font-weight: 500;
}

.jump-prompt-btn:hover {
  background: var(--bg-surface-hover);
  border-color: var(--border-strong);
}

/* Extra Prompt Card */
.extra-prompt-card {
  padding: 0.85rem 1rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.extra-prompt-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.extra-prompt-title-group {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  color: var(--text-primary);
  flex-wrap: wrap;
}

.extra-icon {
  font-size: 18px;
  color: var(--accent-primary);
}

.extra-title {
  font-weight: 600;
}

.extra-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.extra-saved-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: #15803d;
  font-weight: 600;
}

.extra-saved-indicator .material-symbols-rounded {
  font-size: 14px;
}

.extra-prompt-body {
  width: 100%;
}

.extra-input-wrap {
  display: flex;
  align-items: center;
  position: relative;
}

.extra-prompt-input {
  width: 100%;
  padding-right: 2rem;
  font-size: 0.82rem;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
}

.extra-prompt-input:focus {
  border-color: var(--accent-primary);
  background: var(--bg-surface);
}

.clear-extra-btn {
  position: absolute;
  right: 0.5rem;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 0;
}

.clear-extra-btn:hover {
  color: var(--text-primary);
}

.clear-extra-btn .material-symbols-rounded {
  font-size: 16px;
}

/* Pending Hero Banner */
.pending-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: linear-gradient(135deg, rgba(234, 179, 8, 0.08) 0%, rgba(245, 158, 11, 0.04) 100%);
  border: 1px solid rgba(234, 179, 8, 0.25);
  border-radius: var(--radius-md);
  flex-wrap: wrap;
}

.pending-hero-left {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.pending-hero-icon {
  font-size: 28px;
  color: #ca8a04;
}

.pending-hero-title {
  margin: 0 0 0.2rem 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.pending-hero-sub {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

/* Lightbox Action Bar */
.lightbox-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  flex-wrap: wrap;
}

.action-bar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  padding: 0.25rem 0.6rem;
  border-radius: 9999px;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.status-indicator.is-generated .status-dot {
  background: #10b981;
}

.status-indicator.is-pending .status-dot {
  background: #f59e0b;
}

.action-tag-id {
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.gen-config-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.config-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: 0.15rem 0.5rem;
}

.config-icon {
  font-size: 16px;
  color: var(--text-muted);
}

.config-select {
  background: transparent;
  border: none;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
  outline: none;
  padding: 0.15rem 0;
  font-family: var(--font-sans);
}

.config-select option {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.config-select.is-custom-select {
  color: #6d28d9;
  font-weight: 700;
}

.lightbox-override-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  background: rgba(139, 92, 246, 0.12);
  color: #7c3aed;
  border: 1px solid rgba(139, 92, 246, 0.25);
}

.lightbox-inherit-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 500;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  background: var(--status-success-bg);
  color: var(--status-success-text);
  border: 1px solid var(--status-success-border);
}

.reset-pill-btn {
  background: none;
  border: none;
  color: #6d28d9;
  font-size: 0.7rem;
  text-decoration: underline;
  cursor: pointer;
  padding: 0 2px;
}

.reset-pill-btn:hover {
  color: #4c1d95;
}

.dot-override {
  background: #8b5cf6;
}

.dot-inherit {
  background: #10b981;
}

.generation-status-text {
  font-size: 0.82rem;
  color: var(--accent-primary);
  font-weight: 500;
}

.action-bar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.generate-action-btn {
  background: var(--accent-primary);
  color: white;
  border: none;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.generate-action-btn:hover:not(:disabled) {
  opacity: 0.92;
  transform: translateY(-1px);
}

.generate-action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.meta-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

/* Reference Guides Section */
.refs-section {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
}

.refs-header {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5rem 0.75rem;
}

.refs-icon {
  font-size: 18px;
  color: var(--accent-primary);
}

.refs-title {
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--text-primary);
}

.refs-subtitle {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.refs-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
}

.ref-card {
  display: flex;
  gap: 0.85rem;
  padding: 0.75rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  align-items: center;
}

.ref-thumb-wrap {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ref-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.ref-thumb-ph {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-surface-secondary);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  flex-shrink: 0;
}

.empty-char-card {
  align-items: center;
  border-style: dashed;
}

.empty-ref-icon {
  font-size: 24px;
  color: var(--text-muted);
}

.ref-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.ref-tag-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.badge-role {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}

.style-role {
  background: rgba(14, 165, 233, 0.12);
  color: #0284c7;
}

.char-role,
.role-hero {
  background: rgba(168, 85, 247, 0.12);
  color: #9333ea;
}

.role-boss {
  background: rgba(225, 29, 72, 0.12);
  color: #e11d48;
}

.role-enemy {
  background: rgba(234, 88, 12, 0.12);
  color: #ea580c;
}

.generic-role {
  background: rgba(100, 116, 139, 0.12);
  color: #64748b;
}

.badge-always {
  font-size: 0.65rem;
  font-weight: 600;
  color: #0d9488;
  background: rgba(13, 148, 136, 0.1);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.badge-matched {
  font-size: 0.65rem;
  font-weight: 600;
  color: #7c3aed;
  background: rgba(124, 58, 237, 0.1);
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.badge-override {
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.badge-override-tag {
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
  border: 1px solid rgba(37, 99, 235, 0.28);
}

.badge-override-scene {
  color: #d97706;
  background: rgba(217, 119, 6, 0.12);
  border: 1px solid rgba(217, 119, 6, 0.25);
}

.ref-name {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ref-desc {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.35;
}

.ref-upload-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-top: 0.4rem;
}

/* Ensure Change, Reset, and Delete buttons are the exact same size */
.ref-upload-row .change-ref-btn,
.ref-upload-row .reset-ref-btn,
.ref-upload-row .delete-ref-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  height: 28px;
  min-height: 28px;
  max-height: 28px;
  box-sizing: border-box;
  padding: 0 0.65rem;
  font-family: var(--font-sans);
  font-size: 0.75rem;
  font-weight: 500;
  line-height: 1;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
  white-space: nowrap;
}

.ref-upload-row .change-ref-btn .material-symbols-rounded,
.ref-upload-row .reset-ref-btn .material-symbols-rounded,
.ref-upload-row .delete-ref-btn .material-symbols-rounded {
  font-size: 15px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ref-upload-row .change-ref-btn {
  color: var(--text-primary);
  background: var(--bg-surface);
  border-color: var(--border-default);
}

.ref-upload-row .change-ref-btn:hover:not(:disabled) {
  background: var(--bg-surface-secondary);
  border-color: var(--border-strong);
  color: var(--accent-primary);
}

.ref-upload-row .reset-ref-btn {
  color: #d97706;
  border-color: #fcd34d;
  background: #fffbeb;
}

.ref-upload-row .reset-ref-btn:hover:not(:disabled) {
  background: #fef3c7;
  border-color: #f59e0b;
  color: #b45309;
}

.ref-upload-row .delete-ref-btn {
  color: #ef4444;
  border-color: #fca5a5;
  background: #fef2f2;
}

.ref-upload-row .delete-ref-btn:hover:not(:disabled) {
  background: #fee2e2;
  border-color: #f87171;
  color: #dc2626;
}

.ref-upload-row .change-ref-btn:disabled,
.ref-upload-row .reset-ref-btn:disabled,
.ref-upload-row .delete-ref-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Asset Picker Scope Selector */
.picker-scope-card {
  padding: 0.75rem 1.25rem;
  background: var(--bg-surface-secondary);
  border-bottom: 1px solid var(--border-default);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.picker-scope-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.picker-scope-label .scope-icon {
  font-size: 17px;
  color: var(--accent-primary);
}

.picker-scope-options {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.scope-radio-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.75rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.scope-radio-label:hover {
  border-color: var(--border-strong);
}

.scope-radio-label.selected {
  border-color: var(--accent-primary);
  background: rgba(14, 165, 233, 0.08);
}

.scope-radio-label input[type="radio"] {
  accent-color: var(--accent-primary);
  cursor: pointer;
}

.scope-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.scope-text strong {
  font-size: 0.78rem;
  color: var(--text-primary);
}

.scope-hint {
  font-size: 0.68rem;
  color: var(--text-secondary);
}

/* Asset Picker Modal Styles */
.asset-picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 2500;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  animation: pickerOverlayFade 0.2s ease;
}

@keyframes pickerOverlayFade {
  from { opacity: 0; }
  to { opacity: 1; }
}

.asset-picker-modal {
  width: 92vw;
  max-width: 860px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
  overflow: hidden;
  animation: pickerModalPop 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes pickerModalPop {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface-secondary);
}

.picker-title-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.picker-title-icon {
  font-size: 24px;
  color: var(--accent-primary);
}

.picker-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.picker-subtitle {
  margin: 0.15rem 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.picker-close-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.picker-close-btn:hover {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.picker-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface);
  flex-wrap: wrap;
}

.picker-tabs {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--bg-surface-secondary);
  padding: 0.2rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
}

.picker-style-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-surface-secondary);
  padding: 0.3rem 0.75rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
}

.style-ind-icon {
  font-size: 17px;
  color: var(--accent-primary);
}

.picker-tab-btn {
  border: none;
  background: transparent;
  padding: 0.25rem 0.65rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.picker-tab-btn:hover {
  color: var(--text-primary);
}

.picker-tab-btn.active {
  background: var(--bg-surface);
  color: var(--accent-primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.picker-tools {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.picker-search-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.picker-search-wrap .search-icon {
  position: absolute;
  left: 0.5rem;
  font-size: 16px;
  color: var(--text-muted);
  pointer-events: none;
}

.picker-search-input {
  height: 30px;
  padding: 0 1.6rem 0 1.8rem;
  font-size: 0.75rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
  background: var(--bg-surface-secondary);
  color: var(--text-primary);
  outline: none;
  width: 170px;
  transition: all 0.15s ease;
}

.picker-search-input:focus {
  border-color: var(--accent-primary);
  background: var(--bg-surface);
  width: 210px;
}

.search-clear-btn {
  position: absolute;
  right: 0.4rem;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
}

.search-clear-btn .material-symbols-rounded {
  font-size: 14px;
}

.picker-upload-btn {
  height: 30px;
  padding: 0 0.7rem;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
}

.picker-upload-btn .material-symbols-rounded {
  font-size: 16px;
}

.picker-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
  min-height: 280px;
  max-height: calc(85vh - 160px);
}

.picker-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--text-muted);
  gap: 0.5rem;
}

.picker-empty-state .material-symbols-rounded {
  font-size: 36px;
  opacity: 0.6;
}

.picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.85rem;
}

.picker-card {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-surface-secondary);
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  user-select: none;
}

.picker-card:hover {
  border-color: var(--accent-primary);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.18);
}

.picker-card.is-selected {
  border-color: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.35);
}

.picker-card.is-busy {
  pointer-events: none;
  opacity: 0.6;
}

.picker-thumb-wrap {
  aspect-ratio: 16/10;
  width: 100%;
  background: #111;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.picker-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s ease;
}

.picker-card:hover .picker-thumb {
  transform: scale(1.04);
}

.picker-active-badge {
  position: absolute;
  top: 5px;
  right: 5px;
  background: #10b981;
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.picker-active-badge .material-symbols-rounded {
  font-size: 12px;
}

.picker-info {
  padding: 0.45rem 0.55rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.picker-name {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.picker-badge-row {
  display: flex;
  align-items: center;
}

.picker-cat-badge {
  font-size: 0.62rem;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.picker-cat-badge.scene {
  background: rgba(14, 165, 233, 0.12);
  color: #0284c7;
}

.picker-cat-badge.style {
  background: rgba(168, 85, 247, 0.12);
  color: #9333ea;
}

.picker-cat-badge.character {
  background: rgba(234, 88, 12, 0.12);
  color: #ea580c;
}

/* Prompt Inspector */
.prompt-inspector {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.inspector-tabs-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface-secondary);
  padding: 0.35rem 0.75rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.inspector-tabs {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.inspector-tab-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.4rem 0.75rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.inspector-tab-btn:hover {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}

.inspector-tab-btn.active {
  color: var(--accent-primary);
  background: var(--bg-surface);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.tab-i {
  font-size: 16px;
}

.copy-active-btn {
  font-size: 0.78rem;
}

.prompt-panel {
  padding: 0.9rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.panel-hint {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.hint-icon {
  font-size: 16px;
  color: var(--accent-primary);
  flex-shrink: 0;
  margin-top: 1px;
}

.code-box {
  margin: 0;
  padding: 0.85rem 1rem;
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.82rem;
  line-height: 1.55;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 38vh;
  overflow-y: auto;
}

.cli-box {
  color: var(--accent-primary);
  background: rgba(14, 165, 233, 0.05);
  border-color: rgba(14, 165, 233, 0.2);
}

.narrative-box {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--text-primary);
}

.panel-hint {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.hint-left {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex: 1;
}

.hint-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.auto-gen-btn {
  background: var(--primary-container, #eaddff);
  color: var(--primary-on-container, #21005d);
  font-weight: 600;
  border: 1px solid var(--primary);
  border-radius: 9999px;
  padding: 0.2rem 0.6rem;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.edit-btn {
  border-radius: 9999px;
  padding: 0.2rem 0.6rem;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.save-btn {
  background: var(--primary);
  color: #ffffff;
  border-radius: 9999px;
  padding: 0.2rem 0.6rem;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.edit-prompt-textarea {
  width: 100%;
  box-sizing: border-box;
  font-family: inherit;
  font-size: 0.85rem;
  line-height: 1.5;
  padding: 0.6rem 0.8rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-primary);
  resize: vertical;
}

.empty-prompt-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1.75rem 1.25rem;
  text-align: center;
  background: var(--bg-surface-secondary);
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-sm);
  gap: 0.4rem;
}

.empty-prompt-icon {
  font-size: 32px;
  color: var(--text-muted);
}

.empty-prompt-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
  margin: 0;
}

.empty-prompt-desc {
  font-size: 0.8rem;
  color: var(--text-secondary);
  max-width: 360px;
  margin: 0 0 0.4rem 0;
  line-height: 1.4;
}

.auto-gen-primary-btn {
  background: var(--accent-primary);
  color: #fff;
  border: none;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 1rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.82rem;
  transition: all 0.15s ease;
}

.auto-gen-primary-btn:hover:not(:disabled) {
  opacity: 0.92;
  transform: translateY(-1px);
}

.empty-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 0.25rem;
}
</style>
