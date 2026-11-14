-- One row per drug listed on a report. Drug names are free text here;
-- mapping to RxNorm (the drug master) happens downstream in Phase 2.

with reports as (

    select * from {{ ref('base_openfda__latest_reports') }}

)

select
    concat(reports.safety_report_id, '-', cast(drug_offset + 1 as string)) as report_drug_id,
    reports.safety_report_id,
    drug_offset + 1 as drug_seq,
    json_value(drug, '$.medicinalproduct') as medicinal_product,
    case json_value(drug, '$.drugcharacterization')
        when '1' then 'suspect'
        when '2' then 'concomitant'
        when '3' then 'interacting'
    end as drug_role,
    json_value(drug, '$.drugindication') as drug_indication,
    json_value_array(drug, '$.openfda.rxcui') as openfda_rxcuis,
    json_value_array(drug, '$.openfda.generic_name') as openfda_generic_names,
    reports._ingest_id
from reports,
    unnest(json_query_array(reports.payload, '$.patient.drug')) as drug with offset as drug_offset
