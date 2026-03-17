*[Part 1/4]*

Perfect! I have all the evidence I need from the codebase. Let me create your landing page outline with full validation.

---

*TASK A — CODEBASE VALIDATION*

*Core Anomaly Detection Capabilities*

*1. AI-Powered Smart Assertions (ML-based Anomaly Detection)*
:white_check_mark: *VERIFIED*
- *Evidence:* `cloud/docs/managed-datahub/observe/smart-assertions.md`, ML inference engine in `cloud/datahub-executor/src/datahub_executor/common/monitor/inference_v2/`
- *Capabilities:* Trains on historical patterns, accounts for seasonality, predicts normal behavior
- *Types:* Freshness, Volume, Column Metrics, Custom SQL assertions

*2. Supported Data Platforms*
:white_check_mark: *VERIFIED* 
- *Evidence:* `cloud/docs/managed-datahub/observe/assertions.md` (line 4), repeated across freshness-assertions.md, volume-assertions.md, column-assertions.md
- *Platforms:* Snowflake, Redshift, BigQuery, Databricks
- *Additional:* DataHub ingested metrics for any platform

*3. Monitoring Rules (Assertions at Scale)*
:white_check_mark: *VERIFIED*
- *Evidence:* `cloud/docs/managed-datahub/observe/data-health-dashboard.md` (lines 70-99), `cloud/docs/managed-datahub/observe/assertions.md` (lines 25-31)
- *Capabilities:* Search-based predicates to auto-apply monitors across datasets, automatic lifecycle management for new/removed datasets

*4. Tuning &amp; Optimization*
:white_check_mark: *VERIFIED*
- *Evidence:* `cloud/docs/managed-datahub/observe/smart-assertions.md` (lines 32-66)
- *Features:* Sensitivity adjustment, exclusion windows, training data lookback window (configurable days)
- *UI:* "Tune Predictions" button on assertion profile

*5. Anomaly Feedback Loop*
:white_check_mark: *VERIFIED*
- *Evidence:* `cloud/docs/managed-datahub/observe/smart-assertions.md` (lines 52-70)
- *Actions:* Mark as Normal, Train as New Normal, Mark as Anomaly
- *Purpose:* Continuous model improvement based on human feedback

*6. Incident Management*
:white_check_mark: *VERIFIED*
- *Evidence:* `cloud/datahub-graphql-core/src/main/resources/incident.graphql` (full incident API)
- *Capabilities:* Raise incidents, update status, track incidents by entity, incidents timeline

*7. Alerting &amp; Notifications*
:white_check_mark: *VERIFIED*
- *Evidence:* `cloud/docs/managed-datahub/observe/assertions.md` (lines 68-71)
- *Channels:* Slack DMs, Slack team channels, AWS EventBridge
- *Triggers:* Assertion failures, incident raised/resolved

*8. Data Health Dashboard*
:white_check_mark: *VERIFIED*
- *Evidence:* `cloud/docs/managed-datahub/observe/data-health-dashboard.md`
- *Views:* By Assertion, By Table, Incidents tab
- *Filters:* Owner, Domain, Tags, Platform, Time Range, Results status

*9. In-Network Execution (Privacy)*
:white_check_mark: *VERIFIED*
- *Evidence:* `cloud/docs/managed-datahub/observe/assertions.md` (lines 94-96)
- *Feature:* Remote Executor deployment model
- *Benefit:* Assertions run in your network, only results sent to DataHub Cloud, credentials/data never leave network

*10. Query Attribution &amp; Cost Control*
:warning: *VERIFIED (with nuance)*
- *Evidence:* `cloud/docs/managed-datahub/observe/assertion-query-attribution.md`
- *Features:* Snowflake Query Tags, BigQuery Job Labels for tracking DataHub queries
- *Optimization:* Information Schema queries (cheap), conditional direct table queries

---

*TASK B — LANDING PAGE OUTLINE*

_(continued in next message...)_

---

*[Part 2/4]*

