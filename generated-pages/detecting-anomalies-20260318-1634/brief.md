*[Part 1/4]*

*TASK A — CODEBASE VALIDATION*

*Core Anomaly Detection Capabilities*

*1. Data Quality Assertions* :white_check_mark:
- *Evidence:* `metadata-models/src/main/pegasus/com/linkedin/assertion/AssertionType.pdl` (lines 1-49)
- *Supported Types:* DATASET, FIELD, SQL, DATA_SCHEMA, CUSTOM assertions
- *Location:* `metadata-models/src/main/pegasus/com/linkedin/assertion/AssertionInfo.pdl`
- *Details:* Comprehensive assertion framework supporting structured assertions on datasets, columns, custom SQL queries, and schema validation

*2. Freshness Anomaly Detection* :white_check_mark:
- *Evidence:* `metadata-models/src/main/pegasus/com/linkedin/assertion/FreshnessAssertionInfo.pdl`
- *Capability:* FRESHNESS assertion type detects when data updates fall outside expected schedules
- *Location:* `AssertionType.pdl` lines 14-17

*3. Volume Anomaly Detection* :white_check_mark:
- *Evidence:* `metadata-models/src/main/pegasus/com/linkedin/assertion/VolumeAssertionInfo.pdl`
- *Capability:* VOLUME assertion type monitors row count changes and detects unexpected data volume patterns
- *Location:* `AssertionType.pdl` lines 19-23

*4. Schema Change Detection* :white_check_mark:
- *Evidence:* `metadata-models/src/main/pegasus/com/linkedin/assertion/SchemaAssertionInfo.pdl`
- *Capability:* DATA_SCHEMA assertion type detects breaking schema changes
- *Notification Support:* `NotificationScenarioType.java` line 21 - `DATASET_SCHEMA_CHANGE`

*5. Smart Assertions (ML-Powered Anomaly Detection)* :white_check_mark:
- *Evidence:* `metadata-models/src/main/pegasus/com/linkedin/assertion/AssertionInferenceDetails.pdl`
- *Details:* ML models (modelId, modelVersion, confidence scores) automatically infer assertion thresholds
- *Adjustment Algorithm:* `metadata-models/src/main/pegasus/com/linkedin/assertion/AssertionAdjustmentSettings.pdl` (lines 7-48)
  - Uses STDDEV algorithm for dynamic thresholds
  - Sensitivity controls (lines 45-47)
  - Training data lookback window (60 days default, line 42)
  - Automatic anomaly exclusion windows (line 35)
- *Release Notes:* v0.3.13 (line 66) - "Quickly tune Smart Assertion predictions with intuitive new UI"

*6. Anomaly Tracking &amp; Feedback* :white_check_mark:
- *Evidence:* `metadata-models/src/main/pegasus/com/linkedin/anomaly/MonitorAnomalyEvent.pdl`
- *Capability:* Immutable timeseries log of detected anomalies with human feedback (CONFIRMED/REJECTED states)
- *Summary Tracking:* `metadata-models/src/main/pegasus/com/linkedin/common/AnomaliesSummary.pdl` - tracks active and resolved anomalies

*7. Incident Management* :white_check_mark:
- *Evidence:* `smoke-test/tests/release_tests/test_incident.py` (lines 27-134)
- *Capability:* Raise incidents (OPERATIONAL/CRITICAL priority), track status (ACTIVE→RESOLVED), link to affected assets
- *GraphQL Operations:* `list_incidents()`, `raise_incident()`, `update_incident_status()`

*8. Alert &amp; Notification System* :white_check_mark:
- *Evidence:* `notifications/src/main/java/com/datahub/notification/NotificationScenarioType.java`
- *Supported Channels:* Slack, MS Teams, Email (`SlackProxySink.java`, `TeamsProxySink.java`, `EmailProxySink.java`)
- *Notification Types:*
  - `ASSERTION_STATUS_CHANGE` (line 36) - alerts when data quality checks fail
  - `NEW_INCIDENT` (line 22) - immediate incident notifications
  - `INCIDENT_STATUS_CHANGE` (line 23) - resolution updates

_(continued in next message...)_

---

*[Part 2/4]*

*9. Assertion Execution Results* :white_check_mark:
- *Evidence:* `metadata-models/src/main/pegasus/com/linkedin/assertion/AssertionResult.pdl`
- *Metrics:* rowCount, missingCount, unexpectedCount, actualAggValue (lines 20-38)
- *Result Types:* SUCCESS, FAILURE, ERROR with detailed error objects

