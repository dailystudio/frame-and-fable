<template>
  <div class="tasks-tab">
    <!-- Header & Statistics -->
    <div class="tasks-header">
      <div class="header-titles">
        <h2 class="section-title">Generation Activity & Task History</h2>
        <p class="section-subtitle">
          Track real-time progress, inspect detailed execution logs, manage history, and retry generations for scene prompts, images, and videos.
        </p>
      </div>

      <!-- Quick Metrics Pills -->
      <div class="metrics-row">
        <div class="metric-pill" :class="{ active: statusFilter === 'all' }" @click="statusFilter = 'all'">
          <span class="metric-num">{{ tasks.length }}</span>
          <span class="metric-label">Total Tasks</span>
        </div>
        <div
          class="metric-pill metric-running"
          :class="{ active: statusFilter === 'running', 'has-running': runningTasks.length > 0 }"
          @click="statusFilter = 'running'"
        >
          <span class="material-symbols-rounded is-spinning" v-if="runningTasks.length > 0">sync</span>
          <span class="metric-num">{{ runningTasks.length }}</span>
          <span class="metric-label">Running</span>
        </div>
        <div class="metric-pill metric-completed" :class="{ active: statusFilter === 'completed' }" @click="statusFilter = 'completed'">
          <span class="material-symbols-rounded">check_circle</span>
          <span class="metric-num">{{ completedTasks.length }}</span>
          <span class="metric-label">Completed</span>
        </div>
        <div
          class="metric-pill metric-failed"
          :class="{ active: statusFilter === 'failed', 'has-failed': failedTasks.length > 0 }"
          @click="statusFilter = 'failed'"
        >
          <span class="material-symbols-rounded">error</span>
          <span class="metric-num">{{ failedTasks.length }}</span>
          <span class="metric-label">Failed</span>
        </div>
      </div>
    </div>

    <!-- Filter & Control Toolbar -->
    <div class="toolbar-card clean-card">
      <div class="toolbar-left">
        <!-- Status Filter Tabs -->
        <div class="filter-group">
          <span class="filter-label">Status:</span>
          <div class="btn-toggle-group">
            <button
              type="button"
              class="toggle-btn"
              :class="{ active: statusFilter === 'all' }"
              @click="statusFilter = 'all'"
            >
              All ({{ tasks.length }})
            </button>
            <button
              type="button"
              class="toggle-btn"
              :class="{ active: statusFilter === 'running' }"
              @click="statusFilter = 'running'"
            >
              Running ({{ runningTasks.length }})
            </button>
            <button
              type="button"
              class="toggle-btn"
              :class="{ active: statusFilter === 'completed' }"
              @click="statusFilter = 'completed'"
            >
              Completed ({{ completedTasks.length }})
            </button>
            <button
              type="button"
              class="toggle-btn"
              :class="{ active: statusFilter === 'failed' }"
              @click="statusFilter = 'failed'"
            >
              Failed ({{ failedTasks.length }})
            </button>
          </div>
        </div>

        <!-- Type Filter -->
        <div class="filter-group">
          <span class="filter-label">Type:</span>
          <select v-model="typeFilter" class="clean-select toolbar-select">
            <option value="all">All Types</option>
            <option value="image">Images</option>
            <option value="video">Videos</option>
            <option value="prompt">Prompts</option>
            <option value="batch_prompt">Batch Prompts</option>
          </select>
        </div>

        <!-- Search Input -->
        <div class="search-box">
          <span class="material-symbols-rounded search-icon">search</span>
          <input
            v-model="searchQuery"
            type="text"
            class="clean-input search-input"
            placeholder="Search by tag, model, prompt, error..."
          />
          <button
            v-if="searchQuery"
            type="button"
            class="clear-search-btn"
            @click="searchQuery = ''"
          >
            <span class="material-symbols-rounded">close</span>
          </button>
        </div>
      </div>

      <div class="toolbar-right">
        <!-- Refresh Button -->
        <button
          type="button"
          class="clean-btn clean-btn-sm"
          title="Refresh tasks from server"
          :disabled="isRefreshing"
          @click="refreshTasks"
        >
          <span class="material-symbols-rounded" :class="{ 'is-spinning': isRefreshing }">refresh</span>
          <span>Refresh</span>
        </button>

        <!-- Clear History Button -->
        <button
          type="button"
          class="clean-btn clean-btn-sm btn-clear"
          title="Clear completed and failed generation history"
          :disabled="tasks.length === 0 || tasks.every(t => t.status === 'running')"
          @click="clearHistory"
        >
          <span class="material-symbols-rounded">delete_sweep</span>
          <span>Clear History</span>
        </button>
      </div>
    </div>

    <!-- Active Running Tasks Banner (if any running) -->
    <div v-if="runningTasks.length > 0 && statusFilter !== 'running'" class="running-banner clean-card">
      <div class="running-banner-left">
        <span class="material-symbols-rounded is-spinning">sync</span>
        <div>
          <strong>{{ runningTasks.length }} Active Generation{{ runningTasks.length > 1 ? 's' : '' }} in Progress</strong>
          <span class="running-tags">
            ({{ runningTasks.map(t => t.tag_id || t.type).join(', ') }})
          </span>
        </div>
      </div>
      <button
        type="button"
        class="clean-btn clean-btn-sm"
        @click="statusFilter = 'running'"
      >
        View Running Tasks
      </button>
    </div>

    <!-- Tasks List -->
    <div v-if="filteredTasks.length > 0" class="tasks-list">
      <div
        v-for="task in filteredTasks"
        :key="task.id"
        class="task-card clean-card"
        :class="[`status-${task.status}`, `type-${task.type}`]"
      >
        <!-- Card Header -->
        <div class="task-head">
          <div class="task-head-left">
            <!-- Status Badge -->
            <span class="task-status-badge" :class="task.status">
              <span v-if="task.status === 'running'" class="pulse-dot"></span>
              <span class="material-symbols-rounded status-icon">
                {{ getStatusIcon(task.status) }}
              </span>
              <span>{{ getStatusText(task) }}</span>
            </span>

            <!-- Type Chip -->
            <span class="clean-badge type-badge">
              <span class="material-symbols-rounded">{{ getTypeIcon(task.type) }}</span>
              <span>{{ formatType(task.type) }}</span>
            </span>

            <!-- Tag ID Chip -->
            <span v-if="task.tag_id" class="clean-badge tag-badge" :title="'Tag: ' + task.tag_id">
              <span class="material-symbols-rounded">label</span>
              <strong>{{ task.tag_id }}</strong>
            </span>

            <!-- Section Chip -->
            <span v-if="task.section" class="clean-badge sec-badge">
              <span class="material-symbols-rounded">bookmark</span>
              <span>{{ task.section }}</span>
            </span>
          </div>

          <div class="task-head-right">
            <!-- Timestamp -->
            <span class="task-time" :title="task.started_at">
              <span class="material-symbols-rounded">schedule</span>
              {{ formatTime(task.started_at) }}
            </span>
          </div>
        </div>

        <!-- Task Metadata Row -->
        <div class="task-meta-row" v-if="task.model || task.ratio || task.size || task.extra_prompt">
          <span v-if="task.model" class="meta-chip">
            <span class="material-symbols-rounded">psychology</span>
            {{ task.model }}
          </span>
          <span v-if="task.ratio" class="meta-chip">
            <span class="material-symbols-rounded">aspect_ratio</span>
            {{ task.ratio }}
          </span>
          <span v-if="task.size" class="meta-chip">
            <span class="material-symbols-rounded">high_res</span>
            {{ task.size }}
          </span>
          <span v-if="task.extra_prompt" class="meta-chip extra-prompt-chip" :title="task.extra_prompt">
            <span class="material-symbols-rounded">add_circle</span>
            Extra: {{ truncate(task.extra_prompt, 40) }}
          </span>
        </div>

        <!-- Prompt Section -->
        <div v-if="task.prompt" class="task-prompt-box">
          <div class="task-prompt-head">
            <span class="prompt-title">
              <span class="material-symbols-rounded">description</span>
              Scene Prompt
            </span>
            <button
              type="button"
              class="clean-btn clean-btn-xs"
              @click="copyText(task.prompt, `prompt_${task.id}`)"
            >
              <span class="material-symbols-rounded">
                {{ copiedKey === `prompt_${task.id}` ? 'check' : 'content_copy' }}
              </span>
              {{ copiedKey === `prompt_${task.id}` ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <p class="task-prompt-text" :class="{ collapsed: !expandedPrompts[task.id] && task.prompt.length > 200 }">
            {{ task.prompt }}
          </p>
          <button
            v-if="task.prompt.length > 200"
            type="button"
            class="expand-text-btn"
            @click="togglePrompt(task.id)"
          >
            {{ expandedPrompts[task.id] ? 'Show Less' : 'Show Full Prompt' }}
          </button>
        </div>

        <!-- Error Banner (if Failed) -->
        <div v-if="task.status === 'failed'" class="task-error-box">
          <div class="error-box-head">
            <span class="material-symbols-rounded">error</span>
            <strong>Generation Failure Notice</strong>
          </div>
          <pre class="error-message-text">{{ task.error || task.stderr || 'Execution failed with non-zero exit code.' }}</pre>
        </div>

        <!-- Asset Thumbnail Preview (if Completed with Media) -->
        <div v-if="task.status === 'completed' && task.asset_url" class="asset-preview-box">
          <div class="asset-thumb-container">
            <img
              v-if="task.type === 'image'"
              :src="task.asset_url"
              :alt="task.tag_id"
              class="asset-thumb-img"
              @click="previewTaskAsset(task)"
            />
            <video
              v-else-if="task.type === 'video'"
              :src="task.asset_url"
              class="asset-thumb-video"
              controls
            />
          </div>
          <div class="asset-info">
            <div class="asset-status-line">
              <span class="material-symbols-rounded text-success">check_circle</span>
              <span>Asset generated and saved to workspace</span>
            </div>
            <button
              type="button"
              class="clean-btn clean-btn-sm preview-btn"
              @click="previewTaskAsset(task)"
            >
              <span class="material-symbols-rounded">zoom_in</span>
              <span>Preview in Lightbox</span>
            </button>
          </div>
        </div>

        <!-- Terminal Execution Logs Drawer -->
        <div class="task-logs-drawer">
          <button
            type="button"
            class="logs-toggle-btn"
            @click="toggleLogs(task.id)"
          >
            <span class="material-symbols-rounded">terminal</span>
            <span>
              {{ expandedLogs[task.id] ? 'Hide Execution Logs' : 'View Terminal / Execution Logs' }}
            </span>
            <span v-if="task.stdout || task.stderr" class="logs-indicator">
              ({{ getLogLineCount(task) }} lines)
            </span>
            <span class="material-symbols-rounded chevron-icon">
              {{ expandedLogs[task.id] ? 'expand_less' : 'expand_more' }}
            </span>
          </button>

          <div v-if="expandedLogs[task.id]" class="terminal-container">
            <div class="terminal-toolbar">
              <span class="terminal-title">Terminal Console Output</span>
              <button
                type="button"
                class="clean-btn clean-btn-xs"
                @click="copyText(getCombinedLogs(task), `log_${task.id}`)"
              >
                <span class="material-symbols-rounded">
                  {{ copiedKey === `log_${task.id}` ? 'check' : 'content_copy' }}
                </span>
                {{ copiedKey === `log_${task.id}` ? 'Copied' : 'Copy Logs' }}
              </button>
            </div>
            <div class="terminal-body">
              <pre class="terminal-output">{{ getCombinedLogs(task) || 'No output logged.' }}</pre>
            </div>
          </div>
        </div>

        <!-- Card Footer Actions -->
        <div class="task-actions-bar">
          <div class="actions-left">
            <span class="task-duration">
              <span class="material-symbols-rounded">timer</span>
              {{ getDurationText(task) }}
            </span>
          </div>

          <div class="actions-right">
            <!-- Cancel Button if running -->
            <button
              v-if="task.status === 'running'"
              type="button"
              class="clean-btn clean-btn-sm btn-cancel-task"
              @click="handleCancel(task)"
            >
              <span class="material-symbols-rounded">cancel</span>
              <span>Cancel Task</span>
            </button>

            <!-- Retry Button if completed or failed (images/videos) -->
            <button
              v-if="task.status !== 'running' && (task.type === 'image' || task.type === 'video')"
              type="button"
              class="clean-btn clean-btn-sm btn-retry-task"
              :disabled="retryingTaskId === task.id"
              @click="handleRetry(task)"
            >
              <span class="material-symbols-rounded" :class="{ 'is-spinning': retryingTaskId === task.id }">
                replay
              </span>
              <span>Retry Generation</span>
            </button>

            <!-- Jump to Tag in Reader -->
            <button
              v-if="task.tag_id"
              type="button"
              class="clean-btn clean-btn-sm"
              title="View in Story Reader"
              @click="$emit('switch-tab', 'reader')"
            >
              <span class="material-symbols-rounded">auto_stories</span>
              <span>Story Reader</span>
            </button>

            <!-- Jump to Media Tags Review -->
            <button
              v-if="task.tag_id"
              type="button"
              class="clean-btn clean-btn-sm"
              title="View in Media Tags Review"
              @click="$emit('switch-tab', 'tags')"
            >
              <span class="material-symbols-rounded">local_offer</span>
              <span>Media Tags</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="empty-state clean-card">
      <span class="material-symbols-rounded empty-icon">manage_search</span>
      <h3>No Tasks Found</h3>
      <p v-if="searchQuery || statusFilter !== 'all' || typeFilter !== 'all'">
        No generation tasks match your current search and filter criteria.
      </p>
      <p v-else>
        No generation tasks recorded yet. Click <strong>Generate</strong> on any scene tag or prompt to start generating. All progress and logs will be tracked here in real-time.
      </p>
      <button
        v-if="searchQuery || statusFilter !== 'all' || typeFilter !== 'all'"
        type="button"
        class="clean-btn clean-btn-sm"
        @click="resetFilters"
      >
        Reset Filters
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, reactive, watch } from 'vue';
import {
  tasksState,
  fetchWorkspaceTasks,
  clearWorkspaceTasks,
  retryTask,
  cancelTask
} from '../services/api';

const props = defineProps({
  stem: {
    type: String,
    required: true
  }
});

const emit = defineEmits(['preview', 'switch-tab', 'refresh']);

const statusFilter = ref('all');
const typeFilter = ref('all');
const searchQuery = ref('');
const isRefreshing = ref(false);
const retryingTaskId = ref(null);
const copiedKey = ref('');

const expandedLogs = reactive({});
const expandedPrompts = reactive({});
const now = ref(Date.now());

let timerInterval = null;

onMounted(() => {
  if (props.stem) {
    refreshTasks();
  }
  // Tick every second for live elapsed timers
  timerInterval = setInterval(() => {
    now.value = Date.now();
  }, 1000);
});

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval);
});

