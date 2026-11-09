# Measurement interpretation

Camp uses scc's COCOMO estimate: estimated people multiplied by estimated schedule months. A contributor is allocated a share based on surviving physical lines (including comments/blanks) in the counted source tree. Camp divides that allocation by the repository-wide local-ref earliest-to-latest committer-date span, with a minimum of 0.1 months. Summary automatic effort is blame-weighted; manual `--people` and personal modes record their own effort basis. Never add contributor ratios to produce the repository score.

Ignore rules affect the source scan and ownership. They do not turn calendar spans into working hours or remove historical excluded-path commits from that window. Dirty/untracked lines are uncommitted, not credited to a human. Excluded identities and unavailable attribution remain in explicit buckets; their shares are not redistributed.

A short span can produce a large ratio for a small allocation. Deletions, squash merges, generated/imported code, aliases and ref/history differences affect interpretation. Shallow history leaves affected effort/ratios unavailable. A historical contributor owning no surviving counted lines is absent even when every current owner is collected. Names alone do not identify distinct people, and one repository does not capture a person's other work.

The result is a reproducible estimate under recorded inputs, not actual labor, software value, work quality, an AI-use detector or proof of causal AI productivity gains. Inspect scope, accounting, effort basis and diagnostics alongside any ratio.
