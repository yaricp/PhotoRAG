- [x] **1. Schemas (`src/schemas.py`)**
  - [x] Add `PaginatedResponse` generic model.
  - [x] Ensure all necessary exports are present for endpoints.

- [x] **2. Database Layer (`src/db_service.py`)**
  - [x] Update `get_all_photos` to handle pagination, sorting, and filtering.
  - [x] Implement `get_all_tags`
  - [x] Implement `get_all_cameras`
  - [x] Implement `get_all_geopositions`

- [x] **3. API Endpoints (`src/main.py`)**
  - [x] Update `GET /api/photos/` with filtering and `PaginatedResponse`.
  - [x] Create `GET /api/tags/`
  - [x] Create `GET /api/categories/`
  - [x] Create `GET /api/cameras/`
  - [x] Create `GET /api/geopositions/`

- [x] **4. API Tests (`tests/test_main.py`)**
  - [x] Add test for `GET /api/system/status/`
  - [x] Add test for `GET /api/watchers/`
  - [x] Add test for `GET /api/photos/{photo_id}`
  - [x] Add test for `GET /api/photos/` (with pagination/filters)
  - [x] Add test for `POST /api/search/`
  - [x] Add tests for metadata endpoints (`tags`, `categories`, `cameras`, `geopositions`)

- [x] **5. Verification**
  - [x] Run `pytest backend/tests/test_main.py`
  - [x] Run `pytest backend/tests` to verify Global Green.
