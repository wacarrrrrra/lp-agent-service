*[Part 1/6]*

Alright! I've searched the DataHub codebase and validated all capabilities. Here's the technically accurate SEM landing page outline for "detecting anomalies":

---

*TASK A — CODEBASE VALIDATION*

*Core Anomaly Detection Capabilities*

*1. AI-Powered Smart Assertions (Anomaly Detection)* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/smart-assertions.md`
- *Details*: ML-powered anomaly detection that trains on historical patterns, predicts "normal" behavior, and detects deviations. Supports seasonality and trend analysis.
- *Assertion types*: Freshness, Volume, Column Metrics, Custom SQL
- *Code*: `cloud/metadata-models/src/main/pegasus/com/linkedin/anomaly/MonitorAnomalyEvent.pdl`

*2. Freshness Anomaly Detection* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/freshness-assertions.md`
- *Details*: Detects when tables aren't updated as expected (SLA violations)
- *Platforms*: Snowflake, Redshift, BigQuery, Databricks
- *Code*: `cloud/datahub-graphql-core/src/main/java/com/linkedin/datahub/graphql/resolvers/assertion/CreateFreshnessAssertionResolver.java`

*3. Volume Anomaly Detection* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/volume-assertions.md`
- *Details*: Detects unexpected changes in row count, table size, or data volume
- *Platforms*: Snowflake, Redshift, BigQuery, Databricks, DataHub Dataset Profile
- *Code*: `cloud/datahub-graphql-core/src/main/java/com/linkedin/datahub/graphql/resolvers/assertion/CreateVolumeAssertionResolver.java`

*4. Schema Change Anomaly Detection* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/schema-assertions.md`
- *Details*: Detects unexpected column additions, removals, or type changes
- *Platforms*: All data sources with schema ingestion
- *Code*: `cloud/datahub-graphql-core/src/main/java/com/linkedin/datahub/graphql/resolvers/assertion/UpsertDatasetSchemaAssertionMonitorResolver.java`

*5. Column-Level Anomaly Detection* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/column-assertions.md`
- *Details*: Monitors specific columns for null spikes, value distribution changes, metric anomalies
- *Platforms*: Snowflake, Redshift, BigQuery, Databricks
- *Code*: `cloud/datahub-graphql-core/src/main/java/com/linkedin/datahub/graphql/resolvers/assertion/CreateFieldAssertionResolver.java`

*6. Custom SQL Anomaly Detection* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/custom-sql-assertions.md`
- *Details*: Define complex business logic checks via SQL queries to detect domain-specific anomalies
- *Platforms*: Snowflake, Redshift, BigQuery, Databricks
- *Code*: `cloud/datahub-graphql-core/src/main/java/com/linkedin/datahub/graphql/resolvers/assertion/CreateSqlAssertionResolver.java`

*7. Automated Monitoring Rules* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/data-health-dashboard.md` (lines 70-80)
- *Details*: Automatically apply Smart Assertions across datasets based on search predicates (domain, platform, schema). New datasets auto-inherit monitors.
- *Code*: `cloud/metadata-service/services/src/main/java/com/linkedin/metadata/service/AssertionAssignmentRuleService.java`

*8. Data Health Dashboard* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/data-health-dashboard.md`
- *Details*: Centralized dashboard for triaging anomalies, viewing assertion failures, and monitoring coverage
- *Features*: By Assertion view, By Table view, Incidents tab, custom filters

_(continued in next message...)_

---

*[Part 2/6]*

*9. Anomaly Tracking System* :white_check_mark:
- *Evidence*: `cloud/metadata-models/src/main/pegasus/com/linkedin/common/AnomaliesSummary.pdl`
- *Details*: Tracks active and resolved anomalies with timestamps, types, and sources
- *Code*: `cloud/metadata-models/src/main/pegasus/com/linkedin/anomaly/MonitorAnomalyEvent.pdl`

*10. Incident Management Integration* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/assertions.md` (line 69)
- *Details*: Assertion failures can trigger incidents with tracking and resolution workflows

*11. Real-Time Alerting* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/assertions.md` (lines 67-71)
- *Platforms*: Slack (DMs or team channels), AWS EventBridge
- *Features*: Subscribe to assertion run events, incident creation/resolution

*12. Third-Party Integration* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/assertions.md` (lines 59-65)
- *Integrations*: dbt Test, Great Expectations, Custom Assertions API

*13. Historical Analysis &amp; Trending* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/assertions.md` (lines 33-49)
- *Details*: ML models analyze historical patterns including seasonality, standard deviation, trend analysis

