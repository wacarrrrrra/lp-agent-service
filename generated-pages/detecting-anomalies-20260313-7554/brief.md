*[Part 1/3]*

*TASK A — CODEBASE VALIDATION*

*Core Anomaly Detection Capabilities*

*:white_check_mark: Smart Assertions (AI-Powered Anomaly Detection)*
- *Evidence:* `cloud/docs/managed-datahub/observe/smart-assertions.md` (lines 7-27)
- *Implementation:* ML training pipeline in `cloud/datahub-executor/src/datahub_executor/common/monitor/inference/`
- *Claim:* "Powered by sophisticated ML pipeline with Prophet-based forecasting that accounts for seasonality, trends, and data patterns"
- *Data models:* `cloud/metadata-models/src/main/pegasus/com/linkedin/anomaly/MonitorAnomalyEvent.pdl`

*:white_check_mark: Volume Anomaly Detection*
- *Evidence:* `cloud/docs/managed-datahub/observe/volume-assertions.md` (full documentation)
- *Implementation:* `cloud/datahub-executor/src/datahub_executor/common/monitor/inference/volume_assertion_trainer.py` (VolumeAssertionTrainer class)
- *Claim:* Detects unexpected row count changes (growth/decline patterns)

*:white_check_mark: Freshness Anomaly Detection*
- *Evidence:* `cloud/docs/managed-datahub/observe/freshness-assertions.md` (full documentation)
- *Implementation:* `cloud/datahub-executor/src/datahub_executor/common/monitor/inference/freshness_assertion_trainer.py`
- *Claim:* Monitors table update patterns and detects SLA violations

*:white_check_mark: Column Metric Anomaly Detection*
- *Evidence:* `cloud/docs/managed-datahub/observe/column-assertions.md` (lines 1-80)
- *Implementation:* `cloud/datahub-executor/src/datahub_executor/common/monitor/inference/field_assertion_trainer.py`
- *Claim:* Detects anomalies in null rates, distinct counts, min/max values, and custom metrics

*:white_check_mark: Custom SQL Anomaly Detection*
- *Evidence:* `cloud/docs/managed-datahub/observe/smart-assertions.md` (line 26) + `custom-sql-assertions.md`
- *Implementation:* `cloud/datahub-executor/src/datahub_executor/common/monitor/inference/sql_assertion_trainer.py`
- *Claim:* ML-powered detection on custom SQL query results

*:white_check_mark: Supported Data Platforms*
- *Evidence:* `cloud/docs/managed-datahub/observe/assertions.md` (line 4)
- *Platforms:* Snowflake, BigQuery, Redshift, Databricks
- *Note:* Also supports DataHub-ingested metrics for other platforms (line 5-6)

*:white_check_mark: ML Pipeline Features*
- *Seasonality Detection:* Confirmed in `smart-assertions.md` (line 13) - "account for a large variety of trends including seasonality"
- *Sensitivity Tuning:* Lines 48-49 - adjustable sensitivity for tighter/looser anomaly boundaries
- *Training Lookback Window:* Lines 51-52 - configurable days of historical data for training
- *Anomaly Feedback Loop:* Lines 56-68 - "Mark as Normal" and "Train as new Normal" for continuous model improvement
- *Exclusion Windows:* Lines 45-46 - exclude maintenance windows, holidays, or anomalous periods from training

*:white_check_mark: Human-in-the-Loop Feedback*
- *Evidence:* `cloud/metadata-models/src/main/pegasus/com/linkedin/anomaly/MonitorAnomalyEvent.pdl` (lines 22-31)
- *States:* CONFIRMED (validated anomaly) / REJECTED (false positive)
- *Claim:* Timeseries log of anomalies with human review feedback

---

*TASK B — LANDING PAGE OUTLINE*

*Angle*
Platform engineers are drowning in data pipeline failures that slip through static thresholds. DataHub's AI-powered anomaly detection learns your data's natural rhythms—seasonality, growth patterns, and normal fluctuations—automatically catching volume spikes, freshness violations, and schema drift before they cascade into production incidents.

_(continued in next message...)_

---

*Architecture Diagram: DataHub's AI-Powered Anomaly Detection System*

Shows the end-to-end flow from data sources (Snowflake, BigQuery, Redshift, Databricks) through real-time monitoring, ML-based anomaly detection using Prophet forecasting, to automated alerting and incident management.

*Alt text:* Technical architecture diagram illustrating DataHub's anomaly detection system with data sources feeding into monitoring layer, ML pipeline with time-series forecasting, and automated response actions including Slack notifications and incident creation.

---

*UI Mockup: DataHub's Anomaly Detection Dashboard*

Shows the user experience of detecting and managing data anomalies - time-series visualization with ML-predicted baselines, real-time alert cards for volume/freshness/column anomalies, Smart Assertions control panel with AI tuning options, and quick action buttons for feedback and incident management.

*Alt text:* Data dashboard interface showing time-series chart with anomaly detection, alert cards for detected issues, AI-powered Smart Assertions panel with sensitivity controls, and action buttons for marking anomalies and creating incidents.

---

*[Part 2/3]*

*H1: Detecting Anomalies in Your Data Pipelines with AI-Powered Monitoring*

*H2: Stop Reacting to Data Incidents. Start Preventing Them.*

*The Problem with Traditional Rule-Based Monitoring*
- Static thresholds break as data patterns evolve (seasonal traffic, business growth, new features)
- Manual threshold tuning doesn't scale across hundreds of tables
- False positives erode team trust in alerts
- You discover issues when dashboards break or customers complain—not when the pipeline fails

*H2: How DataHub Detects Anomalies Automatically*

*H3: Smart Assertions — Machine Learning That Learns Your Data*

