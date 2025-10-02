# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KonomiTV is a modern web-based TV media server for watching live television and recorded programs. It's designed to provide a Netflix-like viewing experience for Japanese TV broadcasts.

**Tech Stack:**
- **Server:** Python 3.11 + FastAPI + Tortoise ORM + Uvicorn
- **Client:** Vue.js 3.x + Vuetify 3.x SPA
- **Backend Support:** EDCB or Mirakurun/mirakc for TV tuner management

## Development Commands

### Server (Python)

All server commands must be run from the `server/` directory:

```bash
cd /Users/h/project/HonomiTV/server/

# Start server in reload mode (auto-restarts on code changes)
poetry run task dev

# Start server in normal mode
poetry run task serve

# Run linter (ruff + pyright)
poetry run task lint

# Run type checker only
poetry run task typecheck

# Update thirdparty libraries from GitHub Actions
poetry run task update-thirdparty
```

**Important:** Reload mode (`poetry run task dev`) is effectively unusable on Windows due to asyncio limitations. Use it on Linux (Ubuntu) for development.

### Client (Vue.js)

All client commands must be run from the `client/` directory:

```bash
cd /Users/h/project/HonomiTV/client/

# Install dependencies
yarn install

# Start development server (must also run server dev mode)
yarn dev

# Build for production
yarn build

# Run linter
yarn lint
```

**Critical:** When running `yarn dev`, you MUST also run `poetry run task dev` from the server directory. The client dev server only serves static files; the server provides the API endpoints.

### Access URLs

- **Client dev server:** `https://my.local.konomi.tv:7001/`
- **Server (production/dev):** `https://my.local.konomi.tv:7000/`
- **API documentation (Swagger):** `https://my.local.konomi.tv:7000/api/docs`

## Architecture

### Server Architecture

**Directory Structure:**
- `server/app/routers/` - FastAPI route handlers (e.g., `ChannelsRouter.py`, `VideosRouter.py`)
- `server/app/models/` - Tortoise ORM models (e.g., `Channel.py`, `Program.py`, `RecordedProgram.py`)
- `server/app/streams/` - Live and video streaming logic (`LiveStream.py`, `VideoStream.py`, `LiveEncodingTask.py`, `VideoEncodingTask.py`)
- `server/app/utils/` - Utilities including `NotificationService.py`, `JikkyoClient.py`, `TSInformation.py`
- `server/app/config.py` - Server configuration and `ClientSettings` Pydantic model
- `server/app/constants.py` - Version, paths, database config
- `server/app/app.py` - FastAPI application initialization and router registration
- `server/thirdparty/` - Bundled external tools (FFmpeg, QSVEncC, NVEncC, VCEEncC, rkmppenc, Akebi HTTPS Server, standalone Python)

**Key Concepts:**
- KonomiTV uses external encoders (FFmpeg/QSVEncC/NVEncC/VCEEncC/rkmppenc) for live and recorded video streaming
- Akebi HTTPS Server provides HTTPS reverse proxy without self-signed certificates
- Uvicorn serves both the FastAPI application and static client files from `client/dist/`

### Client Architecture

**Directory Structure:**
- `client/src/views/` - Vue route components
  - `TV/` - Live TV viewing (Home.vue, Watch.vue)
  - `Videos/` - Recorded program viewing (Home.vue, Watch.vue, Search.vue, Programs.vue)
  - `Settings/` - Settings pages (Base.vue, General.vue, Quality.vue, Caption.vue, etc.)
  - Root level views: `MyPage.vue`, `Mylist.vue`, `WatchedHistory.vue`, `OfflineVideos.vue`
- `client/src/components/` - Reusable Vue components
- `client/src/services/` - API client classes and service logic
  - `APIClient.ts` - Base API client
  - `Settings.ts`, `Users.ts`, `Videos.ts`, `Channels.ts`, etc. - Domain-specific services
  - `player/` - Player-related services
  - `DownloadManager.ts`, `OfflineDownload.ts` - Offline download functionality
- `client/src/stores/` - Pinia state management stores (SettingsStore.ts, UserStore.ts, PlayerStore.ts, ChannelsStore.ts, etc.)
- `client/src/router/index.ts` - Vue Router configuration
- `client/src/utils/` - Utility functions

**Key Concepts:**
- Settings are stored in browser LocalStorage and optionally synced to server
- Some settings sync across devices, others are device-specific (see `SYNCABLE_SETTINGS_KEYS`)
- Player uses mpegts.js for low-latency MPEG-TS streaming

## Adding New Settings Fields

When adding new client settings fields, you MUST update files in this exact order. Settings must be added in consistent order across all files. See `.cursor/rules/add-new-setting-field.mdc` for full Japanese instructions.

**Required file updates:**

1. **`client/src/stores/SettingsStore.ts`:**
   - Add to `ILocalClientSettings` interface
   - Add default value to `ILocalClientSettingsDefault`
   - If syncable, add to `SYNCABLE_SETTINGS_KEYS` array

2. **`client/src/services/Settings.ts`:**
   - Add to `IClientSettings` interface (if syncable, otherwise add comment)

3. **`server/app/config.py`:**
   - Add to `ClientSettings` Pydantic model (if syncable, otherwise add comment)
   - Default value must match SettingsStore

4. **`client/src/views/Settings/*.vue`:**
   - Add UI controls in the appropriate settings page

**Critical:** Field ordering MUST be consistent across all files. Non-syncable fields should have comments in the same position.

## Configuration

- **Server config:** `config.yaml` (copy from `config.example.yaml`)
- **Client settings:** Stored in browser LocalStorage, synced to server if user enables it
- Main branch for PRs: `cfzt-feature`

## Special Notes

- This is a fork with Cloudflare Zerotrust auto-detection and Cloudflare logout functionality
- Channel logos are sprite-optimized (see `logoGenerator.js`)
- The project uses Poetry for Python dependency management with a standalone Python runtime in `server/thirdparty/Python/`
- Ruff is configured to allow full-width Japanese characters (RUF001-003 disabled)
- TypeScript strict mode is enforced
- Uses EDCB or Mirakurun/mirakc as backend for TV tuner management
