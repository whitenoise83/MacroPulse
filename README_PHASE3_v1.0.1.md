# MacroPulse Internal Phase III Evaluation Release v1.0.1

v1.0.1 is a release-engineering compatibility patch only.

The immutable v1.0.0 tag remains at:

```text
phase3-evaluation-v1.0.0
20c3682a96061d9e740aaf001bf2f72a98377928
```

The v1.0.0 branch closure CI (Phase III Evaluation Guard run #2, run ID
31428781570) passed completely. The subsequent tag-triggered run #3 failed
because GitHub Actions checked out the tag in detached HEAD state while one
bootstrap test required `git branch --show-current` to equal the development
branch.

v1.0.1 changes only that checkout contract: the bootstrap test accepts either
the governed development branch or detached HEAD at an exact semantic-version
Phase III release tag.

No model, database, forecast, evaluation-semantic, or Model 1D behavior changes.
