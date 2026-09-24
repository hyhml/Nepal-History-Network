# Project boundary

This repository is the independent home of the Nepal History Network visualization tool. Work on this project stays inside this repository. Source material is read through `materials/catalog.json`; a user-requested import may copy a source into `materials/local/`.

For a new user requirement, append its wording to `docs/requests.jsonl` (or use `python project.py request add ...`), then update `docs/design-spec.md` to record the resulting design decision. Keep the renderer and documentation consistent with the spec. Preserve dates at the precision actually supported by the source.

`materials/local/` contains the scanned book and full-text research data used by the local chart. It is intentionally excluded from Git. The tracked `examples/` directory contains structured facts and summaries without long source excerpts. Do not add the local PDF, verbatim passage dataset, generated HTML, or virtual environment to a commit.

Use Git commits for reviewable changes and `CHANGELOG.md` plus annotated tags for releases. Do not rewrite published version history. The research project's formal data and other repositories are outside this tool's boundary.

The public interactive site is `docs/index.html`. After changing the tracked example or renderer, regenerate it with `python build_chart.py --data-dir examples/raimajhi-life --output docs/index.html --cdn`, then inspect the committed artifact. GitHub Pages publishes `main` from `/docs`.
