# sudoers-trim — submission sheet

**Phase-1 idea check (advisory):**
Least privilege sudo review on a 21 host Debian bookworm fleet running sudo 1.9.13. The agent gets the fleet wide sudoers tree that ansible pushes (aliases, User_Alias with a negated member, Runas carry forward, a blanket sre (ALL) ALL with !SHELLS, a change freeze of negated entries, a #uid legacy rule, and a stale .orig drop in that sudo skips), an LDAP export (shadowExpire, posixGroup), CMDB records (renames, a retired host, a new one) and 18 weeks of rotated auth.log in two syslog formats. It must write /app/sudoers that keeps, per person, only the rule entries sudo actually decided their runs with (last match wins, today's groups, former host names mapped) between 2025-11-18 and 2026-02-15. Blanket ALL turns into exact command lines with sudoers escaping. Every kept `*` is tightened to one word (anchored POSIX ERE, no lookahead for excluding . and ..). Today's refusals still apply. Graded all or nothing by real sudo -l over 8,468 sealed queries. Naive readings (first match, keep the alias the user seems to use, old groups, ignore renames, keep the .orig file, leave `*` as a glob) each fail between 3 and 733 queries.

**Category:** Security
**Labels:** AppSec, Forensics
**Task name:** sudoers-trim
**Bundle:** tasks/sudoers-trim/sudoers-trim.zip
