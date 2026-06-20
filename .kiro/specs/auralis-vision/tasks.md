# Implementation Plan: AURALIS VISION

## Overview

This plan converts the AURALIS VISION design into an ordered sequence of incremental
coding tasks. The build proceeds foundation-first: project skeleton and configuration, the
common engine contract and scoring utilities, the pluggable search-provider architecture,
ingestion with secure file handling, the security middleware and auth services, then the
asynchronous pipeline orchestrator, each analysis engine, the knowledge graph, the report
generator, the frontend, and finally persistence/indexing wiring plus integration and smoke
tests. Each step builds on prior ones and wires its output into the running system so there
is no orphaned code.

All implementation is in **Python (Flask)** as fixed by the design's technology stack.
Property-based tests use **Hypothesis** at a minimum of 100 iterations each; every one of the
design's 38 Correctness Properties is implemented as its own tagged test. Tasks postfixed
with `*` are optional test tasks and can be skipped for a faster MVP.

## Tasks

- [x] 1. Project foundation and configuration
  - [x] 1.1 Implement configuration loaded from environment and secrets
    - Create `app/config.py` with config classes that read all settings (DB URL, Redis,
      MinIO, OpenSearch, ClamAV, JWT secret, max file size, rate limits, thresholds, result
      caps) from environment variables / secret store, never hard-coded in source
    - Wire `create_app` to load config from `app/config.py`
    - _Requirements: 25.5_

  - [x] 1.2 Author Docker Compose stack and Nginx config
    - Create `docker-compose.yml` defining web, celery-cpu, celery-gpu (NVIDIA runtime),
      redis, postgres, minio, opensearch, and clamav services
    - Create `nginx/nginx.conf` with TLS termination, reverse proxy, CSP, and edge rate limit
    - _Requirements: 21.2, 24.1, 24.4, 25.1, 25.3_

  - [x] 1.3 Set up the database session and SQLAlchemy base
    - Create `app/database/` with engine/session factory and a declarative base
    - Add Alembic environment (`alembic.ini`, `env.py`) wired to the config DB URL
    - _Requirements: 26.1_

  - [x] 1.4 Implement ORM models and initial migration
    - Create `app/models/` ORM classes: users, roles, role_permissions, cases,
      stage_results (unique `(case_id, stage)`), artifacts, kg_nodes, kg_edges, reports,
      provider_config, audit_log (append-only, INSERT-only guard)
    - Generate the initial Alembic migration creating all tables and enums
    - _Requirements: 1.4, 6.6, 19.1, 19.2, 20.1, 21.3, 21.4, 23.4, 24.2, 25.6, 26.1_

  - [x] 1.5 Wire the app factory and blueprint registration
    - Confirm `create_app` registers all blueprints and binds Celery, DB, and config
    - Add a health route and ensure the app boots with the loaded configuration
    - _Requirements: 21.2_

- [x] 2. Common engine contract and scoring utilities
  - [x] 2.1 Implement the common engine contract and case context
    - Create `app/engines/base.py` with `StageResult`, `ArtifactRef`, `CaseContext`, and the
      `AnalysisEngine` protocol; engines return `StageResult` and never raise to the caller
    - _Requirements: 21.3, 21.4_

  - [x] 2.2 Implement the bounded scoring utility
    - Create `app/utils/scoring.py` with a function that clamps/produces a score in `[0, 100]`
      used by all scoring engines
    - _Requirements: 2.5, 3.3, 4.3, 8.5, 9.3, 12.4, 13.2, 14.2, 15.3, 17.2, 18.4_

  - [x]* 2.3 Write property test for bounded scores
    - **Property 1: Scores are bounded to [0, 100]**
    - Tag: `# Feature: auralis-vision, Property 1: Scores are bounded to [0, 100]`
    - **Validates: Requirements 2.5, 3.3, 4.3, 8.5, 9.3, 12.4, 13.2, 14.2, 15.3, 17.2, 18.4**

  - [x] 2.4 Implement the ranking/cap utility
    - Create `app/utils/ranking.py` returning input-only elements sorted non-increasing by
      score, capped to a configured limit
    - _Requirements: 3.4, 4.2, 8.4, 9.4_

  - [x]* 2.5 Write property test for ranked candidate lists
    - **Property 2: Ranked candidate lists are capped and sorted descending**
    - Tag: `# Feature: auralis-vision, Property 2: Ranked candidate lists are capped and sorted descending`
    - **Validates: Requirements 3.4, 4.2, 8.4, 9.4**

  - [x] 2.6 Implement the threshold-flag utility
    - Create `app/utils/thresholds.py` with `flag_at_or_above` and `flag_below` helpers
    - _Requirements: 13.4, 14.3, 17.4_

  - [x]* 2.7 Write property test for threshold flags
    - **Property 3: Threshold flags follow the comparison rule**
    - Tag: `# Feature: auralis-vision, Property 3: Threshold flags follow the comparison rule`
    - **Validates: Requirements 13.4, 14.3, 17.4**

