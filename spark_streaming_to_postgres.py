#!/usr/bin/env python3

import argparse
import json
import os
import time
from datetime import datetime, timezone

import psycopg2
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQueryListener
from pyspark.sql.types import StringType, StructField, StructType

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE

# Where to find the file that lets Spark talk to PostgreSQL.
JDBC_CANDIDATES = [os.path.join(ROOT, "jars", "postgresql-42.7.2.jar"),
                   "/usr/share/java/postgresql.jar"]
DEFAULT_JDBC_JAR = next((j for j in JDBC_CANDIDATES if os.path.exists(j)), JDBC_CANDIDATES[0])

# The 11 columns in every CSV file, all read as text first so one bad value cannot crash the program.
RAW_SCHEMA = StructType([StructField(c, StringType(), True) for c in [
    "event_id", "user_id", "session_id", "event_type", "product_id", "product_name",
    "category", "price", "quantity", "device", "event_timestamp",
]])

# The only three actions a shopper can do.
VALID_EVENT_TYPES = ["view", "add_to_cart", "purchase"]
# The pattern a correct event ID must follow.
UUID_REGEX = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

# The columns saved into the user_events table.
FINAL_COLUMNS = [
    "event_id", "user_id", "session_id", "event_type", "product_id", "product_name",
    "category", "price", "quantity", "total_amount", "device", "event_timestamp",
    "source_file", "batch_id", "processed_at",
]

# Settings

# Gets the database name, user and password from postgres_connection_details.txt.
def load_pg_config(path: str) -> dict:
    cfg = {"PG_HOST": "localhost", "PG_PORT": "5432", "PG_DATABASE": "ecommerce_stream",
           "PG_USER": "spark_user", "PG_PASSWORD": "spark_pass"}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    for k in cfg:
        cfg[k] = os.getenv(k, cfg[k])
    return cfg


# Reads the settings you can type after the command, like how often to check for files.
def parse_args():
    p = argparse.ArgumentParser(description="Stream e-commerce CSV events into PostgreSQL.")
    p.add_argument("--input-dir", default=os.getenv("INPUT_DIR", os.path.join(ROOT, "data", "input")))
    p.add_argument("--checkpoint-dir", default=os.getenv("CHECKPOINT_DIR", os.path.join(ROOT, "data", "checkpoint")))
    p.add_argument("--log-dir", default=os.path.join(ROOT, "logs"))
    p.add_argument("--conn-file", default=os.path.join(ROOT, "postgres_connection_details.txt"))
    p.add_argument("--jdbc-jar", default=os.getenv("JDBC_JAR", DEFAULT_JDBC_JAR),
                   help="Path to the PostgreSQL JDBC driver jar")
    p.add_argument("--trigger-seconds", type=int, default=5, help="Micro-batch interval")
    p.add_argument("--max-files-per-trigger", type=int, default=10)
    p.add_argument("--run-seconds", type=int, default=0,
                   help="Stop after N seconds (0 = run until Ctrl+C)")
    p.add_argument("--available-now", action="store_true",
                   help="Process everything currently in the folder, then stop")
    return p.parse_args()

# Cleaning the data

# Cleans every row (removes spaces, fixes capital letters, turns text into numbers and dates)
# and marks bad rows with the reason, for example "negative price".
def clean_events(raw: DataFrame) -> DataFrame:
    trimmed = raw.select(
        *[F.trim(F.col(c)).alias(c) for c in RAW_SCHEMA.fieldNames()],
        F.col("_metadata.file_name").alias("source_file"),
    )

    df = (trimmed
          .withColumn("event_type", F.lower(F.col("event_type")))
          .withColumn("device", F.lower(F.col("device")))
          .withColumn("price_num", F.col("price").cast("decimal(10,2)"))
          .withColumn("quantity_num", F.col("quantity").cast("int"))
          .withColumn("event_ts", F.coalesce(
              F.to_timestamp("event_timestamp", "yyyy-MM-dd HH:mm:ss.SSS"),
              F.to_timestamp("event_timestamp")))
          )

    blank = lambda c: F.col(c).isNull() | (F.col(c) == "")
    reason = (F.when(blank("event_id") | ~F.col("event_id").rlike(UUID_REGEX), "invalid event_id")
               .when(blank("user_id"), "missing user_id")
               .when(blank("product_id"), "missing product_id")
               .when(~F.col("event_type").isin(VALID_EVENT_TYPES) | F.col("event_type").isNull(),
                     "invalid event_type")
               .when(blank("product_name") | blank("category") | F.col("event_timestamp").isNull(),
                     "incomplete row (missing columns)")
               .when(F.col("price_num").isNull(), "price not numeric")
               .when(F.col("price_num") < 0, "negative price")
               .when(F.col("quantity_num").isNull(), "quantity not integer")
               .when(F.col("quantity_num") <= 0, "non-positive quantity")
               .when(F.col("event_ts").isNull(), "unparseable event_timestamp"))

    return df.withColumn("reject_reason", reason)


