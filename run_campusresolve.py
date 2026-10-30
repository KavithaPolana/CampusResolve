
import threading
import logging

from app import app
from database import create_database
from sla_monitor import check_sla_breaches
from human_escalation import process_pending_escalations


# Monitor tickets every 60 seconds.
CHECK_INTERVAL_SECONDS = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("CampusResolve")

# Allows the background worker to stop cleanly.
stop_event = threading.Event()


def run_monitoring_cycle():
    """
    Perform one complete monitoring cycle.

    Step 1: Detect missed SLA deadlines.
    Step 2: Escalate overdue tickets.
    Step 3: Assign all escalated tickets
            to their authorized human support teams.
    """

    sla_result = check_sla_breaches()

    human_assignment_count = (
        process_pending_escalations()
    )

    logger.info(
        "SLA Monitoring | "
        "Tickets checked: %s | "
        "New response breaches: %s | "
        "New resolution breaches: %s | "
        "New SLA escalations: %s",
        sla_result["checked"],
        sla_result["response_breaches"],
        sla_result["resolution_breaches"],
        sla_result["tickets_escalated"]
    )

    logger.info(
        "Human Escalation | "
        "Escalated tickets checked: %s",
        human_assignment_count
    )

    return {
        "sla": sla_result,
        "human_assignments_checked": (
            human_assignment_count
        )
    }


def monitoring_worker():
    """
    Run monitoring automatically while
    CampusResolve is active.
    """

    logger.info(
        "Automatic SLA and human escalation "
        "monitoring started."
    )

    while not stop_event.is_set():

        try:
            run_monitoring_cycle()

        except Exception:
            logger.exception(
                "Automatic monitoring cycle failed."
            )

        # Wait up to 60 seconds before checking again.
        # This also allows a clean shutdown.
        stop_event.wait(
            CHECK_INTERVAL_SECONDS
        )


def start_monitor():
    """
    Start one background monitoring thread.
    """

    thread = threading.Thread(
        target=monitoring_worker,
        name="CampusResolve-Automatic-Monitor",
        daemon=True
    )

    thread.start()

    return thread


def main():
    print()
    print("=" * 50)
    print("          CampusResolve Support System")
    print("=" * 50)
    print()

    # Upgrade existing database safely.
    create_database()

    # Start automatic SLA monitoring
    # and human escalation assignment.
    monitor_thread = start_monitor()

    print()
    print("Application: http://127.0.0.1:5001")
    print("Automatic SLA monitoring: ENABLED")
    print("Automatic human escalation: ENABLED")
    print("Monitoring interval: 60 seconds")
    print("Business hours: Mon-Fri, 09:00-17:00 IST")
    print()

    try:
        app.run(
            host="127.0.0.1",
            port=5001,
            debug=True,
            use_reloader=False
        )

    finally:
        stop_event.set()
        monitor_thread.join(timeout=5)

        logger.info(
            "CampusResolve monitoring stopped."
        )


if __name__ == "__main__":
    main()
