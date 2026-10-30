
## Local inspection and review artifact boundary

The local mock flow has three separate responsibilities:

1. **Browser inspector**
   Opens the synthetic fixture in headed Chromium and extracts structural metadata only.

2. **Safety policy**
   Enforces local-only execution, blocks external network access, and prohibits fill, upload, click, and submission actions.

3. **Review artifact serializer**
   Accepts only a policy-compliant inspection result and writes sanitized JSON to `artifacts/`.

The serializer is a one-way reporting boundary. It must not read candidate profiles, browser storage, uploaded-file state, or typed form values. The artifact is evidence of inspection, not permission to interact with a form.
