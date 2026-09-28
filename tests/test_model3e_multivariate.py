import numpy as np,pandas as pd,pytest
from macropulse.slack.multivariate import *
from macropulse.slack.state_space import ar2_is_stationary
def panel(n=140,seed=17):
 r=np.random.default_rng(seed); p=np.empty(n); g=np.empty(n); c=np.empty(n); p[0]=np.log(100);g[0]=.005;c[0]=0;lag=0
 for t in range(1,n):
  g[t]=g[t-1]+r.normal(0,.0002);p[t]=p[t-1]+g[t-1];z=.65*c[t-1]-.15*lag+r.normal(0,.004);lag=c[t-1];c[t]=z
 pi=np.empty(n);pi[0]=2
 for t in range(1,n): pi[t]=.8+.55*pi[t-1]+18*c[t-1]+r.normal(0,.35)
 u=5.5-.002*np.arange(n)-35*c+r.normal(0,.2,n);q=pd.period_range("1990Q1",periods=n,freq="Q")
 return pd.DataFrame({"real_gdp_log":p+c,"unemployment_rate":u,"core_pce_inflation":pi},index=q)
def test_validation():
 x=panel(80);x.iloc[10,1]=np.nan
 with pytest.raises(ValueError): validate_multivariate_panel(x)
def test_structures():
 assert MultivariateSlackModel(panel(80),CANDIDATE_3E_A).k_endog==2
 assert MultivariateSlackModel(panel(80),CANDIDATE_3E_B).k_endog==3
def test_transforms():
 for cid in (CANDIDATE_3E_A,CANDIDATE_3E_B):
  m=MultivariateSlackModel(panel(80),cid);x=m.start_params
  assert np.allclose(x,m.transform_params(m.untransform_params(x)),atol=1e-10,rtol=1e-10)
  assert ar2_is_stationary(x[2],x[3])
def test_fit_a():
 f=fit_multivariate_slack(panel(),CANDIDATE_3E_A)
 assert f.diagnostics.converged and f.diagnostics.sigma_pi>0 and f.diagnostics.sigma_potential==0
 assert set(f.estimates.estimate_class)=={"filtered_full_sample_parameters","smoothed_revised"}
def test_fit_b():
 f=fit_multivariate_slack(panel(),CANDIDATE_3E_B)
 assert f.diagnostics.converged and f.diagnostics.sigma_u>0 and f.diagnostics.sigma_potential==0
 assert set(f.estimates.estimate_class)=={"filtered_full_sample_parameters","smoothed_revised"}
def test_gap_identity():
 for cid in (CANDIDATE_3E_A,CANDIDATE_3E_B):
  f=fit_multivariate_slack(panel(),cid).estimates
  assert np.allclose(f.output_gap_pct,100*(f.observed_log_output-f.potential_log_output))

def test_model3e_corrective_governance_markers():
    import inspect
    from macropulse.slack.multivariate import MultivariateSlackModel, MIN_AR_ROOT_MODULUS
    source = inspect.getsource(MultivariateSlackModel.__init__)
    assert 'initialization="known"' in source
    assert "_initial_state_anchor" in source
    assert MIN_AR_ROOT_MODULUS == 1.02
