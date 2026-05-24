# Writing Good Edison Queries

Distilled from the Kosmos best-practices guide; applies broadly to LITERATURE, ANALYSIS, and PRECEDENT.

## Objective

- **Single, well-defined objective** with room for iteration. Avoid questions answerable from a couple of papers.
- **Context like onboarding a new team member**: field nuances, experimental design, unusual assumptions.

## Data (for ANALYSIS / Kosmos)

- **Quality over quantity**: supply processed, well-labelled data (scRNA-seq, proteomics, multi-sample timecourses) rather than raw dumps.
- **Intuitive column names** or a README so a collaborator in the field could interpret the file unaided.

## Strategy

- **Start familiar**: first query on a dataset/topic you know well to build intuition.
- Iterate; use `continued_job_id` to refine.

## Avoid

- Vague prompts: "find correlations".
- Obvious questions answerable from abstracts.
- Raw unprocessed data needing QC.
- Trivially simple datasets without complexity.
