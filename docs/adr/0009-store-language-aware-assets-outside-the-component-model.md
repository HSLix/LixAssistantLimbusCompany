---
status: accepted
---

# Store Language-aware Assets Outside the Component Model

Assets are immutable shared-library files referenced directly by each Manifest through a stable semantic name, capture language, relative path, and complete content hash; they are not Components and receive no Component ID. Image-using Trusted Actions accept only the semantic name and internally select the configured game language, use deterministic cross-language fallback, verify the hash, prioritize the last successful normalized region, and record the actual match. This avoids a general Asset object or `ctx.asset()` while keeping language and path decisions out of Workflow code.

Agent additions are append-only and written atomically into the shared Asset Library. Asset files share the Top-level Execution's durable Candidate File Batch with newly created candidate Component source. Retaining work for review retains the whole closed Batch; approval, rejection, or discard later deletes only Batch files unreferenced by any retained Manifest, durable Working Manifest, or rollback copy. A separate Asset Usage Index records successful use and the latest normalized region; it does not automatically remove accepted old Assets.
