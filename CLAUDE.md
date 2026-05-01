# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wandb Offline Sync is a daemon system for H200 GPU clusters where GPU nodes lack internet access. It enables automatic synchronization of wandb offline training data from shared storage (accessible by GPU nodes) to wandb cloud (via CPU nodes with internet).

**Architecture**: Client-server model using Unix sockets
- **Server (CPU node)**: Daemon monitors directories, auto-syncs offline runs to wandb cloud
- **Client (GPU/CPU node)**: CLI to manage monitored directories
- **Communication**: Unix socket at `/tmp/wandb_sync.sock` (configurable via `WANDB_SYNC_SOCKET`)

## Key Commands

### Installation
```bash
# Development install (editable)
pip install -e .

# From source
pip install .
```

### Running the System
```bash
# Start daemon (foreground for testing)
wandb-sync-server  # or: wbs

# Start daemon (background, recommended)
nohup wandb-sync-server > /tmp/wandb-sync.log 2>&1 &

# Client commands
wandb-sync-client add /path/to/wandb     # or: wbc add /path
wandb-sync-client list                   # or: wbc list
wandb-sync-client status                 # or: wbc status
wandb-sync-client history [--limit 20] [--failed]
wandb-sync-client stats
wandb-sync-client remove /path/to/wandb
```

### Testing
```bash
# Run test suite
python test_history.py
```

## Architecture Details

### Module Structure
```
server/
├── daemon.py          # Main daemon (WandbSyncDaemon)
├── watcher.py         # File monitoring (DirectoryMonitor, WandbWatcher)
├── syncer.py          # Sync logic (WandbSyncer)
├── socket_server.py   # Unix socket server
└── history.py         # SQLite-based sync history tracking

client/
├── cli.py             # CLI interface (argparse)
└── socket_client.py   # Unix socket client

common/
├── protocol.py        # JSON message protocol
└── config.py          # Shared configuration
```

### Core Components

**WandbSyncDaemon** (server/daemon.py:23)
- Orchestrates all server components
- Handles client commands via `_handle_command()` (line 89)
- Runs cleanup thread to remove inactive directories (24h threshold)
- Commands: add, remove, list, status, history, stats, stop

**DirectoryMonitor** (server/watcher.py:42)
- Manages watchdog observers for multiple directories
- Tracks last activity time per directory
- Auto-scans existing `offline-run-*` directories on add
- `cleanup_inactive()` removes directories with no activity for 24h

**WandbSyncer** (server/syncer.py:14)
- Queue-based sync worker (single thread)
- Deduplicates sync tasks via `self.syncing` set
- Calls `wandb sync <run_path>` subprocess (5min timeout)
- Detects offline runs: directory name starts with `offline-run-` AND contains `*.wandb` files

**SyncHistory** (server/history.py)
- SQLite database for sync records
- Tracks: run_path, directory, status, duration, timestamps, errors
- Provides statistics: success rate, avg duration, last 24h count, per-directory stats

**Communication Protocol** (common/protocol.py)
- JSON messages over Unix socket
- Request: `{command, path, [extra]}`
- Response: `{success, message, data}`

### Important Behaviors

1. **Sync Delay**: After detecting a new run, waits `SYNC_DELAY` seconds (from config.py) before syncing to ensure file writes complete

2. **Continuous Sync for Active Runs** (NEW):
   - Newly detected runs are synced immediately
   - Active runs (with file modifications) are resynced every `ACTIVE_RUN_SYNC_INTERVAL` (default: 5 minutes)
   - Runs with no activity for `ACTIVE_RUN_TIMEOUT` (default: 1 hour) are marked as finished
   - Finished runs get one final sync, then are no longer monitored
   - This ensures training metrics are continuously uploaded during training

3. **Deduplication**:
   - `WandbWatcher.active_runs` tracks runs and their last modification time
   - `WandbWatcher.finished_runs` prevents reprocessing completed runs
   - `WandbSyncer.syncing` prevents concurrent syncs of same run
   - `WandbSyncer.last_sync_time` tracks when each run was last synced

4. **Auto-cleanup**: Every `CLEANUP_CHECK_INTERVAL` (from config.py), removes directories inactive for `AUTO_CLEANUP_SECONDS` (default 24h)

5. **Recursive Monitoring**: Watchdog monitors directories recursively, detecting runs in subdirectories

6. **Entry Points**: setup.py defines both full commands (`wandb-sync-server`, `wandb-sync-client`) and short aliases (`wbs`, `wbc`)

## Development Notes

### Adding New Client Commands

1. Add command handler in `WandbSyncDaemon._handle_command()` (server/daemon.py:89)
2. Add command to argparse choices in `client/cli.py:37`
3. Add response formatting in `client/cli.py` main() function
4. Update protocol if new request fields needed

### Testing Considerations

- Test file `test_history.py` uses temporary SQLite databases
- Creates mock wandb directory structures for validation
- Tests cover: database init, sync recording, history queries, statistics

### Configuration

Environment variables (common/config.py):
- `WANDB_SYNC_SOCKET`: Unix socket path (default: `/tmp/wandb_sync.sock`)
- `WANDB_SYNC_LOG_LEVEL`: Logging level (default: INFO)

Key configuration constants:
- `SYNC_DELAY`: Wait time before first sync (default: 5s)
- `ACTIVE_RUN_SYNC_INTERVAL`: Resync interval for active runs (default: 300s / 5min)
- `ACTIVE_RUN_TIMEOUT`: Inactivity timeout to mark run as finished (default: 3600s / 1h)
- `AUTO_CLEANUP_SECONDS`: Time before removing inactive monitored directories (default: 24h)
- `CLEANUP_CHECK_INTERVAL`: How often to check for cleanup (default: 1h)

### GPU Cluster Context

This project is designed for environments where:
- GPU nodes: No internet, shared storage access, run training with `WANDB_MODE=offline`
- CPU nodes: Internet access, shared storage access, run this daemon
- Shared storage: Both node types can read/write (e.g., `/mnt/shared-storage-user/tangjia/`)

The daemon must run on a CPU node with internet access and wandb login credentials.
