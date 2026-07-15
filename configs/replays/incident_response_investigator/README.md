# Production Incident Investigator Replay Fixtures

This directory is reserved for captured real-run replay fixtures.

Do not commit invented or synthetic incident data here. A replay fixture must be exported from
a real authorized run and must declare `provenance: captured_real_run`.

Expected file name:

```text
{source_run_id}.json
```

The runtime resolves `replay_source_run_id` from `POST /workflow-runs` to a fixture in this
directory, or from `REPLAY_FIXTURE_DIR` when that environment variable is configured.

Replay fixtures use schema version `incident_response_investigator.replay.v1` and must include
`data_policy.fake_data_allowed: false`.
