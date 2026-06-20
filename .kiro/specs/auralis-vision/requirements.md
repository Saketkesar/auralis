# Requirements Document

## Introduction

AURALIS VISION is a production-grade enterprise Image Intelligence Platform that unifies GEOINT, OSINT, digital forensics, deepfake and AI-generated content detection, image tampering analysis, metadata forensics, reverse image search, landmark recognition, geolocation intelligence, CTF image investigation, steganography analysis, and threat intelligence correlation into a single workflow. An analyst uploads an image and the platform orchestrates an automated investigation pipeline across all capability modules, then produces a consolidated investigation report with a final confidence score.

The platform serves CTF players, OSINT investigators, journalists, law enforcement, DFIR teams, security researchers, threat intelligence teams, SOC analysts, and cybercrime investigation units. It is delivered as a Flask-based web application with asynchronous processing, persistent case storage, object storage for media, a search index for correlation, and a modular plug-and-play architecture for search and analysis providers.

This document defines the functional and cross-cutting requirements for the platform. Each requirement follows a single EARS pattern and is written to be individually verifiable.

## Glossary

- **Platform**: The complete AURALIS VISION system comprising all engines, services, and the web application.
- **Analyst**: An authenticated human user who performs investigations using the Platform.
- **Case**: A persistent investigation record created when an image is ingested, containing the source image, derived artifacts, findings, and the final report.
- **Investigation_Pipeline**: The orchestrated sequence of analysis stages executed against an ingested image.
- **Ingestion_Engine**: The component that accepts, validates, normalizes, and stores incoming images and creates Cases.
- **Metadata_Engine**: The component that extracts and evaluates image metadata (EXIF, XMP, ICC, thumbnail).
- **GEOINT_Engine**: The component that infers geographic location from image content.
- **Landmark_Engine**: The component that recognizes landmarks and points of interest in images.
- **OCR_Engine**: The component that extracts text from images and derives entities and location clues.
- **Search_Hub**: The component that queries external general, image, map, and social search providers through a uniform provider interface.
- **Reverse_Search_Engine**: The component that correlates reverse image search results into matches, sources, and timelines.
- **AI_Search_Agent**: The autonomous agent that plans and executes multi-engine searches to produce candidate locations.
- **Map_Correlation_Engine**: The component that compares image content against map and street-level imagery sources to score location candidates.
- **Object_Engine**: The component that detects and classifies objects in images.
- **Face_Engine**: The component that detects, counts, and clusters faces.
- **Tampering_Engine**: The component that detects image manipulation.
- **AI_Image_Engine**: The component that estimates the probability that an image is AI-generated.
- **Deepfake_Engine**: The component that estimates the probability that a face or image is synthetic or face-swapped.
- **Stego_Engine**: The component that analyzes images for hidden data.
- **CTF_Engine**: The component that runs CTF-oriented extraction and analysis techniques.
- **Threat_Engine**: The component that assesses images for fraud, scam, and phishing indicators.
- **Weather_Engine**: The component that estimates capture time and weather conditions from environmental cues.
- **Knowledge_Graph**: The component that links entities discovered during an investigation into a navigable graph.
- **Report_Generator**: The component that compiles findings into exportable reports.
- **Provider**: A pluggable external integration (general search, image search, map, or social) registered with the Search_Hub.
- **Authentication_Service**: The component that authenticates Analysts and issues session tokens.
- **Authorization_Service**: The component that enforces role-based access control.
- **Audit_Log**: The append-only record of security-relevant actions performed on the Platform.
- **Confidence_Score**: A numeric value from 0 to 100 expressing the estimated reliability of a finding.
- **Risk_Score**: A numeric value from 0 to 100 expressing the estimated severity of a detected concern.
- **Supported_Format**: One of JPG, JPEG, PNG, WEBP, TIFF, BMP, or HEIC.

## Requirements

### Requirement 1: Image Ingestion

**User Story:** As an Analyst, I want to submit images through multiple input methods, so that I can start an investigation regardless of how I obtained the image.

#### Acceptance Criteria

