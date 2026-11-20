#!/usr/bin/env python3
"""Build i18n/dict/special.json from i18n/dict/special.skeleton.json.

The skeleton holds the *exact* source snippets (including newlines and Jinja
expressions), so keys are guaranteed to match the templates byte for byte.
Translations below are positional; None means "leave this node in English".

Chinese literals inside Jinja are intentionally used (e.g. '虚拟机'/'容器') so the
rendered text reads naturally in every branch.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKELETON = os.path.join(ROOT, "i18n", "dict", "special.skeleton.json")
OUT = os.path.join(ROOT, "i18n", "dict", "special.json")

VM_OR_CT = "{{ '虚拟机' if vm_type == 'qemu' else '容器' }}"
CT_OR_VM = "{{ '容器' if vm_type == 'lxc' else '虚拟机' }}"

T = {
    0: "{{ current_cluster.name }} 的计划作业与已存储备份",
    1: "{{ cluster.name }} · {{ cluster.nodes|length }} 个节点",
    2: "{{ existing_clusters|length }} 个集群",
    3: "{{ cluster.nodes|length }} 个节点",
    4: "{{ current_cluster.name }} 的数据中心级防火墙 · 节点与客户机规则位于各自详情页",
    5: "{{ online_nodes }} 个在线",
    6: "{{ current_cluster.name }} 的节点更新",
    7: "{{ guests|length }} 个客户机",
    9: "集群内共 {{ storages|length }} 个存储",
    10: "克隆虚拟机 {{ config.name or vmid }}",
    12: "{{ config.cores or 1 }} 个核心",
    13: "控制台 - {{ vm_name }} | Proxmox Manager",
    14: (
        f"此{VM_OR_CT}正在迁移至 {{{{ migration_info.target }}}}。\n"
        "            开始于 {{ migration_info.start_time }}。"
    ),
    15: "· 任务 ID：{{ migration_info.task_id }}",
    16: "备份 {{ vmid }}",
    17: (
        '已用 {{ "%.1f"|format(disk.used_gb) }} / {{ "%.1f"|format(disk.total_gb) }} GB\n'
        '                            （空闲 {{ "%.1f"|format(disk.free_gb) }} GB）'
    ),
    20: "{{ value.parsed|length }} 个 SSH 密钥",
    21: "为 {{ vmid }} 创建快照",
    22: f"将{CT_OR_VM} {{{{ vmid }}}} 回滚到快照",
    23: f"迁移{VM_OR_CT} {{{{ vmid }}}}",
    24: f"删除{CT_OR_VM} {{{{ vmid }}}}",
    25: f"确定要删除{CT_OR_VM}",
    26: (
        f"？\n                                这将永久移除{CT_OR_VM}的配置、所有磁盘与数据，"
        "以及所有快照（如有）。"
    ),
    27: f"删除{CT_OR_VM}",
    28: f"编辑{CT_OR_VM} {{{{ vm.name }}}}",
    29: (
        f"部分配置更改需要先关闭{CT_OR_VM}才能生效。\n"
        f"    内存与 CPU 的更改可应用于运行中的{CT_OR_VM}，但可能需要重启才能达到最佳性能。"
    ),
    30: f"{CT_OR_VM}配置",
    31: f"节点启动时自动启动{CT_OR_VM}",
    32: f"{CT_OR_VM}将在 Proxmox 节点启动时自动启动",
    33: "{{ resources|length }} 个客户机",
    34: "VMID：{{ vm.vmid }}",
    35: "{{ vm.maxcpu }} 个 vCPU",
}


def main():
    skel = json.load(open(SKELETON, encoding="utf-8"))
    keys = list(skel.keys())
    out = {}
    for idx, key in enumerate(keys):
        val = T.get(idx)
        if val:
            out[key] = val
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"specials written: {len(out)} / {len(keys)} nodes")
    missing = [i for i in range(len(keys)) if i not in T]
    print(f"left in English (by index): {missing}")


if __name__ == "__main__":
    main()
