# MacroPulse Model 1C v1.0.0 Production Approval

- Model ID: `US_LABOUR_NOWCAST_1C`
- Production version: `1.0.0`
- Lifecycle: `production`
- Promoted from model version: `0.6.0`
- Promoted from package version: `0.6.0.post1`
- Candidate validation ID: `0540c6ee-2d96-493a-adfe-a76c5c91cf31`
- Candidate validation result: **PASS (39/39)**
- Operational validation ID: `f535fdc2-c75c-4da8-a0f8-e3d1b80416f3`
- Operational validation result: **PASS (20/20)**
- Freeze assessment ID: `7eb22dae-54c8-423e-ad1e-9977db08d388`
- Freeze assessment result: **PASS (14/14)**
- Governed live run ID: `56adddf6-2438-43cf-97b0-24e4801ac9a4`
- Approval ID: `cd18cc36-5d5b-49a0-8116-3b731d3c24b9`
- Approved at: `2026-08-01T16:12:00+01:00`
- Approval phrase: `APPROVE MODEL 1C FREEZE`
- Freeze assessment: `reports/labour_freeze/model1c_freeze_assessment_20260801_161037.md`
- Production configuration hash: `286709810e3d5f709df39d5e00eeef02a83d860ad30570f7deab9c971d8ebd76`
- Production code hash: `bfcddb5116d5554dbc019d43281d69e23713454b37097dc76d99233ccd8fbcbc`
- Validated live configuration hash: `2eb289eafcfba7eed364c77e673100bb11e1b88f7fd9a47ebd8089e896774cd5`
- Validated live code hash: `e7f9eb834b50d1c838d8e6b35e42faf46f1aa7db8770cc874d0497ed60f5ab95`
- Validated information-set hash: `e239ca660ccb4edcf76a9b1992f4f3fa4f2004499f70d190bfa4b2bfba5d99ba`
- Validated model-state hash: `16517e61fca43334ae961a13b620b0a760fdeffa0c934dd6db5cbbcedd5f9654`
- Validated governance signature: `f3f456233660c647e0dcff9db0c62b4f54a3cdbd1aa32ab178737f37313e68de`

## Approved production point policy

| Labour target | Forecast stage | Production component |
|---|---|---|
| Nonfarm Payroll Change | Month open | Labour 12-Month Mean |
| Nonfarm Payroll Change | After week 1 | Labour Equal-Weight Ensemble |
| Nonfarm Payroll Change | After week 2 | Labour Bridge Ridge |
| Nonfarm Payroll Change | Month end | Labour Bridge Ridge |
| Nonfarm Payroll Change | Pre-employment report | Labour Bridge Ridge |
| Unemployment Rate | Month open | Labour Equal-Weight Ensemble |
| Unemployment Rate | After week 1 | Labour Equal-Weight Ensemble |
| Unemployment Rate | After week 2 | Labour Equal-Weight Ensemble |
| Unemployment Rate | Month end | Labour Equal-Weight Ensemble |
| Unemployment Rate | Pre-employment report | Labour Equal-Weight Ensemble |
| Average Hourly Earnings Growth | Month open | Labour Bridge Ridge |
| Average Hourly Earnings Growth | After week 1 | Labour Bridge Ridge |
| Average Hourly Earnings Growth | After week 2 | Labour Equal-Weight Ensemble |
| Average Hourly Earnings Growth | Month end | Labour Equal-Weight Ensemble |
| Average Hourly Earnings Growth | Pre-employment report | Labour Equal-Weight Ensemble |

## Approved uncertainty and challenger governance

- Production interval method: `exp_weighted_q80`.
- Nominal interval coverage: `80%`.
- Minimum prior errors: `24`.
- Rolling calibration window: `48 months`.
- Exponential decay: `0.94`.
- Adaptive selector role: `shadow challenger only`.

The stable target-stage map controls production headlines. The adaptive selector cannot replace a production component without a new version, documented challenger evidence, revalidation, and explicit model-owner approval.