- [x] 3. Search provider architecture
  - [x] 3.1 Implement the provider base contract
    - Create `app/search_providers/base.py` with `SearchCategory`, `NormalizedResult`,
      `SearchRequest`, `SearchProvider` protocol, `ProviderFailure`, and `SearchOutcome`
    - _Requirements: 6.1, 6.3_

  - [x] 3.2 Implement the provider registry
    - Create `app/services/provider_registry.py` with `register`, `providers_for(category)`,
      and `set_enabled` reading/persisting enable state from `provider_config`
    - _Requirements: 6.6, 6.7_

  - [ ]* 3.3 Write property test for provider dispatch selection
    - **Property 10: Search Hub dispatches to exactly the enabled providers of a category**
    - Tag: `# Feature: auralis-vision, Property 10: Search Hub dispatches to exactly the enabled providers of a category`
    - **Validates: Requirements 6.2, 6.6**

  - [x] 3.4 Implement the Search Hub with timeout and failure isolation
    - Create `app/services/search_hub.py` that resolves enabled providers, fans out
      concurrently bounded by `timeout_seconds`, records `ProviderFailure` on timeout/error
      while excluding that provider, normalizes successes, and returns a `SearchOutcome`
      without raising
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 3.5 Write property test for result normalization
    - **Property 11: Provider results normalize to the common structure**
    - Tag: `# Feature: auralis-vision, Property 11: Provider results normalize to the common structure`
    - **Validates: Requirements 6.3**

  - [ ]* 3.6 Write property test for provider failure isolation
    - **Property 12: Provider failures are isolated and recorded**
    - Tag: `# Feature: auralis-vision, Property 12: Provider failures are isolated and recorded`
    - **Validates: Requirements 6.4, 6.5**

  - [x] 3.7 Implement built-in providers and the search/providers blueprints
    - Create `app/search_providers/builtin/` with general/image/map/social provider stubs
      that conform to `SearchProvider`; wire `search` and `providers` blueprints to the hub
      and registry
    - Add a unit test asserting provider-interface conformance and registration without
      touching other providers
    - _Requirements: 6.1, 6.2, 6.6, 6.7_

- [x] 4. Image ingestion and secure file handling
  - [x] 4.1 Implement content-based format detection
    - Create `app/utils/format_detection.py` that identifies Supported_Format (JPG/JPEG, PNG,
      WEBP, TIFF, BMP, HEIC) by magic bytes / decoding, independent of file extension
    - _Requirements: 1.2, 1.3, 24.3_

  - [ ]* 4.2 Write property test for content-based format validation
    - **Property 4: Format validation is content-based and extension-independent**
    - Tag: `# Feature: auralis-vision, Property 4: Format validation is content-based and extension-independent`
    - **Validates: Requirements 1.2, 1.3, 24.3**

  - [x] 4.3 Implement the ingestion engine
    - Create `app/services/ingestion_service.py` accepting upload/drag-drop/URL/paste/camera
      sources, fetching URL content server-side, enforcing max size (message states limit),
      storing original bytes unmodified in MinIO, creating one Case per image with a UUID,
      and returning `Accepted`/`Rejected`
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8, 24.4_

  - [ ]* 4.4 Write property test for file-size acceptance
    - **Property 5: File-size acceptance respects the configured maximum**
    - Tag: `# Feature: auralis-vision, Property 5: File-size acceptance respects the configured maximum`
    - **Validates: Requirements 1.7**

  - [ ]* 4.5 Write property test for original-byte round-trip
    - **Property 6: Original bytes are stored unmodified (round-trip)**
    - Tag: `# Feature: auralis-vision, Property 6: Original bytes are stored unmodified (round-trip)`
    - **Validates: Requirements 1.5**

  - [ ]* 4.6 Write property test for one-Case-per-image uniqueness
    - **Property 7: Each accepted image yields exactly one Case with a unique id**
    - Tag: `# Feature: auralis-vision, Property 7: Each accepted image yields exactly one Case with a unique id`
    - **Validates: Requirements 1.4, 1.6**

  - [x] 4.7 Implement malware scanning, audit on rejection, and the cases blueprint
    - Integrate ClamAV scan before processing; reject malicious files and append an
      Audit_Log entry; wire `cases` blueprint `POST /api/v1/cases` to return 202 on accept
      and 400/413/415 with reasons on rejection
    - _Requirements: 1.3, 1.7, 24.1, 24.2, 24.3_

  - [ ]* 4.8 Write property test for malicious-file rejection and audit
    - **Property 32: Malicious files are rejected and audited; security actions are logged**
    - Tag: `# Feature: auralis-vision, Property 32: Malicious files are rejected and audited; security actions are logged`
    - **Validates: Requirements 24.2, 25.6**

