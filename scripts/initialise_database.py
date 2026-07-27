from macropulse.data.repository import MacroRepository


def main() -> None:
    repository = MacroRepository()
    repository.initialise()
    print(f"Database initialised: {repository.database_path}")


if __name__ == "__main__":
    main()
