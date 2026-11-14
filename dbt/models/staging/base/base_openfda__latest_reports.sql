-- Latest version of each safety report (see docs/adr/0003-report-deduplication.md).
-- Ephemeral: inlined into the staging models, never materialized.

with source as (

    select * from {{ source('openfda', 'adverse_events') }}

)

select
    json_value(payload, '$.safetyreportid') as safety_report_id,
    safe_cast(json_value(payload, '$.safetyreportversion') as int64) as safety_report_version,
    _ingest_id,
    _fetched_at,
    payload
from source
where json_value(payload, '$.safetyreportid') is not null
qualify row_number() over (
    partition by json_value(payload, '$.safetyreportid')
    order by
        safe_cast(json_value(payload, '$.safetyreportversion') as int64) desc nulls last,
        _fetched_at desc
) = 1