# Gets the good rows ready to save: removes copies and adds total_amount = price x quantity.
def to_final(valid: DataFrame, batch_id: int) -> DataFrame:
    return (valid
            .dropDuplicates(["event_id"])
            .withColumn("price", F.col("price_num"))
            .withColumn("quantity", F.col("quantity_num"))
            .withColumn("total_amount", (F.col("price_num") * F.col("quantity_num")).cast("decimal(12,2)"))
            .withColumn("event_timestamp", F.col("event_ts"))
            .withColumn("category", F.initcap(F.col("category")))
            .withColumn("batch_id", F.lit(batch_id).cast("long"))
            .withColumn("processed_at", F.current_timestamp())
            .select(*FINAL_COLUMNS))


# Saving to the database

# Saves each group of new rows into the database: good rows and bad rows go to separate tables.
class PostgresBatchWriter:
    # Keeps the database details so Spark knows where to save.
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.jdbc_url = (f"jdbc:postgresql://{cfg['PG_HOST']}:{cfg['PG_PORT']}/{cfg['PG_DATABASE']}"
                         "?stringtype=unspecified&reWriteBatchedInserts=true")
        self.jdbc_props = {"user": cfg["PG_USER"], "password": cfg["PG_PASSWORD"],
                           "driver": "org.postgresql.Driver", "batchsize": "5000"}

    # Connects to the database.
    def _pg(self):
        return psycopg2.connect(host=self.cfg["PG_HOST"], port=self.cfg["PG_PORT"],
                                dbname=self.cfg["PG_DATABASE"], user=self.cfg["PG_USER"],
                                password=self.cfg["PG_PASSWORD"])

    # Handles one group of rows: separates good from bad, saves them without copies,
    # and records how many rows there were and how long it took.
    def __call__(self, batch_df: DataFrame, batch_id: int) -> None:
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        batch_df.persist()
        try:
            input_rows = batch_df.count()
            if input_rows == 0:
                return
            files = batch_df.select("source_file").distinct().count()
            valid = to_final(batch_df.filter(F.col("reject_reason").isNull()), batch_id).persist()
            rejected = (batch_df.filter(F.col("reject_reason").isNotNull())
                        .select(F.col("event_id").alias("raw_event_id"),
                                F.col("user_id").alias("raw_user_id"),
                                F.col("event_type").alias("raw_event_type"),
                                F.col("price").alias("raw_price"),
                                F.col("quantity").alias("raw_quantity"),
                                F.col("event_timestamp").alias("raw_timestamp"),
                                "reject_reason", "source_file",
                                F.lit(batch_id).cast("long").alias("batch_id")))
            valid_rows = valid.count()
            rejected_rows = input_rows - batch_df.filter(F.col("reject_reason").isNull()).count()
            in_batch_dups = input_rows - rejected_rows - valid_rows

            t0 = time.perf_counter()
            with self._pg() as conn, conn.cursor() as cur:
                cur.execute("TRUNCATE user_events_staging")
            if valid_rows:
                valid.write.jdbc(self.jdbc_url, "user_events_staging", mode="append",
                                 properties=self.jdbc_props)
            if rejected_rows:
                rejected.write.jdbc(self.jdbc_url, "rejected_events", mode="append",
                                    properties=self.jdbc_props)
            with self._pg() as conn, conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO user_events ({", ".join(FINAL_COLUMNS)})
                    SELECT {", ".join(FINAL_COLUMNS)} FROM user_events_staging
                    ON CONFLICT (event_id) DO NOTHING""")
                inserted = cur.rowcount
                cur.execute("TRUNCATE user_events_staging")
                write_ms = int((time.perf_counter() - t0) * 1000)
                finished = datetime.now(timezone.utc).replace(tzinfo=None)
                cur.execute("""
                    INSERT INTO pipeline_batch_metrics VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (batch_id) DO UPDATE SET
                      input_rows=EXCLUDED.input_rows, valid_rows=EXCLUDED.valid_rows,
                      rejected_rows=EXCLUDED.rejected_rows, duplicate_rows=EXCLUDED.duplicate_rows,
                      inserted_rows=EXCLUDED.inserted_rows,
                      files_in_batch=EXCLUDED.files_in_batch, write_duration_ms=EXCLUDED.write_duration_ms,
                      batch_started_at=EXCLUDED.batch_started_at, batch_finished_at=EXCLUDED.batch_finished_at""",
                    (batch_id, input_rows, valid_rows, rejected_rows,
                     in_batch_dups + (valid_rows - inserted), inserted, files,
                     write_ms, started, finished))
            print(f"[batch {batch_id}] files={files} input={input_rows} valid={valid_rows} "
                  f"rejected={rejected_rows} inserted={inserted} "
                  f"duplicates_skipped={in_batch_dups + valid_rows - inserted} pg_write={write_ms}ms", flush=True)
            valid.unpersist()
        finally:
            batch_df.unpersist()

# Progress notes

# Writes down how fast Spark worked on each group of rows, in logs/streaming_progress.jsonl.
class ProgressLogger(StreamingQueryListener):
    # Remembers which file to write the notes in.
    def __init__(self, path: str):
        self.path = path

    # Shows a message when the program starts.
    def onQueryStarted(self, event):
        print(f"[stream] query started id={event.id}", flush=True)

    # Saves the speed of each group of rows that was processed.
    def onQueryProgress(self, event):
        p = event.progress
        if p.numInputRows == 0:
            return
        rec = {"batchId": p.batchId, "timestamp": p.timestamp, "numInputRows": p.numInputRows,
               "inputRowsPerSecond": p.inputRowsPerSecond,
               "processedRowsPerSecond": p.processedRowsPerSecond,
               "durationMs": dict(p.durationMs)}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    # Does nothing when there are no new files.
    def onQueryIdle(self, event):
        pass

    # Shows a message when the program stops.
    def onQueryTerminated(self, event):
        print(f"[stream] query terminated id={event.id} exception={event.exception}", flush=True)



# Main program: starts Spark, watches the data/input folder for new CSV files,
# cleans them and saves them to the database until you press Ctrl+C.
def main():
    args = parse_args()
    cfg = load_pg_config(args.conn_file)
    os.makedirs(args.input_dir, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)

    builder = (SparkSession.builder
               .appName("EcommerceEventsToPostgres")
               .config("spark.sql.session.timeZone", "UTC")
               # JDBC writes TIMESTAMP values using the JVM default zone; pin it to UTC
               # so 08:00 UTC in the CSV is stored as 08:00, whatever the host's timezone.
               .config("spark.driver.extraJavaOptions", "-Duser.timezone=UTC")
               .config("spark.executor.extraJavaOptions", "-Duser.timezone=UTC")
               .config("spark.sql.shuffle.partitions", "4")
               .config("spark.sql.streaming.schemaInference", "false")
               .config("spark.ui.showConsoleProgress", "false"))
    if os.path.exists(args.jdbc_jar):
        builder = builder.config("spark.jars", args.jdbc_jar)
    else:
        print(f"[stream] WARNING: JDBC driver not found at {args.jdbc_jar} - pass --jdbc-jar", flush=True)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    spark.streams.addListener(ProgressLogger(os.path.join(args.log_dir, "streaming_progress.jsonl")))

    raw = (spark.readStream
           .format("csv")
           .option("header", "true")
           .option("mode", "PERMISSIVE")
           .option("maxFilesPerTrigger", args.max_files_per_trigger)
           .schema(RAW_SCHEMA)
           .load(args.input_dir))

    cleaned = clean_events(raw)

    writer = (cleaned.writeStream
              .foreachBatch(PostgresBatchWriter(cfg))
              .option("checkpointLocation", args.checkpoint_dir)
              .queryName("ecommerce_events_to_postgres"))
    writer = (writer.trigger(availableNow=True) if args.available_now
              else writer.trigger(processingTime=f"{args.trigger_seconds} seconds"))

    print(f"[stream] watching {args.input_dir} -> postgres://{cfg['PG_HOST']}:{cfg['PG_PORT']}/"
          f"{cfg['PG_DATABASE']}", flush=True)
    query = writer.start()
    try:
        if args.run_seconds > 0:
            query.awaitTermination(args.run_seconds)
            query.stop()
        else:
            query.awaitTermination()
    except KeyboardInterrupt:
        print("[stream] stopping...", flush=True)
        query.stop()
    spark.stop()


if __name__ == "__main__":
    main()