watch(() => props.stem, (newStem) => {
  if (newStem) {
    refreshTasks();
  }
});

const tasks = computed(() => tasksState.tasks || []);

const runningTasks = computed(() => tasks.value.filter(t => t.status === 'running'));
const completedTasks = computed(() => tasks.value.filter(t => t.status === 'completed'));
const failedTasks = computed(() => tasks.value.filter(t => t.status === 'failed'));

const filteredTasks = computed(() => {
  return tasks.value.filter(task => {
    // 1. Status Filter
    if (statusFilter.value !== 'all' && task.status !== statusFilter.value) {
      return false;
    }
    // 2. Type Filter
    if (typeFilter.value !== 'all' && task.type !== typeFilter.value) {
      return false;
    }
    // 3. Search Query
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase();
      const matchTag = (task.tag_id || '').toLowerCase().includes(q);
      const matchSec = (task.section || '').toLowerCase().includes(q);
      const matchModel = (task.model || '').toLowerCase().includes(q);
      const matchPrompt = (task.prompt || '').toLowerCase().includes(q);
      const matchErr = (task.error || '').toLowerCase().includes(q);
      const matchLogs = (task.stdout || '').toLowerCase().includes(q) || (task.stderr || '').toLowerCase().includes(q);
      if (!matchTag && !matchSec && !matchModel && !matchPrompt && !matchErr && !matchLogs) {
        return false;
      }
    }
    return true;
  });
});

