from macropulse.governance.freeze import generate_freeze_assessment


def main() -> None:
    result = generate_freeze_assessment()
    print("Model 1A freeze assessment complete")
    print(f"Readiness: {result['readiness']}")
    print(f"Validation ID: {result['validation_id']}")
    print(f"Validation status: {result['validation_status']}")
    print(f"Failures: {result['failures']}")
    print(f"Warnings: {result['warnings']}")
    print(f"Governed live forecast: {result['has_live_forecast']}")
    print(f"Report: {result['report_path']}")


if __name__ == "__main__":
    main()
