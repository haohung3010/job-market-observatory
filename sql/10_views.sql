-- The populations every later query reads. Run by scripts/build_db.py after the load.

-- BC postings in health occupations: NOC 2021 broad category 3.
drop view if exists bc_health;
create view bc_health as
select *
from postings
where province = 'British Columbia'
  and noc21 like '3%';

-- BC job vacancies for the quarter, one row per NOC code at every level the table publishes.
-- The code is the text between the square brackets: '3' broad category, '31' major group, '311' sub-major,
-- '3111' minor, '31110' unit group. A NULL value is NOT PUBLISHED (status F or '..' or 'x'), never zero.
drop view if exists bc_vacancies;
create view bc_vacancies as
select substr(noc, instr(noc, '[') + 1, instr(noc, ']') - instr(noc, '[') - 1) as code,
       noc as noc_label,
       value as vacancies,
       status
from vacancies
where geo = 'British Columbia'
  and statistic = 'Job vacancies'
  and instr(noc, '[') > 0;
