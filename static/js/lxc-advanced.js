// static/js/lxc-advanced.js — Alpine component for LXC Advanced / Passthrough

const LXC_FLAGS = [
  { key: 'nesting', label: 'Nesting', desc: 'LXC 内运行 Docker、systemd、嵌套 LXC' },
  { key: 'keyctl',  label: 'Keyctl',  desc: '密钥保留服务（部分应用需要）' },
  { key: 'fuse',    label: 'FUSE',    desc: '用户态文件系统支持' },
  { key: 'mount',   label: 'Mount',   desc: '挂载任意文件系统（cifs、nfs…）' },
  { key: 'mknod',   label: 'Mknod',   desc: '允许在非特权容器中执行 mknod' },
];

const QUICKSYNC_DEVICES = [
  { label: 'renderD128（QuickSync / VA-API）', path: '/dev/dri/renderD128', gid: '104', uid: '0' },
  { label: 'card0（DRI 主设备）',              path: '/dev/dri/card0',      gid: '44',  uid: '0' },
  { label: 'card1（DRI 次设备）',            path: '/dev/dri/card1',      gid: '44',  uid: '0' },
  { label: 'net/tun（Tailscale）',              path: '/dev/net/tun',        gid: '',    uid: '' },
  { label: 'fuse',                             path: '/dev/fuse',           gid: '',    uid: '' },
  { label: 'kvm',                              path: '/dev/kvm',            gid: '',    uid: '' },
];

const IDMAP_PRESETS = {
  full_u: { type: 'u', ct_id: 0, host_id: 100000, count: 65536 },
  full_g: { type: 'g', ct_id: 0, host_id: 100000, count: 65536 },
  root_u: { type: 'u', ct_id: 0, host_id: 0,      count: 1 },
  root_g: { type: 'g', ct_id: 0, host_id: 0,      count: 1 },
};

