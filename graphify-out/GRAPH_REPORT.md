# Graph Report - SmartTrading-m10  (2026-09-23)

## Corpus Check
- 119 files · ~44,250 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: (none) 7, .csv 4, .example 1)

## Summary
- 849 nodes · 2577 edges · 56 communities (34 shown, 22 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 380 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0df2f389`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- domain.py
- cli.py
- app.py
- Bar
- _paper_run_async
- test_forward_experiment.py
- ModelArtifact
- PaperTradingEngine
- Forward Experiment V1
- decimal
- Next-Bar Execution
- Graph Query Traversal
- Graphify
- shadow_v2.py
- backtest/__init__.py
- data/__init__.py
- execution/__init__.py
- features/__init__.py
- smarttrading/__init__.py
- models/__init__.py
- monitoring/__init__.py
- paper/__init__.py
- portfolio/__init__.py
- risk/__init__.py
- strategies/__init__.py
- Graph Exports
- Always-On Graphify Integration
- smarttrading
- require_utc
- binance_market_v2.py
- training.py
- test_artifacts_paper.py
- PaperStore
- MarketContextSynchronizer
- DERIVATIVES_CONTEXT.md
- MICROSTRUCTURE.md
- SHADOW_V2.md
- CandleEvent
- freeze.py
- settings.py
- market_v2.py
- MarketDataStore
- datetime
- test_market_v2.py
- InstanceGuard
- BBOEvent
- forward.py
- CausalFeaturePipeline
- dataset.py
- resource
- MLDataset
- .compute_frame
- MARKET_DATA_V2.md

## God Nodes (most connected - your core abstractions)
1. `Bar` - 87 edges
2. `PaperTradingEngine` - 46 edges
3. `PaperStore` - 36 edges
4. `MarketDataStore` - 34 edges
5. `Signal` - 28 edges
6. `Side` - 27 edges
7. `Prediction` - 26 edges
8. `BBOEvent` - 25 edges
9. `IndependentRiskManager` - 25 edges
10. `main()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `V2 ablation report` --references--> `evaluate_ablation()`  [INFERRED]
  docs/ABLATION_V2_REPORT.md → src/smarttrading/models/ablation_v2.py
- `test_runtime_manifest_state_round_trip()` --uses--> `MarketDataStore`  [INFERRED]
  tests/test_market_v2.py → src/smarttrading/data/market_store.py
- `test_duplicate_instance_rejected_and_pid_cleaned()` --uses--> `InstanceGuard`  [INFERRED]
  tests/test_market_v2.py → src/smarttrading/monitoring/runtime.py
- `Idempotent Paper Recovery` --semantically_similar_to--> `Durable Paper Runtime`  [INFERRED] [semantically similar]
  docs/PAPER_TRADING.md → ARCHITECTURE.md
- `main()` --uses--> `CausalFeaturePipeline`  [INFERRED]
  scripts/create_smoke_artifact.py → src/smarttrading/features/pipeline.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Graphify Extraction Pipeline** — codex_skills_graphify_skill_graphify, codex_skills_graphify_skill_structural_extraction, codex_skills_graphify_skill_semantic_extraction, codex_skills_graphify_references_extraction_spec_confidence_audit_trail [EXTRACTED 1.00]
- **Causal Out-of-Sample Validation System** — architecture_reproducibility_controls, docs_market_data_causal_bar_eligibility, docs_ml_methodology_causal_features, docs_ml_methodology_temporal_validation, docs_ml_methodology_sealed_final_holdout [INFERRED 0.95]
- **Safety-First Trading Flow** — architecture_safety_boundary, architecture_decision_flow, config_default_default_risk_limits, docs_paper_trading_paper_trading_runtime [INFERRED 0.95]

## Communities (56 total, 22 thin omitted)

### Community 0 - "domain.py"
Cohesion: 0.05
Nodes (75): dataclasses, enum, hashlib, itertools, json, math, BacktestEngine, BacktestResult (+67 more)

### Community 1 - "cli.py"
Cohesion: 0.20
Nodes (23): ArgumentParser, Namespace, _add_ml_arguments(), _experiment_decisions(), _experiment_export(), _experiment_report(), _experiment_status(), _explain_decision() (+15 more)

### Community 2 - "app.py"
Cohesion: 0.06
Nodes (71): CaptureFixture, Connection, Group, io, LogRecord, Panel, parametrize, rich_console (+63 more)

### Community 3 - "Bar"
Cohesion: 0.07
Nodes (45): BacktestStrategy, Protocol, _strategy(), ApprovedOrder, Bar, Prediction, model_validator, Signal (+37 more)

### Community 4 - "_paper_run_async"
Cohesion: 0.31
Nodes (7): RuntimeError, _paper_run_async(), reconcile(), BinancePublicData, PublicDataError, datetime, Credential-free historical klines with bounded retries and rate-limit handling.

### Community 5 - "test_forward_experiment.py"
Cohesion: 0.19
Nodes (15): sklearn_datasets, ExperimentLock, ExperimentMetadata, ForwardOutcome, FrozenExperimentConfig, mature_predictions(), BaseModel, model_validator (+7 more)

### Community 6 - "ModelArtifact"
Cohesion: 0.17
Nodes (10): main(), main(), ModelArtifact, ModelRegistry, ModelStatus, BaseModel, Path, StrEnum (+2 more)

### Community 7 - "PaperTradingEngine"
Cohesion: 0.26
Nodes (6): PaperTradingEngine, Any, Position, CircuitState, StrEnum, RiskReason

### Community 8 - "Forward Experiment V1"
Cohesion: 0.09
Nodes (22): Trading Decision Flow, Durable Paper Runtime, Ports and Adapters Architecture, Safety Boundary, Default Risk Limits, PostgreSQL Service, Forward Experiment V1, Frozen decision and capital policy (+14 more)

### Community 9 - "decimal"
Cohesion: 0.14
Nodes (14): decimal, DeclarativeBase, sqlalchemy, sqlalchemy_exc, sqlalchemy_orm, BarRepository, BarRow, Base (+6 more)

### Community 10 - "Next-Bar Execution"
Cohesion: 0.22
Nodes (9): Next-Bar Execution, Reproducibility and Bias Controls, Default Execution Costs, Out-of-Sample Economic Evaluation, Sealed Final Holdout, Temporal Validation, Model Evidence Levels, Out-of-Sample Selection Criteria (+1 more)

### Community 11 - "Graph Query Traversal"
Cohesion: 0.25
Nodes (8): Graphify-First Codebase Navigation, Folder Watcher, URL Ingestion, MCP Graph Server, Graph Query Traversal, Query Feedback Loop, Incremental Graph Update, Existing Graph Fast Path

### Community 12 - "Graphify"
Cohesion: 0.33
Nodes (6): Confidence Audit Trail, Cross-Repository Graph Merge, Media Transcription, Graphify, Semantic Extraction, Structural AST Extraction

### Community 13 - "shadow_v2.py"
Cohesion: 0.13
Nodes (25): contextlib, deque, importlib_metadata, Logger, signal, log_event(), runtime_logger(), database_bytes() (+17 more)

### Community 31 - "require_utc"
Cohesion: 0.13
Nodes (14): pytest, datetime, Return a UTC datetime, rejecting ambiguous naive values., require_utc(), utc_now(), datetime, field_validator, calibration_degradation() (+6 more)

### Community 32 - "binance_market_v2.py"
Cohesion: 0.19
Nodes (10): asyncio, httpx, DepthUpdate, LocalOrderBook, OrderBookLevel, OrderBookSnapshot, _asset(), BinanceMarketDataV2 (+2 more)

### Community 33 - "training.py"
Cohesion: 0.14
Nodes (18): ndarray, Pipeline, sklearn, sklearn_calibration, sklearn_dummy, sklearn_ensemble, sklearn_linear_model, sklearn_metrics (+10 more)

### Community 34 - "test_artifacts_paper.py"
Cohesion: 0.18
Nodes (19): _paper_smoke(), DecisionAction, EnsemblePrediction, EnsembleConfig, BaseModel, datetime, WeightedEnsemble, DecisionRecord (+11 more)

### Community 35 - "PaperStore"
Cohesion: 0.24
Nodes (4): PaperStore, Any, Path, SQLite append-only event journal plus atomic latest-state snapshots.

### Community 36 - "MarketContextSynchronizer"
Cohesion: 0.42
Nodes (4): MarketContextSynchronizer, datetime, TimedEvent, timedelta

### Community 40 - "CandleEvent"
Cohesion: 0.11
Nodes (19): collections, CandleEvent, ClosedCandleBuffer, cross_asset_context(), MultiTimeframeStore, BaseModel, datetime, BinanceClosedCandleProvider (+11 more)

### Community 41 - "freeze.py"
Cohesion: 0.13
Nodes (17): ExperimentResult, ModelName, run_experiment(), run_final_evaluation(), freeze_real_artifact(), _git_revision(), ModelName, Path (+9 more)

### Community 42 - "settings.py"
Cohesion: 0.13
Nodes (17): BaseSettings, pydantic_settings, PydanticBaseSettingsSource, AppSettings, DatabaseSettings, ExecutionSettings, load_settings(), Mode (+9 more)

### Community 43 - "market_v2.py"
Cohesion: 0.15
Nodes (19): bisect, DataQualityMetrics, MarketContextSnapshot, BaseModel, StrEnum, quality_metrics(), SourceStatus, SourceValidity (+11 more)

### Community 44 - "MarketDataStore"
Cohesion: 0.12
Nodes (5): inspect_storage(), MarketDataStore, datetime, Path, Read-only physical/logical storage report; never checkpoints or migrates the…

### Community 45 - "datetime"
Cohesion: 0.18
Nodes (12): argparse, base64, datetime, pathlib, pickle, random, MarketDataError, ValueError (+4 more)

### Community 46 - "test_market_v2.py"
Cohesion: 0.15
Nodes (17): logging_handlers, os, structlog, book(), level(), test_causal_snapshot_future_mutation_and_stale_policy(), test_compact_persistence_bounds_rows_and_replays_deterministically(), test_context_history_is_bounded_and_latest_lookup_handles_future_data() (+9 more)

### Community 47 - "InstanceGuard"
Cohesion: 0.27
Nodes (4): BaseException, InstanceGuard, Path, TracebackType

### Community 48 - "BBOEvent"
Cohesion: 0.19
Nodes (11): AggregateTradeEvent, BBOEvent, DerivativesEvent, event_source(), asyncio, MonkeyPatch, test_coverage_and_readiness_are_informational(), test_shadow_bounded_run_gracefully_flushes_and_cleans_pid() (+3 more)

### Community 49 - "forward.py"
Cohesion: 0.22
Nodes (15): shutil, daily_snapshot(), economic_metrics(), ExperimentHealth, export_experiment(), health_from_signals(), prediction_id(), predictive_metrics() (+7 more)

### Community 50 - "CausalFeaturePipeline"
Cohesion: 0.34
Nodes (10): MLDatasetBuilder, CausalFeaturePipeline, BaseModel, TargetConfig, bars_from_prices(), test_all_feature_families_are_causal(), test_dataset_hash_is_reproducible(), test_warmup_is_dropped_without_imputation_and_target_is_not_in_x() (+2 more)

### Community 51 - "dataset.py"
Cohesion: 0.29
Nodes (8): collections_abc, numpy, pandas, pydantic, Series, MLDatasetMetadata, BaseModel, future_returns()

### Community 53 - "MLDataset"
Cohesion: 0.24
Nodes (7): V2 ablation report, MLDataset, Path, EconomicMetrics, evaluate_ablation(), ModelName, Evaluate one predeclared feature family with the existing purged temporal folds.

### Community 55 - ".compute_frame"
Cohesion: 0.25
Nodes (5): DataFrame, FeatureConfig, FeatureSet, _frame(), BaseModel

## Knowledge Gaps
- **27 isolated node(s):** `smarttrading`, `Derivatives context`, `Scope and evidence boundary`, `Frozen models and features`, `Frozen decision and capital policy` (+22 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 190 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Bar` connect `Bar` to `domain.py`, `cli.py`, `test_artifacts_paper.py`, `_paper_run_async`, `PaperTradingEngine`, `CandleEvent`, `decimal`, `freeze.py`, `datetime`, `CausalFeaturePipeline`, `dataset.py`, `.compute_frame`, `require_utc`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `MarketDataStore` connect `MarketDataStore` to `binance_market_v2.py`, `cli.py`, `market_v2.py`, `shadow_v2.py`, `test_market_v2.py`, `BBOEvent`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `PaperTradingEngine` connect `PaperTradingEngine` to `domain.py`, `cli.py`, `test_artifacts_paper.py`, `Bar`, `_paper_run_async`, `test_forward_experiment.py`, `ModelArtifact`, `PaperStore`, `CandleEvent`, `settings.py`, `forward.py`, `CausalFeaturePipeline`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 38 inferred relationships involving `Bar` (e.g. with `BacktestEngine` and `BacktestStrategy`) actually correct?**
  _`Bar` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `PaperTradingEngine` (e.g. with `main()` and `AppSettings`) actually correct?**
  _`PaperTradingEngine` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `PaperStore` (e.g. with `main()` and `PaperTradingEngine`) actually correct?**
  _`PaperStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `MarketDataStore` (e.g. with `AggregateTradeEvent` and `BBOEvent`) actually correct?**
  _`MarketDataStore` has 10 INFERRED edges - model-reasoned connections that need verification._