# ExecPlan — Pluggable Stream Processing: Flink and Spark Structured Streaming

## 1. Objective

Add stream-processing capabilities while preserving engine choice.

The repository must support:

- Apache Flink implementation;
- Spark Structured Streaming / PySpark implementation;
- shared event contracts;
- shared expected-output fixtures;
- independent deployment of one engine at a time.

## 2. Important Constraint

Do not build an artificial runtime interface that attempts to make Flink and Spark APIs identical.

Instead standardize:

- Kafka input topics;
- Kafka output topics;
- schemas;
- semantic transformation definitions;
- test fixtures;
- expected normalized results.

Engine-specific code remains engine-specific.

## 3. Target Structure

```text
stream-processing/
  README.md
  contracts/
    transformations.md
    fixtures/
  flink/
    src/
    tests/
  spark/
    src/
    tests/
```

## 4. Input

Primary topic:

`race.telemetry.validated`

## 5. Outputs

Suggested topics:

- `race.state`
- `race.lap.completed`
- `race.pitstop`
- `race.analytics`

## 6. Initial Transformations

Implement equivalent semantics where practical:

1. latest state per car;
2. moving average speed;
3. fuel consumption rate;
4. lap completion detection;
5. pit-stop completion summary;
6. race ranking snapshot;
7. rolling telemetry aggregates.

## 7. Event-Time Semantics

Define explicitly:

- source timestamp;
- watermark delay;
- allowed lateness;
- duplicate behavior;
- output update semantics.

Document engine differences.

## 8. Engine Selection

Local configuration should support a clear choice such as:

```text
STREAM_ENGINE=flink
```

or:

```text
STREAM_ENGINE=spark
```

This configuration should select which Compose profile/deployment is started, not dynamically replace code inside a running process.

## 9. Flink Implementation

Use Flink-native event-time/state concepts.

Document:

- keyed state;
- watermarks;
- checkpoints;
- restart strategy;
- Kafka source/sink semantics.

## 10. Spark Implementation

Use Structured Streaming with PySpark.

Document:

- watermarking;
- stateful operators;
- checkpoint location;
- trigger configuration;
- Kafka integration;
- output mode.

## 11. Parity Testing

Maintain deterministic fixture data such as:

`contracts/fixtures/telemetry-small.jsonl`

Run both engines against equivalent data.

Normalize engine-specific metadata before comparison.

Compare domain outputs, not internal execution details.

## 12. Done Criteria

- Flink can consume telemetry and produce derived outputs;
- Spark can consume the same contract and produce equivalent domain outputs for parity scenarios;
- only one engine needs to run at a time;
- frontend/backend consumers do not care which engine produced the messages;
- differences are documented.
