from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.mlemodel import MLEModel
from macropulse.slack.state_space import MIN_OBSERVATIONS,_pacf_to_ar2,ar2_is_stationary
REQUIRED_COLUMNS=("real_gdp_log","unemployment_rate","core_pce_inflation")
CANDIDATE_3E_A="3E_A"; CANDIDATE_3E_B="3E_B"
MIN_AR_ROOT_MODULUS=1.02
@dataclass(frozen=True)
class MultivariateDiagnostics:
    candidate_id:str; converged:bool; log_likelihood:float; sigma_potential:float
    sigma_trend_growth:float; sigma_gap:float; phi1:float; phi2:float
    alpha_pi:float; rho_pi:float; kappa:float; sigma_pi:float
    alpha_u:float|None=None; tau_u:float|None=None; lambda_u:float|None=None; sigma_u:float|None=None
    phillips_sign_coherent:bool|None=None; okun_sign_coherent:bool|None=None
@dataclass(frozen=True)
class MultivariateFit:
    estimates:pd.DataFrame; diagnostics:MultivariateDiagnostics; raw_result:object
def validate_multivariate_panel(panel,minimum=MIN_OBSERVATIONS):
    if not isinstance(panel,pd.DataFrame): raise TypeError("Model 3E input must be a pandas DataFrame.")
    missing=[c for c in REQUIRED_COLUMNS if c not in panel.columns]
    if missing: raise ValueError("Model 3E panel missing columns: "+", ".join(missing))
    if not isinstance(panel.index,pd.PeriodIndex) or not str(panel.index.freqstr).startswith("Q"): raise ValueError("Model 3E panel must use a quarterly PeriodIndex.")
    x=panel.loc[:,list(REQUIRED_COLUMNS)].astype(float).sort_index()
    if len(x)<minimum: raise ValueError(f"At least {minimum} joint-complete quarters are required.")
    if x.index.has_duplicates: raise ValueError("Quarter index contains duplicates.")
    if len(x)>1 and not np.all(np.diff([q.ordinal for q in x.index])==1): raise ValueError("Quarter index must be consecutive.")
    if x.isna().any().any() or not np.isfinite(x.to_numpy()).all(): raise ValueError("Model 3E panel must be joint-complete and finite.")
    return x
class MultivariateSlackModel(MLEModel):
    def __init__(self,panel,candidate_id):
        frame=validate_multivariate_panel(panel)
        if candidate_id not in {CANDIDATE_3E_A,CANDIDATE_3E_B}: raise ValueError("candidate_id must be 3E_A or 3E_B.")
        self.candidate_id=candidate_id
        lag=frame.core_pce_inflation.shift(1); use=frame.loc[lag.notna()].copy(); lag=lag.loc[use.index]
        if len(use)<MIN_OBSERVATIONS: raise ValueError(f"At least {MIN_OBSERVATIONS} observations after the inflation lag are required.")
        self._frame=use; self._period_index=use.index.copy(); self._pi_lag=lag.to_numpy(float); self._time=np.arange(len(use),dtype=float)
        cols=["real_gdp_log","core_pce_inflation"]+(["unemployment_rate"] if candidate_id==CANDIDATE_3E_B else [])
        endog=use[cols].to_numpy(float)
        initial_growth=float(np.mean(np.diff(endog[:min(12,len(endog)),0])))
        self._initial_state_anchor=np.array([float(endog[0,0]),initial_growth,0.0,0.0],dtype=float)
        initial_cov=np.diag([1e-6,1e-4,1e-4,1e-4])
        super().__init__(endog=endog,k_states=4,k_posdef=2,initialization="known",initial_state=self._initial_state_anchor,initial_state_cov=initial_cov)
        d=np.zeros((endog.shape[1],4)); d[0]=[1,0,1,0]; self["design"]=d
        self["obs_cov"]=np.zeros((endog.shape[1],endog.shape[1]))
        self["selection"]=np.array([[0.,0.],[1.,0.],[0.,1.],[0.,0.]])
        self["transition"]=np.array([[1.,1.,0.,0.],[0.,1.,0.,0.],[0.,0.,.55,-.10],[0.,0.,1.,0.]])
        self["state_cov"]=np.eye(2)*1e-4; self["obs_intercept"]=np.zeros((endog.shape[1],len(use)))
    @property
    def param_names(self):
        p=["sigma_trend_growth","sigma_gap","phi1","phi2","alpha_pi","rho_pi","kappa","sigma_pi"]
        return p+(["alpha_u","tau_u","lambda_u","sigma_u"] if self.candidate_id==CANDIDATE_3E_B else [])
    @property
    def start_params(self):
        a,b=_pacf_to_ar2(.5,-.1); pi=self._frame.core_pce_inflation.to_numpy(float)
        p=[.001,.01,a,b,float(pi.mean())*.25,.5,.05,max(float(pi.std()),.1)]
        if self.candidate_id==CANDIDATE_3E_B:
            u=self._frame.unemployment_rate.to_numpy(float); p += [float(u.mean()),0.,.5,max(float(u.std()),.1)]
        return np.asarray(p,float)
    def transform_params(self,u):
        u=np.asarray(u,float); c=u.copy(); c[0]=np.exp(np.clip(u[0],-20,5)); c[1]=np.exp(np.clip(u[1],-20,5))
        c[2],c[3]=_pacf_to_ar2(np.tanh(u[2]),np.tanh(u[3])); c[5]=np.tanh(u[5]); c[7]=np.exp(np.clip(u[7],-20,5))
        if self.candidate_id==CANDIDATE_3E_B: c[11]=np.exp(np.clip(u[11],-20,5))
        return c
    def untransform_params(self,c):
        c=np.asarray(c,float); u=c.copy(); pos=[0,1,7]+([11] if self.candidate_id==CANDIDATE_3E_B else [])
        if any(c[i]<=0 for i in pos): raise ValueError("Standard deviations must be positive.")
        u[0]=np.log(c[0]); u[1]=np.log(c[1])
        if not ar2_is_stationary(c[2],c[3]): raise ValueError("AR(2) parameters are not stationary.")
        den=1-c[3]
        if abs(den)<1e-12: raise ValueError("AR(2) parameters cannot be inverted safely.")
        e=np.finfo(float).eps; u[2]=np.arctanh(np.clip(c[2]/den,-1+e,1-e)); u[3]=np.arctanh(np.clip(c[3],-1+e,1-e))
        u[5]=np.arctanh(np.clip(c[5],-1+e,1-e)); u[7]=np.log(c[7])
        if self.candidate_id==CANDIDATE_3E_B: u[11]=np.log(c[11])
        return u
    def update(self,params,transformed=True,includes_fixed=False,**kwargs):
        p=super().update(params,transformed=transformed,includes_fixed=includes_fixed,**kwargs)
        sg,sc,a,b=p[:4]; api,rpi,k,spi=p[4:8]; self["transition",2,2]=a; self["transition",2,3]=b
        self["state_cov"]=np.diag([sg**2,sc**2])
        cov_dtype=np.result_type(a,b,sc)
        A=np.array([[a,b],[1.0,0.0]],dtype=cov_dtype)
        Q=np.array([[sc**2,0.0],[0.0,0.0]],dtype=cov_dtype)
        try:
            vec_p=np.linalg.solve(np.eye(4)-np.kron(A,A),Q.reshape(4,order="F"))
            P=np.real_if_close(vec_p.reshape((2,2),order="F"),tol=1000)
            P=np.asarray(P.real,dtype=float); P=0.5*(P+P.T)
            if np.isfinite(P).all():
                cov=np.diag([1e-6,1e-4,1.0,1.0]); cov[2:4,2:4]=P
                self.ssm.initialize_known(self._initial_state_anchor,cov)
        except np.linalg.LinAlgError:
            pass
        self["design",1,3]=k; self["obs_intercept",1,:]=api+rpi*self._pi_lag; self["obs_cov",1,1]=spi**2
        if self.candidate_id==CANDIDATE_3E_B:
            au,tu,lam,su=p[8:12]; self["design",2,2]=-lam; self["obs_intercept",2,:]=au+tu*self._time; self["obs_cov",2,2]=su**2
