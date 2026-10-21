---
status: accepted
---

# Store Language-aware Assets Outside the Component Model

Under ADR 0021, files are retained directly in their normal stores, review records approval or rejection, and resource maintenance is deferred.

ADR 0020 replaces this decision's historical-region search optimization and blanket exclusion of Agent Asset additions with explicit search regions and additions cropped from a fresh Target Window screenshot taken for that crop request.

Assets are shared-library files protected from Agent modification referenced directly by each Manifest through a stable semantic name, capture language, relative path, and complete content hash; they are not Components and receive no Component ID. Image-using Trusted Actions accept only the semantic name and internally select the configured game language, use deterministic cross-language fallback, verify the hash, search the explicit caller-specified region or full client area by default; successful normalized regions are recorded only for reference and never change the search region, and record the actual match. This avoids a general Asset object or `ctx.asset()` while keeping language and path decisions out of Workflow code.

Assets are shared-library files protected from Agent modification referenced by complete Manifest mappings. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files. New files and complete attempted Manifests are retained in their normal stores regardless of approval or rejection; resource maintenance is deferred to a future module (ADR 0021). A separate Asset Usage Index records the latest non-empty matching result, including all returned detections and normalized regions, without requiring explicit usage acknowledgement or Step success; it does not automatically remove accepted old Assets.
