# Graph Report - SmartTrading-m10  (2026-09-22)

## Corpus Check
- 113 files · ~38,544 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: (none) 7, .csv 4, .example 1)

## Summary
- 753 nodes · 2295 edges · 53 communities (32 shown, 21 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 359 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `78c4cdc3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- backtest/engine.py
- cli.py
- domain.py
- Bar
- CandleEvent
- paper/engine.py
- ModelArtifact
- PaperTradingEngine
- Forward Experiment V1
- collections_abc
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
- FrozenModel
- binance_market_v2.py
- training.py
- _paper_run_async
- PaperStore
- MarketDataStore
- DERIVATIVES_CONTEXT.md
- MICROSTRUCTURE.md
- SHADOW_V2.md
- run_shadow_v2
- test_forward_experiment.py
- forward.py
- market_v2.py
- test_realtime.py
- csv.py
- test_market_v2.py
- InstanceGuard
- settings.py
- drift.py
- Trade
- MultiTimeframeStore
- resource

## God Nodes (most connected - your core abstractions)
1. `Bar` - 87 edges
2. `PaperTradingEngine` - 46 edges
3. `PaperStore` - 36 edges
4. `Signal` - 28 edges
5. `Side` - 26 edges
6. `Prediction` - 26 edges
7. `IndependentRiskManager` - 25 edges
8. `MarketDataStore` - 24 edges
9. `ProposedOrder` - 23 edges
10. `ExecutionSimulator` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Market data V2` --references--> `MarketContextSnapshot`  [INFERRED]
  docs/MARKET_DATA_V2.md → src/smarttrading/data/market_v2.py
- `V2 ablation report` --references--> `evaluate_ablation()`  [INFERRED]
  docs/ABLATION_V2_REPORT.md → src/smarttrading/models/ablation_v2.py
- `test_runtime_manifest_state_round_trip()` --uses--> `MarketDataStore`  [INFERRED]
  tests/test_market_v2.py → src/smarttrading/data/market_store.py
- `test_bar_normalizes_aware_timestamp_to_utc()` --uses--> `Bar`  [INFERRED]
  tests/test_domain.py → src/smarttrading/domain.py
- `test_invalid_ohlc_range_is_rejected()` --uses--> `Bar`  [INFERRED]
  tests/test_domain.py → src/smarttrading/domain.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Graphify Extraction Pipeline** — codex_skills_graphify_skill_graphify, codex_skills_graphify_skill_structural_extraction, codex_skills_graphify_skill_semantic_extraction, codex_skills_graphify_references_extraction_spec_confidence_audit_trail [EXTRACTED 1.00]
- **Causal Out-of-Sample Validation System** — architecture_reproducibility_controls, docs_market_data_causal_bar_eligibility, docs_ml_methodology_causal_features, docs_ml_methodology_temporal_validation, docs_ml_methodology_sealed_final_holdout [INFERRED 0.95]
- **Safety-First Trading Flow** — architecture_safety_boundary, architecture_decision_flow, config_default_default_risk_limits, docs_paper_trading_paper_trading_runtime [INFERRED 0.95]

## Communities (53 total, 21 thin omitted)

### Community 0 - "backtest/engine.py"
Cohesion: 0.07
Nodes (57): dataclasses, BacktestEngine, BacktestResult, cost_stress(), _git_commit(), BaseModel, Decimal, Path (+49 more)

### Community 1 - "cli.py"
Cohesion: 0.21
Nodes (22): ArgumentParser, Namespace, _add_ml_arguments(), _backtest(), _experiment_decisions(), _experiment_export(), _experiment_report(), _experiment_status() (+14 more)

### Community 2 - "domain.py"
Cohesion: 0.16
Nodes (14): decimal, pydantic, pytest, DecisionAction, EnsemblePrediction, MarketRegime, OrderStatus, StrEnum (+6 more)

### Community 3 - "Bar"
Cohesion: 0.07
Nodes (49): BaseSettings, PydanticBaseSettingsSource, BacktestStrategy, Protocol, _strategy(), AppSettings, field_validator, ApprovedOrder (+41 more)

### Community 4 - "CandleEvent"
Cohesion: 0.23
Nodes (6): CandleEvent, ClosedCandleBuffer, BaseModel, BinanceClosedCandleProvider, ResilientCandleStream, candle()

### Community 5 - "paper/engine.py"
Cohesion: 0.19
Nodes (13): argparse, base64, collections, datetime, hashlib, json, math, pathlib (+5 more)

### Community 6 - "ModelArtifact"
Cohesion: 0.16
Nodes (10): main(), main(), ModelArtifact, ModelRegistry, ModelStatus, BaseModel, Path, StrEnum (+2 more)

### Community 7 - "PaperTradingEngine"
Cohesion: 0.22
Nodes (7): PaperTradingEngine, Any, Load closed pre-start context without creating forward predictions or decisions., Position, CircuitState, StrEnum, RiskReason

### Community 8 - "Forward Experiment V1"
Cohesion: 0.09
Nodes (22): Trading Decision Flow, Durable Paper Runtime, Ports and Adapters Architecture, Safety Boundary, Default Risk Limits, PostgreSQL Service, Forward Experiment V1, Frozen decision and capital policy (+14 more)

### Community 9 - "collections_abc"
Cohesion: 0.19
Nodes (8): collections_abc, DeclarativeBase, sqlalchemy, sqlalchemy_orm, BarRepository, BarRow, Base, datetime

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
Cohesion: 0.10
Nodes (21): contextlib, importlib_metadata, Logger, logging_handlers, LogRecord, os, signal, JsonFormatter (+13 more)

### Community 31 - "FrozenModel"
Cohesion: 0.12
Nodes (16): httpx, RuntimeError, datetime, Return a UTC datetime, rejecting ambiguous naive values., require_utc(), utc_now(), DerivativesContext, FrozenModel (+8 more)

### Community 32 - "binance_market_v2.py"
Cohesion: 0.21
Nodes (9): asyncio, DepthUpdate, LocalOrderBook, OrderBookLevel, OrderBookSnapshot, _asset(), BinanceMarketDataV2, datetime (+1 more)

### Community 33 - "training.py"
Cohesion: 0.05
Nodes (58): DataFrame, V2 ablation report, ndarray, numpy, pandas, Pipeline, Series, sklearn (+50 more)

### Community 34 - "_paper_run_async"
Cohesion: 0.14
Nodes (24): _explain_decision(), _paper_run_async(), reconcile(), _paper_smoke(), load_settings(), Path, Load versioned YAML, then apply SMARTTRADING__ nested environment overrides., BinancePublicData (+16 more)

### Community 35 - "PaperStore"
Cohesion: 0.24
Nodes (4): PaperStore, Any, Path, SQLite append-only event journal plus atomic latest-state snapshots.

### Community 36 - "MarketDataStore"
Cohesion: 0.15
Nodes (12): MarketDataStore, Path, AggregateTradeEvent, BBOEvent, DerivativesEvent, asyncio, MonkeyPatch, test_coverage_and_readiness_are_informational() (+4 more)

### Community 40 - "run_shadow_v2"
Cohesion: 0.20
Nodes (14): Market data V2, MarketContextSnapshot, DatasetV2Builder, DatasetV2Metadata, BaseModel, ResearchDatasetV2, derivatives_features(), microstructure_features() (+6 more)

### Community 41 - "test_forward_experiment.py"
Cohesion: 0.19
Nodes (15): sklearn_datasets, ExperimentLock, ExperimentMetadata, ForwardOutcome, FrozenExperimentConfig, mature_predictions(), BaseModel, model_validator (+7 more)

### Community 42 - "forward.py"
Cohesion: 0.22
Nodes (16): itertools, shutil, daily_snapshot(), economic_metrics(), ExperimentHealth, export_experiment(), health_from_signals(), prediction_id() (+8 more)

### Community 43 - "market_v2.py"
Cohesion: 0.21
Nodes (10): DataQualityMetrics, MarketContextSynchronizer, BaseModel, datetime, StrEnum, quality_metrics(), SourceStatus, SourceValidity (+2 more)

### Community 44 - "test_realtime.py"
Cohesion: 0.21
Nodes (12): DetectedRegime, TrendRegime, VolatilityRegime, RegimeDetector, bar(), event(), asyncio, test_closed_duplicate_out_of_order_and_missing_candles() (+4 more)

### Community 45 - "csv.py"
Cohesion: 0.22
Nodes (11): sqlalchemy_exc, MarketDataError, ValueError, Raised when a batch cannot form a reliable historical series., Return a sorted, validated copy without silently repairing source data., validate_bar_series(), make_bar(), Path (+3 more)

### Community 46 - "test_market_v2.py"
Cohesion: 0.24
Nodes (11): storage_measurement(), book(), level(), test_causal_snapshot_future_mutation_and_stale_policy(), test_duplicate_instance_rejected_and_pid_cleaned(), test_health_exit_codes_and_storage_window(), test_order_book_update_duplicate_out_of_order_gap_and_resync(), test_runtime_manifest_state_round_trip() (+3 more)

### Community 47 - "InstanceGuard"
Cohesion: 0.27
Nodes (4): BaseException, InstanceGuard, Path, TracebackType

### Community 48 - "settings.py"
Cohesion: 0.25
Nodes (8): enum, pydantic_settings, DatabaseSettings, ExecutionSettings, Mode, BaseModel, StrEnum, yaml

### Community 49 - "drift.py"
Cohesion: 0.33
Nodes (6): calibration_degradation(), class_balance_change(), ks_statistic(), population_stability_index(), test_drift_is_reproducible(), test_ensemble_determinism_disagreement_and_abstention()

### Community 50 - "Trade"
Cohesion: 0.32
Nodes (5): BestBidAsk, Trade, order_book_features(), quote_features(), trade_features()

### Community 51 - "MultiTimeframeStore"
Cohesion: 0.39
Nodes (4): cross_asset_context(), MultiTimeframeStore, datetime, test_multi_timeframe_and_cross_asset_are_causal()

## Knowledge Gaps
- **26 isolated node(s):** `smarttrading`, `Derivatives context`, `Scope and evidence boundary`, `Frozen models and features`, `Frozen decision and capital policy` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 179 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Bar` connect `Bar` to `backtest/engine.py`, `cli.py`, `domain.py`, `_paper_run_async`, `CandleEvent`, `paper/engine.py`, `training.py`, `PaperTradingEngine`, `collections_abc`, `test_realtime.py`, `csv.py`, `MultiTimeframeStore`, `FrozenModel`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `PaperTradingEngine` connect `PaperTradingEngine` to `backtest/engine.py`, `cli.py`, `_paper_run_async`, `Bar`, `CandleEvent`, `paper/engine.py`, `ModelArtifact`, `domain.py`, `training.py`, `test_forward_experiment.py`, `forward.py`, `PaperStore`, `test_realtime.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `MarketDataStore` connect `MarketDataStore` to `run_shadow_v2`, `cli.py`, `shadow_v2.py`, `test_market_v2.py`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 38 inferred relationships involving `Bar` (e.g. with `BacktestEngine` and `BacktestStrategy`) actually correct?**
  _`Bar` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `PaperTradingEngine` (e.g. with `main()` and `AppSettings`) actually correct?**
  _`PaperTradingEngine` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `PaperStore` (e.g. with `main()` and `PaperTradingEngine`) actually correct?**
  _`PaperStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Signal` (e.g. with `BacktestStrategy` and `FixedFractionSizer`) actually correct?**
  _`Signal` has 10 INFERRED edges - model-reasoned connections that need verification._