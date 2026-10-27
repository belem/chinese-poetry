#!/usr/bin/env bash
# poem-source ⇄ belem/chinese-poetry 的 develop 同步
# 只做 fast-forward：两侧分叉就失败退出，交给人处理，绝不强推。
#
# 用法: sync.sh [push|pull|both]
#   push  CNB → GitHub
#   pull  GitHub → CNB
#   both  先 pull 再 push
set -euo pipefail

MODE="${1:-both}"
BRANCH="${SYNC_BRANCH:-develop}"
GH_SLUG="${GITHUB_SLUG:-belem/chinese-poetry}"
WORK="${WORK_DIR:-${PWD}/.poetry-sync}"

log() { printf '[sync] %s\n' "$*"; }

# 密钥仓库里可能叫 GITHUB_PAT，也可能叫 GITHUB_TOKEN，两者等价
PAT="${GITHUB_PAT:-${GITHUB_TOKEN:-}}"

gh_url() {
  if [ -n "$PAT" ]; then
    # PAT 只出现在本次命令的 URL 中，不落 .git/config、不打日志
    printf 'https://x-access-token:%s@github.com/%s.git' "$PAT" "$GH_SLUG"
  else
    printf 'https://github.com/%s.git' "$GH_SLUG"
  fi
}

require_pat() {
  if [ -z "$PAT" ]; then
    log "没有 GITHUB_PAT / GITHUB_TOKEN，跳过与 GitHub 的同步"
    log "预期来源：密钥仓库 ${SECRETS_SLUG:-?}#${SECRETS_FILE:-?} 经 .cnb.yml 的 imports 注入（见 README「凭据」）"
    log "检查点：密钥仓库文件里需有 GITHUB_TOKEN（或 GITHUB_PAT）字段，且允许本仓库开发者在 ${SECRETS_REF:-main} 上引用"
    exit 0
  fi
  log "凭据已就绪（长度 ${#PAT}，值不打印）"
}

gh_head() {
  git ls-remote "$(gh_url)" "refs/heads/${BRANCH}" | cut -f1
}

do_push() {
  require_pat
  log "CNB → GitHub ${GH_SLUG}#${BRANCH}"
  local head remote_head
  head=$(git rev-parse HEAD)
  remote_head=$(gh_head)
  if [ "$head" = "$remote_head" ]; then
    log "已一致，无需推送"
    return 0
  fi
  # 非快进直接报错，避免把 GitHub 侧的人工提交冲掉
  git push --quiet "$(gh_url)" "HEAD:refs/heads/${BRANCH}"
  log "推送完成 ${head:0:8}"
}

do_pull() {
  require_pat
  log "GitHub → CNB ${GH_SLUG}#${BRANCH}"
  rm -rf "$WORK"
  git init --quiet "$WORK"
  git -C "$WORK" fetch --quiet --depth=1 "$(gh_url)" "$BRANCH"
  local gh_sha local_sha
  gh_sha=$(git -C "$WORK" rev-parse FETCH_HEAD)
  rm -rf "$WORK"

  git fetch --quiet origin "$BRANCH"
  local_sha=$(git rev-parse HEAD)

  if [ "$gh_sha" = "$local_sha" ]; then
    log "已一致，无需拉取"
    return 0
  fi

  # CNB 侧没有 GitHub 独有的提交时才能快进
  if git merge-base --is-ancestor "$local_sha" "$gh_sha"; then
    log "CNB 落后，快进到 ${gh_sha:0:8}"
    git merge --ff-only --quiet "$gh_sha"
    git push --quiet origin "HEAD:refs/heads/${BRANCH}"
    log "已更新到 ${gh_sha:0:8}"
  else
    log "CNB 有 GitHub 没有的提交，跳过拉取（交给 push 环节）"
  fi
}

case "$MODE" in
  push) do_push ;;
  pull) do_pull ;;
  both) do_pull; do_push ;;
  *) log "未知模式: $MODE（可选 push / pull / both）"; exit 2 ;;
esac
