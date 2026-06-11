# Modular Report Skeleton

Drop this whole directory wherever you need to start a new long-form report. It is the proven
scaffold from `~/skills-report/` (skills-collapse performance report 2026-06-05).

## Pre-flight (one time)

```bash
cp -r <this skill>/templates/modular-report-skeleton ~/my-report
cd ~/my-report
mkdir -p data sections styles
```

Then fill in:
- `data/meta.json` — title, lede, KPIs, footer text, core stats
- `data/<topic>.json` — one JSON per data domain (memory, persona, categories, etc.)
- `sections/<sNN>_<name>.py` — one render function per section
- `styles/main.css` — copy from the host skill's `templates/modular-report-skeleton/main.css`
- `build.py` — already provided, edit `OUT_PATH` to point at your output file

## Workflow

```bash
python3 build.py            # full build, run after structural changes
python3 build.py memory     # rebuild just one section after data tweak
```

Each section's render() returns a string of HTML. `build.py` wraps it in
`<!-- BEGIN: SECTION-XX --> ... <!-- END: SECTION-XX -->` markers so partial
rebuilds can find and replace just that block.

## When to use this scaffold vs single-file HTML

Use modular when:
- Report content will be revised more than once (status dashboards, performance reports, project overviews)
- Total output ≥ 60KB or ≥ 3 sections
- Different sections have different data sources that update on different cadences
- Multiple people / future-you will edit different parts

Use single-file when:
- One-shot announcement, landing page, frozen historical snapshot
- < 30KB
- No iteration expected

The 2026-06-05 skills-collapse report iterated 6 times (mostly to tweak numbers in
one section while the rest stayed identical). That was the trigger for this refactor.
