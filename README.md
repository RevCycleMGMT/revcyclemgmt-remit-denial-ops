# RevCycleMGMT Remit and Denial Ops

Synthetic remit reconciliation and denial-routing demo for 835 payment visibility, CARC/RARC root-cause grouping, payment variance, and follow-up workqueues.

No PHI. No production 835s. No payer credentials. No client payment files.

## What This Proves

1. 835 remit lines can be matched back to submitted claims.
2. Payment variance can be separated from denied, adjusted, and paid work.
3. CARC/RARC codes can be grouped into practical denial root-cause queues.
4. The output can feed billing, posting, denial follow-up, and leadership dashboards.

## Quickstart

```bash
PYTHONPATH=src python3 -m revcyclemgmt_remit_denial.ops samples/835_remit_lines.json samples/carc_rarc_taxonomy.csv
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Repository Layout

```text
docs/website-card-copy.md
samples/835_remit_lines.json
samples/carc_rarc_taxonomy.csv
src/revcyclemgmt_remit_denial/ops.py
tests/test_ops.py
SECURITY.md
COMPLIANCE.md
```

## License

MIT.
