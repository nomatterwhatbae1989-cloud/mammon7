# MAMMON-7 Revenue Engine

Small, reliable, legitimate revenue and expense tracking engine.
All records are **SIMULATED** — no real income, payments, or customer data.
No payment processing, transfers, or external commitments.

## Modules (`src/`)

- `core.py` — `RevenueCore`: UTC ISO-8601 timestamps, UUID4-hex IDs.
- `revenue.py` — `RevenueRecord` (frozen) + `RevenueEngine` (create, validate, records).
- `expenses.py` — `ExpenseRecord` (frozen) + `ExpenseEngine` (create, validate, records).
- `ledger.py` — append-only JSONL persistence (`Ledger`); rebuilds records from disk.
- `profit.py` — totals, net profit, summary (SIMULATED-marked).

## V7 task worker (`v7/`)

`mammon7_v7.py` — Termux task worker + Mistral chat (standard library only).
V7.1 structured builder (JSON file generation, safe-path validation, package
dirs, ZIP + integrity checks, verification reports, SHA-256 hashes) plus:
unique task directories on same-second collisions, EOF-safe prompts,
duplicate-filename detection, removed unused import.
Does not submit applications, spend money, or make payments.

## Tests

```
python3 -m unittest discover -s tests
```

80 tests: core (5), revenue (19), expenses (19), ledger (20), profit (11), v7 (3), v7.1 end-to-end (3).

## License

Proprietary — all rights reserved. See `LICENSE`.