*14. Tunable Sensitivity* :white_check_mark:
- *Evidence*: `cloud/docs/managed-datahub/observe/smart-assertions.md` (lines 46-50)
- *Features*: Adjust sensitivity, exclusion windows, training lookback period, anomaly feedback

---

*TASK B — LANDING PAGE OUTLINE*

*ANGLE*
DataHub's AI-powered anomaly detection continuously monitors your data pipelines across Snowflake, BigQuery, Redshift, and Databricks, automatically learning normal patterns and alerting you the moment data quality issues emerge — before they impact downstream analytics or ML models. With Smart Assertions that understand seasonality and trend analysis, plus automated monitoring rules that scale across thousands of datasets, platform engineering teams can shift from reactive firefighting to proactive data reliability.

*H1*
*Detecting Anomalies in Your Data Pipeline Before They Become Incidents*

---

*H2: Why Data Anomalies Break Production Systems*

*H3: The Hidden Cost of Undetected Data Quality Issues*
- Late detection means downstream dashboards, reports, and ML models consume bad data
- Manual spot-checking doesn't scale across hundreds or thousands of tables
- Schema changes, volume spikes, and freshness delays cascade through dependent systems
- Traditional monitoring catches infrastructure failures but misses data-level anomalies

*H3: What Platform Engineers Need from Anomaly Detection*
- *Automatic pattern learning* — systems that understand seasonality, trends, and normal variance without manual thresholds
- *Comprehensive coverage* — monitoring freshness, volume, schema, and column-level metrics across all critical datasets
- *Scalable automation* — rules that apply monitoring to new datasets automatically, not manual assertion creation
- *Contextual alerts* — notifications with lineage, impact analysis, and actionable insights, not just "table X changed"

---

*H2: How DataHub Detects Data Anomalies at Scale*

_(continued in next message...)_

---

*[Part 3/6]*

*H3: AI-Powered Smart Assertions Learn What "Normal" Looks Like*
- Machine learning models train on your historical data patterns to predict expected behavior
- Automatically accounts for seasonality (weekly/monthly cycles), trends, and statistical variance
- Detects anomalies across freshness (SLA violations), volume (unexpected row count changes), schema changes, and column-level metrics
- Tunable sensitivity with exclusion windows for maintenance periods or known seasonal spikes

*H3: Comprehensive Anomaly Detection Across Every Data Layer*
- *Freshness anomalies*: Detect when tables aren't updated on schedule using audit logs, information schema, or high watermark columns
- *Volume anomalies*: Identify unexpected row count changes, data drops, or sudden growth patterns
- *Schema anomalies*: Catch breaking changes when columns are added, removed, or types are altered
- *Column-level anomalies*: Monitor null rate spikes, value distribution shifts, or metric violations within specific columns
- *Custom SQL anomalies*: Define domain-specific business logic checks for complex validation scenarios

*H3: Monitoring Rules: Anomaly Detection That Scales Automatically*
- Define search predicates (domain, platform, schema, tags) to apply Smart Assertions across matching datasets
- New datasets that match your criteria automatically inherit monitoring — no manual configuration
- Remove assertions from datasets that no longer match, keeping coverage aligned with your data landscape
- Centralized management through Data Health Dashboard with filtering by owner, domain, or custom views

*H4: Supported Data Platforms*
- Snowflake, Amazon Redshift, Google BigQuery, Databricks
- DataHub Operations and Dataset Profiles (via ingestion) for additional platform coverage

---

*H2: Triage, Investigate, and Resolve Anomalies Faster*

*H3: Data Health Dashboard: Your Anomaly Command Center*
- *By Assertion view*: Activity log of all assertion runs, filter by failures in last N days, identify flaky checks
- *By Table view*: Coverage analysis showing which tables have active monitoring and their health status
- *Incidents tab*: Track open incidents against tables with ownership, timeline, and resolution status
- *Custom filters*: Drill down by dataset owner, domain, tags, or global views for team-specific dashboards

*H3: Context-Rich Alerts Delivered Where Your Team Works*
- Slack notifications (DMs or team channels) when assertions fail or incidents are raised/resolved
- Subscribe to specific assertion run events or entire dataset monitoring
- AWS EventBridge integration for triggering automated remediation workflows
- Lineage and impact analysis show which downstream assets are affected by detected anomalies

*H3: Continuous Improvement Through Feedback Loops*
- Mark anomalies as confirmed (true positive) or rejected (false positive) to improve ML predictions
- Adjust exclusion windows to remove non-representative data from training (holidays, migrations, outages)
- Tune lookback period to balance capturing seasonal patterns vs. adapting to recent trends
- Assertion run history provides audit trail for compliance and root cause analysis

