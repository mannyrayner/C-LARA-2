# C-LARA-2 experiments workspace

This directory contains lightweight, version-controlled experiment orchestration files.

The intended convention is:

- commit `Makefile`, `README.md`, small config files, and small hand-authored fixtures;
- do **not** commit bulky generated outputs, model responses, scratch files, or local run directories;
- promote only compact, curated summaries or selected evidence artifacts when an experiment becomes report evidence.

The first concrete experiment is:

- `linguistic_processing/segmentation_phase_2/fr_boundary_first_clitic_compound_v2/`

It is the initial French boundary-first segmentation experiment using curated clitic/compound few-shot examples.