1. WHERE the input method is file upload, drag-and-drop, pasted URL, screenshot, or camera capture, THE Ingestion_Engine SHALL accept the image and begin ingestion.
2. WHEN an image is submitted in a Supported_Format, THE Ingestion_Engine SHALL accept the image for processing.
3. IF a submitted image is not in a Supported_Format, THEN THE Ingestion_Engine SHALL reject the submission and return a message identifying the supported formats.
4. WHEN an image is accepted, THE Ingestion_Engine SHALL create a Case with a unique case identifier.
5. WHEN a Case is created, THE Ingestion_Engine SHALL store the original image without modifying its bytes.
6. WHEN an Analyst submits a batch of multiple images, THE Ingestion_Engine SHALL create one Case per image.
7. IF a submitted file exceeds the configured maximum file size, THEN THE Ingestion_Engine SHALL reject the submission and return a message stating the maximum allowed size.
8. WHEN an image is submitted by URL, THE Ingestion_Engine SHALL retrieve the image and validate that the retrieved content is a Supported_Format before creating a Case.

### Requirement 2: Metadata Forensics

**User Story:** As an OSINT investigator, I want detailed metadata extracted and evaluated, so that I can identify the device, time, and location associated with an image and detect metadata manipulation.

#### Acceptance Criteria

1. WHEN a Case is created, THE Metadata_Engine SHALL extract available EXIF, XMP, ICC, thumbnail, and orientation metadata from the image.
2. WHERE GPS coordinates are present in metadata, THE Metadata_Engine SHALL record the latitude and longitude.
3. WHERE camera model, device, or capture software fields are present in metadata, THE Metadata_Engine SHALL record each present field.
4. WHERE timestamp fields are present in metadata, THE Metadata_Engine SHALL record each timestamp.
5. THE Metadata_Engine SHALL compute a metadata Risk_Score for the Case.
6. IF expected metadata fields are absent, THEN THE Metadata_Engine SHALL flag each absent field as missing.
7. IF GPS metadata is absent while other camera-origin metadata is present, THEN THE Metadata_Engine SHALL flag the image as having GPS data removed.
8. IF a recorded timestamp field is inconsistent with another recorded timestamp field, THEN THE Metadata_Engine SHALL flag a timestamp anomaly.
9. IF metadata indicates editing software inconsistent with the recorded capture device, THEN THE Metadata_Engine SHALL flag potential metadata manipulation.

### Requirement 3: GEOINT Location Inference

**User Story:** As an OSINT investigator, I want the Platform to infer where an image was taken from its visual content, so that I can geolocate images that lack GPS metadata.

#### Acceptance Criteria

1. WHEN a Case enters the GEOINT stage, THE GEOINT_Engine SHALL detect geographic cues including buildings, roads, poles, mountains, rivers, signs, architecture, vehicles, and road markings present in the image.
2. WHEN geographic cues are detected, THE GEOINT_Engine SHALL produce candidate locations expressed as country, state, and city.
3. WHEN a candidate location is produced, THE GEOINT_Engine SHALL associate a Confidence_Score with the candidate location.
4. THE GEOINT_Engine SHALL rank candidate locations in descending order of Confidence_Score.
5. IF no geographic cues are detected, THEN THE GEOINT_Engine SHALL record that no location inference was possible for the Case.

### Requirement 4: Landmark Recognition

**User Story:** As an investigator, I want recognizable landmarks identified, so that I can quickly anchor an image to a known place.

#### Acceptance Criteria

1. WHEN a Case enters the landmark stage, THE Landmark_Engine SHALL evaluate the image against known landmarks including monuments, tourist sites, universities, airports, and stadiums.
2. WHEN landmark matches are found, THE Landmark_Engine SHALL return at most the top 20 matches ranked by Confidence_Score.
3. WHEN a landmark match is returned, THE Landmark_Engine SHALL associate a Confidence_Score with the match.
4. IF no landmark is provided to the Analyst, whether because no match met the configured minimum Confidence_Score or for any other reason, THEN THE Landmark_Engine SHALL record that no landmark was identified for the Case.

### Requirement 5: OCR Intelligence

**User Story:** As an investigator, I want text in images extracted and analyzed, so that I can read signs, names, and numbers that reveal location and identity clues.

#### Acceptance Criteria

