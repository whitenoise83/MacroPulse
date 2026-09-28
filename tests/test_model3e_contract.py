import json
from pathlib import Path
C=json.loads((Path(__file__).resolve().parents[1]/"MODEL3E_MULTIVARIATE_SLACK_CONTRACT.json").read_text())
def test_contract():
 assert C["model"]=="3" and C["workstream"]=="3E"
 assert C["model3d_base_commit"]=="4a33072b8c2d767fb4eecdf6efc1aba879373ff2"
 assert C["input_contract"]["joint_complete_model3b_panel_required"] is True
 assert C["inherited_gdp_state_system"]["sigma_potential_fixed"]==0.
 assert set(C["candidates"])=={"3E_A","3E_B"}
 assert C["candidates"]["3E_B"]["stochastic_nairu_allowed"] is False
 assert C["selection"]["production_selection_allowed"] is False
 assert C["selection"]["pseudo_real_time_selection_deferred_to"]=="3H"
 assert C["bootstrap"]["passing_3e_authorizes_only"]=="3F_model1_current_state_integration"
