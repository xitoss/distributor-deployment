<!-- Copilot / AI agent guidance for the distributor-deployment repo -->
# Quick orientation (what this repo is)
- This repository holds the deployment and host-side tooling for the Django "Distributor" app (the application source lives in the sibling `distributor/` folder). It uses Docker Compose for runtime, a small sys_scripts toolset for updates/backups, and version metadata in `version/*.json`.

# Key places to read first
- `distributor/` — the Django project and app modules (apps: `core`, `public`, `employee`, etc.). See `distributor/README.md` for app-level notes.
- `distributor-deployment/` — compose files, deployment assets and `sys_scripts/`.
- `distributor-deployment/sys_scripts/update_application.py` — host update flow (important example of how this repo runs `docker compose` from inside a container).
- `distributor-deployment/sys_scripts/utils.py` — runtime constants and `Context` helper (e.g. `VERSION_DIR`, `REPO_LATEST_FILE_URL`, `APP_IMAGE_URL`).

# Big-picture architecture (short)
- Single Django monolith with multiple apps for public/staff features. The deployment repo runs whole app as containers (web, db, nginx). The update flow depends on two version files under `version/`: `running.json` and `latest.json`.
- The update script pulls a Docker image (`APP_IMAGE_URL`), runs `docker compose up -d --no-deps web` from the host context and updates `running.json`. It also manages maintenance flags, backups and health checks via `Context`.

# Developer workflows and exact commands
- Local development
  - Install dependencies from `requirements.txt` and use Python 3.12 / Django 5.x (project README lists versions). Standard Django commands apply: `python manage.py makemigrations`, `python manage.py migrate`, `python manage.py createsuperuser`, `python manage.py runserver`.
  - Run tests with `python manage.py test` (apps include `tests.py`).
- Deployment / maintenance (what `update_application.py` demonstrates)
  - The update process expects version files in `version/` on the host: `running.json` and `latest.json`.
  - The updater uses a temporary docker container (`docker:cli`) and mounts the host project directory to run `docker compose` from the host perspective. See `run_compose_on_host()` in `sys_scripts/update_application.py` for the exact `docker run` invocation and Windows path conversion via `convert_windows_path_to_docker()`.
  - `.env` and `processing/` directories live under `distributor-deployment/` and are used by sys_scripts (see `sys_scripts/utils.py`).

# Project-specific conventions and patterns
- Role-based access: `Role.access_priority` (int) is used to gate employee features — look for `access_priority` checks in `employee/` and `core/` code instead of generic Django permissions.
- Staff panel routes live under `staff_panel/*` and expect authentication via a custom `Employee` model (see `employee/` and `decorators.py`).
- PDF generation: `core/pdf_generator.py` and `pdf/` contain code that programmatically builds PDFs for invoices and requests — follow their patterns for document creation.
- Versioning: version metadata is JSON in `distributor-deployment/version/`. The update path reads `latest.json` from the repo (`REPO_LATEST_FILE_URL`) if present.
- Host-aware compose: scripts assume they may run inside an agent/container and include logic to detect the host path by inspecting mounts for `/workspace` (see `get_host_project_path()` in `update_application.py`). If you change how the agent runs, update this detection.

# Integration points and external dependencies
- Container images: `APP_IMAGE_URL` is `ghcr.io/xitoss/distributor-app:latest` (see `sys_scripts/utils.py`). Changing image names or registries requires updating this constant.
- Network/compose labels: DB helpers look for docker-compose labels to find the DB container. If you change compose project names or service labels, update the DB lookup logic in `utils.Context.get_db_container()`.
- Remote version file: `REPO_LATEST_FILE_URL` points to raw GitHub URL; updates to repository branch or path must be reflected here.

# How AI agents should operate here (concrete rules)
- Prefer reading `distributor-deployment/sys_scripts/*` and `distributor/README.md` before applying changes; many deployment behaviors are encoded there.
- When proposing changes to deploy code, include the exact runtime effect: which file in `version/` changes, whether `running.json` will be updated, and how docker-compose will be invoked. Use the same `docker:cli` pattern unless explicitly switching to native host docker CLI.
- When editing DB scripts or backup flow, preserve the existing label filters and the `BACKUP_DIR`/`PROCESS_DIR` conventions from `sys_scripts/utils.py`.
- For Windows-specific fixes, follow the `convert_windows_path_to_docker()` pattern to create correct docker mount paths.

# Quick examples to cite in PRs
- To run the updater locally (diagnose): inspect logs in `processing/update-application-log.txt` and run `python sys_scripts/update_application.py` inside the deployment repo (it uses `Context` to log).
- To change the container image used by the updater: edit `APP_IMAGE_URL` in `distributor-deployment/sys_scripts/utils.py` (and update any CI/publishing that pushes the image).

# If something looks missing
- If there is no `.env` at repo root, the scripts will warn and continue; add a `.env` only with non-secret placeholders for local testing. Real secrets live in your CI/host environment, not in the repo.

---
If any of the sections above feel too terse or you want more examples (e.g., exact `docker run` command breakdown or common PR templates for deployment changes), tell me which section to expand and I will update this file.