# MacroPulse Model 1D v0.3.2.post1

## Scope

Test-only identity hotfix for Model 1D v0.3.2.

## Problem

Two inherited v0.3.1 regression tests still asserted:

`config["model"]["version"] == "0.3.1"`

The production configuration correctly reports Model 1D v0.3.2, so those stale assertions caused two failures in the complete v0.3 research suite.

## Fix

The tests now:

- use the name `test_model_identity_is_v032`;
- assert Model 1D version `0.3.2`;
- preserve all existing tournament and stability configuration checks.

## Unchanged

- temporal diagnostic implementation;
- v0.3.1 rolling-origin tournament logic;
- database schema;
- model scores and decisions;
- governance configuration.
