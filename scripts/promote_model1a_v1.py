from macropulse.governance.promotion import promote_model1a


def main() -> None:
    result = promote_model1a()
    print("Model 1A production promotion complete")
    print(f"Model: {result['model_id']}")
    print(f"Production version: {result['production_version']}")
    print(f"Promoted from: {result['source_version']}")
    print(
        f"Validation: {result['validation_id']} "
        f"({result['validation_passed']}/{result['validation_total']} passed)"
    )
    print(f"Approval ID: {result['approval_id']}")
    print(f"Validated stage backtest: {result['stage_backtest_id']}")
    print(f"Report: {result['report_path']}")
    print(f"Configuration hash: {result['config_hash'][:12]}...")
    print(f"Code hash: {result['code_hash'][:12]}...")


if __name__ == "__main__":
    main()
