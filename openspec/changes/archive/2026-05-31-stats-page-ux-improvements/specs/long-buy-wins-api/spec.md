## MODIFIED Requirements

### Requirement: Response schema for long-buy-history
The endpoint SHALL return `prospectai_version` (string | null) as an additional field on each history item. All other fields remain unchanged.

#### Scenario: prospectai_version included in response
- **WHEN** a valid request is made to `GET /api/long-buy-history`
- **THEN** each item in the `history` array includes a `prospectai_version` field whose value is the version string stored on the record (e.g. `"1.9.0"`) or `null` if the field was not present on the stored record
