# Sends one heart rate reading per patient to Kafka, every second.
#
#   python -m pulseguard.services.producer                       100 patients, until Ctrl+C
#   python -m pulseguard.services.producer --patients 20 --seconds 60
#   python -m pulseguard.services.producer --emergency PT-0007   PT-0007's heart races -> alert email
#
# New patients are added to the database the first time.
import argparse
import json
import time
import traceback

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from pulseguard.config import KAFKA_SERVER, TOPIC
from pulseguard.storage.database import connect
from pulseguard.simulation.generator import make_reading, start_emergencies, start_watching
from pulseguard.notifications.back_online import report_back_online
from pulseguard.notifications.system_alerts import send_failure_email
from pulseguard.simulation.patients import load_or_create_patients


# Connect to Kafka (keeps trying for a minute while it starts).
def connect_to_kafka():
    for attempt in range(20):
        try:
            return KafkaProducer(
                bootstrap_servers=KAFKA_SERVER,
                key_serializer=lambda key: key.encode("utf-8"),
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                acks="all",   # wait until Kafka has safely stored it
            )
        except NoBrokersAvailable:
            print("Kafka not ready yet, trying again...")
            time.sleep(3)
    raise SystemExit(f"Could not connect to Kafka at {KAFKA_SERVER}. Is 'docker compose up -d' running?")


# Start here: read the options, run the producer, and email the IT team if it crashes.
def main():
    parser = argparse.ArgumentParser(description="Send fake heart rate readings to Kafka")
    parser.add_argument("--patients", "--customers", type=int, default=100, help="how many patients to simulate")
    parser.add_argument("--seconds", type=int, default=0, help="stop after this many seconds (0 = run forever)")
    parser.add_argument("--bad-chance", type=float, default=0.02, help="share of sensor glitches, e.g. 0.02 = 2%%")
    parser.add_argument("--event-chance", type=float, default=0.00001,   # about 4 events an hour for 100 patients
                        help="chance per patient per second that a medical event starts")
    parser.add_argument("--emergency", action="append", default=[], metavar="PATIENT_ID",
                        help="start a medical event for this patient right away (can repeat)")
    parser.add_argument("--emergency-kind", choices=["high", "low"], default="high")
    args = parser.parse_args()

    # Error? Email the IT team, then stop. (Ctrl+C = normal stop, no email.)
    try:
        run_producer(args)
    except (Exception, SystemExit) as error:
        send_failure_email("producer", error, traceback.format_exc())
        raise


# Load the patients, then send one reading each every second until Ctrl+C
# (or until --seconds is up). Prints progress every 5 seconds.
def run_producer(args):
    conn = connect()
    patients = [start_watching(p) for p in load_or_create_patients(conn, args.patients)]
    conn.close()

    start_emergencies(patients, args.emergency, args.emergency_kind)

    producer = connect_to_kafka()
    print(f"Sending readings for {len(patients)} patients to topic '{TOPIC}'. Press Ctrl+C to stop.")
    report_back_online("producer")   # was down before? email "back online"

    sent = 0
    start = time.time()
    try:
        while True:
            # One round = one reading per patient (and we time it)
            round_start = time.time()
            for patient in patients:
                reading = make_reading(patient, args.bad_chance, args.event_chance)
                # key = patient id -> Kafka keeps each patient's readings in order
                producer.send(TOPIC, key=patient["customer_id"], value=reading)
                sent += 1
            round_ms = (time.time() - round_start) * 1000

            seconds_running = int(time.time() - start)
            if seconds_running % 5 == 0:
                print(f"[{time.strftime('%H:%M:%S')}] sent {sent} readings in {seconds_running} s "
                      f"| this round took {round_ms:.1f} ms for {len(patients)} patients "
                      f"| latest: {reading}")
            if args.seconds and seconds_running >= args.seconds:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush()   # make sure everything was delivered
        producer.close()
        total_seconds = time.time() - start
        rate = sent / total_seconds if total_seconds else 0
        print(f"Producer stopped. Sent {sent} readings in {total_seconds:.1f} seconds "
              f"({rate:.1f} readings per second).")


if __name__ == "__main__":
    main()
