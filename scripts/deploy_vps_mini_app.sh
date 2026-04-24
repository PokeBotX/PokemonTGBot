#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/root/pokemonbot"
FRONTEND_DIR="$REPO_DIR/frontend"
STATIC_DIR="/var/www/app.pokemoncollection.ru"
SERVICE_NAME="pokecollect.service"
NODE_VERSION="v20.19.5"
NODE_DIST="node-${NODE_VERSION}-linux-x64"
NODE_ARCHIVE="${NODE_DIST}.tar.xz"
NODE_BASE_DIR="/opt/${NODE_DIST}"
NODE_LINK="/opt/node20"

BRANCH="${1:-}"

log() {
  printf '[deploy-mini-app] %s\n' "$*"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root on the VPS." >&2
    exit 1
  fi
}

ensure_clean_worktree() {
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Repository has uncommitted tracked changes. Commit or stash them first." >&2
    git status --short
    exit 1
  fi
}

ensure_portable_node() {
  if [[ -x "${NODE_LINK}/bin/node" ]]; then
    export PATH="${NODE_LINK}/bin:${PATH}"
    return
  fi

  log "Installing portable Node.js ${NODE_VERSION}..."
  cd /opt
  curl -fsSL "https://nodejs.org/dist/${NODE_VERSION}/${NODE_ARCHIVE}" -o "${NODE_ARCHIVE}"
  rm -rf "${NODE_BASE_DIR}"
  tar -xf "${NODE_ARCHIVE}"
  ln -sfn "${NODE_BASE_DIR}" "${NODE_LINK}"
  export PATH="${NODE_LINK}/bin:${PATH}"
}

main() {
  require_root

  cd "${REPO_DIR}"
  ensure_clean_worktree

  if [[ -z "${BRANCH}" ]]; then
    BRANCH="$(git branch --show-current)"
  fi

  log "Deploying branch: ${BRANCH}"
  git fetch origin "${BRANCH}"
  git checkout "${BRANCH}"
  git pull --ff-only origin "${BRANCH}"

  ensure_portable_node
  log "Node: $(node -v)"
  log "npm: $(npm -v)"

  cd "${FRONTEND_DIR}"
  log "Installing frontend dependencies..."
  npm ci

  log "Building frontend export..."
  npm run build -- --webpack

  if [[ ! -d "${FRONTEND_DIR}/out" ]]; then
    echo "Expected static export in ${FRONTEND_DIR}/out, but it was not created." >&2
    exit 1
  fi

  log "Publishing static frontend to ${STATIC_DIR}..."
  mkdir -p "${STATIC_DIR}"
  rm -rf "${STATIC_DIR:?}/"*
  cp -a "${FRONTEND_DIR}/out/." "${STATIC_DIR}/"
  chown -R www-data:www-data "${STATIC_DIR}"

  log "Checking and reloading nginx..."
  nginx -t
  systemctl reload nginx

  log "Restarting ${SERVICE_NAME}..."
  systemctl restart "${SERVICE_NAME}"

  log "Service status:"
  systemctl status "${SERVICE_NAME}" --no-pager | sed -n '1,12p'

  log "Done."
}

main "$@"