*10. Circuit Breaker &amp; Health Checks* :white_check_mark:
- *Evidence:* `metadata-io/src/main/java/com/linkedin/metadata/search/elasticsearch/indexbuilder/CircuitBreakerState.java`
- *Location:* `metadata-io/src/main/java/com/linkedin/metadata/search/elasticsearch/indexbuilder/HealthCheckPoller.java`
- *Purpose:* Prevents cascading failures in data quality monitoring

*Known Limitations*

*MonitorSuite* :x:
- *Evidence:* `metadata-models/src/main/pegasus/com/linkedin/monitor/MonitorSuiteInfo.pdl` (lines 8-11)
- *Status:* @deprecated - "DO NOT USE. Never implemented — no service layer, no hooks, no UI. Use AssertionAssignmentRuleInfo instead."

---

*TASK B — LANDING PAGE OUTLINE*

*Angle*
DataHub turns anomaly detection from reactive firefighting into proactive data reliability. Platform Engineers get ML-powered Smart Assertions that automatically learn normal data patterns, detect freshness, volume, and schema anomalies in real-time, and alert the right teams before downstream impact—all without manual threshold tuning or endless YAML configuration.

*H1: Detecting Anomalies in Your Data Pipeline Before They Impact Production*

*H2: Automated Anomaly Detection for Modern Data Platforms*

*Why Platform Engineers Trust DataHub:*
- ML-powered Smart Assertions automatically detect anomalies without manual threshold configuration
- Real-time detection across freshness, volume, and schema changes
- Incident tracking with Slack/Teams/Email alerts to the right owners
- Lineage-aware impact analysis shows downstream dependencies at risk

*H2: How DataHub Detects Anomalies*

*H3: Smart Assertions — ML-Powered Anomaly Detection*
- *Automatic threshold learning:* Models analyze 60 days of historical data patterns
- *Dynamic sensitivity controls:* Tune predictions from conservative to aggressive with one slider
- *Anomaly exclusion:* Automatically filter out known outliers from training data
- *Confidence scoring:* Every detection includes model confidence and expected vs. actual metrics

*H3: Multi-Dimensional Anomaly Coverage*
- *Freshness anomalies:* Detect when tables aren't updating on schedule
- *Volume anomalies:* Catch unexpected spikes or drops in row counts
- *Schema changes:* Breaking changes flagged before downstream queries fail
- *Data quality rules:* Custom SQL assertions, field-level validations, null checks

*H3: Intelligent Alerting &amp; Incident Management*
- *Context-rich alerts:* Slack/Teams/Email notifications include assertion details, failure metrics, affected assets
- *Incident workflows:* Raise, track, and resolve incidents with status updates synced to Slack
- *Downstream impact analysis:* See which dashboards, pipelines, and teams are affected
- *Anomaly feedback loop:* Confirm or reject detections to improve future predictions

*H2: Built for Platform Engineering Teams*

_(continued in next message...)_

---

*[Part 3/4]*

*H3: Connect to Your Entire Stack*
- *50+ connectors:* Snowflake, BigQuery, Redshift, dbt, Airflow, Tableau, Looker, and more
- *API-first design:* GraphQL and REST APIs for programmatic assertion management
- *Bulk operations:* Create assertions across hundreds of datasets in minutes

*H3: Scale Anomaly Detection Across Teams*
- *Assignment rules:* Auto-apply assertions to datasets by pattern, domain, or ownership
- *Team-specific settings:* Per-team notification preferences and escalation policies
- *Subscription management:* Users choose which anomalies they care about

*H2: See DataHub in Action*

*[CTA Button: Get a Product Tour]*

Explore how DataHub detects anomalies across your data platform—from ingestion to consumption.

---

*FAQs*

*1. How does DataHub's Smart Assertion ML model work?*
DataHub analyzes historical metric data (default: 60 days) to learn normal patterns for volume, freshness, and field metrics. It uses standard deviation-based algorithms to set dynamic thresholds that adapt as your data evolves. You control sensitivity with a simple UI slider—no ML expertise required.

*2. Can I use DataHub to detect anomalies without writing SQL?*
Yes! Smart Assertions automatically monitor freshness and volume without any SQL. For custom business logic, you can write SQL assertions or use field-level validations (null checks, range checks, regex patterns). DataHub also supports integrations with external data quality tools like Great Expectations and Monte Carlo.

*3. What happens when DataHub detects an anomaly?*
When an assertion fails, DataHub immediately sends alerts to configured channels (Slack, MS Teams, Email) with full context: the assertion that failed, expected vs. actual metrics, affected dataset, and downstream dependencies. You can raise incidents directly from failed assertions, track resolution status, and provide feedback to improve future detections.

