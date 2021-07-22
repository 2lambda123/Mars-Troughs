#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 12 09:31:34 2021

@author: kris
"""
#import modules
import time
from typing import Dict, List, Optional, Union
import numpy as np
import scipy.optimize as op
import mars_troughs as mt
import emcee
from mars_troughs import DATAPATHS, Model
from mars_troughs.datapaths import load_insolation_data
import os

class MCMC():
    """
    Class for running MCMC chains to obtain a sample of climate parameters
    of trough migration.
    """
    def __init__(
        self,
        maxSteps: int,
        subIter: int,
        directory: str,
        acc_model_name = Union[str, Model],
        lag_model_name = Union[str, Model],
        acc_params: Optional[List[float]] = None,
        lag_params: Optional[List[float]] = None,
        errorbar = np.sqrt(1.6), #errorbar in pixels on the datapoints
        angle= 5.0,
    ):
        self.maxSteps = maxSteps
        self.subIter = subIter
        self.acc_model_name = acc_model_name
        self.lag_model_name = lag_model_name
        
        
        #Load data
        self.xdata,self.ydata=np.loadtxt(DATAPATHS.TMP, unpack=True) #Observed TMP data
        self.xdata=self.xdata*1000 #km to m 
        (inst,times) = load_insolation_data() #Insolation data and times
        self.times=-times
        
        # Create  trough object 
        self.tr = mt.Trough(self.acc_model_name,self.lag_model_name,acc_params,
                       lag_params,
                       errorbar,angle)
        
        self.parameter_names = ([key for key in self.tr.all_parameters])
        
        #Find number of dimensions and number of parameters per submodel
        self.ndim=len(self.parameter_names)
        self.nwalkers=self.ndim*4
        
        #Create directory to save ensemble and figures
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.subdir='acc_'+acc_model_name+'_lag_'+lag_model_name+'/'
        if not os.path.exists(directory+self.subdir):
            os.makedirs(directory+self.subdir)
    
        self.filename=directory+self.subdir+str(self.maxSteps)
        
        
        #Define the log likelihood
    
        #Linear optimization
        guessParams=np.array([errorbar]+acc_params+lag_params)
        optObj= op.minimize(self.neg_ln_likelihood, x0=guessParams, 
                            method='Nelder-Mead')
        self.optParams=optObj['x']
        
        #Set file to save progress 
        backend=emcee.backends.HDFBackend(self.filename+'.h5')
        backend.reset(self.nwalkers,self.ndim)
        
        #Set optimized parameter values as initial values of MCMC chains 
        self.initParams=np.array([self.optParams+ 
                        1e-3*self.optParams*np.random.randn(self.ndim) 
                        for i in range(self.nwalkers)])
    
        start = time.time()
        
        #Initialize sampler
        self.sampler = emcee.EnsembleSampler(self.nwalkers, self.ndim, 
                                             self.ln_likelihood, 
                                             backend=backend, 
                                             parameter_names=self.parameter_names)
        #Run MCMC and track progress
        self.sampler.reset()
        #Iteratively compute autocorrelation time Tau
        index=0
        autocorr=np.zeros(int(maxSteps/subIter))
        old_tau=np.inf
        
        #compute tau every subIter iterations
        for sample in self.sampler.sample(self.initParams,iterations=self.maxSteps, 
        progress=True):
        
            if self.sampler.iteration%self.subIter:
                continue
                
            tau=self.sampler.get_autocorr_time(tol=0)
            autocorr[index]=np.mean(tau)
            index+=1
            converged=np.all(tau*50<self.sampler.iteration)
            converged&=np.all(np.abs(old_tau-tau)/tau<0.01)
            
            if converged:
                break
            
            old_tau=tau
            
        end = time.time()
        running_time=end-start

        print("MCMC running time {0:.1f} seconds".format(running_time))

    def ln_likelihood(self,params: Dict[str,float]):
        
        errorbar: float = params["errorbar"]
        
        if errorbar < 0: #prior on the variance (i.e. the error bars)
            return -1e99
    
        self.tr.set_model(params)
        
        lag_t=self.tr.lagModel.get_lag_at_t(self.times)
    
        if any(lag_t < 0) or any(lag_t > 20):
    
            return -1e99
    
        return self.tr.lnlikelihood(self.xdata,self.ydata)
    
    #And the negative of the log likelihood
    def neg_ln_likelihood(self,paramsArray):
        
        params=dict(zip(self.parameter_names, paramsArray))
        
        return -self.ln_likelihood(params)

    



        

        