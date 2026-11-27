# What the consumer does if the database goes down while it's running.
# Instead of crashing, it holds on to the batch, emails the IT team once,
# waits, reconnects, and then saves that same batch.
import time
import traceback

from pulseguard.notifications.back_online import report_back_online
from pulseguard.notifications.system_alerts import send_failure_email
from pulseguard.storage.database import CONNECTION_PROBLEMS, reconnect, save_batch

RETRY_EVERY_SECONDS = 10   # wait between tries


# Wait without taking new messages, but keep polling so Kafka knows we're alive.
# If a consumer doesn't poll for 5 minutes, Kafka assumes it died and gives
# its partitions to another consumer.
def wait_and_keep_kafka_happy(consumer, seconds):
    partitions = consumer.assignment() if hasattr(consumer, "assignment") else set()
    if partitions:
        consumer.pause(*partitions)
    end = time.time() + seconds
    while True:
        batch = consumer.poll(timeout_ms=1000)
        # just in case poll() still returned messages: rewind so they get read again later
        for partition, messages in batch.items():
            if messages and hasattr(consumer, "seek"):
                consumer.seek(partition, messages[0].offset)
        if time.time() >= end:
            break


# Save one batch. If the database is down, wait and try the same batch again.
# Nothing is committed to Kafka while we wait, so no reading gets lost.
# Only connection problems are retried; anything else (a bug) is raised.
# Returns (number of readings saved, the connection that worked).
def save_until_it_works(conn, good, rejected, events, consumer, wait_seconds=None):
    wait_seconds = RETRY_EVERY_SECONDS if wait_seconds is None else wait_seconds
    problem_reported = False
    while True:
        if conn is not None:
            try:
                saved = save_batch(conn, good, rejected, events)       # try to save
                if problem_reported:                                    # it was down before, so it's back now
                    print(f"[{time.strftime('%H:%M:%S')}] Database is back. Batch saved, carrying on.")
                    if hasattr(consumer, "resume") and consumer.assignment():
                        consumer.resume(*consumer.assignment())         # take new messages again
                    report_back_online("consumer")                      # email: BACK ONLINE
                return saved, conn
            except CONNECTION_PROBLEMS as error:                        # can't reach the database
                if not problem_reported:
                    send_failure_email("consumer", error, traceback.format_exc(),
                                       retrying_every=wait_seconds)     # only one email per outage
                    problem_reported = True
        print(f"[{time.strftime('%H:%M:%S')}] Database is down. Holding {len(good) + len(rejected)} "
              f"messages and trying again in {wait_seconds} s...")
        wait_and_keep_kafka_happy(consumer, wait_seconds)               # wait (and keep polling Kafka)
        conn = reconnect(conn)                                          # the old connection is dead, get a new one