async function refreshTasks() {
  if (!props.stem) return;
  isRefreshing.value = true;
  try {
    await fetchWorkspaceTasks(props.stem);
  } finally {
    isRefreshing.value = false;
  }
}

async function clearHistory() {
  if (!props.stem) return;
  if (!confirm('Are you sure you want to clear completed and failed generation history?')) {
    return;
  }
  try {
    await clearWorkspaceTasks(props.stem);
  } catch (err) {
    alert(`Failed to clear history: ${err.message}`);
  }
}

async function handleRetry(task) {
  if (!props.stem || !task.id) return;
  retryingTaskId.value = task.id;
  try {
    await retryTask(props.stem, task.id);
    statusFilter.value = 'all';
    await refreshTasks();
  } catch (err) {
    alert(`Retry failed: ${err.message}`);
  } finally {
    retryingTaskId.value = null;
  }
}

async function handleCancel(task) {
  if (!props.stem || !task.id) return;
  if (!confirm(`Cancel running task for ${task.tag_id || task.type}?`)) return;
  try {
    await cancelTask(props.stem, task.id);
    await refreshTasks();
  } catch (err) {
    alert(`Cancel failed: ${err.message}`);
  }
}

function resetFilters() {
  statusFilter.value = 'all';
  typeFilter.value = 'all';
  searchQuery.value = '';
}

