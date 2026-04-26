# Domain Model

Core entities:

- Catalog: `Product`, `Sku`, `SkuAlias`, `Category`
- Clients: `Client`, `ClientAlias`, `DiyPolicy`
- Ingestion: `UploadBatch`, `UploadFile`, `UploadedRowIssue`, `MappingTemplate`, `MappingRule`, `DataSource`
- Operational facts: `SalesFact`, `StockSnapshot`, `InboundDelivery`
- Reserve: `ReserveRun`, `ReserveRow`
- Quality: `QualityIssue`
- Operations: `User`, `Role`, `AccessPolicy`, `JobRun`, `SystemEvent`

Design notes:

- Raw uploads are never discarded; file metadata and row-level issues remain traceable.
- Facts carry `source_batch_id` where applicable so lineage survives recalculation.
- Reserve rows store fallback path and explanation payload, making shortages explainable.
