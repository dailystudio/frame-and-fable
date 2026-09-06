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

  const extraPrompt = sceneOverride.extra_prompt || '';

  return {
    isOverridden: hasRatioOverride || hasSizeOverride || hasModelOverride || Boolean(extraPrompt),
    hasRatioOverride,
    hasSizeOverride,
    hasModelOverride,
    hasExtraPrompt: Boolean(extraPrompt),
    extraPrompt,
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

export function getStoredApiKey() {
  try {
    return localStorage.getItem('storybook_gemini_api_key') || '';
  } catch (e) {
    return '';
  }
}

export function setStoredApiKey(key) {
  try {
    if (key) {
      localStorage.setItem('storybook_gemini_api_key', key);
    } else {
      localStorage.removeItem('storybook_gemini_api_key');
    }
  } catch (e) {}
}

export async function fetchServerApiKeyStatus() {
  try {
    const res = await fetch('/api/settings/api-key');
    if (!res.ok) return { has_key: false, masked_key: '' };
    return await res.json();
  } catch (e) {
    return { has_key: false, masked_key: '' };
  }
}

export async function saveServerApiKey(apiKey) {
  setStoredApiKey(apiKey);
  const res = await fetch('/api/settings/api-key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to save API key: ${res.statusText}`);
  }
  return await res.json();
}

export async function generateAsset(stem, { tagId, section, type = 'image', ratio, size, model, extraPrompt, apiKey }) {
  const wsSettings = workspaceSettingsCache[stem];
  const tagResolved = wsSettings ? resolveTagSettings(wsSettings, tagId, type) : null;
  const defaults = getGenerationSettings();

  const effectiveRatio = (ratio && ratio !== 'inherit') ? ratio : (tagResolved?.ratio || defaults.ratio || '16:9');
  const effectiveSize = (size && size !== 'inherit') ? size : (tagResolved?.size || defaults.size || '1K');
  const effectiveModel = (model && model !== 'inherit') ? model : (tagResolved?.model || defaults.model || (type === 'video' ? 'veo-2.0-generate-001' : 'gemini-3.1-flash-image'));
  const effectiveExtraPrompt = extraPrompt !== undefined ? extraPrompt : (tagResolved?.extraPrompt || '');
  const effectiveApiKey = apiKey || getStoredApiKey() || '';

  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tag_id: tagId,
      section,
      type,
      ratio: effectiveRatio,
      size: effectiveSize,
      model: effectiveModel,
      extra_prompt: effectiveExtraPrompt,
      api_key: effectiveApiKey
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

export const tasksState = reactive({
  tasks: [],
  loading: false,
  runningCount: 0,
  failedCount: 0,
  lastSync: null
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

const notifiedTasks = new Set();
let syncPollingTimer = null;

export async function fetchWorkspaceTasks(stem) {
  if (!stem) return [];
  try {
    const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/tasks`);
    if (!res.ok) return [];
    const data = await res.json();
    const tasks = data.tasks || [];
    tasksState.tasks = tasks;
    tasksState.runningCount = tasks.filter(t => t.status === 'running').length;
    tasksState.failedCount = tasks.filter(t => t.status === 'failed').length;
    tasksState.lastSync = Date.now();

    const runningTagIds = new Set();

    // Sync running and completed tasks
    tasks.forEach(task => {
      if (!task.tag_id) return;
      const key = `${stem}::${task.tag_id}`;
      if (task.status === 'running') {
        runningTagIds.add(task.tag_id);
        if (!generationState.activeMap[key] || generationState.activeMap[key].status !== 'generating') {
          generationState.activeMap[key] = {
            stem,
            tagId: task.tag_id,
            taskId: task.id,
            section: task.section,
            type: task.type,
            ratio: task.ratio,
            size: task.size,
            model: task.model,
            extraPrompt: task.extra_prompt,
            status: 'generating',
            message: `Generating ${task.tag_id} (${task.model || ''})...`,
            startTime: task.started_at ? new Date(task.started_at).getTime() : Date.now()
          };
        }
      } else if (task.status === 'completed') {
        if (generationState.activeMap[key]) {
          delete generationState.activeMap[key];
        }
        if (!notifiedTasks.has(task.id)) {
          notifiedTasks.add(task.id);
          completionCallbacks.forEach(cb => {
            try { cb(null, { stem, tagId: task.tag_id, section: task.section, type: task.type, res: task }); } catch (e) {}
          });
        }
      } else if (task.status === 'failed') {
        if (generationState.activeMap[key]) {
          delete generationState.activeMap[key];
        }
      }
    });

    // Clear stale activeMap entries for this stem that are not running on the server
    Object.keys(generationState.activeMap).forEach(key => {
      const item = generationState.activeMap[key];
      if (item && item.stem === stem && item.status === 'generating') {
        if (!runningTagIds.has(item.tagId)) {
          if (Date.now() - (item.startTime || 0) > 3000) {
            delete generationState.activeMap[key];
          }
        }
      }
    });

    // Schedule next poll ONLY if tasks are actively running on server
    if (tasksState.runningCount > 0) {
      if (!syncPollingTimer) {
        syncPollingTimer = setTimeout(() => {
          syncPollingTimer = null;
          fetchWorkspaceTasks(stem);
        }, 2000);
      }
    } else {
      if (syncPollingTimer) {
        clearTimeout(syncPollingTimer);
        syncPollingTimer = null;
      }
    }

    return tasks;
  } catch (e) {
    console.error('[fetchWorkspaceTasks] Error:', e);
    return [];
  }
}

export async function clearWorkspaceTasks(stem) {
  if (!stem) return [];
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/tasks/clear`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to clear tasks: ${res.statusText}`);
  const data = await res.json();
  const tasks = data.tasks || [];
  tasksState.tasks = tasks;
  tasksState.runningCount = tasks.filter(t => t.status === 'running').length;
  tasksState.failedCount = tasks.filter(t => t.status === 'failed').length;
  return tasks;
}

export async function retryTask(stem, taskId) {
  if (!stem || !taskId) return;
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/tasks/retry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to retry task: ${res.statusText}`);
  }
  const data = await res.json();
  await fetchWorkspaceTasks(stem);
  return data;
}

export async function cancelTask(stem, taskId) {
  if (!stem || !taskId) return;
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/tasks/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to cancel task: ${res.statusText}`);
  }
  const data = await res.json();
  await fetchWorkspaceTasks(stem);
  return data;
}

export async function runTagGeneration(stem, { tagId, section, type = 'image', ratio, size, model, extraPrompt, apiKey }) {
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
  const effectiveExtraPrompt = extraPrompt !== undefined ? extraPrompt : (tagResolved?.extraPrompt || '');
  const effectiveApiKey = apiKey || getStoredApiKey() || '';

  const engineName = type === 'video' ? 'Veo' : 'Gemini 3.1 Flash Image';
  generationState.activeMap[key] = {
    stem,
    tagId,
    section,
    type,
    ratio: effectiveRatio,
    size: effectiveSize,
    model: effectiveModel,
    extraPrompt: effectiveExtraPrompt,
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
      model: effectiveModel,
      extraPrompt: effectiveExtraPrompt,
      apiKey: effectiveApiKey
    });

    const taskId = res.task_id;
    if (taskId) {
      generationState.activeMap[key].taskId = taskId;
      // Trigger tasks refresh so Generations tab updates immediately
      fetchWorkspaceTasks(stem);

      // Poll task until finished
      return new Promise((resolve, reject) => {
        const checkInterval = setInterval(async () => {
          try {
            const tasks = await fetchWorkspaceTasks(stem);
            const currentTask = tasks.find(t => t.id === taskId);
            if (!currentTask) return;

            if (currentTask.status === 'completed') {
              clearInterval(checkInterval);
              generationState.activeMap[key] = {
                stem,
                tagId,
                section,
                type,
                status: 'done',
                message: `Asset generated successfully for ${tagId}!`,
                assetUrl: currentTask.asset_url,
                completedTime: Date.now(),
                timestamp: Date.now()
              };

              completionCallbacks.forEach(cb => {
                try { cb(null, { stem, tagId, section, type, res: currentTask }); } catch (e) { console.error(e); }
              });

              setTimeout(() => {
                if (generationState.activeMap[key]?.status === 'done') {
                  delete generationState.activeMap[key];
                }
              }, 5000);

              resolve({ success: true, ...currentTask });
            } else if (currentTask.status === 'failed') {
              clearInterval(checkInterval);
              const errMsg = currentTask.error || currentTask.stderr || 'Generation failed';
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
                try { cb(new Error(errMsg), { stem, tagId, section, type, res: currentTask }); } catch (e) {}
              });

              reject(new Error(errMsg));
            } else {
              // Still running - update progress message with elapsed time
              const elapsed = Math.round((Date.now() - generationState.activeMap[key].startTime) / 1000);
              generationState.activeMap[key].message = `Generating ${tagId} (${engineName}, ${elapsed}s)...`;
            }
          } catch (err) {
            console.error('[runTagGeneration poll error]:', err);
          }
        }, 1200);
      });
    }

    // Fallback if no task_id returned
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
      completionCallbacks.forEach(cb => {
        try { cb(null, { stem, tagId, section, type, res }); } catch (e) { console.error(e); }
      });
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

export async function buildPrompt(stem, { type = 'image', section = '', beforeText = '', afterText = '', tagId = '', useAi = false, apiKey = '' } = {}) {
  const effectiveApiKey = apiKey || getStoredApiKey() || '';
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/build-prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type,
      section,
      before_text: beforeText,
      after_text: afterText,
      tag_id: tagId,
      use_ai: useAi,
      api_key: effectiveApiKey
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

export async function enrichPrompts(stem, { force = false, useAi = false, apiKey = '' } = {}) {
  const effectiveApiKey = apiKey || getStoredApiKey() || '';
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}/enrich-prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force, use_ai: useAi, api_key: effectiveApiKey })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to enrich prompts: ${res.statusText}`);
  }
  return await res.json();
}
