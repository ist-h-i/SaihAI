# UI/UX Flow Cleanup (Issue #47)

## Scope
- Dashboard / genome / simulator
- Navigation and in-page secondary actions tied to the three screens

## Primary CTA (per screen)
- Dashboard: Next Action panel (contextual primary button only)
- Genome: Search + filter inputs (reset button appears only when filters are active)
- Simulator: input section "AI自動編成" (before results), results section "介入へ" (after results)

## 削除/統合一覧
| Screen | Item | Change | Reason |
| --- | --- | --- | --- |
| App shell | Debug & Demo buttons | Removed from desktop/mobile nav | Demo CTA duplicated primary flow and added noise |
| App header | レポート / AI自動編成 | Removed | Global CTA duplicated page CTAs |
| Dashboard | Next Action secondary buttons | Removed secondary simulator/demo buttons | Keep a single primary CTA per state |
| Dashboard | Today Focus CTA | Converted to static summary | Avoid duplicate primary CTA |
| Dashboard | AI提案 header CTA | Removed "シミュレーターへ" | Redundant navigation |
| Dashboard | Empty-state CTAs | Removed secondary/duplicate buttons | Reduce noise; rely on Next Action |
| Genome | "スキルをクリックでフィルタ" | Removed helper text | Self-explanatory interaction |
| Genome | Always-visible "Clear" | Show reset only when filters active | Remove unused button |
| Genome | Card footer "詳細を見る" | Removed | Reduce redundant guidance |
| Simulator | Demo buttons | Removed | Not part of main flow |
| Simulator | Next Action buttons | Removed | Remove duplicate CTAs |
| Simulator | Input CTA | Disabled until ready; demoted after results | Clarify when it is the primary action |
| Simulator | Results CTA | Promoted to primary when results exist | Make the next step obvious |

## Notes
- Character icon and comment bubble components remain unchanged.

## 回帰確認チェックリスト（手動）
- Dashboard: Next Action CTA is the only primary; navigation to simulator works.
- Dashboard: Today Focus and AI提案 sections show information without extra CTA.
- Genome: search + skill filter works; reset button appears only when filters are active.
- Genome: member selection updates the detail panel; selection clear works.
- Simulator: run simulation -> results -> open intervention overlay -> approve.
- Simulator: when no members selected -> team suggestions -> apply -> results.
- Simulator (mobile): layout remains usable; primary CTA visible without overlap.
