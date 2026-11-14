-- One row per adverse reaction on a report, coded as a MedDRA preferred term.

with reports as (

    select * from {{ ref('base_openfda__latest_reports') }}

)

select
    concat(reports.safety_report_id, '-', cast(reaction_offset + 1 as string))
        as report_reaction_id,
    reports.safety_report_id,
    reaction_offset + 1 as reaction_seq,
    upper(json_value(reaction, '$.reactionmeddrapt')) as meddra_preferred_term,
    case json_value(reaction, '$.reactionoutcome')
        when '1' then 'recovered'
        when '2' then 'recovering'
        when '3' then 'not recovered'
        when '4' then 'recovered with sequelae'
        when '5' then 'fatal'
        when '6' then 'unknown'
    end as reaction_outcome,
    reports._ingest_id
from reports,
    unnest(json_query_array(reports.payload, '$.patient.reaction'))
        as reaction with offset as reaction_offset
