
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TESTS = [
    ("Routing Engine", "test_routing.py"),
    ("Policy Engine", "test_policy_engine.py"),
    ("SLA Engine", "test_sla_engine.py"),
    ("SLA Monitor", "test_sla_monitor.py"),
    ("Baseline Dataset", "validate_dataset.py"),
    ("Negative Cases", "validate_negative_cases.py"),
    ("Lifecycle Consistency", "validate_lifecycle.py"),
    ("Reproducibility", "test_reproducibility.py"),
]


def run_test(name, filename):
    script = ROOT / filename

    if not script.exists():
        return {
            "name": name,
            "status": "MISSING",
            "seconds": 0,
            "details": f"File not found: {filename}",
        }

    print(f"\nRunning: {name}")
    print(f"File: {filename}")

    start = time.perf_counter()

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=240,
        )

        elapsed = time.perf_counter() - start

        output = (
            result.stdout.strip()
            + "\n"
            + result.stderr.strip()
        ).strip()

        if output:
            print(output[-3000:])

        return {
            "name": name,
            "status": (
                "PASS"
                if result.returncode == 0
                else "FAIL"
            ),
            "seconds": elapsed,
            "details": output,
        }

    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "status": "TIMEOUT",
            "seconds": time.perf_counter() - start,
            "details": "Test exceeded 240 seconds.",
        }

    except Exception as exc:
        return {
            "name": name,
            "status": "ERROR",
            "seconds": time.perf_counter() - start,
            "details": str(exc),
        }


def main():
    print("=" * 55)
    print("CampusResolve — Final Automated Test Suite")
    print("=" * 55)

    results = []

    for name, filename in TESTS:
        result = run_test(name, filename)
        results.append(result)

        print(
            f"\n[{result['status']}] "
            f"{name} "
            f"({result['seconds']:.2f}s)"
        )

    print("\n" + "=" * 55)
    print("FINAL TEST SUMMARY")
    print("=" * 55)

    for result in results:
        print(
            f"{result['status']:<8} "
            f"{result['name']}"
        )

    passed = sum(
        result["status"] == "PASS"
        for result in results
    )

    total = len(results)

    print("-" * 55)
    print(f"Test groups passed: {passed}/{total}")
    print(f"Test groups failed: {total - passed}")

    if passed == total:
        print("RESULT: ALL TEST GROUPS PASSED")
        return 0

    print("RESULT: TEST SUITE NEEDS REVIEW")
    return 1


if __name__ == "__main__":
    sys.exit(main())