function toggleLogs(taskId) {
  expandedLogs[taskId] = !expandedLogs[taskId];
}

function togglePrompt(taskId) {
  expandedPrompts[taskId] = !expandedPrompts[taskId];
}

function getStatusIcon(status) {
  switch (status) {
    case 'running': return 'sync';
    case 'completed': return 'check_circle';
    case 'failed': return 'error';
    default: return 'help';
  }
}

function getStatusText(task) {
  if (task.status === 'running') {
    const elapsed = getElapsedSeconds(task);
    return `Running (${elapsed}s)`;
  }
  if (task.status === 'completed') {
    return `Completed (${task.duration_sec || 0}s)`;
  }
  if (task.status === 'failed') {
    return `Failed (${task.duration_sec || 0}s)`;
  }
  return task.status;
}

function getElapsedSeconds(task) {
  if (!task.started_at) return 0;
  const start = new Date(task.started_at).getTime();
  return Math.max(0, Math.round((now.value - start) / 1000));
}

function getDurationText(task) {
  if (task.status === 'running') {
    return `In progress for ${getElapsedSeconds(task)}s`;
  }
  if (task.duration_sec !== undefined && task.duration_sec !== null) {
    return `Finished in ${task.duration_sec}s`;
  }
  return 'Finished';
}