1. WHEN a Case enters the OCR stage, THE OCR_Engine SHALL extract text regions from the image.
2. WHEN text extraction succeeds, THE OCR_Engine SHALL detect the language of each extracted text region.
3. WHERE extracted text is detected as a language other than English, THE OCR_Engine SHALL produce an English translation of the extracted text.
4. WHEN text is extracted, THE OCR_Engine SHALL extract named entities including business names, street names, and vehicle registration numbers.
5. WHEN entities are extracted, THE OCR_Engine SHALL record location clues derived from the extracted entities.
6. IF no text is detected in the image, THEN THE OCR_Engine SHALL record that no text was extracted for the Case.

### Requirement 6: Multi-Engine Search Hub

**User Story:** As an investigator, I want the Platform to query many external search engines through one interface, so that I can correlate evidence across general, image, map, and social sources.

#### Acceptance Criteria

1. THE Search_Hub SHALL expose a uniform Provider interface for general search, image search, map, and social Providers.
2. WHEN a search request is issued for a category, THE Search_Hub SHALL dispatch the request to each enabled Provider registered for that category.
3. WHEN a Provider returns results, THE Search_Hub SHALL normalize the results into a common result structure.
4. IF a Provider fails to respond within its configured timeout, THEN THE Search_Hub SHALL record the Provider failure and continue processing results from the remaining Providers.
5. IF a Provider returns an error instead of results, THEN THE Search_Hub SHALL record the Provider failure, exclude that Provider's output from normalization, and continue processing results from the remaining Providers.
6. WHERE an Analyst disables a Provider, THE Search_Hub SHALL exclude the disabled Provider from subsequent search requests.
7. WHEN a new Provider is registered through the Provider interface, THE Search_Hub SHALL make the Provider available for search requests without requiring changes to other Providers.

### Requirement 7: Reverse Image Search Correlation

**User Story:** As a journalist, I want reverse image search results correlated into a source timeline, so that I can find the original source and earliest appearance of an image.

#### Acceptance Criteria

1. WHEN a Case enters the reverse search stage, THE Reverse_Search_Engine SHALL submit the image to the image search Providers through the Search_Hub.
2. WHEN reverse search results are returned, THE Reverse_Search_Engine SHALL classify each result as an exact match or a near match.
3. WHEN reverse search results include publication dates, THE Reverse_Search_Engine SHALL identify the oldest appearance among the results.
4. WHEN reverse search results are correlated, THE Reverse_Search_Engine SHALL record the list of websites on which the image appears.
5. WHEN reverse search results are correlated, THE Reverse_Search_Engine SHALL produce a source and discovery timeline ordered by date.
6. IF no reverse search matches are found, THEN THE Reverse_Search_Engine SHALL record that no matches were found for the Case.

### Requirement 8: Autonomous AI Search Agent

**User Story:** As an OSINT investigator, I want an autonomous agent to plan and run searches, so that I get ranked candidate locations without manually querying each engine.

#### Acceptance Criteria

1. WHEN an Analyst starts the AI_Search_Agent for a Case, THE AI_Search_Agent SHALL analyze the image and the existing Case findings.
2. WHEN analysis is complete, THE AI_Search_Agent SHALL generate search queries derived from the Case findings.
3. WHEN search queries are generated, THE AI_Search_Agent SHALL execute the queries through the Search_Hub.
4. WHEN search results are returned, THE AI_Search_Agent SHALL rank the results and produce at most the top 20 candidate locations.
5. WHEN a candidate location is produced, THE AI_Search_Agent SHALL associate a Confidence_Score with the candidate location.

### Requirement 9: Map Correlation

**User Story:** As an investigator, I want image content compared against map and street-level sources, so that I can confirm a candidate location.

#### Acceptance Criteria

1. WHEN a candidate location is available for a Case, THE Map_Correlation_Engine SHALL retrieve map and street-level imagery for the candidate location from the map Providers.
2. WHEN map imagery is retrieved, THE Map_Correlation_Engine SHALL compare road layouts, building shapes, and terrain between the image and the map imagery.
3. WHEN a comparison is performed, THE Map_Correlation_Engine SHALL produce a location Confidence_Score for the candidate location.
4. THE Map_Correlation_Engine SHALL rank compared candidate locations in descending order of location Confidence_Score.

### Requirement 10: Object Detection

**User Story:** As an investigator, I want objects detected and classified, so that I can build an inventory of evidence visible in the image.

#### Acceptance Criteria

