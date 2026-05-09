# Huey Task System — Documentation Index

This folder documents the asynchronous task processing system used for photo analysis.

| Document | What it covers |
|---|---|
| [overview.md](overview.md) | High-level architecture, queue list, entry points, pipeline phases summary |
| [pipeline_phases.md](pipeline_phases.md) | Detailed flow diagram, per-task description, phase transitions, progress tracking |
| [queues.md](queues.md) | Each queue's purpose, SQLite file location, startup hook, registered tasks, how to start workers |
| [utils_reference.md](utils_reference.md) | `phase_logic`, `_dispatch_tasks`, `_finish_task`, `_start_next_phase` — how each function works, concurrency safety, error handling |
| [task_contract.md](task_contract.md) | How to write a new pipeline task, required signature and structure, rules, how to add an independent (non-phase) task |

## Quick orientation

- **Entry points:** `src/observer.py` (file watcher) and `src/tasks/folder_scanners.py` (manual scan)
- **Pipeline start:** `src/tasks/__init__.py → start_pipeline()`
- **Phase orchestration:** `src/tasks/utils.py`
- **Task implementations:** `src/tasks/{clip,vision,embedding,translation}_tasks.py`
- **Queue definitions:** `src/queues/*.py`