function getTypeIcon(type) {
  switch (type) {
    case 'image': return 'photo_camera';
    case 'video': return 'videocam';
    case 'prompt': return 'auto_fix_high';
    case 'batch_prompt': return 'playlist_add_check';
    default: return 'smart_toy';
  }
}

function formatType(type) {
  switch (type) {
    case 'image': return 'Image Generation';
    case 'video': return 'Video Generation';
    case 'prompt': return 'Prompt Auto-Gen';
    case 'batch_prompt': return 'Batch Prompts Enrichment';
    default: return type || 'Task';
  }
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
      ' (' + d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ')';
  } catch (e) {
    return isoStr;
  }
}

function truncate(str, maxLen = 60) {
  if (!str) return '';
  return str.length > maxLen ? str.slice(0, maxLen) + '...' : str;
}

function getCombinedLogs(task) {
  const parts = [];
  if (task.command) {
    parts.push(`$ ${task.command}`);
  }
  if (task.stdout) {
    parts.push(task.stdout.trim());
  }
  if (task.stderr) {
    parts.push(`[stderr]\n${task.stderr.trim()}`);
  }
  if (task.error && task.status !== 'completed') {
    parts.push(`[error]\n${task.error.trim()}`);
  }
  return parts.join('\n\n');
}

function getLogLineCount(task) {
  const text = getCombinedLogs(task);
  return text ? text.split('\n').length : 0;
}

function previewTaskAsset(task) {
  if (!task.asset_url) return;
  emit('preview', {
    type: task.type === 'video' ? 'video' : 'image',
    src: task.asset_url,
    tag: {
      id: task.tag_id,
      section: task.section,
      prompt: task.prompt,
      type: task.type
    }
  });
}

function copyText(text, key) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    copiedKey.value = key;
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = '';
    }, 2000);
  });
}
</script>

<style scoped>
.tasks-tab {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  max-width: 1200px;
  margin: 0 auto;
  padding-bottom: 3rem;
}

/* Header & Metrics */
.tasks-header {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

@media (min-width: 768px) {
  .tasks-header {
    flex-direction: row;
    justify-content: space-between;
    align-items: flex-end;
  }
}

.section-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
  color: var(--color-text-main);
}

.section-subtitle {
  font-size: 0.9rem;
  color: var(--color-text-sub);
  max-width: 600px;
  line-height: 1.4;
}

