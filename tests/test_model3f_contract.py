import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=json.loads((ROOT/'MODEL3F_MODEL1_INTEGRATION_CONTRACT.json').read_text(encoding='utf-8'))
def test_predecessor(): assert C['model3e_predecessor_commit']=='5378dd8aeef716f17e46f73716803ac20d101516'
def test_model1_read_only(): assert C['inputs']['model1_read_only'] and not C['inputs']['model1_refit_allowed'] and not C['inputs']['model1_mutation_allowed']
def test_model2_deferred(): assert C['inputs']['model2_forecasts_allowed'] is False
def test_selection_deferred(): assert C['inputs']['model3e_candidate_selection_allowed'] is False
def test_db_read_only(): assert C['governance']['database_writes_allowed'] is False
def test_next(): assert C['passing_authorizes_only']=='3G_model2_forward_gap_integration'
