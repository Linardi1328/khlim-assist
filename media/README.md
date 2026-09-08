# Media staging

Use this folder for manually supplied **public-safe media and reference assets** that may later be used by KHLIM Assist or connected KHLIM event/admin experiences.

## Good candidates

- Public event posters, flyers, schedules, and approved graphics
- KHLIM logos, icons, and brand assets
- Synthetic screenshots or mock content for assistant testing
- Public-safe reference media intended for deliberate later ingestion

## Public-repository rule

This repository is public. Do not commit private member or staff information, secrets, credentials, internal-only documents, unapproved personal media, or identifiable photos/videos of children unless the appropriate consent and publication rights are confirmed.

## Knowledge and ingestion rule

`media/` is a manual staging area only. Do **not** automatically treat every file here as trusted assistant knowledge. Any indexing, embedding, OCR, extraction, or knowledge-base ingestion must be explicit, reviewed, permission-aware, and traceable to an approved source.

## Implementation rule

When an asset is approved for runtime use, deliberately move/copy or ingest it into the appropriate application storage or approved knowledge source rather than coupling production behavior directly to this staging folder.

## File conventions

- Prefer descriptive lowercase kebab-case filenames.
- Keep originals where practical and avoid unnecessary duplicates.
- Organize related assets into descriptive subfolders as the collection grows.
