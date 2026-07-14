# CompositionSpec 1.0.0

`composition.schema.json` is the only hand-authored schema source for Python,
JavaScript, the CLI, renderers, examples, skills, and the catalog.

Timing is always expressed as integer frames. Frame rates are reduced rational
numbers, so 23.976 fps is represented as `{ "numerator": 24000,
"denominator": 1001 }`. Implementations must reject an unknown major version.
They may read a newer minor version only when every unknown field is optional
under that version's published compatibility notes.

Schema evolution is additive within a major version. Removing fields, changing
meaning, changing timing interpretation, or narrowing accepted values requires
a new major version and an explicit migration. Writers emit one exact supported
version and never silently rewrite an input document.

`fixtures/` contains cross-language contract inputs. Both packages must produce
byte-identical canonical JSON after recursively sorting object keys and writing
UTF-8 with no insignificant whitespace.

