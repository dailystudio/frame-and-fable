import { reactive } from 'vue';

export async function getWorkspaces() {
  const res = await fetch('/api/workspaces');
  if (!res.ok) {
    throw new Error(`Failed to load workspaces: ${res.status} ${res.statusText}`);
  }
  const data = await res.json();
  return data.workspaces || [];
}

export const workspaceSettingsCache = reactive({});

export async function getWorkspace(stem) {
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}`);
  if (!res.ok) {
    throw new Error(`Failed to load workspace '${stem}': ${res.statusText}`);
  }
  const data = await res.json();
  if (data.settings) {
    workspaceSettingsCache[stem] = data.settings;
  }
  return data;
}

export async function getWorkspaceSettings(stem) {
  if (!stem) return null;
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/settings`);
  if (!res.ok) {
    throw new Error(`Failed to load settings for workspace '${stem}': ${res.statusText}`);
  }
  const data = await res.json();
  workspaceSettingsCache[stem] = data;
  return data;
}

export async function saveWorkspaceSettings(stem, settings) {
  if (!stem) return null;
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to save workspace settings: ${res.statusText}`);
  }
  const data = await res.json();
  workspaceSettingsCache[stem] = data.settings;
  return data.settings;
}

export function resolveTagSettings(settings, tagId, mediaType = 'image') {
  const globalImg = settings?.global?.image || { ratio: '16:9', size: '1K', model: 'gemini-3.1-flash-image' };
  const globalVid = settings?.global?.video || { ratio: '16:9', model: 'veo-2.0-generate-001', duration: '5s' };
  const globalDefaults = mediaType === 'video' ? globalVid : globalImg;

  const sceneOverride = settings?.scenes?.[tagId] || {};
  const hasRatioOverride = Boolean(sceneOverride.ratio && sceneOverride.ratio !== 'inherit');
  const hasSizeOverride = Boolean(sceneOverride.size && sceneOverride.size !== 'inherit');
  const hasModelOverride = Boolean(sceneOverride.model && sceneOverride.model !== 'inherit');

  const effectiveRatio = hasRatioOverride ? sceneOverride.ratio : (globalDefaults.ratio || '16:9');
  const effectiveSize = hasSizeOverride ? sceneOverride.size : (globalDefaults.size || '1K');
  const effectiveModel = hasModelOverride ? sceneOverride.model : globalDefaults.model;

  return {
    isOverridden: hasRatioOverride || hasSizeOverride || hasModelOverride,
    hasRatioOverride,
    hasSizeOverride,
    hasModelOverride,
    ratio: effectiveRatio,
    size: effectiveSize,
    model: effectiveModel,
    overrideRatio: sceneOverride.ratio || 'inherit',
    overrideSize: sceneOverride.size || 'inherit',
    overrideModel: sceneOverride.model || 'inherit',
    globalRatio: globalDefaults.ratio || '16:9',
    globalSize: globalDefaults.size || '1K',
    globalModel: globalDefaults.model
  };
}

export function getAssetUrl(stem, relativePath) {
  if (!relativePath) return '';
  if (relativePath.startsWith('http://') || relativePath.startsWith('https://') || relativePath.startsWith('/api/asset/')) {
    return relativePath;
  }
  const cleanPath = relativePath.startsWith('/') ? relativePath.slice(1) : relativePath;
  return `/api/asset/${encodeURIComponent(stem)}/${cleanPath}`;
}

export function getCharImageUrl(stem, charName, imgName) {
  if (!imgName) return '';
  return `/api/asset/${encodeURIComponent(stem)}/char-ref/${encodeURIComponent(charName)}/${encodeURIComponent(imgName)}`;
}

export function getStyleImageUrl(stem, imgName) {
  if (!imgName) return '';
  return `/api/asset/${encodeURIComponent(stem)}/style-ref/${encodeURIComponent(imgName)}`;
}

export async function uploadReferenceImage(stem, { type, characterName, filename, imageBase64 }) {
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/upload-ref`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type,
      character_name: characterName,
      filename,
      image_base64: imageBase64
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to upload reference image: ${res.statusText}`);
  }
  return await res.json();
}

export async function deleteReferenceImage(stem, { type, characterName, filename }) {
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/delete-ref`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type,
      character_name: characterName,
      filename
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to delete reference image: ${res.statusText}`);
  }
  return await res.json();
}

export function getGenerationSettings() {
  try {
    const raw = localStorage.getItem('storybook_gen_settings');
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return {
    ratio: '16:9',
    size: '1K',
    model: 'gemini-3.1-flash-image'
  };
}

export function saveGenerationSettings(settings) {
  try {
    localStorage.setItem('storybook_gen_settings', JSON.stringify(settings));
  } catch (e) {}
}

export async function generateAsset(stem, { tagId, section, type = 'image', ratio, size, model }) {
  const wsSettings = workspaceSettingsCache[stem];
  const tagResolved = wsSettings ? resolveTagSettings(wsSettings, tagId, type) : null;
  const defaults = getGenerationSettings();

  const effectiveRatio = (ratio && ratio !== 'inherit') ? ratio : (tagResolved?.ratio || defaults.ratio || '16:9');
  const effectiveSize = (size && size !== 'inherit') ? size : (tagResolved?.size || defaults.size || '1K');
  const effectiveModel = (model && model !== 'inherit') ? model : (tagResolved?.model || defaults.model || (type === 'video' ? 'veo-2.0-generate-001' : 'gemini-3.1-flash-image'));

  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tag_id: tagId,
      section,
      type,
      ratio: effectiveRatio,
      size: effectiveSize,
      model: effectiveModel
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to generate asset: ${res.statusText}`);
  }
  return await res.json();
}

