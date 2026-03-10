"""
工作流显式连线迁移脚本

用途:
1. 将历史“按数组顺序执行”的工作流，批量补成显式连线并写回数据库

用法:
  python -X utf8 workflow_links.py --dry-run
  python -X utf8 workflow_links.py
  python -X utf8 workflow_links.py --only-enabled
  python -X utf8 workflow_links.py --backup ./workflow_backup.json
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask
from config import config as app_config
from Models import db, Workflow


EDGE_FIELDS = ("next_node", "true_next", "false_next", "true_branch", "false_branch", "loop_body")


def normalize_explicit_links(workflow_steps: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """按引擎兼容逻辑补全显式连线，返回 。"""
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

        true_field = "true_branch" if "true_branch" in config else ("true_next" if "true_next" in config else "")
        false_field = "false_branch" if "false_branch" in config else ("false_next" if "false_next" in config else "")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量将工作流补齐为显式连线")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写数据库")
    parser.add_argument("--only-enabled", action="store_true", help="仅处理启用中的工作流")
    parser.add_argument("--backup", type=str, default="", help="备份文件路径(JSON)")
    parser.add_argument("--no-backup", action="store_true", help="写库时不自动备份")
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
        backup_records: list[dict[str, Any]] = []

        for wf in workflows:
            config = wf.get_config() or {}
            old_steps = config.get("workflow", [])
            new_steps, patched_count = normalize_explicit_links(old_steps)
            if patched_count <= 0:
                continue

            changed += 1
            patched_total += patched_count
            backup_records.append(
                {
                    "id": wf.id,
                    "name": wf.name,
                    "enabled": wf.enabled,
                    "patched_count": patched_count,
                    "workflow_before": old_steps,
                }
            )

            if not args.dry_run:
                config["workflow"] = new_steps
                wf.config = config
                print(f"[UPDATE] id={wf.id} name={wf.name} patched={patched_count}")
            else:
                print(f"[DRY-RUN] id={wf.id} name={wf.name} patched={patched_count}")

        if args.dry_run:
            print(f"\n完成(预览): total={total}, changed={changed}, patched_edges={patched_total}")
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
                "records": backup_records,
            }
            backup_path.write_text(
                json.dumps(backup_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[BACKUP] {backup_path.resolve()}")

        db.session.commit()
        db.session.remove()
        print(f"\n迁移完成: total={total}, changed={changed}, patched_edges={patched_total}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