- [x] 5. Security middleware and auth services
  - [x] 5.1 Implement the JWT authentication service
    - Create `app/security/auth.py` validating credentials, issuing signed JWTs on success,
      denying invalid credentials with a failure message, and verifying tokens on requests
    - _Requirements: 23.1, 23.2, 23.3_

  - [x] 5.2 Implement RBAC authorization
    - Create `app/security/rbac.py` with a `@require_permission(perm)` decorator that permits
      an action only when the role's permission set contains the required permission, else
      denies with an authorization failure message
    - _Requirements: 23.4, 23.5_

  - [ ]* 5.3 Write property test for protected-resource token requirement
    - **Property 30: Protected resources require a valid token**
    - Tag: `# Feature: auralis-vision, Property 30: Protected resources require a valid token`
    - **Validates: Requirements 23.3**

  - [ ]* 5.4 Write property test for permission-based authorization
    - **Property 31: Authorization permits an action iff the role grants the permission**
    - Tag: `# Feature: auralis-vision, Property 31: Authorization permits an action iff the role grants the permission`
    - **Validates: Requirements 23.4, 23.5**

  - [x] 5.5 Implement CSP, CSRF, and rate-limiting middleware
    - Create `app/security/middleware.py` emitting a CSP header on every response, validating
      a CSRF token before processing state-changing requests, and enforcing per-client rate
      limits (Flask-Limiter + Redis) where a configured limit of zero rejects all
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [ ]* 5.6 Write property test for the CSP header
    - **Property 33: Every response carries a CSP header**
    - Tag: `# Feature: auralis-vision, Property 33: Every response carries a CSP header`
    - **Validates: Requirements 25.1**

  - [ ]* 5.7 Write property test for CSRF validation
    - **Property 34: State-changing requests require a valid CSRF token**
    - Tag: `# Feature: auralis-vision, Property 34: State-changing requests require a valid CSRF token`
    - **Validates: Requirements 25.2**

  - [ ]* 5.8 Write property test for rate limiting
    - **Property 35: Rate limiting admits up to the limit then rejects until reset**
    - Tag: `# Feature: auralis-vision, Property 35: Rate limiting admits up to the limit then rejects until reset`
    - **Validates: Requirements 25.3, 25.4**

  - [x] 5.9 Implement the append-only Audit_Log service
    - Create `app/services/audit.py` appending exactly one entry per security-relevant action;
      no UPDATE/DELETE paths
    - _Requirements: 25.6_

  - [x] 5.10 Implement the auth blueprint and auth-flow unit tests
    - Wire `auth` blueprint `POST /login` and `POST /logout`; add unit tests for valid and
      invalid credential flows
    - _Requirements: 23.1, 23.2, 23.3_

