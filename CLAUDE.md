# MotionEye Project Instructions

## Important: Platform-Specific Updates

This version of Motion and MotionEye has been updated specifically for:
- **Raspberry Pi 5**
- **Pi Camera v3** (IMX708 sensor)

These updates were required due to changes in the Raspberry Pi camera library (libcamera). The Pi 5 no longer supports MMAL - it exclusively uses libcamera for camera access.

Key changes made:
- Motion 5.0 compatibility (stream endpoints, config option mappings)
- libcamera device detection and configuration
- Removal of deprecated stream_* options (stream_port, stream_localhost, etc.)
- Updated pyproject.toml to include all subpackages

---

## Testing on Raspberry Pi 5

### Before Running Tests

**IMPORTANT: Always ask the user if the Pi 5 is powered on before attempting to connect or run tests.**

### SSH Connection

Connect to the test Pi 5:
```bash
ssh admin@192.168.1.176
```

The SSH key has been configured for passwordless access from the development Mac.

### Deployment Workflow

1. **Sync code to Pi:**
   ```bash
   rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/
   ```

2. **Install on Pi:**
   ```bash
   ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"
   ```

3. **Restart service:**
   ```bash
   ssh admin@192.168.1.176 "sudo systemctl restart motioneye"
   ```

4. **Check logs:**
   ```bash
   ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager"
   ```

### Verify Camera Streaming

Test Motion stream directly:
```bash
ssh admin@192.168.1.176 "curl -s --max-time 3 'http://localhost:7999/1/mjpg/stream' -o /tmp/test.dat && file /tmp/test.dat"
```

Access MotionEye web interface: `http://192.168.1.176:8765/`

### Common Issues

- **Port conflicts**: Kill orphaned motion processes with `sudo pkill -9 motion`
- **Permission errors**: Ensure `/etc/motioneye` is owned by `motion:motion`
- **Camera not detected**: Verify with `rpicam-hello --list-cameras`

---

# Documentation Directory Structure

This directory contains project documentation organized by purpose. All new documentation files should include a datetime suffix in the format `-YYYYMMDD-HHMM.md`.

---

## Directory Purposes

### `/analysis/`
**Purpose**: Deep-dive reviews, audits, and evaluations of existing code or systems.

**Create here**:
- Code review reports
- Technical debt assessments
- Performance analysis reports
- Security audits
- Dependency evaluations
- Architecture reviews

**Naming examples**:
- `auth-flow-analysis-20251207-1430.md`
- `database-performance-review-20251208-0900.md`

---

### `/designs/`
**Purpose**: Technical design documents for features, systems, or architectural decisions.

**Create here**:
- Feature design specifications
- API design documents
- System architecture proposals
- Database schema designs
- Component interface specifications
- Technical RFCs

**Naming examples**:
- `user-notifications-design-20251207-1100.md`
- `api-v2-migration-design-20251210-1530.md`

---

### `/handoff-prompts/`
**Purpose**: Context documents for resuming or transferring work between sessions or developers.

**Create here**:
- Session continuation prompts
- Task handoff documents
- Work-in-progress context summaries
- Multi-session project continuity docs
- Collaboration handover notes

**Naming examples**:
- `HANDOFF-streaming-feature-20251207-1700.md`
- `session-context-websockets-20251209-0800.md`

---

### `/plans/`
**Purpose**: Implementation plans, roadmaps, and step-by-step execution strategies.

**Create here**:
- Implementation plans (phased steps)
- Migration strategies
- Refactoring roadmaps
- Feature rollout plans
- Testing strategies
- Deployment plans

**Naming examples**:
- `auth-migration-plan-20251207-1400.md`
- `performance-optimization-plan-20251211-1000.md`

---

### `/scratchpads/`
**Purpose**: Working notes, temporary documentation, and exploratory content.

**Create here**:
- Research notes
- Debugging session notes
- Quick reference guides (temporary)
- Experiment logs
- Build/setup steps for specific scenarios
- Troubleshooting logs

**Naming examples**:
- `redis-cache-exploration-20251207-1600.md`
- `debug-session-auth-errors-20251208-1100.md`

---

### `/summaries/`
**Purpose**: Completed work summaries and retrospective documentation.

**Create here**:
- Task/feature completion summaries
- Sprint retrospectives
- Implementation wrap-up reports
- Post-mortem documents
- Milestone summaries

**Naming examples**:
- `config-refactor-summary-20251207-1800.md`
- `v2-release-retrospective-20251215-1400.md`

---

## Naming Convention

All documentation files should follow this pattern:

```
<descriptive-name>-YYYYMMDD-HHMM.md
```

- **descriptive-name**: Kebab-case description of the content
- **YYYYMMDD**: Date (e.g., 20251207 for December 7, 2025)
- **HHMM**: Time in 24-hour format (e.g., 1430 for 2:30 PM)

---

### `/directories/`
**Purpose**: Navigation indexes for large files to help AI agents efficiently locate and modify code.

**Contents**:
- `main-html-index.md` - Comprehensive index of `motioneye/templates/main.html` (~1400 lines)
  - Line number ranges for all UI sections
  - Element ID reference tables
  - CSS class documentation
  - Dependency system explanation
  - i18n system details

**Usage**: Read the index file BEFORE editing the corresponding source file to:
- Find the exact line range for the section you need to modify
- Identify element IDs and their purposes
- Understand dependencies between settings
- Locate dynamic content injection points

---

## Root-Level Documents

The following documents live directly in `/docs/`:
- `MotionEye-Integration-Guide.md` - Main integration documentation
- `Update-Motion-MotionEye.md` - Motion/MotionEye update procedures

These are stable, long-lived documents that don't require datetime suffixes.

## Reading Files

**Caution** Some files in this project are very large intentionally