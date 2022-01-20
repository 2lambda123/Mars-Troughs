#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 29 20:37:17 2021

@author: kris
"""
import numpy as np
import corner
import pickle
import matplotlib.pyplot as plt
import argparse
import os
import glob
import sys

def main():
    p=argparse.ArgumentParser(description="filename for plotting")
    p.add_argument("-objpath",type=str,help="name file or dir \
                                           for loading mcmc object")
    p.add_argument("-plotdir",type=str,help="name dir for saving plots")
    p.add_argument("-initmodel",type=int,help="initial model for \
                                                   plotting")
    p.add_argument("-stepEnsemble",type=int,help="skip models for \
                                                  plotting")
    args=p.parse_args()
    
    if os.path.isfile(args.objpath):
        listObj=[args.objpath]
        numfiles=len(listObj)
        print('Input file path')
    elif os.path.isdir(args.objpath):
        listObj=glob.glob(args.objpath+'*obj')
        numfiles=len(listObj)
        print('Input directory path')
        print(numfiles,' files')
        
        
    for ifile in np.arange(0,numfiles):
            
        infile=open(listObj[ifile],'rb')
        print(listObj[ifile])
        newmcmc=pickle.load(infile)
        infile.close()
        
        
        #create folder for saving figures
        if not os.path.exists(args.plotdir+'figures/'):
            os.makedirs(args.plotdir+'figures/')
        
        #set parameters for plotting
        paramsList=list(newmcmc.tr.all_parameter_names)
        numparams=len(paramsList)
        
        #subsample ensemble
        if newmcmc.totalSteps<= args.initmodel:
            ensemble=newmcmc.samples[int((newmcmc.totalSteps/newmcmc.thin_by-1)/2)::args.stepEnsemble,:,:]
            xaxis=np.arange(int(newmcmc.totalSteps/2),newmcmc.totalSteps+1,args.stepEnsemble*newmcmc.thin_by)
            nmodels=len(xaxis)
            logprob=newmcmc.logprob[int((newmcmc.totalSteps/newmcmc.thin_by-1)/2)::args.stepEnsemble,:]
        else:
            ensemble=newmcmc.samples[int(args.initmodel/newmcmc.thin_by-1)::args.stepEnsemble,:,:]
            xaxis=np.arange(args.initmodel,newmcmc.totalSteps+1,args.stepEnsemble*newmcmc.thin_by)
            nmodels=len(xaxis) 
            logprob=newmcmc.logprob[int(args.initmodel/newmcmc.thin_by-1)::args.stepEnsemble,:]
        
        #parameter values per iteration---------------------------------
        plt.figure()
        
        for i in np.arange(1,numparams):
            plt.subplot(numparams,1,i)
            plt.plot(xaxis,ensemble[:,:,i-1])
            plt.xticks([], [])
            plt.title(paramsList[i-1])
            
        plt.subplot(numparams,1,numparams)
        plt.plot(xaxis,ensemble[:,:,numparams-1])
        plt.title(paramsList[numparams-1])
        plt.xlabel('Step')
        
        #create folder for saving figure
        if not os.path.exists(args.plotdir+'figures/'+'paramsIter/'):
            os.makedirs(args.plotdir+'figures/'+'paramsIter/')
            
        plt.savefig(args.plotdir+'figures/'+'paramsIter/'
                    +newmcmc.modelName+'_'+str(newmcmc.maxSteps)+'.pdf',
                    facecolor='w',pad_inches=0.1)
        
        #corner plot posterior ----------------------------------------------
        #reshape ensemble
        ensemble2d=ensemble.reshape((newmcmc.nwalkers*nmodels,numparams))
            
        #plot
        corner.corner(ensemble2d,labels=paramsList,quiet=True)
        
        #create folder for saving figure
        if not os.path.exists(args.plotdir+'figures/'+'corner/'):
            os.makedirs(args.plotdir+'figures/'+'corner/')
            
        plt.savefig(args.plotdir+'figures/'+'corner/'
                    +newmcmc.modelName+'_'+str(newmcmc.maxSteps)+'.pdf',
                    facecolor='w',pad_inches=0.1)
        
        
        #log likelihood -------------------------------------------------------
        plt.figure()
        plt.plot(xaxis,logprob)
        plt.title(label='mean acceptance ratio = '+ str(np.round(np.mean(newmcmc.accFraction),2)))
        plt.xlabel('Step')
        plt.ylabel('log prob')
        
        #create folder for saving figure
        if not os.path.exists(args.plotdir+'figures/'+'logprob/'):
            os.makedirs(args.plotdir+'figures/'+'logprob/')
            
        plt.savefig(args.plotdir+'figures/'+'logprob/'
                    +newmcmc.modelName+'_'+str(newmcmc.maxSteps)+'.pdf',
                    facecolor='w',pad_inches=0.1)
        
        #autocorrelation values-----------------------------------------------
        plt.figure()
        autoxaxis=(newmcmc.maxSteps/10)*np.arange(1,11)
        autoxaxis=autoxaxis[:len(newmcmc.autocorr)]
        
        plt.plot(autoxaxis,autoxaxis/50,"--k",label=r'50*steps')
        plt.plot(autoxaxis[np.nonzero(newmcmc.autocorr)],newmcmc.autocorr[np.nonzero(newmcmc.autocorr)],label=r'$\tau$ estimate')
        plt.xlabel('Step')
        plt.ylabel(r'mean $\tau$')
        ax=plt.gca()
        ax.legend()
        
        
        #create folder for saving figure
        if not os.path.exists(args.plotdir+'figures/'+'autocorr/'):
            os.makedirs(args.plotdir+'figures/'+'autocorr/')
            
        plt.savefig(args.plotdir+'figures/'+'autocorr/'
                    +newmcmc.modelName+'_'+str(newmcmc.maxSteps)+'.pdf',
                    facecolor='w',pad_inches=0.1)
        
        #lag, acc rate and y per time for each model ----------------------------
        #indxlagparams=paramsList.index(lagparamsList[0])
        lagt=np.zeros((nmodels*newmcmc.nwalkers,len(newmcmc.tr.accuModel._times)))
        acct=np.zeros((nmodels*newmcmc.nwalkers,len(newmcmc.tr.accuModel._times)))
        tmpt=np.zeros((nmodels*newmcmc.nwalkers,len(newmcmc.tr.accuModel._times),2))
        
        indxw=0
        for i in range(0,nmodels):
            for w in range(0,newmcmc.nwalkers):
                iparams=dict(zip(newmcmc.tr.all_parameter_names,ensemble[i,w,:]))
                newmcmc.tr.set_model(iparams)
                
                lagti=newmcmc.tr.lagModel.get_lag_at_t(newmcmc.tr.accuModel._times)
                accti=newmcmc.tr.accuModel.get_accumulation_at_t(newmcmc.tr.accuModel._times)
                tmpti=np.array(newmcmc.tr.get_trajectory(newmcmc.tr.accuModel._times))
                
                lagt[indxw]=lagti
                acct[indxw]=accti
                tmpt[indxw,:,:]=tmpti.T
                indxw=indxw+1
                
                
        plt.figure()
        
        subsample=10
        timeaxis=newmcmc.tr.accuModel._times
        timesub=timeaxis[0::subsample]
        
        #plot lagt
        plt.subplot(4,1,1)
        plt.plot(timesub,lagt[:,0::subsample].T)
        plt.xticks([], [])
        plt.title('Lag (mm)')
        
        #plot lagt
        plt.subplot(4,1,2)
        plt.plot(timesub,acct[:,0::subsample].T)
        plt.xticks([], [])
        plt.title('acc rate (m/year)')
        
        #plot yt
        plt.subplot(4,1,3)
        plt.plot(timesub,tmpt[:,0::subsample,1].T)
        plt.title('Vertical distance (m)')
        plt.xticks([], [])
        
        #plot xt
        plt.subplot(4,1,4)
        plt.plot(timesub,tmpt[:,0::subsample,0].T)
        plt.xlabel('Time (years)')
        plt.title('Horizontal distance (m)')
        
        #create folder for saving figure
        if not os.path.exists(args.plotdir+'figures/'+'lagaccdist/'):
            os.makedirs(args.plotdir+'figures/'+'lagaccdist/')
            
        plt.savefig(args.plotdir+'figures/'+'lagaccdist/'
                    +newmcmc.modelName+'_'+str(newmcmc.maxSteps)+'.png',
                    facecolor='w',pad_inches=0.1)
        
        # tmp fit ---------------------------------------------------
        #reshape logprob
        plt.figure()
        
        logprob1d=logprob.reshape(nmodels*newmcmc.nwalkers,1)
        #best model params
        bestTMPindx=np.argmax(logprob1d)
        bestTMP=tmpt[bestTMPindx,:,:]
        plt.plot(bestTMP[:,0],bestTMP[:,1],c='b',label='Best TMP')
        
        #get errorbar of best tmp
        errorbar1d=ensemble[:,:,0].reshape(nmodels*newmcmc.nwalkers,1)
        bestErrorbar=errorbar1d[bestTMPindx]
        
        ratioyx=0.4;
        
        #find nearest points
        x_model=bestTMP[:,0]
        y_model=bestTMP[:,1]
        xnear = np.zeros_like(newmcmc.xdata)
        ynear = np.zeros_like(newmcmc.ydata)
        timenear = np.zeros_like(newmcmc.xdata)
        
        
        for i, (xdi, ydi) in enumerate(zip(newmcmc.xdata, newmcmc.ydata)):
            dist = newmcmc.tr._L2_distance(x_model, xdi, y_model, ydi)
            ind = np.argmin(dist)
            xnear[i] = x_model[ind]
            ynear[i] = y_model[ind]
            timenear[i] = newmcmc.tr.accuModel._times[ind]
            
        #plot tmp data and errorbar
        xerr, yerr = bestErrorbar*newmcmc.tr.meters_per_pixel
        
        for i in range(nmodels):
            indx=np.random.randint(0,nmodels*newmcmc.nwalkers)
            plt.plot(tmpt[indx,:,0],tmpt[indx,:,1],c="gray", alpha=0.1, zorder=-1)
        plt.plot(tmpt[indx,:,0],tmpt[indx,:,1],c="gray", alpha=0.1, zorder=-1,label='Ensemble models')
        plt.xlabel("Horizontal dist [m]")
        plt.ylabel("V. dist [m]")
        ax=plt.gca()
        ax.legend(bbox_to_anchor=(0.5, -0.3), loc='upper left')
        #ymin,ymax=ax.get_ylim()
        #xmin,xmax=ax.get_xlim()
        xmax=np.max(newmcmc.xdata)+1000
        ymin=np.min(newmcmc.ydata)-100
        ax.set_ylim(ymin,0)
        ax.set_xlim(0,xmax)
        ax.set_box_aspect(ratioyx)
        
        #plot times on upper axis
        ax2=ax.twiny()
        color='m'
        ax2.set_xlabel('Time before present ( Million years)',color=color)
        plt.scatter(xnear,ynear,marker="o",color='m')
        plt.errorbar(x=newmcmc.xdata, xerr=xerr, y=newmcmc.ydata, yerr=yerr, 
                 c='r', marker='.', ls='',label='Observed TMP')
        ax2.set_ylim(ymin,0)
        ax2.set_xlim(0,xmax)
        ax2.tick_params(axis='x',labelcolor=color)
        plt.xticks(xnear,np.round(timenear/1000000,2).astype(float),rotation=90)
        ax2.set_box_aspect(ratioyx)
        
        #create folder for saving figure
        if not os.path.exists(args.plotdir+'figures/'+'tmp/'):
            os.makedirs(args.plotdir+'figures/'+'tmp/')
    
            
        plt.savefig(args.plotdir+'figures/'+'tmp/'
                    +newmcmc.modelName+'_'+str(newmcmc.maxSteps)+'.pdf',
                    facecolor='w',pad_inches=0.1)
        
        plt.close('all')
        print(ifile,file=sys.stderr)
        
def mainArgs(objpath,plotdir,init,step):
    sys.argv = ['maintest.py', 
                '-objpath', str(objpath),
                '-plotdir', str(plotdir),
                '-initmodel',str(init),
                '-stepEnsemble', str(step)]
    main()
    
if __name__ == "__main__":
    main()
    