- [x] 6. Checkpoint - foundation, security, and search hub
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Investigation pipeline orchestration
  - [x] 7.1 Implement the orchestrator and per-stage Celery tasks
    - Create `app/services/pipeline_orchestrator.py` and `app/tasks/` task wrappers; on Case
      creation dispatch all thirteen stages asynchronously as a Celery group with intra-group
      chains (object→face→deepfake; metadata→geoint→landmark/reverse/map); each stage runs
      under the engine contract so failures are recorded and the pipeline continues; update
      Case status/results per stage; a chord callback finalizes (KG build + mark complete +
      index) only after all branches reach a terminal state
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_

  - [ ]* 7.2 Write property test for stage scheduling
    - **Property 27: Pipeline schedules exactly the thirteen stages**
    - Tag: `# Feature: auralis-vision, Property 27: Pipeline schedules exactly the thirteen stages`
    - **Validates: Requirements 21.1**

  - [ ]* 7.3 Write property test for stage failure isolation
    - **Property 28: Pipeline isolates stage failures and tracks status**
    - Tag: `# Feature: auralis-vision, Property 28: Pipeline isolates stage failures and tracks status`
    - **Validates: Requirements 21.3, 21.4**

  - [ ]* 7.4 Write property test for case completion condition
    - **Property 29: Case completes iff all stages are terminal**
    - Tag: `# Feature: auralis-vision, Property 29: Case completes iff all stages are terminal`
    - **Validates: Requirements 21.5**

- [x] 8. Metadata forensics engine
  - [x] 8.1 Implement the metadata engine
    - Create `app/forensics/metadata_engine.py` extracting EXIF/XMP/ICC/thumbnail/orientation,
      recording present GPS/camera/software/timestamp fields, flagging missing fields,
      computing a metadata Risk_Score, and emitting `gps_removed`, `timestamp_anomaly`, and
      `metadata_manipulation` flags
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [ ]* 8.2 Write property test for metadata field recording
    - **Property 8: Metadata recording preserves present fields and flags absences**
    - Tag: `# Feature: auralis-vision, Property 8: Metadata recording preserves present fields and flags absences`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6**

  - [ ]* 8.3 Write property test for metadata anomaly flags
    - **Property 9: Metadata anomaly flags follow their rules**
    - Tag: `# Feature: auralis-vision, Property 9: Metadata anomaly flags follow their rules`
    - **Validates: Requirements 2.7, 2.8, 2.9**

- [x] 9. GEOINT and landmark engines
  - [x] 9.1 Implement the GEOINT engine
    - Create `app/geoint/geoint_engine.py` detecting geographic cues, producing ranked
      `{country, state, city, confidence}` candidates, recording `location_inference=none`
      when no cues are found
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 9.2 Implement the landmark engine
    - Create `app/geoint/landmark_engine.py` matching against a landmark embedding index,
      returning at most the top 20 matches ranked by Confidence_Score, recording
      `landmark=none` when nothing clears the minimum confidence
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 10. OCR engine
  - [x] 10.1 Implement the OCR engine
    - Create `app/ocr/ocr_engine.py` extracting text regions, detecting language per region,
      translating non-English regions to English, extracting named entities (business/street
      names, vehicle registrations), deriving location clues, and recording `text=none` when
      empty
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 10.2 Write property test for OCR translation presence
    - **Property 22: OCR translation presence rule**
    - Tag: `# Feature: auralis-vision, Property 22: OCR translation presence rule`
    - **Validates: Requirements 5.3**

- [x] 11. Reverse search, AI agent, and map correlation
  - [x] 11.1 Implement the reverse search engine
    - Create `app/geoint/reverse_search_engine.py` submitting the image to IMAGE providers via
      the Search_Hub, classifying results as exact/near matches, identifying the oldest
      appearance, recording the website set, building a date-ordered timeline, and recording
      `matches=none` when empty
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 11.2 Write property test for match classification
    - **Property 13: Reverse-search match classification follows the similarity threshold**
    - Tag: `# Feature: auralis-vision, Property 13: Reverse-search match classification follows the similarity threshold`
    - **Validates: Requirements 7.2**

  - [ ]* 11.3 Write property test for reverse-search correlation
    - **Property 14: Reverse-search correlation selects the oldest date, the website set, and an ordered timeline**
    - Tag: `# Feature: auralis-vision, Property 14: Reverse-search correlation selects the oldest date, the website set, and an ordered timeline`
    - **Validates: Requirements 7.3, 7.4, 7.5**

  - [x] 11.4 Implement the AI search agent
    - Create `app/geoint/ai_search_agent.py` analyzing the image plus existing findings,
      generating derived queries, executing them through the Search_Hub, and returning at most
      the top 20 candidate locations each with a Confidence_Score
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 11.5 Implement the map correlation engine
    - Create `app/geoint/map_correlation_engine.py` retrieving map/street-level imagery from
      MAP providers, comparing road layouts/building shapes/terrain, producing a location
      Confidence_Score, and ranking candidates descending
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 12. Object and face engines
  - [x] 12.1 Implement the object detection engine
    - Create `app/forensics/object_engine.py` detecting objects (faces, vehicles, logos,
      animals, aircraft, boats, buildings), recording class/bounding region/Confidence_Score,
      producing an inventory of detections meeting the minimum confidence, and recording
      `objects=none` otherwise
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 12.2 Write property test for object detection structure
    - **Property 15: Object detections carry valid structure**
    - Tag: `# Feature: auralis-vision, Property 15: Object detections carry valid structure`
    - **Validates: Requirements 10.2, 10.3**

  - [x] 12.3 Implement the face analysis engine
    - Create `app/deepfake/face_engine.py` detecting faces, recording the count, clustering
      visually similar faces across the Case, storing only non-identity-resolvable
      embeddings/cluster IDs, and recording count zero when none detected
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ]* 12.4 Write property test for face count and clustering
    - **Property 16: Face count matches detections and clustering is a valid partition**
    - Tag: `# Feature: auralis-vision, Property 16: Face count matches detections and clustering is a valid partition`
    - **Validates: Requirements 11.2, 11.3, 11.5**

  - [ ]* 12.5 Write property test for face attribute privacy
    - **Property 17: Stored face attributes contain no identity-resolvable data**
    - Tag: `# Feature: auralis-vision, Property 17: Stored face attributes contain no identity-resolvable data`
    - **Validates: Requirements 11.4**

