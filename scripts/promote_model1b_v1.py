from macropulse.inflation.promotion import promote_model1b


def main() -> None:
    result = promote_model1b()
    print("Model 1B production promotion complete")
    print(f"Model: {result['model_id']}")
    print(f"Production version: {result['production_version']}")
    print(f"Promoted from: {result['source_version']}")
    print(f"Candidate validation ID: {result['candidate_validation_id']}")
    print(f"Operational validation ID: {result['operational_validation_id']}")
    print(f"Freeze assessment ID: {result['freeze_assessment_id']}")
    print(f"Governed live run ID: {result['live_run_id']}")
    print(f"Approval ID: {result['approval_id']}")
    print(f"Report: {result['report_path']}")
    print(f"Configuration hash: {result['config_hash'][:12]}...")
    print(f"Code hash: {result['code_hash'][:12]}...")


if __name__ == "__main__":
    main()
