-- The trust test: each health occupation's share of BC postings against its share of BC vacancies, 2026 Q2.
--
-- Shares are within health occupations (NOC code '3'): the survey counts vacancies on one day of each month (a
-- stock), while postings are counted when first posted (a flow), so counts are not comparable and shares are.
--
-- Revised on an independent second read of this method:
--   1. every level carries an '(unpublished)' row on BOTH sides: the vacancies Statistics Canada does not publish
--      at that level, and the postings in those same codes. Shares are also shown renormalised to published codes.
--   2. claims are gated, not rows: every published cell is shown with its grade; a gap is CLAIMED only for grades
--      A to D whose sign holds for all postings, direct postings and external postings AND whose every arm is at
--      least 2 points from zero (smaller gaps sit inside the duplicate bracket); grade E is shown as 'caution',
--      never cited; an unpublished cell is 'unmeasured', never zero. The 2-point floor is a judgement, not a
--      measurement, and is stated as one in METHODS.md.
--   3. what this cannot carry is stated in METHODS.md (stock against flow, no expiry date in the feed, one quarter).

drop view if exists representativeness;
create view representativeness as
with levels(lvl) as (values (2), (4)),
post as (
    select l.lvl, substr(p.noc21, 1, l.lvl) as code,
           count(*) as n_all, sum(p.external = '0') as n_direct, sum(p.external = '1') as n_external
    from bc_health p cross join levels l
    group by 1, 2
),
tot as (
    select count(*) as all_t, sum(external = '0') as direct_t, sum(external = '1') as external_t,
           (select vacancies from bc_vacancies where code = '3') as vac_t
    from bc_health
),
vac as (
    select l.lvl, v.code, v.noc_label, v.vacancies, v.status
    from bc_vacancies v join levels l on length(v.code) = l.lvl
    where v.code like '3%'
),
pub as (   -- published vacancies and the postings in published codes, per level
    select v.lvl, sum(v.vacancies) as vac_pub, coalesce(sum(p.n_all), 0) as post_pub
    from vac v left join post p on p.lvl = v.lvl and p.code = v.code
    where v.vacancies is not null
    group by v.lvl
),
rows_ as (
    select v.lvl, v.code, v.noc_label, v.status, v.vacancies,
           coalesce(p.n_all, 0) as n_all, coalesce(p.n_direct, 0) as n_direct, coalesce(p.n_external, 0) as n_external
    from vac v left join post p on p.lvl = v.lvl and p.code = v.code
    union all
    select u.lvl, '(unpublished)', 'codes whose vacancies are not published at this level', 'F or ..',
           t.vac_t - u.vac_pub,
           t.all_t - u.post_pub,
           null, null
    from pub u cross join tot t
),
g as (
    select r.*, t.vac_t, t.all_t, t.direct_t, t.external_t, u.vac_pub, u.post_pub,
           100.0 * r.vacancies / t.vac_t as vac_share,
           100.0 * r.n_all / t.all_t as share_all,
           100.0 * r.n_direct / t.direct_t as share_direct,
           100.0 * r.n_external / t.external_t as share_external
    from rows_ r cross join tot t join pub u on u.lvl = r.lvl
)
select lvl as level_digits, code, noc_label, status as grade, vacancies, n_all as postings,
       round(vac_share, 1) as vacancy_share_pct,
       round(share_all, 1) as postings_share_pct,
       round(share_all - vac_share, 1) as gap_all,
       round(share_direct - vac_share, 1) as gap_direct,
       round(share_external - vac_share, 1) as gap_external,
       case when code = '(unpublished)' or vacancies is null then null
            else round(100.0 * n_all / post_pub - 100.0 * vacancies / vac_pub, 1) end as gap_renormalised,
       case
         when code = '(unpublished)' then 'residual, shown for balance'
         when vacancies is null then 'unmeasured; its postings are inside (unpublished)'
         when status = 'E' then 'caution, not cited'
         when status not in ('A', 'B', 'C', 'D') then 'not claimed'
         when not ((share_all - vac_share) * (share_direct - vac_share) > 0
               and (share_all - vac_share) * (share_external - vac_share) > 0) then 'not claimed: sign not stable'
         when abs(share_all - vac_share) >= 2 and abs(share_direct - vac_share) >= 2
          and abs(share_external - vac_share) >= 2 then 'claimed'
         else 'consistent but small: not claimed'
       end as claim
from g;
