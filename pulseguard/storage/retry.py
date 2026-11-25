# Database down while running? Don't stop.
# Keep the batch, email the IT team once, wait, get a new connection,
# and save the SAME batch when the database is back.
import time
import traceback

from pulseguard.notifications.back_online import report_back_online
from pulseguard.notifications.system_alerts import send_failure_email
from pulseguard.storage.database import CONNECTION_PROBLEMS, reconnect, save_batch

RETRY_EVERY_SECONDS = 10   # wait between tries


def wait_and_keep_kafka_happy(consumer, seconds):
    """Wait without taking new messages, but tell Kafka we are still alive.
    (Silent for 5 minutes = Kafka thinks we died and gives our work away.)
    Like a driver at a locked door answering the radio: "Still here, still holding the boxes." """
    partitions = consumer.assignment() if hasattr(consumer, "assignment") else set()
    if partitions:
        consumer.pause(*partitions)
    end = time.time() + seconds
    while True:
        batch = consumer.poll(timeout_ms=1000)
        # Safety net: got messages anyway? Put them back so they aren't skipped.
        for partition, messages in batch.items():
            if messages and hasattr(consumer, "seek"):
                consumer.seek(partition, messages[0].offset)
        if time.time() >= end:
            break


def save_until_it_works(conn, good, rejected, events, consumer, wait_seconds=None):
    """Save one batch. Database down? Wait and try the SAME batch again.

    Delivery-driver story:
      - Batch = boxes in the truck. Database = the house. Kafka = the warehouse.
      - Door locked: keep the boxes, don't fetch new ones, don't tick the clipboard (commit).
      - Wait, then try again with a NEW key (connection).
      - Door opens: deliver the SAME boxes. Then the caller ticks the clipboard.

    Returns (readings saved, the connection that worked). Bugs are not retried."""
    wait_seconds = RETRY_EVERY_SECONDS if wait_seconds is None else wait_seconds
    problem_reported = False
    while True:
        if conn is not None:
            try:
                saved = save_batch(conn, good, rejected, events)       # knock on the door
                if problem_reported:                                    # it worked again!
                    print(f"[{time.strftime('%H:%M:%S')}] Database is back. Batch saved, carrying on.")
                    if hasattr(consumer, "resume") and consumer.assignment():
                        consumer.resume(*consumer.assignment())         # take new messages again
                    report_back_online("consumer")                      # email: BACK ONLINE
                return saved, conn
            except CONNECTION_PROBLEMS as error:                        # the door is locked
                if not problem_reported:
                    send_failure_email("consumer", error, traceback.format_exc(),
                                       retrying_every=wait_seconds)     # tell the IT team, once
                    problem_reported = True
        print(f"[{time.strftime('%H:%M:%S')}] Database is down. Holding {len(good) + len(rejected)} "
              f"messages and trying again in {wait_seconds} s...")
        wait_and_keep_kafka_happy(consumer, wait_seconds)               # wait in the truck
        conn = reconnect(conn)                                          # new key
