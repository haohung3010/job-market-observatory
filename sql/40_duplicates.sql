-- How many postings may be the same job listed twice. Reported as a bracket, never one number.
-- STRICT: the publisher's posting id. Measured unique across the quarter, so the strict count is zero.
-- LOOSE: same title, occupation, city, first posting date and source. An over-count: one employer posting two
-- identical vacancies on one day reads as a repeat. The feed carries no employer name, so it cannot be tighter.

drop view if exists duplicates;
create view duplicates as
select 'strict: same posting id' as definition,
       (select count(*) - count(distinct id) from bc_health) as repeat_postings,
       (select count(*) from bc_health) as postings
union all
select 'loose: same title, NOC, city, date and source',
       (select sum(n - 1) from (select count(*) as n from bc_health
                                group by lower(title), noc21, lower(city), first_posting_date, external
                                having count(*) > 1)),
       (select count(*) from bc_health);
