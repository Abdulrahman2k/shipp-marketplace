# Databricks notebook source
# MAGIC %md
# MAGIC # SHIPP Gate S0 — Velocity streaming spike (read-only probe)
# MAGIC
# MAGIC **Question this answers:** inside ONE warm serverless session, how fast does a new
# MAGIC Lakebase Request become visible to a checkpointed streaming read of Bronze?
# MAGIC
# MAGIC Serverless does not support `processingTime` triggers, so we loop short
# MAGIC `availableNow` runs inside one session. No Silver / Gold / Lakebase writes.
# MAGIC Results go to `shipp_gold.velocity_spike_log` (probe-only table, drop after the decision).
# MAGIC
# MAGIC **Run:** start this notebook on Serverless → while it loops, create 3 Requests
# MAGIC (app, or the Lakebase INSERT in the gate instructions) about 1 minute apart → wait for it to finish.

# COMMAND ----------

import time
from datetime import datetime, timezone

from pyspark.sql import functions as F

SOURCE = "bootcamp_students.shipp_bronze.lb_requests_history"
PROBE_LOG = "bootcamp_students.shipp_gold.velocity_spike_log"
VOLUME = "bootcamp_students.shipp_bronze.checkpoints"
CHECKPOINT = "/Volumes/bootcamp_students/shipp_bronze/checkpoints/velocity_spike_v1"

RUN_MINUTES = 6
SLEEP_BETWEEN_CYCLES_S = 3

spark.sql(f"CREATE VOLUME IF NOT EXISTS {VOLUME}")
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {PROBE_LOG} (
  batch_id BIGINT,
  request_id STRING,
  change_type STRING,
  operational_change_at TIMESTAMP_NTZ,
  seen_by_stream_at TIMESTAMP_NTZ,
  stream_lag_seconds DOUBLE
) USING DELTA
""")
print("PASS — volume and probe table ready.")

# COMMAND ----------

def probe(batch_df, batch_id):
    """Record when each new Request event becomes visible to the stream.

    Runs server-side on serverless (Spark Connect): print() is not visible,
    so evidence is written to a Delta table instead.
    """
    seen = datetime.now(timezone.utc).replace(tzinfo=None)
    (
        batch_df
        .filter(F.col("_pg_change_type").isin("insert", "update_postimage"))
        .select(
            F.lit(batch_id).cast("bigint").alias("batch_id"),
            F.col("request_id"),
            F.col("_pg_change_type").alias("change_type"),
            F.col("_timestamp").cast("timestamp_ntz").alias("operational_change_at"),
            F.lit(seen).cast("timestamp_ntz").alias("seen_by_stream_at"),
        )
        .withColumn(
            "stream_lag_seconds",
            F.col("seen_by_stream_at").cast("double")
            - F.col("operational_change_at").cast("double"),
        )
        .write.mode("append").saveAsTable(PROBE_LOG)
    )

# COMMAND ----------

deadline = time.time() + RUN_MINUTES * 60
cycle_seconds = []

while time.time() < deadline:
    t0 = time.time()
    query = (
        spark.readStream
        .option("startingVersion", "latest")   # only changes after the first start
        .table(SOURCE)
        .writeStream
        .foreachBatch(probe)
        .option("checkpointLocation", CHECKPOINT)
        .trigger(availableNow=True)
        .start()
    )
    query.awaitTermination()
    cycle_seconds.append(round(time.time() - t0, 1))
    time.sleep(SLEEP_BETWEEN_CYCLES_S)

cycle_seconds.sort()
print(f"cycles run       : {len(cycle_seconds)}")
print(f"median cycle (s) : {cycle_seconds[len(cycle_seconds) // 2]}")
print(f"slowest cycle (s): {cycle_seconds[-1]}")

# COMMAND ----------

display(spark.sql(f"""
SELECT request_id, change_type, operational_change_at, seen_by_stream_at,
       round(stream_lag_seconds, 1) AS stream_lag_seconds
FROM {PROBE_LOG}
ORDER BY operational_change_at DESC
LIMIT 20
"""))