def _frame(idx,y,s,cid,cls):
    pot=s[0]; g=s[1]; f=pd.DataFrame({"estimate_origin":idx.astype(str),"candidate_id":cid,"estimate_class":cls,"observed_log_output":y,"potential_log_output":pot,"potential_output_level":np.exp(pot),"potential_output_growth_annualized_pct":400*g,"output_gap_pct":100*(y-pot)},index=idx); f.index.name="quarter"; return f
def fit_multivariate_slack(panel,candidate_id,*,maxiter=1000,require_convergence=True):
    m=MultivariateSlackModel(panel,candidate_id); r=m.fit(method="powell",maxiter=int(maxiter),disp=False); p=np.asarray(r.params,float); conv=bool(r.mle_retvals.get("converged",False))
    pos=[0,1,7]+([11] if candidate_id==CANDIDATE_3E_B else [])
    if not np.isfinite(p).all(): raise RuntimeError("Model 3E estimation produced non-finite parameters.")
    if any(p[i]<=0 for i in pos): raise RuntimeError("Model 3E produced non-positive standard deviations.")
    if not ar2_is_stationary(p[2],p[3]): raise RuntimeError("Model 3E produced a nonstationary output-gap AR(2).")
    if require_convergence and not conv: raise RuntimeError("Model 3E maximum-likelihood optimization did not converge.")
    y=m._frame.real_gdp_log.to_numpy(float); fs=np.asarray(r.filtered_state); ss=np.asarray(r.smoothed_state)
    kw=dict(candidate_id=candidate_id,converged=conv,log_likelihood=float(r.llf),sigma_potential=0.,sigma_trend_growth=float(p[0]),sigma_gap=float(p[1]),phi1=float(p[2]),phi2=float(p[3]),alpha_pi=float(p[4]),rho_pi=float(p[5]),kappa=float(p[6]),sigma_pi=float(p[7]),phillips_sign_coherent=bool(p[6]>=0))
    if candidate_id==CANDIDATE_3E_B: kw.update(alpha_u=float(p[8]),tau_u=float(p[9]),lambda_u=float(p[10]),sigma_u=float(p[11]),okun_sign_coherent=bool(p[10]>0))
    return MultivariateFit(pd.concat([_frame(m._period_index,y,fs,candidate_id,"filtered_full_sample_parameters"),_frame(m._period_index,y,ss,candidate_id,"smoothed_revised")]),MultivariateDiagnostics(**kw),r)
