## ADDED Requirements

### Requirement: Perceptual duplicate matches use corroborating hashes

PhotoRAG SHALL require a dHash match and corroboration from at least one of aHash or pHash before recording a perceptual duplicate. It SHALL exclude absolutely uniform images as both source and candidate images. Exact file-hash matches SHALL remain unchanged.

#### Scenario: A detailed photo and a uniform image share a nearby dHash

- **WHEN** their aHash and pHash distances do not corroborate the dHash match
- **THEN** PhotoRAG does not record them as perceptual duplicates

#### Scenario: Two uniform images have identical perceptual hashes

- **WHEN** a uniform image is processed or an older uniform image is encountered as a candidate
- **THEN** PhotoRAG excludes the uniform image from near-duplicate matching

#### Scenario: Perceptual hashes corroborate a real duplicate

- **WHEN** dHash and at least one additional hash are within the documented thresholds for two non-uniform photos
- **THEN** PhotoRAG records their perceptual duplicate relationship

#### Scenario: An older perceptual record has no corroborating hashes

- **WHEN** PhotoRAG displays a previously stored perceptual match whose source or candidate is uniform or lacks corroborating hashes
- **THEN** PhotoRAG omits that stale match from the duplicate results
- **AND** exact file-hash duplicates remain visible

#### Scenario: Files are byte-identical

- **WHEN** two image files have the same exact file hash
- **THEN** PhotoRAG retains the existing exact-duplicate behavior regardless of perceptual quality checks