export const generationState = reactive({
  activeMap: {}
});

const completionCallbacks = new Set();

export function onGenerationComplete(callback) {
  completionCallbacks.add(callback);
  return () => completionCallbacks.delete(callback);
}

export function getGenerationStatus(stem, tagId) {
  if (!stem || !tagId) return null;
  const key = `${stem}::${tagId}`;
  return generationState.activeMap[key] || null;
}

export function isTagGenerating(stem, tagId) {
  const status = getGenerationStatus(stem, tagId);
  return status?.status === 'generating';
}

export async function runTagGeneration(stem, { tagId, section, type = 'image', ratio, size, model }) {
  if (!stem || !tagId) return;
  const key = `${stem}::${tagId}`;

  // If already generating, avoid duplicate concurrent executions
  if (generationState.activeMap[key]?.status === 'generating') {
    return;
  }

  const wsSettings = workspaceSettingsCache[stem];
  const tagResolved = wsSettings ? resolveTagSettings(wsSettings, tagId, type) : null;
  const defaults = getGenerationSettings();

  const effectiveRatio = (ratio && ratio !== 'inherit') ? ratio : (tagResolved?.ratio || defaults.ratio || '16:9');
  const effectiveSize = (size && size !== 'inherit') ? size : (tagResolved?.size || defaults.size || '1K');
  const effectiveModel = (model && model !== 'inherit') ? model : (tagResolved?.model || defaults.model || (type === 'video' ? 'veo-2.0-generate-001' : 'gemini-3.1-flash-image'));

  const engineName = type === 'video' ? 'Veo' : 'Gemini 3.1 Flash Image';
  generationState.activeMap[key] = {
    stem,
    tagId,
    section,
    type,
    ratio: effectiveRatio,
    size: effectiveSize,
    model: effectiveModel,
    status: 'generating',
    message: `Invoking ${engineName} (${effectiveRatio}${type === 'image' ? ', ' + effectiveSize : ''})...`,
    startTime: Date.now()
  };

  try {
    const res = await generateAsset(stem, {
      tagId,
      section,
      type,
      ratio: effectiveRatio,
      size: effectiveSize,
      model: effectiveModel
    });
    if (res.success) {
      generationState.activeMap[key] = {
        stem,
        tagId,
        section,
        type,
        status: 'done',
        message: `Asset generated successfully for ${tagId}!`,
        completedTime: Date.now(),
        timestamp: Date.now()
      };

      // Notify subscribers to reload workspace data
      completionCallbacks.forEach(cb => {
        try { cb(null, { stem, tagId, section, type, res }); } catch (e) { console.error(e); }
      });

      // Clear 'done' notification after 5s
      setTimeout(() => {
        if (generationState.activeMap[key]?.status === 'done') {
          delete generationState.activeMap[key];
        }
      }, 5000);

      return res;
    } else {
      const errMsg = res.error || 'Generation failed';
      generationState.activeMap[key] = {
        stem,
        tagId,
        section,
        type,
        status: 'error',
        message: `Generation failed: ${errMsg}`,
        completedTime: Date.now()
      };
      completionCallbacks.forEach(cb => {
        try { cb(new Error(errMsg), { stem, tagId, section, type }); } catch (e) {}
      });
      throw new Error(errMsg);
    }
  } catch (err) {
    generationState.activeMap[key] = {
      stem,
      tagId,
      section,
      type,
      status: 'error',
      message: `Error: ${err.message}`,
      completedTime: Date.now()
    };
    completionCallbacks.forEach(cb => {
      try { cb(err, { stem, tagId, section, type }); } catch (e) {}
    });
    throw err;
  }
}

export async function buildPrompt(stem, { type = 'image', section = '', beforeText = '', afterText = '', tagId = '', useAi = false } = {}) {
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/build-prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type,
      section,
      before_text: beforeText,
      after_text: afterText,
      tag_id: tagId,
      use_ai: useAi
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to build prompt: ${res.statusText}`);
  }
  return await res.json();
}

export async function insertTag(stem, { tagId, type = 'image', section = '', prompt = '', insertAfterText = '', afterTagId = '' }) {
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/insert-tag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tag_id: tagId,
      type,
      section,
      prompt,
      insert_after_text: insertAfterText,
      after_tag_id: afterTagId
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to insert tag: ${res.statusText}`);
  }
  return await res.json();
}

export async function updateTagPrompt(stem, { tagId, prompt }) {
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/update-tag-prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tag_id: tagId,
      prompt
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to update tag prompt: ${res.statusText}`);
  }
  return await res.json();
}

export async function enrichPrompts(stem, { force = false, useAi = false } = {}) {
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/enrich-prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force, use_ai: useAi })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to enrich prompts: ${res.statusText}`);
  }
  return await res.json();
}
