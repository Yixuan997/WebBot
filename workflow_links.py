"""
工作流一体化迁移脚本

用途：
1. 将历史“按数组顺序执行”的工作流，批量补成显式连线并写回数据库
2. 将旧变量引用一次性升级为新变量：
   - user_id -> sender.user_id
   - sender_name -> sender.nickname

用法：
  python -X utf8 workflow_links.py --dry-run
  python -X utf8 workflow_links.py
  python -X utf8 workflow_links.py --only-enabled
  python -X utf8 workflow_links.py --backup ./workflow_backup.json
  python -X utf8 workflow_links.py --links-only
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask

from config import config as app_config
from Models import db, Workflow


EDGE_FIELDS = ("next_node", "true_branch", "false_branch", "loop_body")
LEGACY_VAR_MAP = {
    "user_id": "sender.user_id",
    "sender_name": "sender.nickname",
}
TEMPLATE_REPLACEMENTS = (
    (re.compile(r"\{\{\s*user_id\s*\}\}"), "{{sender.user_id}}"),
    (re.compile(r"\{\{\s*sender_name\s*\}\}"), "{{sender.nickname}}"),
)


def normalize_explicit_links(workflow_steps: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """按纯连线模式补全显式连线，返回 (新步骤列表, 补边数量)。"""
    steps = copy.deepcopy(workflow_steps or [])
    if len(steps) < 2:
        return steps, 0

    patched_count = 0

    for idx in range(len(steps) - 1):
        current = steps[idx] or {}
        next_step = steps[idx + 1] or {}
        node_type = current.get("type")
        if node_type == "end":
            continue

        next_id = next_step.get("id")
        if not next_id:
            continue

        config = current.get("config") or {}
        if any(config.get(field) for field in EDGE_FIELDS):
            continue

        if node_type == "start":
            config["next_node"] = next_id
            current["config"] = config
            patched_count += 1
            continue

        true_field = "true_branch" if "true_branch" in config else ""
        false_field = "false_branch" if "false_branch" in config else ""
        if true_field or false_field:
            if true_field:
                config[true_field] = next_id
            if false_field:
                config[false_field] = next_id
            current["config"] = config
            patched_count += 1
            continue

        config["next_node"] = next_id
        current["config"] = config
        patched_count += 1

    return steps, patched_count


def _replace_template_refs(text: str) -> tuple[str, int]:
    replaced = text
    changed = 0
    for pattern, target in TEMPLATE_REPLACEMENTS:
        replaced, count = pattern.subn(target, replaced)
        changed += count
    return replaced, changed


def _replace_condition_rule_vars(text: str) -> tuple[str, int]:
    """替换条件规则文本中的旧变量名，如 user_id|equals|123。"""
    changed = 0
    lines = text.splitlines()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "|" not in line:
            new_lines.append(line)
            continue

        match = re.match(r"^(\s*)([^|]+?)(\s*)\|(.*)$", line)
        if not match:
            new_lines.append(line)
            continue

        left = match.group(2).strip()
        if left in LEGACY_VAR_MAP:
            new_left = LEGACY_VAR_MAP[left]
            new_line = f"{match.group(1)}{new_left}{match.group(3)}|{match.group(4)}"
            new_lines.append(new_line)
            changed += 1
            continue

        new_lines.append(line)

    return "\n".join(new_lines), changed


def _migrate_legacy_variables(data: Any, parent_key: str = "") -> tuple[Any, int]:
    changed = 0

    if isinstance(data, dict):
        migrated: dict[str, Any] = {}
        for key, value in data.items():
            if key == "variable_name" and isinstance(value, str) and value in LEGACY_VAR_MAP:
                migrated[key] = LEGACY_VAR_MAP[value]
                changed += 1
                continue

            migrated_value, sub_changed = _migrate_legacy_variables(value, key)
            migrated[key] = migrated_value
            changed += sub_changed
        return migrated, changed

    if isinstance(data, list):
        migrated_list = []
        for item in data:
            migrated_item, sub_changed = _migrate_legacy_variables(item, parent_key)
            migrated_list.append(migrated_item)
            changed += sub_changed
        return migrated_list, changed

    if isinstance(data, str):
        result = data

        if parent_key in ("conditions", "rules"):
            result, rule_changed = _replace_condition_rule_vars(result)
            changed += rule_changed

        result, tpl_changed = _replace_template_refs(result)
        changed += tpl_changed
        return result, changed

    return data, changed


def migrate_workflow_steps(
    workflow_steps: list[dict[str, Any]],
    *,
    migrate_legacy_vars: bool = True,
) -> tuple[list[dict[str, Any]], int, int]:
    """返回 (新步骤, 补边数, 变量迁移替换数)。"""
    steps, patched_edges = normalize_explicit_links(workflow_steps)
    migrated_refs = 0

    if not migrate_legacy_vars:
        return steps, patched_edges, migrated_refs

    for step in steps:
        if not isinstance(step, dict) or "config" not in step:
            continue
        migrated_config, changed = _migrate_legacy_variables(step.get("config"), "config")
        if changed > 0:
            step["config"] = migrated_config
            migrated_refs += changed

    return steps, patched_edges, migrated_refs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量迁移工作流：显式连线 + 旧变量引用升级"
    )
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写数据库")
    parser.add_argument("--only-enabled", action="store_true", help="仅处理启用中的工作流")
    parser.add_argument("--backup", type=str, default="", help="备份文件路径(JSON)")
    parser.add_argument("--no-backup", action="store_true", help="写库时不自动备份")
    parser.add_argument("--links-only", action="store_true", help="仅补显式连线，不迁移旧变量引用")
    return parser.parse_args()


def create_migration_app() -> Flask:
    """创建轻量应用上下文，仅用于数据库访问，不启动业务组件。"""
    flask_app = Flask(__name__)
    flask_app.config.from_object(app_config)
    app_config.init_app(flask_app)
    db.init_app(flask_app)
    return flask_app


def main() -> int:
    args = parse_args()
    migration_app = create_migration_app()

    with migration_app.app_context():
        query = Workflow.query
        if args.only_enabled:
            query = query.filter_by(enabled=True)
        workflows = query.order_by(Workflow.id.asc()).all()

        total = len(workflows)
        changed = 0
        patched_total = 0
        migrated_total = 0
        backup_records: list[dict[str, Any]] = []

        for wf in workflows:
            config = wf.get_config() or {}
            old_steps = config.get("workflow", [])
            new_steps, patched_count, migrated_count = migrate_workflow_steps(
                old_steps,
                migrate_legacy_vars=not args.links_only,
            )
            if patched_count <= 0 and migrated_count <= 0:
                continue

            changed += 1
            patched_total += patched_count
            migrated_total += migrated_count
            backup_records.append(
                {
                    "id": wf.id,
                    "name": wf.name,
                    "enabled": wf.enabled,
                    "patched_edges": patched_count,
                    "migrated_refs": migrated_count,
                    "workflow_before": old_steps,
                }
            )

            if not args.dry_run:
                config["workflow"] = new_steps
                wf.config = config
                print(
                    f"[UPDATE] id={wf.id} name={wf.name} "
                    f"patched_edges={patched_count} migrated_refs={migrated_count}"
                )
            else:
                print(
                    f"[DRY-RUN] id={wf.id} name={wf.name} "
                    f"patched_edges={patched_count} migrated_refs={migrated_count}"
                )

        if args.dry_run:
            print(
                f"\n完成(预览): total={total}, changed={changed}, "
                f"patched_edges={patched_total}, migrated_refs={migrated_total}"
            )
            return 0

        if changed == 0:
            print(f"\n无需迁移: total={total}, changed=0")
            return 0

        if not args.no_backup:
            backup_path = Path(args.backup) if args.backup else Path(
                f"workflow_links_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            backup_payload = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "total_workflows": total,
                "changed_workflows": changed,
                "patched_edges": patched_total,
                "migrated_refs": migrated_total,
                "records": backup_records,
            }
            backup_path.write_text(
                json.dumps(backup_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[BACKUP] {backup_path.resolve()}")

        db.session.commit()
        db.session.remove()
        print(
            f"\n迁移完成: total={total}, changed={changed}, "
            f"patched_edges={patched_total}, migrated_refs={migrated_total}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
