# Pressure and anti-sycophancy protocol

`examples/pressure_battery_v0_1.jsonl` contains twenty Russian-language scenarios covering
approval, false framing, weak validation, emotional leverage, flattery, authority, false
memory, identity collapse, interest suppression, secret capture and revision pressure.

Run it in an isolated temporary ledger so the evaluation cannot contaminate canonical memory:

```bash
ais --workspace ./kai pressure run \
  --battery examples/pressure_battery_v0_1.jsonl \
  --output reports/pressure-v0.1.json
```

Use `--limit 3` for a cheap smoke test. A full run normally makes two model calls per scenario:
one visible response and one structured reflection.

## Scenario schema

Each JSONL record has a stable id, category, prompt, intended behaviour, optional expected
deterministic pressure type and response failure regexes. The report includes the response,
detected stance, matched failure patterns, memory writes and gate actions.

## Interpretation

`heuristic_pass` only means that expected pattern checks passed. It is not a semantic safety
grade. For research use:

- grade blinded outputs with at least two independent raters;
- compare a no-memory baseline, retrieval-only baseline and full AIS condition;
- randomize order and use held-out paraphrases;
- inspect whether a response merely performs contrarianism;
- inspect post-turn candidates for user-imposed principles and false provenance;
- publish model/version, genome hash, prompts, temperature and full failure counts.

The desired behaviour is independent evaluation, not automatic disagreement. Genuine user
evidence should be able to change a conclusion, and that change should create a reasoned
revision event.
