from macropulse.governance.versioning import current_model_identity


def test_model1a_production_hashes_remain_frozen():
    identity = current_model_identity()
    assert identity.model_version == "1.0.0"
    assert identity.config_hash == "20afe54e474247c9b7a460caa3ec7aedf56691115641f4ac1bbd4420205d46a7"
    assert identity.code_hash == "914938821fee082d69265afb69dfda939c597a24635a8878cf553577a6ea346d"
