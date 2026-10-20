# Skill installation and recovery

Install only the workflow needed by the current production. `skills list`,
`skills install`, `skills check`, `skills update` and `skills remove` share the
Python and JavaScript content/checksum contract for Codex, Claude Code, Agents
and OpenCode project/user layouts. Modified user files are preserved.

The44 donor skills keep their original pinned source revision/SHA and stable IDs.
Portable adaptations have a separate package SHA and an explicit parent-bound
adaptation record. Their installed tree is the runnable authority. Source
provenance is not a claim that an adapted file remains byte-identical. Three
SDK-authored routers are indexed separately in `skills/owned.json`. Integrity
checks and editorial/runtime qualification are separate evidence.

Installation and update copy into a staged sibling, verify the package checksum,
then rename the prior install into a backup and publish the new tree. A small
operation journal permits Python and JavaScript to recover one another's
interrupted operations. A per-skill directory lock prevents concurrent mutation.
The old copy is removed only after the new tree is verified. A user-modified
install or backup, symlink, special file or unknown directory is never adopted or
silently overwritten.

A dead process lock can be recovered. Missing/invalid ownership, unknown process
liveness and a reused live PID require inspection of the original operation;
the installer does not guess that the lock is stale. Quarantined partial copies
and unknown temporary files remain available for inspection. Keep the installed
package version and source manifest when rolling back; reinstall the exact prior
artifact and update only unmodified skills after inspecting the journal.

Donor refresh tooling refuses to overwrite adapted skills. Review upstream
changes against the historical source, apply intentional changes to the installed
portable tree, then regenerate its adaptation index. No private library or model
weight is included by skill installation. Optional dependencies have their own
setup, rights and capability checks.