.metrics-row {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.metric-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.8rem;
  border-radius: 9999px;
  background: var(--bg-surface);
  border: 1px solid var(--color-border);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.metric-pill:hover {
  border-color: var(--color-primary);
  transform: translateY(-1px);
}

.metric-pill.active {
  background: var(--color-primary-container, #e8f0fe);
  border-color: var(--color-primary);
  color: var(--color-primary);
  font-weight: 600;
}

.metric-num {
  font-weight: 700;
  font-size: 0.92rem;
}

.metric-label {
  color: var(--color-text-sub);
}

.metric-pill.active .metric-label {
  color: inherit;
}

.metric-running.has-running {
  background: #fff8e1;
  border-color: #fbc02d;
  color: #b26a00;
  animation: pulse-border 2s infinite;
}

.metric-failed.has-failed {
  background: #ffebee;
  border-color: #ef9a9a;
  color: #c62828;
}

@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(251, 192, 45, 0.4); }
  50% { box-shadow: 0 0 0 4px rgba(251, 192, 45, 0.2); }
}

/* Toolbar */
.toolbar-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 1.25rem;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.filter-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--color-text-sub);
}

.btn-toggle-group {
  display: inline-flex;
  border-radius: 8px;
  background: var(--color-surface-subtle, #f5f5f5);
  padding: 2px;
  border: 1px solid var(--color-border);
}

.toggle-btn {
  padding: 0.3rem 0.65rem;
  border: none;
  background: transparent;
  font-size: 0.78rem;
  border-radius: 6px;
  cursor: pointer;
  color: var(--color-text-sub);
  transition: all 0.15s;
}

.toggle-btn:hover {
  color: var(--color-text-main);
}

.toggle-btn.active {
  background: var(--bg-surface, #fff);
  color: var(--color-primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.toolbar-select {
  padding: 0.35rem 0.6rem;
  font-size: 0.82rem;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 0.6rem;
  font-size: 1.1rem;
  color: var(--color-text-sub);
  pointer-events: none;
}

.search-input {
  padding: 0.4rem 1.8rem 0.4rem 2.2rem;
  font-size: 0.82rem;
  width: 240px;
  border-radius: 9999px;
}

.clear-search-btn {
  position: absolute;
  right: 0.5rem;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  color: var(--color-text-sub);
  display: flex;
}

.clear-search-btn .material-symbols-rounded {
  font-size: 1rem;
}

.btn-clear {
  color: #c62828;
}

.btn-clear:hover:not(:disabled) {
  background: #ffebee;
  border-color: #ef9a9a;
}

/* Running Banner */
.running-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.25rem;
  background: #fff8e1;
  border-color: #ffe082;
  color: #8d6e00;
}

.running-banner-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.88rem;
}

.running-tags {
  margin-left: 0.4rem;
  font-weight: normal;
  color: #a67c00;
}

/* Tasks List */
.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.task-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.1rem 1.25rem;
  transition: box-shadow 0.2s, border-color 0.2s;
  border-left: 4px solid var(--color-border);
}

.task-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}

.task-card.status-running {
  border-left-color: #fbc02d;
  background: linear-gradient(to right, #fffde7 0%, var(--bg-surface) 100%);
}

.task-card.status-completed {
  border-left-color: #4caf50;
}

.task-card.status-failed {
  border-left-color: #e53935;
  background: linear-gradient(to right, #fff8f8 0%, var(--bg-surface) 100%);
}

/* Task Head */
.task-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.task-head-left, .task-head-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.task-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.65rem;
  border-radius: 9999px;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: capitalize;
}

.task-status-badge.running {
  background: #fff8e1;
  color: #b26a00;
  border: 1px solid #fbc02d;
}

.task-status-badge.completed {
  background: #e8f5e9;
  color: #2e7d32;
  border: 1px solid #a5d6a7;
}

.task-status-badge.failed {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef9a9a;
}

.status-icon {
  font-size: 1rem;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fbc02d;
  animation: pulse-ring 1.5s infinite;
}

@keyframes pulse-ring {
  0% { transform: scale(0.9); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.5; }
  100% { transform: scale(0.9); opacity: 1; }
}

.type-badge {
  font-size: 0.78rem;
  font-weight: 600;
}

.tag-badge {
  background: var(--color-primary-container, #e8f0fe);
  color: var(--color-primary);
  border-color: transparent;
  font-size: 0.8rem;
}

.sec-badge {
  font-size: 0.76rem;
  color: var(--color-text-sub);
}

.task-time {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.76rem;
  color: var(--color-text-sub);
}

.task-time .material-symbols-rounded {
  font-size: 0.9rem;
}

/* Metadata Row */
.task-meta-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.55rem;
  background: var(--color-surface-subtle, #f0f0f0);
  border-radius: 6px;
  font-size: 0.76rem;
  font-family: monospace;
  color: var(--color-text-main);
}

.meta-chip .material-symbols-rounded {
  font-size: 0.85rem;
  color: var(--color-text-sub);
}

.extra-prompt-chip {
  background: #e3f2fd;
  color: #1565c0;
}

/* Prompt Box */
.task-prompt-box {
  background: var(--color-surface-subtle, #fafafa);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 0.7rem 0.9rem;
}

.task-prompt-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
}

.prompt-title {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.76rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-sub);
}

.prompt-title .material-symbols-rounded {
  font-size: 0.95rem;
}

.task-prompt-text {
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--color-text-main);
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.task-prompt-text.collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.expand-text-btn {
  background: none;
  border: none;
  padding: 0.25rem 0;
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--color-primary);
  cursor: pointer;
}