*Angle*
Platform engineers searching for "detecting anomalies" need automated, intelligent monitoring that adapts to their data patterns—not brittle static rules that break with every data shift. DataHub Cloud delivers AI-powered anomaly detection that learns seasonal patterns, auto-tunes sensitivity, and scales across your entire Snowflake, BigQuery, Redshift, or Databricks warehouse—catching data incidents before they impact downstream dashboards or production ML models.

*H1*
*Detecting Anomalies in Your Data Warehouse with AI-Powered Monitoring*

*H2: Why Traditional Rules Fail at Detecting Anomalies*

*H3: The Static Rule Problem*
- Manual thresholds break when data patterns evolve (seasonal spikes, growth trends)
- Requires constant maintenance across hundreds or thousands of tables
- High false positive rates erode trust in alerts

*H3: The Scale Challenge*
- Impossible to manually configure rules for every table and column
- No way to automatically monitor new datasets as they appear
- Inconsistent coverage creates blind spots in critical data pipelines

*H2: How DataHub Cloud Detects Anomalies Automatically*

*H3: AI-Powered Smart Assertions*
- Machine learning trains on your historical data patterns
- Automatically accounts for seasonality (daily, weekly, monthly cycles)
- Adapts to gradual trends while flagging true anomalies

*H3: Four Types of Anomaly Detection*
- *Freshness Anomalies:* Detects unexpected delays in table updates
- *Volume Anomalies:* Catches sudden spikes or drops in row counts
- *Column Metric Anomalies:* Monitors null rates, uniqueness, min/max, standard deviation
- *Custom SQL Anomalies:* Validates business logic with custom queries

*H3: Monitoring Rules — Anomaly Detection at Scale*
- Define search predicates (domain, platform, schema, tags)
- Automatically apply monitors to all matching datasets
- New datasets auto-inherit monitoring as they're discovered

*H2: Tuning Anomaly Detection for Your Data*

*H3: Sensitivity Controls*
- Adjust tightness of predictions to balance false positives vs. missed anomalies
- Higher sensitivity = tighter fit, lower sensitivity = more tolerance

*H3: Exclusion Windows*
- Exclude maintenance windows, known incidents, or seasonal events from training
- Prevent historical outliers from polluting "normal" baseline

*H3: Lookback Windows*
- Configure training data range (days/weeks/months)
- Balance capturing long-term patterns vs. adapting to recent changes

*H3: Human-in-the-Loop Feedback*
- Mark false alarms as "Normal" to retrain model
- Flag missed anomalies to improve future detection
- "Train as New Normal" for step-changes in data patterns

*H2: Real-Time Alerts When Anomalies Are Detected*

*H3: Multi-Channel Notifications*
- Slack DMs and team channels
- AWS EventBridge for custom integrations
- Subscribe by asset, owner, domain, or tag

*H3: Incident Management*
- Automatic incident creation for failed assertions
- Track resolution timeline and ownership
- Historical incident log for root cause analysis

*H2: Enterprise-Grade Deployment for Platform Engineers*

*H3: In-Network Execution*
- Remote Executor runs inside your VPC/network
- Credentials and raw data never leave your infrastructure
- Only assertion results transmitted to DataHub Cloud

_(continued in next message...)_

---

*[Part 3/4]*

*H3: Multi-Platform Support*
- Snowflake, BigQuery, Redshift, Databricks
- Query attribution with Snowflake Query Tags and BigQuery Job Labels
- Optimized queries using Information Schema when possible

*H3: Data Health Dashboard*
- Triage failed assertions across your entire data landscape
- Filter by owner, domain, platform, time range
- Track monitoring coverage and identify gaps

*H2: Frequently Asked Questions*

*Q: How does AI anomaly detection differ from static threshold rules?*
A: Static rules require manual configuration and break when data patterns change. DataHub's Smart Assertions use machine learning to learn your data's normal behavior—including seasonality and trends—and automatically adapt over time. You can still use traditional threshold-based assertions when strict rules are needed.

*Q: What data platforms are supported for detecting anomalies?*
A: DataHub Cloud natively supports Snowflake, BigQuery, Redshift, and Databricks for live assertion execution. For other platforms, you can monitor anomalies using ingested dataset statistics and freshness metadata.

