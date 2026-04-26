# Data Quality

Upload validation issues are now part of the product data-quality surface.

## Current Bridge

During validation and apply:

- row-level issues are stored in `UploadedRowIssue`
- mirrored records are emitted into `QualityIssue`

This allows:

- upload-local issue review on Mapping / Upload Center
- system-wide quality listing on `/quality`

## Severity Model

- `info`
- `warning`
- `error`
- `critical`

## Example Issue Codes

- `mapping_required`
- `required_field_missing`
- `invalid_numeric`
- `invalid_date`
- `negative_stock`
- `duplicate_row`
- `duplicate_upload`
- `duplicate_active_policy`
- `broken_hierarchy`
- `unmatched_client`
- `unmatched_sku`

## Next Step

Later phases can split `QualityIssueOccurrence` out of the current bridge if aggregation and remediation workflows need a stronger first-class quality domain.
