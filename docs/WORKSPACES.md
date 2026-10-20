# Developer workspaces

The two editor workspaces provide navigation over one Git checkout:

```sh
code --new-window Aevora.Product.code-workspace
code --new-window Aevora.Maintainer.code-workspace
python3 tools/workspace_check.py
```

| Workspace | Contents |
|---|---|
| Product | Core source/contracts, receipt example, Console runtime/UI, the Observatory replay example, documentation and canonical public evidence tools |
| Maintainer | The product view plus OrderFlow, Benchmark, evaluator, Trusted Host, Agent integrations, tests, scripts, development tools and history index |

These are editor views, not package selectors or security sandboxes. Source control covers the entire repository in either view. The [repository layout](REPOSITORY_LAYOUT.md) maps components to paths; [development setup](../DEVELOPMENT.md) explains installation and commands.

Terminals and process tasks start at the real repository root. The Python interpreter defaults to `.venv/bin/python`. Git parent discovery is explicit, so each component belongs to the same repository rather than an independently initialized nested Git project.

Provided tasks check workspace paths, generated public evidence, the command map and Console build/tests. They do not start models, databases or Host publishers. Cache filters cover regenerable virtual environments, bytecode, node_modules, build/dist and package metadata. Source files and recorded failures remain tracked and available.

The optional pinned replay is in `examples/observatory/`. Edit generated verifier/projection consumers only through their canonical source in `tools/public_evidence/`, then run `python3 tools/sync_public_evidence.py --check`. Real graph and Host validation needs an explicitly owned environment and fresh external outputs; see [reproducibility](REPRODUCIBILITY.md).