*What Makes Smart Assertions Different*
- Prophet-based forecasting trained on historical patterns (configurable 30-90+ day lookback)
- Automatically accounts for weekly/monthly seasonality and long-term trends
- Adapts to "new normal" when your business changes (via feedback loop)
- Tunable sensitivity for precision vs. recall tradeoffs

*H3: Four Types of Anomaly Detection*

*Volume Anomalies*
- Detect unexpected row count spikes or drops in Snowflake, BigQuery, Redshift, Databricks tables
- Catch data pipeline failures, duplicate data ingestion, or missing upstream sources
- Works for both absolute totals and change rates between runs

*Freshness (SLA) Anomalies*
- Monitor when tables should update and alert when they don't
- Support for Information Schema, Audit Logs, Last Modified Columns, and High Watermark tracking
- Ideal for time-sensitive reporting dashboards and operational analytics

*Column Metric Anomalies*
- Automatically detect null rate spikes, unexpected distinct count changes, or min/max violations
- Bulk create assertions across dozens of columns with one click
- Catch schema changes, data quality regressions, and PII exposure risks

*Custom SQL Anomalies*
- Run any SQL query and apply ML-based anomaly detection to the results
- Perfect for business-specific metrics (daily active users, revenue totals, conversion rates)
- Full flexibility with the power of automated anomaly detection

*H2: Built for Platform Engineering Teams*

*H3: Deploy Anywhere, Keep Data In Your Network*

*Remote Executor Deployment*
- Assertions run inside your VPC/network—credentials never leave your infrastructure
- Only assertion results flow back to DataHub Cloud
- Support for AWS, GCP, Azure, and on-premises deployments

*H3: Cost-Optimized Query Execution*

*Smart Query Strategy*
- Defaults to Information Schema for low-cost volume/freshness checks
- Automatically partitions queries for large tables to reduce warehouse compute
- Configurable to use audit logs when available (cheaper than querying tables directly)

*H3: Integrate with Your Existing Stack*

*Alerting &amp; Incident Management*
- Slack notifications (DMs or team channels) with customizable subscriptions
- AWS EventBridge integration for custom workflows
- Native incident creation and tracking in DataHub
- API-first design for integration with PagerDuty, Opsgenie, Jira, etc.

*H2: Tune, Don't Rebuild: Anomaly Feedback Loop*

*H3: Continuous Model Improvement*

*Mark as Normal / Mark as Anomaly*
- One-click feedback directly on anomaly results
- Model retrains automatically, reducing false positives over time
- "Train as new Normal" feature for permanent baseline shifts (e.g., after product launches)

_(continued in next message...)_

---

*[Part 3/3]*

*Exclusion Windows*
- Exclude known maintenance windows, holiday spikes, or past incidents from training data
- Prevents historical anomalies from polluting the model's notion of "normal"

*Sensitivity Control*
- Adjust per-assertion sensitivity: higher = tighter fit, lower = more tolerance
- Balance precision (catch real issues) vs. recall (minimize noise)

*H2: Get Started in Minutes*

*H3: Bulk Create Smart Assertions*

*Data Health Dashboard*
- Scan your warehouse and identify tables missing data quality checks
- Bulk create volume + freshness Smart Assertions across dozens of tables
- Filter by ownership, domain, or tag for targeted monitoring

*H3: API-First Design*

*Programmatic Assertion Management*
- Python SDK for creating, updating, and managing assertions as code
- Bulk operations for large-scale deployments
- Integrate with your CI/CD pipeline for data contract testing

---

*TASK C — FAQS*

*1. How does DataHub's anomaly detection handle seasonal data patterns?*
DataHub uses Prophet-based forecasting models that automatically detect and account for weekly, monthly, and yearly seasonality. You can configure the training lookback window (e.g., 90 days) to capture seasonal cycles. The model also supports tuning sensitivity and adding exclusion windows to ignore one-off events like holidays or maintenance periods.

*2. What data platforms are supported for anomaly detection?*
Smart Assertions work with Snowflake, BigQuery, Redshift, and Databricks for native query-based monitoring. DataHub can also detect anomalies on any platform by analyzing ingested metadata (DatasetProfile, SchemaFieldProfile) from sources like dbt, Great Expectations, or custom ingestion pipelines.

*3. How much does it cost to run anomaly detection on large tables?*
DataHub optimizes for cost by defaulting to Information Schema and Audit Logs (cheapest options) for volume and freshness checks. For column metrics and custom SQL, queries are automatically partitioned and optimized. With the Remote Executor deployment, you control exactly where and how queries run, giving you full cost visibility and control.

*4. Can I use anomaly detection without sharing my data externally?*
Yes. The Remote Executor runs entirely within your VPC/network—your credentials and raw data never leave your infrastructure. Only assertion results (pass/fail status, metrics) are sent back to DataHub Cloud. This architecture is ideal for regulated industries and security-conscious teams.

*5. How do I reduce false positives from anomaly detection?*
DataHub provides multiple tuning mechanisms: (1) Adjust sensitivity per assertion, (2) Add exclusion windows to remove bad training data, (3) Use "Mark as Normal" feedback to retrain the model, and (4) Configure training lookback windows to focus on recent patterns. The model continuously improves as you provide feedback.

*6. Can I integrate anomaly alerts with my existing incident management tools?*
Yes. DataHub supports Slack notifications, AWS EventBridge for custom workflows, and a REST API for triggering external systems. You can route alerts to PagerDuty, Opsgenie, Jira, or any tool that accepts webhooks or API calls. DataHub also has native incident management for tracking and resolving data quality issues.

---

BART_DONE

• • •
:moneybag: `$0.2241` (API `$0.1232`, Tools `$0.1000`)
:bar_chart: Session: `$0.2241` (1 message)