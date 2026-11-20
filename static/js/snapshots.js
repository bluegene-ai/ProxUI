// static/js/snapshots.js — VM/LXC snapshot card on the guest detail page

const NAME_RE = /^[A-Za-z][A-Za-z0-9_-]{1,39}$/;

export function vmSnapshots(node, vmid, vmType) {
  const U = window.ProxUtils;
  return {
    vmType,
    snapshots: [],
    current: null,
    loading: true,
    error: '',
    busy: false,
    createForm: { name: '', description: '', vmstate: false },
    // Destructive actions go through this staging object so the confirm dialog
    // can name the snapshot it is about to destroy.
    pending: { action: '', name: '', start: false },
    _createModal: null,
    _confirmModal: null,

    fmtDate(ts) { return ts ? U.formatDateTime(ts) : '—'; },

    get nameError() {
      const n = this.createForm.name.trim();
      if (!n) return '';
      if (n === 'current') return "“current” 为 Proxmox 保留名称";
      if (!NAME_RE.test(n)) return '使用 2–40 个字符：以字母开头，其后可含字母、数字、_ 或 -';
      if (this.snapshots.some(s => s.name === n)) return '已存在同名快照';
      return '';
    },
    get canCreate() {
      return !!this.createForm.name.trim() && !this.nameError && !this.busy;
    },
    get confirmTitle() {
      return this.pending.action === 'rollback' ? '回滚到快照' : '删除快照';
    },

    async load() {
      this.loading = true; this.error = '';
      try {
        const r = await U.apiJson(`/api/vm/${node}/${vmid}/snapshots`);
        this.snapshots = r.snapshots || [];
        this.current = r.current || null;
        this.vmType = r.vm_type || this.vmType;
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },

    openCreate() {
      this.createForm = { name: '', description: '', vmstate: false };
      this._createModal = this._createModal || new bootstrap.Modal(this.$refs.createModal);
      this._createModal.show();
    },

    async submitCreate() {
      if (!this.canCreate) return;
      this.busy = true;
      try {
        const r = await U.apiJson(`/api/vm/${node}/${vmid}/snapshots`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: this.createForm.name.trim(),
            description: this.createForm.description.trim(),
            vmstate: this.vmType === 'qemu' && this.createForm.vmstate,
          }),
        });
        this._createModal.hide();
        U.notify(r.message + '进度显示在最近任务中。', 'success');
        setTimeout(() => this.load(), 2000);
      } catch (e) {
        U.notify('快照启动失败：' + e.message, 'error');
      } finally {
        this.busy = false;
      }
    },

    ask(action, snap) {
      this.pending = { action, name: snap.name, start: false };
      this._confirmModal = this._confirmModal || new bootstrap.Modal(this.$refs.confirmModal);
      this._confirmModal.show();
    },

    async runPending() {
      const { action, name, start } = this.pending;
      this.busy = true;
      try {
        const r = action === 'rollback'
          ? await U.apiJson(`/api/vm/${node}/${vmid}/snapshots/${encodeURIComponent(name)}/rollback`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ start }),
            })
          : await U.apiJson(`/api/vm/${node}/${vmid}/snapshots/${encodeURIComponent(name)}`, {
              method: 'DELETE',
            });
        this._confirmModal.hide();
        U.notify(r.message + '进度显示在最近任务中。', 'success');
        setTimeout(() => this.load(), 2000);
      } catch (e) {
        U.notify(`快照操作（${action}）失败：` + e.message, 'error');
      } finally {
        this.busy = false;
      }
    },

    init() { this.load(); },
  };
}
