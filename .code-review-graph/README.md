# Nyxuri personal code review graph

This graph indexes the Nyxuri-personal worktree on night/personal-overlay,
including personal configuration source and supported upstream source.

```sh
code-review-graph build       # Full rebuild, including after language mapping changes
code-review-graph update      # Incremental update after edits
code-review-graph status
code-review-graph visualize   # Regenerate graph.html after updates
```

QML indexing uses the bundled qmljs grammar configured in languages.toml.
It extracts JavaScript functions, imports and calls. Component instantiation,
property bindings, signal wiring and QML module resolution are not
comprehensively modeled. KDL and TOML configuration semantics are not parsed
by this setup. Deployed configuration outside this worktree is not indexed.

Generated database and visualization files stay local and are ignored by Git.
This setup does not enable hooks, a watcher or cloud embeddings.
