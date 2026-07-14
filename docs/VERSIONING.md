# Version and Compatibility Policy

The npm package, Python package, catalog, and bundled skill set release under one
package version. Compatibility metadata records the CompositionSpec version,
catalog version, and skill-bundle version.

CompositionSpec follows semantic versioning. Readers reject unknown majors.
Minor releases may add optional fields but cannot change frame interpretation,
field meaning, or existing valid values. Writers emit one exact version. Major
migrations are explicit and must preserve original source plus a migration
report.

Catalog identifiers are permanent. Behavior changes bump the catalog item
version; replacements use a new ID and `supersedes`. Skill installers compare
both bundle version and content checksum.
