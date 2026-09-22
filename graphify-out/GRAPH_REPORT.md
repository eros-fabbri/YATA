# Graph Report - SmartTrading  (2026-09-22)

## Corpus Check
- 99 files · ~32,284 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: (none) 7, .csv 4, .example 1)

## Summary
- 612 nodes · 1869 edges · 33 communities (15 shown, 18 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 298 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- backtest/engine.py
- cli.py
- experiment.py
- Bar
- domain.py
- dataset.py
- decimal
- paper/engine.py
- Forward Experiment V1
- test_market_data.py
- Next-Bar Execution
- Graph Query Traversal
- Graphify
- logging.py
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
- .compute_frame

## God Nodes (most connected - your core abstractions)
1. `Bar` - 87 edges
2. `PaperTradingEngine` - 46 edges
3. `PaperStore` - 36 edges
4. `Signal` - 28 edges
5. `Prediction` - 26 edges
6. `IndependentRiskManager` - 25 edges
7. `ProposedOrder` - 23 edges
8. `ExecutionSimulator` - 23 edges
9. `CausalFeaturePipeline` - 23 edges
10. `CandleEvent` - 22 edges

## Surprising Connections (you probably didn't know these)
- `test_bar_normalizes_aware_timestamp_to_utc()` --uses--> `Bar`  [INFERRED]
  tests/test_domain.py → src/smarttrading/domain.py
- `test_invalid_ohlc_range_is_rejected()` --uses--> `Bar`  [INFERRED]
  tests/test_domain.py → src/smarttrading/domain.py
- `test_naive_timestamp_is_rejected()` --uses--> `Bar`  [INFERRED]
  tests/test_domain.py → src/smarttrading/domain.py
- `Idempotent Paper Recovery` --semantically_similar_to--> `Durable Paper Runtime`  [INFERRED] [semantically similar]
  docs/PAPER_TRADING.md → ARCHITECTURE.md
- `main()` --calls--> `load_settings()`  [INFERRED]
  scripts/verify_forward_v1.py → src/smarttrading/config/settings.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Graphify Extraction Pipeline** — codex_skills_graphify_skill_graphify, codex_skills_graphify_skill_structural_extraction, codex_skills_graphify_skill_semantic_extraction, codex_skills_graphify_references_extraction_spec_confidence_audit_trail [EXTRACTED 1.00]
- **Causal Out-of-Sample Validation System** — architecture_reproducibility_controls, docs_market_data_causal_bar_eligibility, docs_ml_methodology_causal_features, docs_ml_methodology_temporal_validation, docs_ml_methodology_sealed_final_holdout [INFERRED 0.95]
- **Safety-First Trading Flow** — architecture_safety_boundary, architecture_decision_flow, config_default_default_risk_limits, docs_paper_trading_paper_trading_runtime [INFERRED 0.95]

## Communities (33 total, 18 thin omitted)

### Community 0 - "backtest/engine.py"
Cohesion: 0.06
Nodes (63): dataclasses, enum, itertools, BacktestEngine, BacktestResult, cost_stress(), _git_commit(), BaseModel (+55 more)

### Community 1 - "cli.py"
Cohesion: 0.07
Nodes (54): ArgumentParser, httpx, Namespace, os, RuntimeError, main(), main(), signal (+46 more)

### Community 2 - "experiment.py"
Cohesion: 0.07
Nodes (44): BaseSettings, ndarray, Pipeline, PydanticBaseSettingsSource, sklearn, sklearn_calibration, sklearn_dummy, sklearn_ensemble (+36 more)

### Community 3 - "Bar"
Cohesion: 0.13
Nodes (22): BacktestStrategy, Protocol, _strategy(), Bar, Prediction, model_validator, Signal, SignalDirection (+14 more)

### Community 4 - "domain.py"
Cohesion: 0.07
Nodes (42): asyncio, collections, collections_abc, ClosedCandleBuffer, cross_asset_context(), MultiTimeframeStore, datetime, ApprovedOrder (+34 more)

### Community 5 - "dataset.py"
Cohesion: 0.07
Nodes (42): argparse, base64, datetime, hashlib, json, math, numpy, pandas (+34 more)

### Community 6 - "decimal"
Cohesion: 0.13
Nodes (19): decimal, pydantic_settings, DatabaseSettings, ExecutionSettings, load_settings(), Mode, BaseModel, Path (+11 more)

### Community 7 - "paper/engine.py"
Cohesion: 0.07
Nodes (45): shutil, sklearn_datasets, sqlite3, PaperTradingEngine, Any, Decimal, Load closed pre-start context without creating forward predictions or decisions., ShadowPortfolio (+37 more)

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

### Community 31 - "require_utc"
Cohesion: 0.21
Nodes (9): pytest, datetime, Return a UTC datetime, rejecting ambiguous naive values., require_utc(), utc_now(), datetime, field_validator, test_require_utc_converts_offset() (+1 more)

### Community 32 - ".compute_frame"
Cohesion: 0.25
Nodes (5): DataFrame, FeatureConfig, FeatureSet, _frame(), BaseModel

## Knowledge Gaps
- **23 isolated node(s):** `smarttrading`, `Scope and evidence boundary`, `Frozen models and features`, `Frozen decision and capital policy`, `Independent shadows` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 147 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Bar` connect `Bar` to `backtest/engine.py`, `cli.py`, `.compute_frame`, `experiment.py`, `domain.py`, `dataset.py`, `decimal`, `paper/engine.py`, `test_market_data.py`, `require_utc`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Why does `PaperTradingEngine` connect `paper/engine.py` to `backtest/engine.py`, `cli.py`, `experiment.py`, `Bar`, `domain.py`, `dataset.py`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `PaperStore` connect `paper/engine.py` to `cli.py`, `Bar`, `dataset.py`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 38 inferred relationships involving `Bar` (e.g. with `BacktestEngine` and `BacktestStrategy`) actually correct?**
  _`Bar` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `PaperTradingEngine` (e.g. with `main()` and `AppSettings`) actually correct?**
  _`PaperTradingEngine` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `PaperStore` (e.g. with `main()` and `PaperTradingEngine`) actually correct?**
  _`PaperStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Signal` (e.g. with `BacktestStrategy` and `FixedFractionSizer`) actually correct?**
  _`Signal` has 10 INFERRED edges - model-reasoned connections that need verification._