# Model 3 Potential Output & Macroeconomic Slack v1.0.0

Model 3 v1.0.0 freezes the governed 3D state-space potential-output specification selected in Model 3H and hardened in Model 3I.

The immutable pseudo-real-time predecessor is `model3-pseudo-real-time-v1.0.0` at `a8ebf2d05a3b49d0c21f5ab1b03ca6eefca0b094`.

The econometric/source-hardening closure is `568b1302d4406736e5568371d7354c6ce10bcbb6`. The pre-release closure, including read-only Model 2 and Model 3 Streamlit integration, is `c018b4771108bbc646614d61f1970f4e55e4544a` and passed Model 3 Potential Output Guard #6 (run 36425589715).

The selected candidate is **3D — State-Space Potential Output**. The governed current estimate class is `production_current_endpoint`. Historical `smoothed_revised` estimates are revised history and are not presented as historical real-time estimates.

Forward gap integration uses frozen Model 2 GDP-growth draws with dense horizons 1–8 and governed report horizons 1, 2, 4 and 8. Potential output is continued deterministically; this release does **not** claim forward potential-output uncertainty.

The fixed-quarter revision audit is a disclosure and robustness diagnostic, not a selection reopening. The largest initial-to-latest revision is approximately 3.80 percentage points for 2020Q2, with a maximum path revision of approximately 4.70 percentage points; large revisions are concentrated in the COVID shock window. No post-hoc revision cutoff is introduced.

No Model 1 or Model 2 mutation, Model 4-based retuning, automatic candidate switching, or database-write authority is introduced.

The release tag `model3-potential-output-v1.0.0` must not be created until the metadata commit passes branch CI. Once created, the tag is immutable and tag CI must pass for release closure.