- [x] 13. Tampering, AI-image, and deepfake engines
  - [x] 13.1 Implement the tampering engine
    - Create `app/forensics/tampering_engine.py` analyzing for copy-move/cloning/object
      removal/insertion/splicing via ELA, noise, JPEG quantization, compression, and PRNU;
      producing a heatmap when indicators are found and generation succeeds; always producing
      a tampering Confidence_Score; recording `heatmap_produced=false` on heatmap failure
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 13.2 Implement the AI-generated image detection engine
    - Create `app/ai_detection/ai_image_engine.py` analyzing for generation artifacts and
      generative-model signatures, producing an AI-generation probability Confidence_Score,
      recording the suspected generator family, and flagging the Case when the probability
      meets the configured threshold
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 13.3 Implement the deepfake engine
    - Create `app/deepfake/deepfake_engine.py` analyzing each detected face for face-swap and
      synthetic indicators, producing an authenticity Confidence_Score, flagging likely
      deepfake when the score is below threshold, and recording `not_applicable` when no face
      is present
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [x] 14. Steganography and CTF engines
  - [x] 14.1 Implement the steganography engine
    - Create `app/forensics/stego_engine.py` scanning for embedded archives/text/files/
      payloads, extracting detected payloads as Case artifacts, producing a suspicion
      Risk_Score, and recording `hidden_data=none` when nothing is found
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

  - [ ]* 14.2 Write property test for stego extraction round-trip
    - **Property 18: Stego extraction round-trips embedded payloads**
    - Tag: `# Feature: auralis-vision, Property 18: Stego extraction round-trips embedded payloads`
    - **Validates: Requirements 15.2**

  - [x] 14.3 Implement the CTF engine
    - Create `app/forensics/ctf_engine.py` running hidden-ZIP, QR, Base64, RGB channel split,
      channel analysis, entropy analysis, file carving, and LSB analysis with per-technique
      isolation; providing a hex view of raw bytes; storing recovered data as artifacts; and
      emitting a summary listing every technique and its outcome
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [ ]* 14.4 Write property test for CTF technique isolation
    - **Property 19: CTF mode isolates technique failures and reports every technique**
    - Tag: `# Feature: auralis-vision, Property 19: CTF mode isolates technique failures and reports every technique`
    - **Validates: Requirements 16.2, 16.5**

  - [ ]* 14.5 Write property test for hex-view round-trip
    - **Property 20: Hex view round-trips the raw bytes**
    - Tag: `# Feature: auralis-vision, Property 20: Hex view round-trips the raw bytes`
    - **Validates: Requirements 16.3**

