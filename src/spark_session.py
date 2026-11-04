import os
import sys
from pyspark.sql import SparkSession


# Create (or reuse) one local Spark session for the whole project.
def get_spark(app_name="TMDB Movie Analysis"):
    # Use the same Python as the venv for Spark's workers (avoids a common Windows error)
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    # Keep all Spark connections on this computer (avoids Windows network/firewall issues)
    os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"

    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[2]")                           # 2 cores: plenty for small data, fewer Python workers on Windows
        .config("spark.default.parallelism", "2")
        .config("spark.sql.shuffle.partitions", "4")  # small dataset, so few partitions is faster
        .config("spark.driver.memory", "2g")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.python.worker.reuse", "true")  # reuse Python workers instead of starting new ones
        .getOrCreate()
    )

    # Only show real errors, not the many INFO/WARN lines
    spark.sparkContext.setLogLevel("ERROR")
    return spark