1. WHEN a Case enters the object stage, THE Object_Engine SHALL detect objects including faces, vehicles, logos, animals, aircraft, boats, and buildings.
2. WHEN an object is detected, THE Object_Engine SHALL record the object class, bounding region, and a Confidence_Score.
3. WHEN object detection is complete, THE Object_Engine SHALL produce an object intelligence inventory for the Case.
4. IF no objects meet the configured minimum Confidence_Score, THEN THE Object_Engine SHALL record that no objects were detected for the Case.

### Requirement 11: Face Analysis

**User Story:** As an investigator, I want faces detected, counted, and clustered, so that I can identify how many distinct individuals appear across an investigation while preserving privacy.

#### Acceptance Criteria

1. WHEN a Case enters the face stage, THE Face_Engine SHALL detect faces in the image.
2. WHEN faces are detected, THE Face_Engine SHALL record the count of detected faces.
3. WHEN multiple faces are detected across a Case, THE Face_Engine SHALL cluster faces that share visual similarity.
4. WHEN a face is detected, THE Face_Engine SHALL record face attributes without storing externally resolvable personal identity data.
5. IF no faces are detected, THEN THE Face_Engine SHALL record a face count of zero for the Case.

### Requirement 12: Image Tampering Detection

**User Story:** As a DFIR analyst, I want manipulation of an image detected and localized, so that I can determine whether an image has been edited.

#### Acceptance Criteria

1. WHEN a Case enters the tampering stage, THE Tampering_Engine SHALL analyze the image for copy-move, cloning, object removal, object insertion, and splicing.
2. WHEN tampering analysis is performed, THE Tampering_Engine SHALL apply error level analysis, noise analysis, JPEG quantization analysis, compression analysis, and PRNU analysis.
3. WHERE tampering indicators are found and heatmap production succeeds, THE Tampering_Engine SHALL produce a tampering heatmap identifying the affected regions.
4. WHEN tampering analysis is complete, THE Tampering_Engine SHALL produce a tampering Confidence_Score for the Case.
5. IF heatmap production fails while tampering indicators are detected, THEN THE Tampering_Engine SHALL record the tampering detection and record that the heatmap was not produced.

### Requirement 13: AI-Generated Image Detection

**User Story:** As a journalist, I want to know whether an image was generated by an AI model, so that I can assess its authenticity.

#### Acceptance Criteria

1. WHEN a Case enters the AI-detection stage, THE AI_Image_Engine SHALL analyze the image for generation artifacts and metadata signatures associated with generative models.
2. WHEN analysis is complete, THE AI_Image_Engine SHALL produce an AI-generation probability expressed as a Confidence_Score.
3. WHERE generator-specific signatures are detected, THE AI_Image_Engine SHALL record the suspected generator family.
4. IF the AI-generation probability meets the configured alert threshold, THEN THE AI_Image_Engine SHALL flag the Case as likely AI-generated.

### Requirement 14: Deepfake Detection

**User Story:** As a threat intelligence analyst, I want synthetic and face-swapped imagery detected, so that I can identify fabricated media.

#### Acceptance Criteria

1. WHEN a Case contains at least one detected face, THE Deepfake_Engine SHALL analyze each detected face for face-swap and synthetic generation indicators.
2. WHEN analysis is complete, THE Deepfake_Engine SHALL produce an authenticity Confidence_Score for the Case.
3. IF the authenticity Confidence_Score falls below the configured alert threshold, THEN THE Deepfake_Engine SHALL flag the Case as likely deepfake.
4. IF no face is present in the Case, THEN THE Deepfake_Engine SHALL record that deepfake analysis was not applicable.

### Requirement 15: Steganography Analysis

**User Story:** As a CTF player, I want hidden data inside images detected and extracted, so that I can recover concealed payloads.

#### Acceptance Criteria

1. WHEN a Case enters the steganography stage, THE Stego_Engine SHALL scan the image for embedded archives, text, files, and payloads.
2. WHEN embedded data is detected, THE Stego_Engine SHALL extract the embedded data as a Case artifact.
3. WHEN steganography analysis is complete, THE Stego_Engine SHALL produce a steganography suspicion Risk_Score for the Case.
4. IF no embedded data is detected, THEN THE Stego_Engine SHALL record that no hidden data was found for the Case.