- [x] 15. Threat and weather engines
  - [x] 15.1 Implement the threat intelligence engine
    - Create `app/forensics/threat_engine.py` evaluating for fake identity documents,
      fabricated screenshots, scam imagery, and phishing assets; producing a threat
      Risk_Score; recording each indicator with its category; and flagging a potential threat
      when the score meets the configured threshold
    - _Requirements: 17.1, 17.2, 17.3, 17.4_

  - [ ]* 15.2 Write property test for threat indicator categories
    - **Property 21: Threat indicators carry a valid category**
    - Tag: `# Feature: auralis-vision, Property 21: Threat indicators carry a valid category`
    - **Validates: Requirements 17.3**

  - [x] 15.3 Implement the weather/shadow engine
    - Create `app/forensics/weather_engine.py` detecting shadow direction/angle, estimating
      sun direction and time of day, estimating weather conditions, associating a
      Confidence_Score with the estimated capture time, and recording that estimation is not
      possible when no shadows/cues exist
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

- [x] 16. Checkpoint - all analysis engines
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Knowledge graph
  - [x] 17.1 Implement the knowledge graph service
    - Create `app/services/knowledge_graph_service.py` building nodes for image, text,
      objects, businesses, websites, search results, locations, map references, similar
      images, and social profiles plus relationship edges; on node-creation failure the build
      reports failure so the view can render without the graph
    - _Requirements: 19.1, 19.2, 19.3_

  - [ ]* 17.2 Write property test for graph coverage and edge integrity
    - **Property 23: Knowledge graph covers findings and contains no dangling edges**
    - Tag: `# Feature: auralis-vision, Property 23: Knowledge graph covers findings and contains no dangling edges`
    - **Validates: Requirements 19.1, 19.2**

  - [ ]* 17.3 Write property test for node neighborhood query
    - **Property 24: Node neighborhood query returns exact adjacency**
    - Tag: `# Feature: auralis-vision, Property 24: Node neighborhood query returns exact adjacency`
    - **Validates: Requirements 19.4**

  - [x] 17.4 Implement the graph blueprint
    - Wire `graph` blueprint `GET /api/v1/cases/{id}/graph` returning nodes/edges and, when a
      node is selected, its details and directly connected nodes
    - _Requirements: 19.4, 19.5_

- [x] 18. Report generator
  - [x] 18.1 Implement the report service and renderers
    - Create `app/reports/report_service.py` plus PDF/DOCX/JSON renderers compiling findings
      from exactly the completed stages into an executive summary, per-stage findings, and a
      final Confidence_Score; returning an informational message and no report structure when
      no stages are completed
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

  - [ ]* 18.2 Write property test for report compilation
    - **Property 25: Reports compile exactly the completed stages with required structure**
    - Tag: `# Feature: auralis-vision, Property 25: Reports compile exactly the completed stages with required structure`
    - **Validates: Requirements 20.1, 20.2**

  - [ ]* 18.3 Write property test for JSON report round-trip
    - **Property 26: JSON report round-trips**
    - Tag: `# Feature: auralis-vision, Property 26: JSON report round-trips`
    - **Validates: Requirements 20.3**

  - [x] 18.4 Implement the reports blueprint
    - Wire `reports` blueprint `POST /api/v1/cases/{id}/report` to generate and return the
      requested format
    - _Requirements: 20.1, 20.3, 20.4_

- [x] 19. Frontend
  - [x] 19.1 Implement the dashboard
    - Create Jinja2 templates and the `ui` blueprint for a dashboard with sidebar navigation
      to capability areas and a recent-cases list with status badges
    - _Requirements: 22.1_

  - [x] 19.2 Implement the tabbed investigation view
    - Create the investigation-view template with Alpine-controlled tabs per stage group and
      per-stage status chips
    - _Requirements: 22.2, 22.3_

  - [x] 19.3 Implement HTMX status polling and result fragments
    - Wire `GET /api/v1/cases/{id}/status` HTMX polling to refresh stage chips and swap in
      result fragments as stages finish
    - _Requirements: 22.3, 22.4_

  - [x] 19.4 Implement the Cytoscape knowledge-graph visualization
    - Embed an interactive Cytoscape.js graph in its tab; selecting a node calls
      `hx-get /cases/{id}/graph?node=`; render an error message in-tab if the graph build
      failed while keeping the rest of the view usable
    - _Requirements: 19.3, 19.4, 19.5_