/* Error Box */
.task-error-box {
  background: #ffebee;
  border: 1px solid #ef9a9a;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  color: #c62828;
}

.error-box-head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  margin-bottom: 0.4rem;
}

.error-message-text {
  font-family: monospace;
  font-size: 0.8rem;
  line-height: 1.4;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 160px;
  overflow-y: auto;
  background: rgba(255,255,255,0.7);
  padding: 0.5rem;
  border-radius: 6px;
}

/* Asset Preview */
.asset-preview-box {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.6rem 0.8rem;
  background: var(--color-surface-subtle, #f5f5f5);
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.asset-thumb-container {
  width: 90px;
  height: 60px;
  border-radius: 6px;
  overflow: hidden;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.asset-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s;
}

.asset-thumb-img:hover {
  transform: scale(1.05);
}

.asset-thumb-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.asset-info {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.asset-status-line {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-main);
}

.text-success {
  color: #2e7d32;
  font-size: 1.1rem;
}

.preview-btn {
  align-self: flex-start;
}

/* Logs Drawer */
.task-logs-drawer {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.logs-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: none;
  border: none;
  padding: 0.3rem 0;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--color-text-sub);
  cursor: pointer;
  align-self: flex-start;
  transition: color 0.15s;
}

.logs-toggle-btn:hover {
  color: var(--color-primary);
}

.logs-indicator {
  font-weight: normal;
  font-size: 0.74rem;
  opacity: 0.8;
}

.chevron-icon {
  font-size: 1rem;
}

.terminal-container {
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: inset 0 2px 6px rgba(0,0,0,0.3);
}

.terminal-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #2d2d2d;
  padding: 0.35rem 0.8rem;
  border-bottom: 1px solid #3e3e3e;
}

.terminal-title {
  font-family: monospace;
  font-size: 0.75rem;
  color: #9e9e9e;
}

.terminal-body {
  padding: 0.8rem 1rem;
  max-height: 240px;
  overflow-y: auto;
}

.terminal-output {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  color: #81c784;
}

/* Card Actions Bar */
.task-actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.6rem;
  border-top: 1px solid var(--color-border);
  padding-top: 0.75rem;
}

.actions-left, .actions-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.task-duration {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: var(--color-text-sub);
}

.task-duration .material-symbols-rounded {
  font-size: 0.95rem;
}

.btn-cancel-task {
  color: #c62828;
}

.btn-cancel-task:hover {
  background: #ffebee;
  border-color: #ef9a9a;
}

.btn-retry-task {
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.btn-retry-task:hover:not(:disabled) {
  background: var(--color-primary-container, #e8f0fe);
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3.5rem 2rem;
  text-align: center;
  gap: 0.75rem;
}

.empty-icon {
  font-size: 3rem;
  color: var(--color-text-sub);
  opacity: 0.6;
}

.empty-state h3 {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0;
  color: var(--color-text-main);
}

.empty-state p {
  font-size: 0.88rem;
  color: var(--color-text-sub);
  max-width: 480px;
  line-height: 1.5;
  margin: 0;
}

.is-spinning {
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
