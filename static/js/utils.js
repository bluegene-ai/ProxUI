// static/js/utils.js — shared frontend helpers (ES module)

export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text == null ? '' : String(text);
  return div.innerHTML;
}

export function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes <= 0) return '0 B';
  const k = 1024;
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(decimals)} ${units[i]}`;
}

export function formatUptime(seconds) {
  seconds = Number(seconds) || 0;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h`;
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

export const TASK_TYPE_NAMES = {
  qmstart: '启动虚拟机', qmstop: '停止虚拟机', qmshutdown: '关闭虚拟机',
  qmreset: '重置虚拟机', qmreboot: '重启虚拟机', qmigrate: '迁移虚拟机',
  qmclone: '克隆虚拟机', qmcreate: '创建虚拟机', qmdestroy: '销毁虚拟机',
  qmtemplate: '创建虚拟机模板', qmrestore: '恢复虚拟机',
  vzstart: '启动容器', vzstop: '停止容器', vzshutdown: '关闭容器',
  vzmigrate: '迁移容器', vzclone: '克隆容器', vzcreate: '创建容器',
  vzdestroy: '销毁容器', vzdump: '备份容器',
  vzrestore: '恢复容器',
  download: '下载 ISO', aptupdate: '更新软件包数据库',
  startall: '批量启动虚拟机与容器', stopall: '批量停止虚拟机与容器',
  srvreload: 'SRV 网络 - 重载', vncproxy: 'VNC 控制台',
  clusterjoin: '添加节点到集群', resize: '磁盘扩容',
  imgdel: '删除存储卷',
};

export function taskTypeName(type) {
  return TASK_TYPE_NAMES[type] || (type ? String(type).toUpperCase() : 'UNKNOWN');
}

// Items from /api/activity: native Proxmox tasks (source "pve") and ProxUI
// jobs (source "proxui") share one shape.
export function activityTitle(item) {
  if (item.title) return item.title;
  const name = taskTypeName(item.type);
  return item.vmid ? `${name} ${item.vmid}` : name;
}

export function activityUrl(item) {
  return `/tasks/${encodeURIComponent(item.id)}`;
}

export function activityVmUrl(item) {
  if (!item.vmid || !item.node) return null;
  return `/vm/${encodeURIComponent(item.node)}/${encodeURIComponent(item.vmid)}`;
}

export function activityIsActive(item) {
  return item.status === 'running' || item.status === 'queued';
}

const ACTIVITY_STATUS = {
  running: { label: '运行中', pill: 'info', color: 'primary', icon: 'bi-arrow-repeat spin' },
  queued:  { label: 'Queued',  pill: 'info', color: 'secondary', icon: 'bi-clock' },
  ok:      { label: 'OK',      pill: 'ok',   color: 'success', icon: 'bi-check-circle' },
  warning: { label: 'Warnings', pill: 'maint', color: 'warning', icon: 'bi-exclamation-triangle' },
  failed:  { label: '失败',  pill: 'err',  color: 'danger', icon: 'bi-x-circle' },
};
const ACTIVITY_STATUS_UNKNOWN = { label: 'Unknown', pill: 'info', color: 'secondary', icon: 'bi-dash-circle' };

export function activityStatus(item) {
  return ACTIVITY_STATUS[item?.status] || ACTIVITY_STATUS_UNKNOWN;
}

export function formatDuration(secs) {
  if (secs == null || secs < 0) return '';
  secs = Math.floor(secs);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
}

export function activityDuration(item) {
  if (!item.started_at) return '';
  if (item.ended_at) return formatDuration(item.ended_at - item.started_at);
  if (activityIsActive(item)) return formatDuration(Date.now() / 1000 - item.started_at);
  return '';
}

const DEMO_MODE = window.DEMO_MODE === true;

export async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let errorMessage;
    try {
      const data = await response.clone().json();
      errorMessage = data.error || data.message || response.statusText;
    } catch {
      errorMessage = response.statusText;
    }
    if (DEMO_MODE && (response.status === 403 || response.status === 401)) {
      errorMessage = '演示模式：此操作需要写权限，演示环境不提供。';
    }
    const error = new Error(errorMessage);
    error.status = response.status;
    error.response = response;
    throw error;
  }
  return response;
}

export async function apiJson(url, options = {}) {
  return (await apiFetch(url, options)).json();
}

/**
 * Adaptive poller: calls fn() on a base interval when the tab is active,
 * backs off exponentially when hidden, stops after the 10-minute step,
 * and immediately refreshes + resets when the tab becomes visible again.
 *
 * Backoff when hidden: baseMs → 60s → 2m → 5m → 10m → stop
 */
export function createAdaptivePoller(fn, baseMs = 30000) {
  const hiddenDelays = [60_000, 120_000, 300_000, 600_000];
  let timerId = null;
  let hiddenCount = 0;
  let active = true;

  function scheduleNext() {
    if (!active) return;
    const delay = (document.hidden && hiddenCount > 0)
      ? hiddenDelays[Math.min(hiddenCount - 1, hiddenDelays.length - 1)]
      : baseMs;
    timerId = setTimeout(tick, delay);
  }

  function tick() {
    timerId = null;
    if (!active) return;
    if (document.hidden) {
      hiddenCount++;
      if (hiddenCount > hiddenDelays.length) return; // stop; resumes on focus
    } else {
      hiddenCount = 0;
      fn();
    }
    scheduleNext();
  }

  function onVisible() {
    if (!active || document.hidden) return;
    clearTimeout(timerId);
    timerId = null;
    hiddenCount = 0;
    fn();
    scheduleNext();
  }

  document.addEventListener('visibilitychange', onVisible);
  scheduleNext();

  return {
    destroy() {
      active = false;
      clearTimeout(timerId);
      document.removeEventListener('visibilitychange', onVisible);
    },
  };
}

/**
 * Format a Unix timestamp (seconds) for a chart x-axis label, using the
 * *browser's* local timezone — Date's locale methods are always
 * timezone-correct for whoever is viewing the page, unlike formatting the
 * timestamp on the server (which depends on the server/container's own
 * timezone and is frequently wrong, e.g. Docker images defaulting to UTC).
 */
export function formatChartLabel(unixSeconds, timeframe) {
  const d = new Date(unixSeconds * 1000);
  switch (timeframe) {
    case 'hour':
    case 'day':
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    case 'week':
      return d.toLocaleDateString([], { month: '2-digit', day: '2-digit' }) + ' ' +
        d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    case 'month':
      return d.toLocaleDateString([], { month: '2-digit', day: '2-digit' });
    default: // year
      return d.toLocaleDateString([], { year: 'numeric', month: '2-digit' });
  }
}

/** Format a Unix timestamp (seconds) as a full local date+time string. */
export function formatDateTime(unixSeconds) {
  if (!unixSeconds) return 'Unknown';
  return new Date(unixSeconds * 1000).toLocaleString([], {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export function notify(message, type = 'info') {
  const cls = type === 'error' ? 'danger' : type;
  const el = document.createElement('div');
  el.className = `alert alert-${cls} alert-dismissible fade show position-fixed`;
  el.style.cssText = 'top:20px;right:20px;z-index:10000;min-width:300px;';
  el.textContent = message;
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'btn-close';
  btn.setAttribute('data-bs-dismiss', 'alert');
  el.appendChild(btn);
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}
