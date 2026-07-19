# Lessons Learned

<!-- Append new entries below. Format:

### YYYY-MM-DD — Brief title
- **Friction**: What went wrong or was suboptimal
- **Fix**: How it was resolved
- **Rule**: Generalizable takeaway for future invocations
-->

### 2026-05-21 — Rules audit 併入 skill-curator
- **Why**: Plan mighty-exploring-hearth.md Phase 3，Anthropic 文章「3-6 月 CLAUDE.md 翻修」缺口的降級實作；Critic 認為 Cronicle 季度 job backfire 風險高（評分指標失真，session-archiver-stub-pollution 教訓），降級為 curator 附帶 scan。
- **How**: scripts/rules_scan.py flag 重複/矛盾/stale > 180 天；安全規則白名單 hardcoded；不自動刪。
