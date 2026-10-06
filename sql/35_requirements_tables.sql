-- The requirements tables: what BC health employers ask for, by minor group (four-digit NOC 2021), 2026 Q2.
-- Read from direct employer postings only (external = '0'); external postings carry 'NA' in both fields and their
-- share of each group is printed beside every row, so a reader sees how much of the group the figures rest on.
-- Groups with fewer than 20 direct postings are shown and marked 'not cited'.

-- Education, in the publisher's wording, placed on one ladder.
drop view if exists education_ladder;
create view education_ladder as
select education,
       case education
           when 'No degree, certificate or diploma' then 0
           when 'Secondary (high) school graduation certificate' then 1
           when 'Registered Apprenticeship certificate' then 2
           when 'Other trades certificate or diploma' then 2
           when 'College, CEGEP or other non-university certificate or diploma from a program of 3 months to less than 1 year' then 3
           when 'College, CEGEP or other non-university certificate or diploma from a program of 1 year to 2 years' then 4
           when 'College/CEGEP' then 4
           when 'Bachelor''s degree' then 5
           when 'Master''s degree' then 6
           when 'Degree in medicine, dentistry, veterinary medicine or optometry' then 7
           when 'Earned doctorate degree' then 7
       end as rung,
       case
           when education in ('No degree, certificate or diploma',
                              'Secondary (high) school graduation certificate') then 'secondary or none'
           when education in ('Registered Apprenticeship certificate', 'Other trades certificate or diploma',
                              'College/CEGEP')
             or education like 'College, CEGEP or other%' then 'college or trades'
           when education = 'Bachelor''s degree' then 'bachelor''s'
           when education in ('Master''s degree', 'Earned doctorate degree',
                              'Degree in medicine, dentistry, veterinary medicine or optometry') then 'graduate or professional'
           else null   -- a value no band names stays null and is caught by requirements_check, never counted high
       end as band
from (select distinct education from bc_health where external = '0');

-- Experience bands, in months, on one ladder.
drop view if exists experience_ladder;
create view experience_ladder as
select experience,
       case experience
           when 'No experience' then 0
           when '1 to less than 7 months' then 1
           when '7 months to less than 1 year' then 7
           when '1 year to less than 2 years' then 12
           when '2 years to less than 3 years' then 24
           when '3 years to less than 5 years' then 36
           when '5 years or more' then 60
       end as min_months
from (select distinct experience from bc_health where external = '0');

-- [CONTROL] every value seen in the data must sit on a ladder; a null rung here is a value the ladder missed.
drop view if exists ladder_check;
create view ladder_check as
select 'education' as field, count(*) as values_seen, sum(rung is null) as off_ladder from education_ladder
union all
select 'experience', count(*), sum(min_months is null) from experience_ladder;

drop view if exists requirements_by_group;
create view requirements_by_group as
with g as (
    select substr(p.noc21, 1, 4) as minor_group,
           count(*) as postings,
           sum(p.external = '0') as direct
    from bc_health p
    group by 1
),
d as (
    select substr(p.noc21, 1, 4) as minor_group,
           sum(e.band = 'secondary or none') as edu_secondary,
           sum(e.band = 'college or trades') as edu_college,
           sum(e.band = 'bachelor''s') as edu_bachelor,
           sum(e.band = 'graduate or professional') as edu_graduate,
           sum(x.min_months = 0) as exp_none,
           sum(x.min_months between 1 and 11) as exp_under_1y,
           sum(x.min_months between 12 and 35) as exp_1_to_3y,
           sum(x.min_months >= 36) as exp_3y_plus
    from bc_health p
    left join education_ladder e on e.education = p.education
    left join experience_ladder x on x.experience = p.experience
    where p.external = '0'
    group by 1
)
select g.minor_group,
       (select noc_label from bc_vacancies v where v.code = g.minor_group) as label,
       g.postings,
       g.direct,
       round(100.0 * g.direct / g.postings, 1) as direct_pct,
       round(100.0 * d.edu_secondary / g.direct, 1) as edu_secondary_pct,
       round(100.0 * d.edu_college / g.direct, 1) as edu_college_pct,
       round(100.0 * d.edu_bachelor / g.direct, 1) as edu_bachelor_pct,
       round(100.0 * d.edu_graduate / g.direct, 1) as edu_graduate_pct,
       round(100.0 * d.exp_none / g.direct, 1) as exp_none_pct,
       round(100.0 * d.exp_under_1y / g.direct, 1) as exp_under_1y_pct,
       round(100.0 * d.exp_1_to_3y / g.direct, 1) as exp_1_to_3y_pct,
       round(100.0 * d.exp_3y_plus / g.direct, 1) as exp_3y_plus_pct,
       case when g.direct >= 20 then 'cited' else 'not cited (fewer than 20 direct postings)' end as status
from g join d on d.minor_group = g.minor_group
order by g.direct desc;

-- [CONTROL] every direct posting must land in exactly one education band and one experience band, so each group's
-- band counts sum to its direct postings. run_all.py stops when any row here is non-zero (second read, 2026-10-06).
drop view if exists requirements_check;
create view requirements_check as
select substr(p.noc21, 1, 4) as minor_group,
       count(*) as direct,
       count(*) - sum(e.band is not null) as education_unbanded,
       count(*) - sum(x.min_months is not null) as experience_unbanded
from bc_health p
left join education_ladder e on e.education = p.education
left join experience_ladder x on x.experience = p.experience
where p.external = '0'
group by 1;