### Requirement 16: CTF Investigation Mode

**User Story:** As a CTF player, I want one-click access to common CTF image techniques, so that I can rapidly investigate challenge images.

#### Acceptance Criteria

1. WHEN an Analyst activates CTF Investigation Mode for a Case, THE CTF_Engine SHALL run hidden ZIP detection, QR detection, Base64 detection, RGB channel splitting, channel analysis, entropy analysis, file carving, and LSB analysis.
2. IF an individual CTF technique fails to execute, THEN THE CTF_Engine SHALL record the technique failure and continue running the remaining techniques.
3. WHEN a hex view is requested for a Case, THE CTF_Engine SHALL present the raw bytes of the image in hexadecimal form.
4. WHEN a CTF technique recovers data, THE CTF_Engine SHALL store the recovered data as a Case artifact.
5. WHEN CTF Investigation Mode completes, THE CTF_Engine SHALL produce a summary of the techniques run and their outcomes.

### Requirement 17: Threat Intelligence Assessment

**User Story:** As a SOC analyst, I want images assessed for fraud and phishing indicators, so that I can triage potentially malicious media.

#### Acceptance Criteria

1. WHEN a Case enters the threat stage, THE Threat_Engine SHALL evaluate the image for fake identity documents, fabricated screenshots, scam imagery, and phishing assets.
2. WHEN threat evaluation is complete, THE Threat_Engine SHALL produce a threat Risk_Score for the Case.
3. WHEN threat indicators are found, THE Threat_Engine SHALL record each detected indicator with its category.
4. IF the threat Risk_Score meets the configured alert threshold, THEN THE Threat_Engine SHALL flag the Case as a potential threat.

### Requirement 18: Weather and Shadow Analysis

**User Story:** As an investigator, I want capture time estimated from environmental cues, so that I can corroborate or challenge a claimed timestamp.

#### Acceptance Criteria

1. WHEN a Case enters the weather stage, THE Weather_Engine SHALL detect shadow direction and shadow angle present in the image.
2. WHERE shadows are detected, THE Weather_Engine SHALL estimate the sun direction and the time of day.
3. WHEN environmental cues are analyzed, THE Weather_Engine SHALL estimate the weather conditions at capture time.
4. WHEN time estimation is complete, THE Weather_Engine SHALL associate a Confidence_Score with the estimated capture time.
5. IF no shadows or environmental cues are detected, THEN THE Weather_Engine SHALL record that capture time could not be estimated for the Case and SHALL indicate that time estimation is not possible.

### Requirement 19: Knowledge Graph

**User Story:** As an investigator, I want all findings linked into an interactive graph, so that I can explore relationships between evidence in one place.

#### Acceptance Criteria

1. WHEN investigation stages complete for a Case, THE Knowledge_Graph SHALL create nodes for the image, extracted text, detected objects, businesses, websites, search results, locations, map references, similar images, and social profiles.
2. WHEN nodes are created, THE Knowledge_Graph SHALL create edges representing the relationships between connected nodes.
3. IF node creation fails, THEN THE Platform SHALL present the investigation view without the Knowledge_Graph and display an error message.
4. WHEN an Analyst selects a node, THE Knowledge_Graph SHALL display the node details and its directly connected nodes.
5. THE Knowledge_Graph SHALL present the graph as an interactive visualization within the investigation view.

### Requirement 20: Report Generation

**User Story:** As an investigator, I want a complete investigation report exported, so that I can share findings with stakeholders.

#### Acceptance Criteria

1. WHEN an Analyst requests a report for a Case, THE Report_Generator SHALL compile the findings from all completed investigation stages.
2. WHEN a report is compiled, THE Report_Generator SHALL include an executive summary, the per-stage findings, and a final Confidence_Score.
3. WHERE the requested format is PDF, DOCX, or JSON, THE Report_Generator SHALL produce the report in the requested format.
4. IF a report is requested for a Case with no completed investigation stages, THEN THE Report_Generator SHALL return a message stating that no findings are available to report without generating a report structure.

### Requirement 21: Investigation Pipeline Orchestration

**User Story:** As an Analyst, I want the analysis stages to run automatically after ingestion, so that I receive a complete investigation without triggering each stage manually.

#### Acceptance Criteria