export function lxcAdvanced(node, vmid) {
  return {
    node, vmid,
    loading: true,
    errorMsg: '',
    LXC_FLAGS,

    features: {},
    desiredFeatures: {},
    devices: [],
    legacyDevices: [],
    mounts: [],
    idmaps: [],
    profiles: [],

    isRunning: false,
    canWrite: true,
    isRoot: true,
    supportsDevN: true,
    pveVersion: '',
    hasBackup: false,
    backupTimestamp: '',

    flash: { show: false, cls: '', msg: '' },

    dev: { preset: '', path: '', gid: '', uid: '0' },
    idmap: { preset: '', type: 'u', ct_id: 0, host_id: 100000, count: 65536 },
    mount: { host_path: '', mp: '', ro: false, backup: false },

    previewDiffText: '',
    previewRunningWarn: false,
    pendingFeatures: {},

    profileDiff: null,
    profileTitle: '',
    profileApplyId: null,

    modalError: '',
    busy: { addDevice: false, addIdmap: false, addMount: false, applyFeatures: false, applyProfile: false },
    _modals: {},

    get idmapPreviewText() {
      return `lxc.idmap = ${this.idmap.type} ${this.idmap.ct_id} ${this.idmap.host_id} ${this.idmap.count}`;
    },

    get profileApplyDisabled() {
      const d = this.profileDiff;
      if (!d || d.loading || d.error) return true;
      if (d.alreadyApplied) return true;
      if (d.running && d.devicesRequireStop) return true;
      if (!d.supportsDevN && d.devicesToAdd && d.devicesToAdd.length > 0) return true;
      return false;
    },

    init() {
      ['addDeviceModal', 'addIdmapModal', 'addMountModal', 'previewModal', 'profileDiffModal']
        .forEach(r => { this._modals[r] = new bootstrap.Modal(this.$refs[r]); });
      this.load();
    },

    destroy() {
      Object.values(this._modals).forEach(m => m.dispose());
    },

    openModal(name) { this._modals[name + 'Modal']?.show(); },
    closeModal(name) { this._modals[name + 'Modal']?.hide(); },

    showFlash(cls, msg) {
      this.flash = { show: true, cls, msg };
      setTimeout(() => { this.flash.show = false; }, 5000);
    },

    async load() {
      this.loading = true;
      this.errorMsg = '';
      try {
        const [fData, dData, mData, iData] = await Promise.all([
          window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/features`),
          window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/devices`),
          window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/mounts`),
          window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/idmap`),
        ]);

        if (fData.error && dData.error && mData.error && iData.error) {
          this.errorMsg = fData.error;
          return;
        }

        this.features = fData.features || {};
        const df = {};
        LXC_FLAGS.forEach(f => { df[f.key] = (this.features[f.key] === '1'); });
        this.desiredFeatures = df;

        this.isRunning = fData.running || dData.running || mData.running || iData.running;
        this.canWrite = (fData.can_write !== false) && (dData.can_write !== false);
        this.isRoot = mData.is_root !== false;
        this.supportsDevN = dData.pve_supports_dev_n !== false;
        this.pveVersion = dData.pve_version || '';
        this.hasBackup = !!fData.has_backup;
        this.backupTimestamp = fData.backup_timestamp || '';

        this.devices = dData.devices || [];
        this.legacyDevices = dData.legacy_devices || [];
        this.mounts = mData.mounts || [];
        this.idmaps = iData.idmaps || [];
      } catch {
        this.errorMsg = '加载高级配置失败';
      } finally {
        this.loading = false;
      }
      await this.loadProfiles();
    },

    refresh() { this.load(); },

    async loadProfiles() {
      try {
        const data = await window.ProxUtils.apiJson('/api/lxc-profiles');
        this.profiles = data.profiles || [];
      } catch {
        this.profiles = [];
      }
    },

    idmapDesc(m) {
      const end = m.ct_id + m.count - 1;
      const hEnd = m.host_id + m.count - 1;
      return `${m.ct_id}–${end} → ${m.host_id}–${hEnd} (${m.count})`;
    },

    // ── Feature flags ──────────────────────────────────────────────────────────

    previewFeatures() {
      const desired = {};
      LXC_FLAGS.forEach(f => { desired[f.key] = this.desiredFeatures[f.key] ? '1' : '0'; });
      const before = Object.entries(this.features).filter(([, v]) => v === '1').map(([k]) => `${k}=1`).join(',') || '(none)';
      const after = Object.entries(desired).filter(([, v]) => v === '1').map(([k]) => `${k}=1`).join(',') || '(none)';
      this.previewDiffText = `features: ${before}\n       → ${after}`;
      this.previewRunningWarn = this.isRunning;
      this.pendingFeatures = desired;
      this.openModal('preview');
    },

    async applyFeatures() {
      this.busy.applyFeatures = true;
      try {
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/features`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ features: this.pendingFeatures }),
        });
        this.closeModal('preview');
        this.showFlash(data.success ? 'success' : 'danger', data.success ? data.message : data.error);
        if (data.success) this.load();
      } catch(e) {
        this.closeModal('preview');
        this.showFlash('danger', e.message || '请求失败');
      } finally {
        this.busy.applyFeatures = false;
      }
    },

    // ── Devices ────────────────────────────────────────────────────────────────

    openAddDevice() {
      this.dev = { preset: '', path: '', gid: '', uid: '0' };
      this.modalError = '';
      this.openModal('addDevice');
    },

    applyDevicePreset() {
      const opt = QUICKSYNC_DEVICES[this.dev.preset];
      if (!opt) return;
      this.dev.path = opt.path;
      this.dev.gid = opt.gid;
      this.dev.uid = opt.uid;
    },

    async addDevice() {
      if (!this.dev.path.trim()) { this.modalError = '需要填写设备路径'; return; }
      this.busy.addDevice = true;
      this.modalError = '';
      try {
        const body = { path: this.dev.path.trim() };
        if (this.dev.gid) body.gid = this.dev.gid;
        if (this.dev.uid) body.uid = this.dev.uid;
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/devices`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        this.closeModal('addDevice');
        this.showFlash('success', data.message);
        this.load();
      } catch(e) {
        this.modalError = e.message || '请求失败';
      } finally {
        this.busy.addDevice = false;
      }
    },

    async removeDevice(key) {
      if (!confirm(`移除设备条目 ${key}？`)) return;
      try {
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/devices/${key}`, { method: 'DELETE' });
        this.showFlash(data.success ? 'success' : 'danger', data.success ? data.message : data.error);
        if (data.success) this.load();
      } catch(e) {
        this.showFlash('danger', e.message || '请求失败');
      }
    },

    // ── Mounts ─────────────────────────────────────────────────────────────────

    openAddMount() {
      this.mount = { host_path: '', mp: '', ro: false, backup: false };
      this.modalError = '';
      this.openModal('addMount');
    },

    async addMount() {
      if (!this.mount.host_path.trim() || !this.mount.mp.trim()) {
        this.modalError = '宿主机路径与容器路径均为必填'; return;
      }
      this.busy.addMount = true;
      this.modalError = '';
      try {
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/mounts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            host_path: this.mount.host_path.trim(),
            mp: this.mount.mp.trim(),
            ro: this.mount.ro,
            backup: this.mount.backup,
          }),
        });
        this.closeModal('addMount');
        this.showFlash('success', data.message);
        this.load();
      } catch(e) {
        this.modalError = e.message || '请求失败';
      } finally {
        this.busy.addMount = false;
      }
    },

    async removeMount(key) {
      if (!confirm(`移除挂载 ${key}？`)) return;
      try {
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/mounts/${key}`, { method: 'DELETE' });
        this.showFlash(data.success ? 'success' : 'danger', data.success ? data.message : data.error);
        if (data.success) this.load();
      } catch(e) {
        this.showFlash('danger', e.message || '请求失败');
      }
    },

    // ── UID/GID idmap ──────────────────────────────────────────────────────────

    openAddIdmap() {
      this.idmap = { preset: '', type: 'u', ct_id: 0, host_id: 100000, count: 65536 };
      this.modalError = '';
      this.openModal('addIdmap');
    },

    applyIdmapPreset() {
      const p = IDMAP_PRESETS[this.idmap.preset];
      if (!p) return;
      this.idmap.type = p.type;
      this.idmap.ct_id = p.ct_id;
      this.idmap.host_id = p.host_id;
      this.idmap.count = p.count;
    },

    async addIdmap() {
      const { type, ct_id, host_id, count } = this.idmap;
      if (!type || isNaN(ct_id) || isNaN(host_id) || isNaN(count)) {
        this.modalError = '所有字段均为必填'; return;
      }
      this.busy.addIdmap = true;
      this.modalError = '';
      try {
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/idmap`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type, ct_id: +ct_id, host_id: +host_id, count: +count }),
        });
        this.closeModal('addIdmap');
        this.showFlash('success', data.message);
        this.load();
      } catch(e) {
        this.modalError = e.message || '请求失败';
      } finally {
        this.busy.addIdmap = false;
      }
    },

    async removeIdmap(key) {
      if (!confirm(`移除 idmap 条目 ${key}？`)) return;
      try {
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/idmap/${key}`, { method: 'DELETE' });
        this.showFlash(data.success ? 'success' : 'danger', data.success ? data.message : data.error);
        if (data.success) this.load();
      } catch(e) {
        this.showFlash('danger', e.message || '请求失败');
      }
    },

    // ── Restore ────────────────────────────────────────────────────────────────

    async restore() {
      if (!confirm('恢复写入前的配置快照？这将撤销所有高级/直通相关的更改。')) return;
      try {
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/config-restore`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
        });
        this.showFlash(data.success ? 'success' : 'danger', data.success ? data.message : data.error);
        if (data.success) this.load();
      } catch(e) {
        this.showFlash('danger', e.message || '请求失败');
      }
    },

    // ── Profiles ───────────────────────────────────────────────────────────────

    async openPreviewProfile(profileId, profileName) {
      this.profileApplyId = profileId;
      this.profileTitle = profileName + '— 预览';
      this.profileDiff = {
        loading: true, error: '', alreadyApplied: false,
        featuresToAdd: [], devicesToAdd: [],
        featuresAlreadySet: [], devicesAlreadyPresent: [],
        running: false, devicesRequireStop: false, supportsDevN: true,
      };
      this.openModal('profileDiff');
      try {
        const diff = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/profile-diff/${profileId}`);
        if (diff.error) {
          this.profileDiff = { ...this.profileDiff, loading: false, error: diff.error };
          return;
        }
        this.profileDiff = {
          loading: false,
          error: '',
          alreadyApplied: !diff.changes_needed,
          featuresToAdd: diff.features_to_add || [],
          devicesToAdd: diff.devices_to_add || [],
          featuresAlreadySet: diff.features_already_set || [],
          devicesAlreadyPresent: diff.devices_already_present || [],
          running: !!diff.running,
          devicesRequireStop: !!diff.devices_require_stop,
          supportsDevN: diff.pve_supports_dev_n !== false,
        };
      } catch {
        this.profileDiff = { ...this.profileDiff, loading: false, error: '加载差异失败' };
      }
    },

    async applyProfile() {
      this.busy.applyProfile = true;
      try {
        const data = await window.ProxUtils.apiJson(`/api/vm/${node}/${vmid}/lxc/profile-apply/${this.profileApplyId}`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
        });
        this.closeModal('profileDiff');
        this.showFlash(data.success ? 'success' : 'danger', data.success ? data.message : data.error);
        if (data.success) this.load();
      } catch(e) {
        this.showFlash('danger', e.message || '请求失败');
      } finally {
        this.busy.applyProfile = false;
      }
    },
  };
}
