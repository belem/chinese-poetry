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

# 推送被拒时翻译成人话。常见的一种是 PAT 缺 workflow scope：
# 只要待推提交里改过 .github/workflows/，GitHub 就整条 push 都不收，
# 报错里只有一句 remote rejected。见 docs/同步.md。
explain_push_failure() {
  local err_file="$1"
  if grep -q "without .workflow. scope" "$err_file"; then
    log ""
    log "原因：PAT 缺少 workflow scope，GitHub 拒绝了整个 push。"
    log "      待推提交里改过 .github/workflows/ 下的文件（改一行也算），"
    log "      classic PAT 必须勾上 workflow 才能推，repo 只管 Contents 读写。"
    log "      修法：重新生成 PAT（勾 repo + workflow）→ 更新密钥仓库"
    log "            ${SECRETS_SLUG:-?}#${SECRETS_FILE:-?} 里的 GITHUB_TOKEN → 重跑本任务。"
    log "      注意：换完凭据前的每个提交都会带着这个未推送的历史反复撞同一堵墙，"
    log "            所以一卡就是一串，不是某一次提交的问题。"
    log ""
  elif grep -q "non-fast-forward\|\[rejected\]" "$err_file"; then
    log ""
    log "原因：GitHub 侧有了本仓库没有的提交，非快进被拒（脚本不强推）。"
    log "      先跑一次 pull 模式把 GitHub 的提交合回来，再重试 push。"
    log ""
  else
    sed 's/^/  /' "$err_file" >&2
  fi
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
  local err_file rc=0
  err_file=$(mktemp)
  git push --quiet "$(gh_url)" "HEAD:refs/heads/${BRANCH}" 2>"$err_file" || rc=$?
  if [ "$rc" -ne 0 ]; then
    explain_push_failure "$err_file"
    rm -f "$err_file"
    log "推送失败"
    return "$rc"
  fi
  rm -f "$err_file"
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