---

*H2: Deploy Anomaly Detection Without Exposing Data*

_(continued in next message...)_

---

*[Part 4/6]*

*H3: Execute Monitoring In-Network with Remote Executor*
- Assertions run within your private network using DataHub Remote Executor
- Only assertion results are sent to DataHub Cloud — credentials and source data never leave your environment
- Queries leverage information schema, audit logs, or direct table queries based on cost optimization needs
- Compatible with existing ingestion sources for Snowflake, Redshift, BigQuery, and Databricks

*H3: Integrate with Existing Data Quality Tools*
- Ingest assertion results from dbt Test or Great Expectations
- Custom Assertions API for proprietary testing frameworks
- Subscribe to assertion events via Kafka (Actions Framework) for downstream automation
- Open Assertions Spec for interoperability

---

*H2: Get Started with DataHub Anomaly Detection*

*H3: Start Monitoring Critical Datasets in Minutes*
1. Connect your data platform (Snowflake, BigQuery, Redshift, or Databricks) via ingestion source
2. Create Smart Assertions on key tables or define Monitoring Rules to apply monitoring at scale
3. Configure Slack notifications or AWS EventBridge for real-time alerts
4. Monitor the Data Health Dashboard to triage failures and track coverage

*H3: Scale from Pilot to Production*
- Begin with high-impact tables (core facts, critical aggregations, customer-facing datasets)
- Expand coverage using Monitoring Rules based on domain, platform, or schema
- Tune ML models with exclusion windows and sensitivity adjustments as patterns emerge
- Integrate with incident management and on-call workflows for 24/7 monitoring

---

*FAQs*

*1. How does DataHub detect anomalies without manual thresholds?*
DataHub Smart Assertions use machine learning to analyze historical data patterns and predict expected behavior. The models automatically account for seasonality (daily/weekly/monthly cycles), trends, and statistical variance. When observed values deviate significantly from predictions, an anomaly is flagged. You can tune sensitivity to balance false positives vs. detection accuracy.

*2. What types of data anomalies can DataHub detect?*
DataHub detects five categories of anomalies: (1) Freshness — tables not updated on schedule, (2) Volume — unexpected row count changes or data drops, (3) Schema — columns added/removed or type changes, (4) Column-level — null rate spikes, value distribution shifts, metric violations, and (5) Custom SQL — domain-specific business logic checks. All five support both rule-based assertions and AI-powered Smart Assertions.

*3. How do Monitoring Rules work, and why are they better than manual assertion creation?*
Monitoring Rules let you define search predicates (e.g., "all tables in Finance domain" or "all Snowflake datasets with tag:critical") and automatically apply Smart Assertions to matching datasets. New datasets that match your criteria inherit monitoring immediately, and datasets that no longer match have assertions removed. This eliminates manual assertion creation for each table and ensures coverage scales with your data landscape.

_(continued in next message...)_

---

*[Part 5/6]*

*4. Will DataHub's anomaly detection work with our existing data quality tools like dbt or Great Expectations?*
Yes. DataHub integrates with dbt Test and Great Expectations to ingest their assertion results into the unified Data Health Dashboard. You can also use the Custom Assertions API for proprietary testing frameworks. This gives you a single pane of glass for all data quality monitoring, whether powered by DataHub Smart Assertions or third-party tools.

*5. How do we prevent false positives from seasonal data patterns?*
Smart Assertions automatically learn seasonal patterns (weekly, monthly cycles) during training. You can further reduce false positives by: (1) Setting exclusion windows for known maintenance periods, holidays, or migrations, (2) Adjusting sensitivity to allow more variance before flagging anomalies, (3) Tuning the training lookback window to balance capturing seasonality vs. adapting to recent trends, and (4) Providing feedback by marking anomalies as confirmed or rejected to improve future predictions.

*6. Can we run anomaly detection without exposing our data to DataHub Cloud?*
Absolutely. DataHub Remote Executor runs within your private network and executes assertion queries against your data warehouse. Only assertion results (pass/fail status, metrics) are sent to DataHub Cloud — your credentials and source data never leave your environment. This architecture is ideal for regulated industries or sensitive datasets.

---

*TASK C — DIAGRAM BRIEFS*

*Prompt 1: AI Anomaly Detection Workflow*
Layout type: Horizontal workflow (left-to-right stages)

