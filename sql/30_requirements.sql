-- What BC health employers ask for: education and years, from direct employer postings only.
-- External postings (external = '1') carry 'NA' in both fields, so they are excluded here and counted in
-- requirements_coverage, which states how much of the population these figures rest on.

drop view if exists requirements_coverage;
create view requirements_coverage as
select substr(noc21, 1, 2) as major_group,
       count(*) as postings,
       sum(external = '0') as direct_postings,
       round(100.0 * sum(external = '0') / count(*), 1) as direct_pct
from bc_health
group by 1;

drop view if exists education_required;
create view education_required as
select substr(noc21, 1, 2) as major_group, education, count(*) as postings
from bc_health
where external = '0'
group by 1, 2;

drop view if exists experience_required;
create view experience_required as
select substr(noc21, 1, 2) as major_group, experience, count(*) as postings
from bc_health
where external = '0'
group by 1, 2;