*Q: How do I prevent false positives in anomaly detection?*
A: DataHub provides three tuning levers: (1) Adjust sensitivity to control prediction tightness, (2) Add exclusion windows to ignore known maintenance periods or incidents, (3) Mark false alarms as "Normal" to retrain the model. You can access these controls via the "Tune Predictions" button on any Smart Assertion.

*Q: Can I automatically monitor new datasets as they're created?*
A: Yes! Monitoring Rules let you define search predicates (e.g., "all tables in the Finance domain" or "all Snowflake tables with tag:PII"). DataHub automatically creates Smart Assertions on matching datasets and removes them when datasets no longer match.

*Q: Do my credentials or data leave my network?*
A: Not with the Remote Executor deployment model. The executor runs inside your VPC and executes assertions locally. Only assertion results (pass/fail, metrics) are sent to DataHub Cloud—your credentials and raw data stay in your infrastructure.

*Q: How much does it cost to run anomaly detection queries?*
A: DataHub optimizes costs by using Information Schema queries (nearly free) for freshness and volume checks when possible. For column-level assertions, queries are optimized to minimize data scanned. Query attribution tags (Snowflake Query Tags, BigQuery Job Labels) let you track DataHub-generated queries in your warehouse billing.

---

*TASK C — DIAGRAM BRIEFS*

*Prompt 1: DataHub Anomaly Detection Architecture*
*Layout:* architecture
*Description:* Three-stage left-to-right architecture showing data sources connecting to DataHub monitoring core, then outputs. Left section contains data warehouse icons (Snowflake, BigQuery, Redshift, Databricks) with bidirectional arrows labeled "Assertion Queries" pointing to center section. Center section is a vertical stack containing: "Remote Executor (In Your VPC)" at top, "Smart Assertions Engine (ML Models)" in middle, "Incident Manager" at bottom. Right section shows outputs: "Slack Notifications", "Data Health Dashboard", "AWS EventBridge" stacked vertically. Arrows flow left to right showing data movement: sources → executor → engine → outputs.

_(continued in next message...)_

---

*[Part 4/4]*

*Text labels verbatim:*
- Snowflake
- BigQuery
- Redshift
- Databricks
- Assertion Queries
- Remote Executor (In Your VPC)
- Smart Assertions Engine (ML Models)
- Incident Manager
- Slack Notifications
- Data Health Dashboard
- AWS EventBridge

---

*Prompt 2: Anomaly Detection Workflow — From Detection to Resolution*
*Layout:* workflow
*Description:* Six-stage horizontal workflow with left-to-right arrows connecting each stage. Each stage is a rounded rectangle box containing a title and 2-3 bullet points. Flow: (1) Data Change → (2) Assertion Execution → (3) Anomaly Detected → (4) Alert Sent → (5) Investigation → (6) Resolution &amp; Feedback. Arrows between stages show progression. Final stage has a curved arrow looping back to stage (2) labeled "Model Retraining".

*Text labels verbatim:*
- *Stage 1:* Data Change
  - Table updated
  - New rows added
  - Schema modified
- *Stage 2:* Assertion Execution
  - Smart Assertion runs on schedule
  - Queries Information Schema or table
  - ML model predicts expected range
- *Stage 3:* Anomaly Detected
  - Actual value outside predicted range
  - Incident automatically raised
  - Historical context captured
- *Stage 4:* Alert Sent
  - Slack notification to owner
  - Incident appears in dashboard
  - EventBridge event triggered
- *Stage 5:* Investigation
  - Review assertion timeline
  - Check historical patterns
  - Identify root cause
- *Stage 6:* Resolution &amp; Feedback
  - Mark as Normal or Anomaly
  - Tune sensitivity if needed
  - Add exclusion window
- *Arrow from Stage 6 to Stage 2:* Model Retraining

---

*BART_DONE*

• • •
:moneybag: `$0.1015` (API `$0.1004`) • Session: `$0.1015` (1 msg)