Flow shows how Smart Assertions detect anomalies in 4 stages:
- Stage 1 (left): "Historical Data Collection" — DataHub ingests table metadata, row counts, schema, column metrics from Snowflake/BigQuery/Redshift/Databricks over time
- Stage 2: "ML Pattern Learning" — Smart Assertion trains on historical patterns, learning seasonality, trends, and normal statistical variance
- Stage 3: "Continuous Monitoring" — Assertions run on schedule (hourly, daily, etc.), comparing observed values to ML predictions
- Stage 4 (right): "Anomaly Alerting" — When deviation exceeds threshold, alert is sent via Slack/EventBridge and logged in Data Health Dashboard

Text labels:
- "Historical Data Collection"
- "Metadata Ingestion"
- "Row Counts, Schema, Column Metrics"
- "ML Pattern Learning"
- "Seasonality &amp; Trend Analysis"
- "Continuous Monitoring"
- "Scheduled Assertion Runs"
- "Anomaly Alerting"
- "Slack, EventBridge, Dashboard"

Arrows connect stages left-to-right with feedback loop from Stage 4 back to Stage 2 labeled "Feedback Loop: Confirmed/Rejected Anomalies Improve Model"

---

*Prompt 2: Comprehensive Anomaly Detection Coverage*
Layout type: 2x2 grid (4 categories with titles + bullets)

Grid shows 4 types of anomaly detection, each in its own quadrant:

Top-left quadrant: "Freshness Anomalies"
- SLA violations — table not updated on time
- Audit log monitoring
- High watermark column checks
- Information schema tracking

Top-right quadrant: "Volume Anomalies"
- Unexpected row count changes
- Data drops or sudden growth
- Partition-level volume shifts
- Statistical variance detection

Bottom-left quadrant: "Schema Anomalies"
- Columns added or removed
- Data type changes
- Breaking schema evolution
- Column rename detection

_(continued in next message...)_

---

*[Part 6/6]*

Bottom-right quadrant: "Column &amp; SQL Anomalies"
- Null rate spikes
- Value distribution shifts
- Custom business logic (SQL)
- Metric threshold violations

Text labels (exactly as above, no additional styling)

---

*Prompt 3: Monitoring Rules Architecture for Scale*
Layout type: Architecture diagram (hub + connected systems)

Central hub: "Monitoring Rules Engine"

Connected systems radiating from center:
- Left side: "Search Predicates" box containing bullets: "Domain: Finance", "Platform: Snowflake", "Tags: critical, pii", "Schema: prod_*"
- Top: "Smart Assertions" box containing bullets: "Freshness Monitors", "Volume Monitors", "Schema Monitors", "Column Monitors"
- Right side: "Dataset Discovery" box with flow: "New datasets auto-matched" → "Monitors auto-applied" → "Removed datasets cleaned up"
- Bottom: "Matching Datasets" showing grid of dataset icons (representing hundreds of tables)

Text labels:
- "Monitoring Rules Engine" (center)
- "Search Predicates"
- "Domain: Finance", "Platform: Snowflake", "Tags: critical, pii", "Schema: prod_*"
- "Smart Assertions"
- "Freshness Monitors", "Volume Monitors", "Schema Monitors", "Column Monitors"
- "Dataset Discovery"
- "New datasets auto-matched", "Monitors auto-applied", "Removed datasets cleaned up"
- "Matching Datasets (Auto-Monitored)"

Arrows show bidirectional flow between all components and central hub

---

*Prompt 4: Anomaly Response &amp; Resolution Workflow*
Layout type: Horizontal workflow (left-to-right stages)

Flow shows 5 stages of responding to detected anomalies:
- Stage 1 (left): "Anomaly Detected" — Smart Assertion flags deviation from expected pattern (volume spike, schema change, freshness delay)
- Stage 2: "Contextual Alert" — Notification sent to Slack/EventBridge with lineage showing downstream impact (dashboards, ML models affected)
- Stage 3: "Triage in Dashboard" — Data Health Dashboard shows assertion failure details, historical trends, and filtering by team/domain
- Stage 4: "Investigation" — Platform engineer reviews assertion run details, queries source data, checks upstream pipelines
- Stage 5 (right): "Resolution &amp; Feedback" — Issue fixed (or anomaly marked as expected), feedback loop improves ML model

Text labels:
- "Anomaly Detected"
- "Volume Spike, Schema Change, Freshness Delay"
- "Contextual Alert"
- "Slack, EventBridge, Lineage Impact"
- "Triage in Dashboard"
- "Data Health Dashboard"
- "Investigation"
- "Source Data, Upstream Pipelines"
- "Resolution &amp; Feedback"
- "ML Model Improvement"

Arrows connect stages left-to-right with dotted line from Stage 5 back to Stage 1 labeled "Continuous Monitoring"

---

BART_DONE

• • •
:moneybag: `$0.1317` (API `$0.1305`) • Session: `$0.1317` (1 msg)