- [x] 20. Persistence and indexing wiring
  - [x] 20.1 Wire Case persistence into the pipeline
    - Persist Case and findings to PostgreSQL on create/update; restore findings and artifacts
      when an Analyst reopens a Case via `GET /api/v1/cases/{id}`
    - _Requirements: 26.1, 26.5_

  - [ ]* 20.2 Write property test for persistence round-trip
    - **Property 38: Persistence round-trip restores findings and artifacts**
    - Tag: `# Feature: auralis-vision, Property 38: Persistence round-trip restores findings and artifacts`
    - **Validates: Requirements 26.1, 26.5**

  - [x] 20.3 Implement OpenSearch indexing and authorized search
    - Index Case findings after persistence; on index failure record it and retain the Case;
      wire `GET /api/v1/find?q=` to return only Cases within the Analyst's authorization scope
    - _Requirements: 26.2, 26.3, 26.4_

  - [ ]* 20.4 Write property test for indexing-failure resilience
    - **Property 36: Indexing failure retains the persisted Case**
    - Tag: `# Feature: auralis-vision, Property 36: Indexing failure retains the persisted Case`
    - **Validates: Requirements 26.3**

  - [ ]* 20.5 Write property test for authorized indexed search
    - **Property 37: Indexed search returns only authorized Cases**
    - Tag: `# Feature: auralis-vision, Property 37: Indexed search returns only authorized Cases`
    - **Validates: Requirements 26.4**

- [ ] 21. Integration and smoke tests
  - [ ]* 21.1 Write end-to-end ingestion → pipeline → report integration test
    - Drive a real image through ingestion, the async pipeline, and report generation
    - _Requirements: 1.1, 21.1, 21.2, 21.5, 20.1_

  - [ ]* 21.2 Write ClamAV and MinIO integration tests
    - Verify malware scanning rejects/accepts correctly and object storage stores originals
      isolated from execution paths
    - _Requirements: 24.1, 24.4_

  - [ ]* 21.3 Write OpenSearch, Celery, and HTMX integration tests
    - Verify indexing and authorized search, async stage dispatch, and the investigation view
      rendering with HTMX status polling
    - _Requirements: 21.2, 22.1, 22.2, 22.3, 22.4, 26.2, 26.4_

  - [ ]* 21.4 Write configuration smoke tests
    - Verify object-storage isolation and secrets-from-store with no secrets present in source
    - _Requirements: 24.4, 25.5_

- [x] 22. Final checkpoint - full platform
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for a faster MVP.
- Each task references specific granular requirements for traceability.
- All 38 Correctness Properties from the design are implemented as Hypothesis property-based
  tests (minimum 100 iterations), each tagged with
  `# Feature: auralis-vision, Property {number}: {property_text}` and placed next to the code
  it validates so logic errors surface early.
- Properties 1, 2, and 3 are tested once at the shared scoring/ranking/threshold utility level
  (section 2); the engines that depend on them reuse those utilities rather than re-testing.
- Unit/example tests cover ML-driven detection sanity, empty/edge cases, provider-interface
  conformance, and auth flows; integration and smoke tests cover cross-service behavior.
- Checkpoints (tasks 6, 16, 22) provide incremental validation points.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4"] },
    { "id": 2, "tasks": ["1.5", "2.1", "2.2", "2.4", "2.6"] },
    { "id": 3, "tasks": ["2.3", "2.5", "2.7", "3.1", "5.1", "5.9"] },
    { "id": 4, "tasks": ["3.2", "5.2", "5.5", "4.1"] },
    { "id": 5, "tasks": ["3.3", "3.4", "5.3", "5.4", "5.6", "5.7", "5.8", "5.10", "4.2"] },
    { "id": 6, "tasks": ["3.5", "3.6", "3.7", "4.3", "4.7"] },
    { "id": 7, "tasks": ["4.4", "4.5", "4.6", "4.8", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3", "7.4", "8.1", "9.1", "9.2", "10.1", "12.1", "12.3", "13.1", "13.2", "13.3", "14.1", "14.3", "15.1", "15.3"] },
    { "id": 9, "tasks": ["8.2", "8.3", "10.2", "11.1", "11.4", "11.5", "12.2", "14.2", "14.4", "14.5", "15.2"] },
    { "id": 10, "tasks": ["11.2", "11.3", "12.4", "12.5", "17.1"] },
    { "id": 11, "tasks": ["17.2", "17.3", "17.4", "18.1"] },
    { "id": 12, "tasks": ["18.2", "18.3", "18.4", "20.1", "20.3"] },
    { "id": 13, "tasks": ["19.1", "19.2", "19.3", "19.4", "20.2", "20.4", "20.5"] },
    { "id": 14, "tasks": ["21.1", "21.2", "21.3", "21.4"] }
  ]
}
```
