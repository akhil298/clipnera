-- Pre-deploy check for the grandparent fix (docs/revamp/06-flags.md §1.3, §12 step 1.0).
-- Read-only. Run against production BEFORE turning remote config
-- `flags.legacy_parent_semantics` off:
--
--   psql "$DATABASE_URL" -f backend/scripts/check_grandchild_flags.sql
--
-- Under the old rule a flag is live when it and its direct parent are switched
-- on, whatever is above the parent. Each row below is a flag that is live today
-- only because of that rule, with the higher ancestor that is off (or has no
-- row, which means off). It goes dark once full-chain evaluation is on; the
-- owner decides per row whether to switch the ancestor on first.
--
-- The parent comes from the dotted key, which matches feature_flags/registry.py
-- for all 13 pre-revamp keys. This widens §12's three-level query to any depth
-- and also counts a missing ancestor row as off.
WITH RECURSIVE chain AS (
    SELECT c.key AS flag, p.key AS ancestor
      FROM feature_flags c
      JOIN feature_flags p ON p.key = regexp_replace(c.key, '\.[^.]+$', '')
     WHERE c.key LIKE '%.%' AND c.enabled AND p.enabled
    UNION ALL
    SELECT chain.flag, regexp_replace(chain.ancestor, '\.[^.]+$', '')
      FROM chain
     WHERE chain.ancestor LIKE '%.%'
)
SELECT chain.flag, chain.ancestor AS off_ancestor
  FROM chain
  LEFT JOIN feature_flags a ON a.key = chain.ancestor
 WHERE a.key IS NULL OR NOT a.enabled
 ORDER BY chain.flag, chain.ancestor;