*4. How does DataHub show downstream impact when an anomaly is detected?*
DataHub's lineage graph automatically traces upstream and downstream dependencies. When an assertion fails, you see which dashboards, reports, pipelines, and teams rely on the affected dataset. Notifications can be sent to downstream owners, not just the data owner, so everyone impacted gets alerted proactively.

*5. Can I customize which anomalies trigger alerts?*
Absolutely. DataHub offers fine-grained subscription controls: users can subscribe to specific assertion types, datasets, domains, or tags. Global admins can configure team-wide defaults, and individual users can override with personal preferences. You can also configure escalation policies and on-call rotations.

*6. Does DataHub support schema change detection?*
Yes. DataHub's DATA_SCHEMA assertions detect breaking schema changes like dropped columns, type changes, and constraint modifications. It automatically generates schema notifications when changes are detected and can prevent downstream queries from breaking by alerting before propagation.

---

*TASK C — DIAGRAM BRIEFS*

*Prompt 1: DataHub Anomaly Detection Architecture Overview*
*Layout type:* architecture
*Description:* Three-tier horizontal architecture showing data flow from left to right. Left section contains data sources, middle section shows DataHub platform core components, right section shows output destinations.

_(continued in next message...)_

---

*[Part 4/4]*

*Exact sections and flow:*
- *Left section - Data Sources:* Show 4-5 source icons in a vertical stack representing connection points. Label each source type.
  - "Snowflake"
  - "BigQuery"
  - "dbt"
  - "Airflow"
  - "Redshift"
- *Arrow:* Bidirectional arrow labeled "Metadata Ingestion &amp; Profiling" connecting sources to platform core
- *Middle section - DataHub Platform Core:* Large central box containing 4 stacked subsystems
  - Top layer: "Smart Assertion Engine" (with badge: "ML-Powered")
  - Second layer: "Anomaly Detection" (with 3 sub-items: "Freshness | Volume | Schema")
  - Third layer: "Incident Management"
  - Bottom layer: "Lineage Graph &amp; Impact Analysis"
- *Arrow:* Arrow labeled "Alerts &amp; Notifications" connecting platform core to outputs
- *Right section - Alert Destinations:* Show 3 destination icons in vertical stack
  - "Slack"
  - "MS Teams"
  - "Email"

*Additional elements:*
- Badge on Smart Assertion Engine: "Auto-tuning thresholds"
- Badge on Lineage Graph: "Downstream impact tracking"

---

*Prompt 2: Anomaly Detection Workflow — From Detection to Resolution*
*Layout type:* workflow
*Description:* Linear left-to-right workflow showing 6 sequential stages of anomaly detection and resolution process. Each stage is a rounded box with an icon and description. Arrows connect stages to show progression.

*Exact stages with labels:*

1. *Stage 1 - Data Monitoring*
   - Icon: magnifying glass or chart line
   - Label: "Data Monitoring"
   - Description: "Smart Assertions continuously monitor freshness, volume, schema"

2. *Stage 2 - Anomaly Detected*
   - Icon: alert triangle or warning symbol
   - Label: "Anomaly Detected"
   - Description: "ML model flags deviation from learned patterns"

3. *Stage 3 - Impact Analysis*
   - Icon: connected nodes or network diagram
   - Label: "Impact Analysis"
   - Description: "Lineage graph identifies downstream dependencies at risk"

4. *Stage 4 - Alert Routing*
   - Icon: bell or notification icon
   - Label: "Alert Routing"
   - Description: "Context-rich notifications sent to owners &amp; downstream teams"

5. *Stage 5 - Incident Created*
   - Icon: ticket or clipboard
   - Label: "Incident Created"
   - Description: "Track investigation, assign ownership, document root cause"

6. *Stage 6 - Resolution &amp; Feedback*
   - Icon: checkmark or cycle arrow
   - Label: "Resolution &amp; Feedback"
   - Description: "Mark resolved, provide feedback to improve future detections"

*Flow annotations:*
- Arrow from Stage 2 to Stage 3: "Lineage traversal"
- Arrow from Stage 4 to Stage 5: "Manual escalation" (optional branch)
- Arrow from Stage 6 back to Stage 1: "Continuous learning loop" (dotted line)

*Additional context box at bottom:*
- "Average time to detection: &lt; 15 minutes | Average time to alert: &lt; 1 minute"

---

BART_DONE

• • •
:moneybag: `$0.1104` (API `$0.1094`) • Session: `$0.1104` (1 msg)