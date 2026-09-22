# Graph Report - SmartTrading-m10  (2026-09-22)

## Corpus Check
- 113 files · ~41,175 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: (none) 7, .csv 4, .example 1)

## Summary
- 775 nodes · 2364 edges · 62 communities (39 shown, 23 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 374 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `78c4cdc3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Side
- cli.py
- ensemble.py
- Bar
- CandleEvent
- datetime
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
- domain.py
- binance_market_v2.py
- training.py
- test_artifacts_paper.py
- PaperStore
- BBOEvent
- DERIVATIVES_CONTEXT.md
- MICROSTRUCTURE.md
- SHADOW_V2.md
- MarketContextSnapshot
- test_forward_experiment.py
- paper/engine.py
- market_v2.py
- MarketDataStore
- csv.py
- test_market_v2.py
- InstanceGuard
- decimal
- PortfolioAccount
- CausalFeaturePipeline
- backtest/engine.py
- resource
- ProposedOrder
- test_backtest.py
- .compute_frame
- IndependentRiskManager
- SealedFinalHoldout
- evaluate_ablation
- test_domain.py
- .build
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
10. `ProposedOrder` - 23 edges

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

## Communities (62 total, 23 thin omitted)

### Community 0 - "Side"
Cohesion: 0.20
Nodes (13): Fill, OrderType, Side, CostModel, ExecutionSimulator, Decimal, Deterministic OHLCV simulator; strict limit penetration is required for a fill., ExecutionVenue (+5 more)

### Community 1 - "cli.py"
Cohesion: 0.18
Nodes (24): ArgumentParser, Namespace, _add_ml_arguments(), _backtest(), _experiment_decisions(), _experiment_export(), _experiment_report(), _experiment_status() (+16 more)

### Community 2 - "ensemble.py"
Cohesion: 0.23
Nodes (12): _paper_smoke(), DecisionAction, EnsemblePrediction, EnsembleConfig, BaseModel, datetime, WeightedEnsemble, DecisionRecord (+4 more)

### Community 3 - "Bar"
Cohesion: 0.07
Nodes (50): BaseSettings, PydanticBaseSettingsSource, BacktestStrategy, Protocol, run(), _strategy(), AppSettings, field_validator (+42 more)

### Community 4 - "CandleEvent"
Cohesion: 0.12
Nodes (18): collections, CandleEvent, ClosedCandleBuffer, cross_asset_context(), MultiTimeframeStore, BaseModel, datetime, BinanceClosedCandleProvider (+10 more)

### Community 5 - "datetime"
Cohesion: 0.24
Nodes (12): base64, collections_abc, datetime, hashlib, json, math, numpy, pandas (+4 more)

### Community 6 - "ModelArtifact"
Cohesion: 0.18
Nodes (9): main(), ModelArtifact, ModelRegistry, ModelStatus, BaseModel, Path, StrEnum, test_real_estimators_round_trip_without_prediction_change() (+1 more)

### Community 7 - "PaperTradingEngine"
Cohesion: 0.33
Nodes (4): PaperTradingEngine, Any, Position, CircuitState

### Community 8 - "Forward Experiment V1"
Cohesion: 0.09
Nodes (22): Trading Decision Flow, Durable Paper Runtime, Ports and Adapters Architecture, Safety Boundary, Default Risk Limits, PostgreSQL Service, Forward Experiment V1, Frozen decision and capital policy (+14 more)

### Community 9 - "test_market_data.py"
Cohesion: 0.15
Nodes (13): DeclarativeBase, sqlalchemy, sqlalchemy_exc, sqlalchemy_orm, BarRepository, BarRow, Base, datetime (+5 more)

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
Cohesion: 0.12
Nodes (28): contextlib, deque, importlib_metadata, Logger, signal, log_event(), runtime_logger(), database_bytes() (+20 more)

### Community 31 - "domain.py"
Cohesion: 0.06
Nodes (37): httpx, pytest, RuntimeError, datetime, Return a UTC datetime, rejecting ambiguous naive values., require_utc(), utc_now(), ApprovedOrder (+29 more)

### Community 32 - "binance_market_v2.py"
Cohesion: 0.21
Nodes (9): asyncio, DepthUpdate, LocalOrderBook, OrderBookLevel, OrderBookSnapshot, _asset(), BinanceMarketDataV2, datetime (+1 more)

### Community 33 - "training.py"
Cohesion: 0.12
Nodes (22): dataclasses, ndarray, Pipeline, sklearn, sklearn_calibration, sklearn_dummy, sklearn_ensemble, sklearn_linear_model (+14 more)

### Community 34 - "test_artifacts_paper.py"
Cohesion: 0.23
Nodes (13): load_settings(), Path, Load versioned YAML, then apply SMARTTRADING__ nested environment overrides., artifact(), candle(), make_bars(), Path, test_artifact_validation_promotion_and_feature_mismatch() (+5 more)

### Community 35 - "PaperStore"
Cohesion: 0.24
Nodes (4): PaperStore, Any, Path, SQLite append-only event journal plus atomic latest-state snapshots.

### Community 36 - "BBOEvent"
Cohesion: 0.21
Nodes (12): sqlite3, AggregateTradeEvent, BBOEvent, DerivativesEvent, event_source(), asyncio, MonkeyPatch, test_coverage_and_readiness_are_informational() (+4 more)

### Community 40 - "MarketContextSnapshot"
Cohesion: 0.31
Nodes (8): MarketContextSnapshot, DatasetV2Builder, DatasetV2Metadata, BaseModel, ResearchDatasetV2, derivatives_features(), microstructure_features(), test_funding_oi_alignment_dataset_determinism_and_version_isolation()

### Community 41 - "test_forward_experiment.py"
Cohesion: 0.22
Nodes (13): sklearn_datasets, ExperimentLock, ExperimentMetadata, FrozenExperimentConfig, BaseModel, model_validator, config(), datetime (+5 more)

### Community 42 - "paper/engine.py"
Cohesion: 0.19
Nodes (19): pathlib, shutil, daily_snapshot(), economic_metrics(), ExperimentHealth, export_experiment(), ForwardOutcome, health_from_signals() (+11 more)

### Community 43 - "market_v2.py"
Cohesion: 0.20
Nodes (11): bisect, DataQualityMetrics, MarketContextSynchronizer, BaseModel, datetime, StrEnum, quality_metrics(), SourceStatus (+3 more)

### Community 44 - "MarketDataStore"
Cohesion: 0.14
Nodes (3): MarketDataStore, datetime, Path

### Community 45 - "csv.py"
Cohesion: 0.17
Nodes (11): argparse, itertools, random, main(), load_bars_csv(), Path, MarketDataError, ValueError (+3 more)

### Community 46 - "test_market_v2.py"
Cohesion: 0.12
Nodes (19): logging_handlers, LogRecord, os, JsonFormatter, structlog, book(), level(), test_causal_snapshot_future_mutation_and_stale_policy() (+11 more)

### Community 47 - "InstanceGuard"
Cohesion: 0.27
Nodes (4): BaseException, InstanceGuard, Path, TracebackType

### Community 48 - "decimal"
Cohesion: 0.17
Nodes (17): decimal, enum, pydantic_settings, DatabaseSettings, ExecutionSettings, Mode, BaseModel, StrEnum (+9 more)

### Community 49 - "PortfolioAccount"
Cohesion: 0.20
Nodes (12): calculate_metrics(), PerformanceMetrics, Decimal, ShadowPortfolio, AccountingError, EquityPoint, PortfolioAccount, BaseModel (+4 more)

### Community 50 - "CausalFeaturePipeline"
Cohesion: 0.22
Nodes (15): _features(), _ml(), MLDatasetBuilder, CausalFeaturePipeline, BaseModel, TargetConfig, freeze_real_artifact(), _git_revision() (+7 more)

### Community 51 - "backtest/engine.py"
Cohesion: 0.22
Nodes (13): BacktestEngine, BacktestResult, cost_stress(), _git_commit(), BaseModel, Decimal, Path, RiskSummary (+5 more)

### Community 53 - "ProposedOrder"
Cohesion: 0.31
Nodes (5): ProposedOrder, model_validator, FixedFractionSizer, datetime, Decimal

### Community 54 - "test_backtest.py"
Cohesion: 0.36
Nodes (7): bars_from_prices(), AuditStrategy, engine(), test_backtest_is_economically_deterministic(), test_golden_end_to_end_accounting(), test_no_lookahead_future_jump_is_not_visible_early(), test_all_feature_families_are_causal()

### Community 55 - ".compute_frame"
Cohesion: 0.25
Nodes (5): DataFrame, FeatureConfig, FeatureSet, _frame(), BaseModel

### Community 56 - "IndependentRiskManager"
Cohesion: 0.33
Nodes (3): RiskDecision, RiskManager, IndependentRiskManager

### Community 57 - "SealedFinalHoldout"
Cohesion: 0.29
Nodes (3): SealedFinalHoldout, MonkeyPatch, test_artifact_freeze_never_opens_final_holdout()

### Community 58 - "evaluate_ablation"
Cohesion: 0.33
Nodes (5): V2 ablation report, EconomicMetrics, evaluate_ablation(), ModelName, Evaluate one predeclared feature family with the existing purged temporal folds.

### Community 59 - "test_domain.py"
Cohesion: 0.40
Nodes (4): test_bar_normalizes_aware_timestamp_to_utc(), test_invalid_ohlc_range_is_rejected(), test_limit_order_requires_price_and_market_forbids_it(), test_naive_timestamp_is_rejected()

## Knowledge Gaps
- **27 isolated node(s):** `smarttrading`, `Derivatives context`, `Scope and evidence boundary`, `Frozen models and features`, `Frozen decision and capital policy` (+22 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 182 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Bar` connect `Bar` to `Side`, `cli.py`, `test_artifacts_paper.py`, `CandleEvent`, `datetime`, `PaperTradingEngine`, `test_market_data.py`, `paper/engine.py`, `csv.py`, `CausalFeaturePipeline`, `backtest/engine.py`, `ProposedOrder`, `test_backtest.py`, `.compute_frame`, `test_domain.py`, `.build`, `domain.py`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Why does `MarketDataStore` connect `MarketDataStore` to `binance_market_v2.py`, `cli.py`, `BBOEvent`, `MarketContextSnapshot`, `shadow_v2.py`, `test_market_v2.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `PaperTradingEngine` connect `PaperTradingEngine` to `Side`, `cli.py`, `ensemble.py`, `Bar`, `CandleEvent`, `PaperStore`, `ModelArtifact`, `test_artifacts_paper.py`, `test_forward_experiment.py`, `paper/engine.py`, `PortfolioAccount`, `CausalFeaturePipeline`, `backtest/engine.py`, `ProposedOrder`, `IndependentRiskManager`, `domain.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 38 inferred relationships involving `Bar` (e.g. with `BacktestEngine` and `BacktestStrategy`) actually correct?**
  _`Bar` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `PaperTradingEngine` (e.g. with `main()` and `AppSettings`) actually correct?**
  _`PaperTradingEngine` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `PaperStore` (e.g. with `main()` and `PaperTradingEngine`) actually correct?**
  _`PaperStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `MarketDataStore` (e.g. with `AggregateTradeEvent` and `BBOEvent`) actually correct?**
  _`MarketDataStore` has 10 INFERRED edges - model-reasoned connections that need verification._