# Candidate profile

Put your own background here as `candidate_profile.md` in this folder
(copy `candidate_profile.example.md` as a starting point). It's read by
`app/profile.py` and used by the grading layer to steer fit matching —
your skills get merged into the keyword list, so scoring reflects who
you actually are instead of the plan's generic default keyword list.

`candidate_profile.md` is gitignored since it's personal information.
Only the example/template stays in version control.

## Format expectations

Plain markdown. The loader specifically looks for a heading called
`Skills` (or `Keywords` / `Tech Stack` / `Technologies`) and reads its
bullet list as extra keywords — everything else in the file is free
text for your own reference and for future use in more refined
matching (target roles, locations, level, what to avoid).
