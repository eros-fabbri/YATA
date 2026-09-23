# Graph Report - SmartTrading-m10  (2026-09-22)

## Corpus Check
- 119 files · ~43,880 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: (none) 7, .csv 4, .example 1)

## Summary
- 837 nodes · 2541 edges · 49 communities (27 shown, 22 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 378 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `cd69ceb8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- backtest/engine.py
- cli.py
- app.py
- Bar
- CandleEvent
- domain.py
- ModelArtifact
- PaperTradingEngine
- Forward Experiment V1
- test_market_data.py
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
- experiment.py
- load_settings
- PaperStore
- MarketContextSynchronizer
- DERIVATIVES_CONTEXT.md
- MICROSTRUCTURE.md
- SHADOW_V2.md
- drift.py
- market_v2.py
- MarketDataStore
- test_market_v2.py
- InstanceGuard
- CausalFeaturePipeline
- resource
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
- `test_bar_normalizes_aware_timestamp_to_utc()` --uses--> `Bar`  [INFERRED]
  tests/test_domain.py → src/smarttrading/domain.py
- `test_invalid_ohlc_range_is_rejected()` --uses--> `Bar`  [INFERRED]
  tests/test_domain.py → src/smarttrading/domain.py
- `test_naive_timestamp_is_rejected()` --uses--> `Bar`  [INFERRED]
  tests/test_domain.py → src/smarttrading/domain.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Graphify Extraction Pipeline** — codex_skills_graphify_skill_graphify, codex_skills_graphify_skill_structural_extraction, codex_skills_graphify_skill_semantic_extraction, codex_skills_graphify_references_extraction_spec_confidence_audit_trail [EXTRACTED 1.00]
- **Causal Out-of-Sample Validation System** — architecture_reproducibility_controls, docs_market_data_causal_bar_eligibility, docs_ml_methodology_causal_features, docs_ml_methodology_temporal_validation, docs_ml_methodology_sealed_final_holdout [INFERRED 0.95]
- **Safety-First Trading Flow** — architecture_safety_boundary, architecture_decision_flow, config_default_default_risk_limits, docs_paper_trading_paper_trading_runtime [INFERRED 0.95]

## Communities (49 total, 22 thin omitted)

### Community 0 - "backtest/engine.py"
Cohesion: 0.06
Nodes (59): BacktestEngine, BacktestResult, cost_stress(), _git_commit(), BaseModel, Decimal, Path, RiskSummary (+51 more)

### Community 1 - "cli.py"
Cohesion: 0.25
Nodes (18): ArgumentParser, Namespace, _add_ml_arguments(), _backtest(), _experiment_decisions(), _experiment_export(), _experiment_report(), _experiment_status() (+10 more)

### Community 2 - "app.py"
Cohesion: 0.08
Nodes (56): CaptureFixture, Connection, contextlib, Group, Panel, parametrize, rich_console, rich_live (+48 more)

### Community 3 - "Bar"
Cohesion: 0.07
Nodes (39): BacktestStrategy, Protocol, _strategy(), cross_asset_context(), MultiTimeframeStore, datetime, ApprovedOrder, Bar (+31 more)

### Community 4 - "CandleEvent"
Cohesion: 0.19
Nodes (11): RuntimeError, _paper_run_async(), reconcile(), CandleEvent, BaseModel, BinancePublicData, PublicDataError, datetime (+3 more)

### Community 5 - "domain.py"
Cohesion: 0.05
Nodes (71): argparse, base64, collections_abc, datetime, decimal, enum, hashlib, itertools (+63 more)

### Community 6 - "ModelArtifact"
Cohesion: 0.17
Nodes (9): main(), ModelArtifact, ModelRegistry, ModelStatus, BaseModel, Path, StrEnum, test_real_estimators_round_trip_without_prediction_change() (+1 more)

### Community 7 - "PaperTradingEngine"
Cohesion: 0.12
Nodes (14): ClosedCandleBuffer, PaperTradingEngine, Any, Load closed pre-start context without creating forward predictions or decisions., Position, CircuitState, StrEnum, RiskReason (+6 more)

### Community 8 - "Forward Experiment V1"
Cohesion: 0.09
Nodes (22): Trading Decision Flow, Durable Paper Runtime, Ports and Adapters Architecture, Safety Boundary, Default Risk Limits, PostgreSQL Service, Forward Experiment V1, Frozen decision and capital policy (+14 more)

### Community 9 - "test_market_data.py"
Cohesion: 0.11
Nodes (18): DeclarativeBase, sqlalchemy, sqlalchemy_exc, sqlalchemy_orm, BarRepository, BarRow, Base, datetime (+10 more)

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
Nodes (35): deque, importlib_metadata, Logger, signal, DatasetV2Builder, DatasetV2Metadata, BaseModel, ResearchDatasetV2 (+27 more)

### Community 31 - "FrozenModel"
Cohesion: 0.15
Nodes (14): datetime, Return a UTC datetime, rejecting ambiguous naive values., require_utc(), utc_now(), DerivativesContext, FrozenModel, BaseModel, datetime (+6 more)

### Community 32 - "binance_market_v2.py"
Cohesion: 0.19
Nodes (10): asyncio, httpx, DepthUpdate, LocalOrderBook, OrderBookLevel, OrderBookSnapshot, _asset(), BinanceMarketDataV2 (+2 more)

### Community 33 - "experiment.py"
Cohesion: 0.06
Nodes (46): BaseSettings, dataclasses, V2 ablation report, ndarray, Pipeline, PydanticBaseSettingsSource, sklearn, sklearn_calibration (+38 more)

### Community 34 - "load_settings"
Cohesion: 0.16
Nodes (21): main(), _paper_smoke(), load_settings(), Path, Load versioned YAML, then apply SMARTTRADING__ nested environment overrides., EnsembleConfig, BaseModel, WeightedEnsemble (+13 more)

### Community 35 - "PaperStore"
Cohesion: 0.18
Nodes (10): daily_snapshot(), economic_metrics(), export_experiment(), predictive_metrics(), Any, Path, PaperStore, Any (+2 more)

### Community 36 - "MarketContextSynchronizer"
Cohesion: 0.42
Nodes (4): MarketContextSynchronizer, datetime, TimedEvent, timedelta

### Community 40 - "drift.py"
Cohesion: 0.43
Nodes (5): calibration_degradation(), class_balance_change(), ks_statistic(), population_stability_index(), test_drift_is_reproducible()

### Community 43 - "market_v2.py"
Cohesion: 0.14
Nodes (13): bisect, DataQualityMetrics, MarketContextSnapshot, BaseModel, StrEnum, quality_metrics(), SourceStatus, SourceValidity (+5 more)

### Community 44 - "MarketDataStore"
Cohesion: 0.11
Nodes (17): inspect_storage(), MarketDataStore, datetime, Path, Read-only physical/logical storage report; never checkpoints or migrates the…, AggregateTradeEvent, BBOEvent, DerivativesEvent (+9 more)

### Community 46 - "test_market_v2.py"
Cohesion: 0.12
Nodes (18): collections, logging_handlers, LogRecord, os, JsonFormatter, structlog, book(), level() (+10 more)

### Community 47 - "InstanceGuard"
Cohesion: 0.27
Nodes (4): BaseException, InstanceGuard, Path, TracebackType

### Community 50 - "CausalFeaturePipeline"
Cohesion: 0.21
Nodes (17): _features(), _ml(), load_bars_csv(), Path, MLDatasetBuilder, CausalFeaturePipeline, BaseModel, TargetConfig (+9 more)

### Community 55 - ".compute_frame"
Cohesion: 0.25
Nodes (5): DataFrame, FeatureConfig, FeatureSet, _frame(), BaseModel

## Knowledge Gaps
- **27 isolated node(s):** `smarttrading`, `Derivatives context`, `Scope and evidence boundary`, `Frozen models and features`, `Frozen decision and capital policy` (+22 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 190 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Bar` connect `Bar` to `backtest/engine.py`, `experiment.py`, `load_settings`, `CandleEvent`, `domain.py`, `PaperTradingEngine`, `test_market_data.py`, `CausalFeaturePipeline`, `.compute_frame`, `FrozenModel`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `MarketDataStore` connect `MarketDataStore` to `binance_market_v2.py`, `cli.py`, `market_v2.py`, `shadow_v2.py`, `test_market_v2.py`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `PaperTradingEngine` connect `PaperTradingEngine` to `backtest/engine.py`, `cli.py`, `load_settings`, `experiment.py`, `CandleEvent`, `domain.py`, `Bar`, `ModelArtifact`, `PaperStore`, `CausalFeaturePipeline`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 38 inferred relationships involving `Bar` (e.g. with `BacktestEngine` and `BacktestStrategy`) actually correct?**
  _`Bar` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `PaperTradingEngine` (e.g. with `main()` and `AppSettings`) actually correct?**
  _`PaperTradingEngine` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `PaperStore` (e.g. with `main()` and `PaperTradingEngine`) actually correct?**
  _`PaperStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `MarketDataStore` (e.g. with `AggregateTradeEvent` and `BBOEvent`) actually correct?**
  _`MarketDataStore` has 10 INFERRED edges - model-reasoned connections that need verification._