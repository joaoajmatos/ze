# Quickstart: Speech-Act System One (163)

```bash
make test-memory   # gate, thresholds, fallback — mocked clients
make test-core     # judgments attach to the trace
```

Enable (only after calibrating the bars on Ze fixtures, including Portuguese):

```yaml
system_one:
  enabled: true
  surfaces:
    speech_act:
      enabled: true
      act_min_peakedness: <measured>
      family_min_peakedness: <measured>
      biography_min: <measured>
```

Missing any bar keeps the surface off and the pre-163 judge runs. Check a turn's trace "Judgments" section: `speech_act` (and `family` + `biography` for fact acts) show `consumed`.
