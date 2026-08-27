# Decision records

This directory stores durable context for non-obvious script behavior and architecture. Decision records help future maintainers and agents continue work without reconstructing earlier experiments.

Record conclusions and reproducible evidence, not chat transcripts or unfiltered reasoning. A useful record contains:

- the user outcome and invariants;
- approaches evaluated and why they were accepted or rejected;
- measured evidence, test conditions, and confidence level;
- the accepted pipeline and parameter meanings;
- known limitations, implementation traps, and remaining experiments;
- links to the related issue, pull request, script, and user guide.

Update an existing record when its accepted decision is refined. If a decision is replaced, mark the old record as superseded and link to the replacement instead of erasing the historical evidence.

## Index

| Record | Status | Scope |
| --- | --- | --- |
| [0001 — Linked STL slice contour extraction](0001-linked-stl-slice-contour.md) | Accepted for the current draft | Exterior model-line contour from a horizontal linked-STL section |