1. WHEN a Case is created, THE Investigation_Pipeline SHALL execute the metadata, GEOINT, landmark, OCR, reverse search, object, face, tampering, AI-detection, deepfake, steganography, threat, and weather stages.
2. THE Investigation_Pipeline SHALL execute analysis stages asynchronously.
3. IF an individual stage fails, THEN THE Investigation_Pipeline SHALL record the stage failure and continue executing the remaining stages.
4. WHEN a stage completes, THE Investigation_Pipeline SHALL update the Case with the stage status and results.
5. WHEN all stages reach a terminal state, THE Investigation_Pipeline SHALL mark the Case investigation as complete.

### Requirement 22: Dashboard and Investigation User Interface

**User Story:** As an Analyst, I want a dashboard with navigation and a tabbed investigation view, so that I can manage cases and review findings efficiently.

#### Acceptance Criteria

1. THE Platform SHALL present a dashboard with sidebar navigation to the Platform capability areas.
2. WHEN an Analyst opens a Case, THE Platform SHALL present the investigation view with tabbed sections for the investigation stages.
3. WHILE a Case investigation is in progress, THE Platform SHALL display the status of each investigation stage.
4. WHEN a stage produces results, THE Platform SHALL display the results within the corresponding tab.

### Requirement 23: Authentication and Authorization

**User Story:** As a security administrator, I want access controlled by authenticated identity and role, so that only authorized users can perform sensitive actions.

#### Acceptance Criteria

1. WHEN an Analyst submits valid credentials, THE Authentication_Service SHALL authenticate the Analyst and issue a signed session token.
2. IF an Analyst submits invalid credentials, THEN THE Authentication_Service SHALL deny authentication and return an authentication failure message.
3. WHEN an Analyst requests a protected resource without a valid session token, THE Authorization_Service SHALL deny the request.
4. WHEN an Analyst requests an action, THE Authorization_Service SHALL permit the action only where the Analyst's assigned role grants the required permission.
5. IF an Analyst's role does not grant the required permission, THEN THE Authorization_Service SHALL deny the action and return an authorization failure message.

### Requirement 24: Secure File Handling

**User Story:** As a security administrator, I want uploaded files scanned and isolated, so that malicious uploads cannot compromise the Platform.

#### Acceptance Criteria

1. WHEN a file is uploaded, THE Ingestion_Engine SHALL scan the file for malware before processing.
2. IF a malware scan identifies a file as malicious, THEN THE Ingestion_Engine SHALL reject the file and record the rejection in the Audit_Log.
3. WHEN a file is accepted, THE Ingestion_Engine SHALL validate that the file content matches a Supported_Format independently of the file extension.
4. THE Platform SHALL store uploaded files in object storage isolated from application execution paths.

### Requirement 25: Platform Security Controls

**User Story:** As a security administrator, I want standard web security controls enforced, so that the Platform resists common attacks.

#### Acceptance Criteria

1. WHEN the Platform serves a response, THE Platform SHALL include a Content Security Policy header.
2. WHEN an Analyst submits a state-changing request, THE Platform SHALL validate a CSRF token before processing the request.
3. WHEN the number of requests from a client exceeds the configured rate limit, THE Platform SHALL reject further requests from that client until the rate limit window resets.
4. WHERE the configured rate limit is zero, THE Platform SHALL reject all requests subject to rate limiting.
5. THE Platform SHALL retrieve secrets from a secrets management mechanism rather than from source code.
6. WHEN a security-relevant action is performed, THE Platform SHALL record the action in the append-only Audit_Log.

### Requirement 26: Data Persistence and Indexing

**User Story:** As an Analyst, I want cases and findings persisted and searchable, so that I can revisit and correlate prior investigations.

#### Acceptance Criteria

1. WHEN a Case is created or updated, THE Platform SHALL persist the Case and its findings in the relational data store.
2. WHEN a Case is persisted, THE Platform SHALL index the Case findings in the search index.
3. IF indexing fails after the Case is persisted, THEN THE Platform SHALL retain the persisted Case and record the indexing failure.
4. WHEN an Analyst searches indexed findings, THE Platform SHALL return the matching Cases the Analyst is authorized to access.
5. WHEN an Analyst reopens a persisted Case, THE Platform SHALL restore the Case findings and artifacts.
