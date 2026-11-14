-- One row per unique safety report (latest version).

with reports as (

    select * from {{ ref('base_openfda__latest_reports') }}

)

select
    safety_report_id,
    safety_report_version,
    safe.parse_date('%Y%m%d', json_value(payload, '$.receivedate')) as received_date,
    safe.parse_date('%Y%m%d', json_value(payload, '$.receiptdate')) as latest_receipt_date,

    -- openFDA: serious = 1 (serious) / 2 (not serious); seriousness flags are "1" or absent.
    json_value(payload, '$.serious') = '1' as is_serious,
    coalesce(json_value(payload, '$.seriousnessdeath') = '1', false) as is_death,
    coalesce(json_value(payload, '$.seriousnesshospitalization') = '1', false)
        as is_hospitalization,
    coalesce(json_value(payload, '$.seriousnesslifethreatening') = '1', false)
        as is_life_threatening,

    json_value(payload, '$.occurcountry') as occur_country,
    json_value(payload, '$.primarysource.qualification') as reporter_qualification_code,

    -- Patient demographics: candidates for PHI policy tags in Phase 3.
    safe_cast(json_value(payload, '$.patient.patientonsetage') as numeric) as patient_onset_age,
    json_value(payload, '$.patient.patientonsetageunit') as patient_onset_age_unit_code,
    json_value(payload, '$.patient.patientsex') as patient_sex_code,

    _ingest_id,
    _fetched_at
from reports
