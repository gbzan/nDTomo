# -*- coding: utf-8 -*-
"""
Class to integrate XRD-CT data collected with the continuous rotation-translation method.
The integration can be performed with CPU, GPU, or the multi-CPU ID15A PC.

@author: A. Vamvakeros
"""

from PThread import Periodic
from PyQt5.QtCore import pyqtSignal, QThread
import os, fabio, h5py, pyFAI, time, json
from numpy import zeros, array, arange, mod, ceil, deg2rad, sin, pi, round

class Fast_XRDCT_LiveSqueeze(QThread): 
    
    '''
    Integrate continuous rotation-translation XRD-CT data
    '''    
    
    progress = pyqtSignal(int)
    
    def __init__(self,prefix,dataset,xrdctpath,maskname,poniname,na,nt,npt_rad,filt,procunit,units,prc,thres,datatype,savepath,scantype,energy,jsonname,omega,trans,dio,etime):
        QThread.__init__(self)
        self.prefix = prefix; self.dataset=dataset; self.xrdctpath = xrdctpath; self.maskname = maskname; self.poniname = poniname
        self.filt=filt; self.procunit=procunit;self.units =units;self.E = energy
        self.prc=prc;self.thres = thres;self.datatype = datatype;self.savepath = savepath
        self.na = int(na); self.nt = int(nt); self.npt_rad = int(npt_rad); self.scantype = scantype; self.jsonname = jsonname
        self.omega = omega; self.trans = trans;self.dio = dio; self.etime = etime
        self.gpuxrdctpath = '/gz%s' %self.xrdctpath
        
        self.data = zeros((1,1,1))
                
        dpath = os.path.join(self.xrdctpath, self.dataset)
        try:
            os.chdir(dpath)		

            self.mask = fabio.open(self.maskname)
            self.mask = array(self.mask.data)
                        
        except:
            print "Cannot open mask file or the xrd-ct dataset directory is wrong"

    def run(self):
        self.previousLine = 0
        self.nextLine = 1        
        self.nextimageFile  =  "%s/%s/%s_%.4d.cbf" % (self.xrdctpath, self.dataset, self.dataset, self.na)     
        print self.nextimageFile    
        if self.procunit == "MultiGPU":
            self.periodEventraw = Periodic(1, self.checkForImageFile)   
        else:
            self.periodEventraw = Periodic(1, self.checkForImageFileOar)   

    def checkForImageFileOar(self):
            
        if os.path.exists(self.nextimageFile) & (self.nextLine == 1):
            print('%s exists' % self.nextimageFile)
            self.periodEventraw.stop()
            self.integrateLineDataOar()
            self.setnextimageFileOar()       
        elif os.path.exists(self.nextimageFile) & (self.nextLine < self.nt+1) & os.path.exists(self.hdf5_fn):
            print('%s exists' % self.nextimageFile)
            self.periodEventraw.stop()
            self.integrateLineDataOar()
            self.setnextimageFileOar()     
        else: # keep looking
            print('%s' %self.nextimageFile ,'does not exist')
            print('or %s does not exist' % self.previousdatFile)
#            self.periodEventraw.stop()

    def setnextimageFileOar(self):

        self.previousLine += 1
        self.nextLine += 1
        if self.nextLine < self.nt:

            self.nextimageFile =  "%s/%s/%s_%.4d.cbf" % (self.xrdctpath, self.dataset, self.dataset, self.nextLine*self.na)
            print self.nextimageFile
            self.periodEventraw.start()

        elif self.nextLine == self.nt: #might need a sleep to give time to write the last image
            
            self.nextimageFile =  "%s/%s/%s_%.4d.cbf" % (self.xrdctpath, self.dataset, self.dataset, self.nextLine*self.na-1)
            print self.nextimageFile
            self.periodEventraw.start()            
        else:
            print('All done')
            
    def integrateLineDataOar(self):
        
        try:

            self.Int = zeros((self.na,self.npt_rad-10));
         
            ai = pyFAI.load(self.poniname)       
            kk = 0
            for ii in range(int(self.na)*self.previousLine,int(self.na)*self.nextLine):             
            
                start=time.time()
                if self.datatype == 'cbf':
                    s = '%s/%s_%.4d.cbf' % (self.dataset,self.prefix,ii)
                else:
                    s = '%s/%s_%.4d.edf' % (self.dataset,self.prefix,ii)
                pat = os.path.join(self.xrdctpath, s)
                f = fabio.open(pat)
                d = array(f.data)
                if self.filt == "No":
                    if self.procunit == "CPU":
                        r, I = ai.integrate1d(data=d, npt=self.npt_rad, mask=self.mask, unit=self.units, method="cython",correctSolidAngle=False, polarization_factor=0.95)
                    elif self.procunit == "GPU":
                        r, I = ai.integrate1d(data=d, npt=self.npt_rad, mask=self.mask, unit=self.units, method="ocl_CSR_gpu",correctSolidAngle=False, polarization_factor=0.95)
                elif self.filt == "Median":
                    if self.procunit == "CPU":
                        r, I = ai.medfilt1d(data=d, npt_rad=int(self.npt_rad), percentile=50, unit=self.units, mask=self.mask, method="splitpixel", correctSolidAngle=False, polarization_factor=0.95);
                    elif self.procunit == "GPU":
                        r, I = ai.medfilt1d(data=d, npt_rad=int(self.npt_rad), percentile=50, unit=self.units, mask=self.mask, method="ocl_CSR_gpu", correctSolidAngle=False, polarization_factor=0.95);
                elif self.filt == "trimmed_mean":
                    if self.procunit == "CPU":
                        r, I = ai.medfilt1d(data=d, npt_rad=int(self.npt_rad), percentile=(round(float(self.prc)/2),100-round(float(self.prc)/2)), unit=self.units, mask=self.mask, method="cython", correctSolidAngle=False, polarization_factor=0.95); #"splitpixel"
                    elif self.procunit == "GPU":
                        r, I = ai.medfilt1d(data=d, npt_rad=int(self.npt_rad), percentile=(round(float(self.prc)/2),100-round(float(self.prc)/2)), unit=self.units, mask=self.mask, method="ocl_CSR_gpu", correctSolidAngle=False, polarization_factor=0.95); 
                elif self.filt == "sigma":
                    if self.procunit == "CPU":
                        r, I, std = ai.sigma_clip(data=d, npt_rad=int(self.npt_rad), thres=float(self.thres), max_iter=5, unit=self.units, mask=self.mask, method="cython", correctSolidAngle=False, polarization_factor=0.95);
                    elif self.procunit == "GPU":
                        r, I, std = ai.sigma_clip(data=d, npt_rad=int(self.npt_rad), thres=float(self.thres), max_iter=5, unit=self.units, mask=self.mask, method="ocl_CSR_gpu", correctSolidAngle=False, polarization_factor=0.95);
                self.Int[kk,:] = I[0:self.npt_rad-10]
                r = r[0:self.npt_rad-10]
                
                v = (round((100.*(ii+1))/(int(self.na)*int(self.nt))))
                self.progress.emit(v)
                kk += 1;
                print s, time.time()-start
                    
    
            print "Integration done, now saving the data"
            self.r = r
            if self.units=='q_A^-1':
                self.q = self.r
            elif self.units=='2th_deg':
                self.tth = self.r
                self.tth2q()
            self.writehdf5()

        except:
            print "Something is wrong with the actual integration..." 
            exit
        
    def tth2q(self):
        self.h = 6.620700406E-34;self.c = 3E8
        self.wavel = 1E10*6.242E18*self.h*self.c/(self.E*1E3)
        self.d = self.wavel/(2*sin(deg2rad(0.5*self.tth)))
        self.q = pi*2/self.d
            
    def writehdf5(self):
        self.hdf5_fn = "%s/%s_linescan_%.3d.hdf5" % (self.savepath, self.dataset, self.nextLine)
        h5f = h5py.File(self.hdf5_fn, "w")
        h5f.create_dataset('I', data=self.Int)
        h5f.create_dataset('q', data=self.q)
        if self.units=='2th_deg':
            h5f.create_dataset('twotheta', data=self.tth)
            h5f.create_dataset('d', data=self.d)
        h5f.close()
    	
        os.chdir(self.savepath)
        os.system('chmod 777 *.hdf5')
                 
    def checkForImageFile(self):
            
        if os.path.exists(self.nextimageFile) & (self.nextLine == 1):
            print('%s exists' % self.nextimageFile)
            self.periodEventraw.stop()
            self.writeLineData()
            self.setnextimageFile()       
        elif os.path.exists(self.nextimageFile) & (self.nextLine < self.nt+1) & os.path.exists(self.previoush5File):
            print('%s exists' % self.nextimageFile)
            self.periodEventraw.stop()
            self.writeLineData()
            self.setnextimageFile()     
        else: # keep looking
            print('%s' %self.nextimageFile ,'does not exist')
            print('or %s does not exist' % self.previoush5File)

    def writeLineData(self):

        self.json = "%s%s_%.4d.json" % (self.savepath, self.dataset, self.nextLine)
        print(self.json)
	
        self.creategpujson() # write the .json files
        self.gpuproc() # integrate the 2D diffraction patterns
            
    def setnextimageFile(self):
        self.nextLine += 1
        self.previoush5File =  "%s/%s_%.4d.azim.h5" % (self.savepath, self.dataset, self.nextLine-1)
        if self.nextLine < self.nt:
            self.nextimageFile =  "%s%s/%s_%.4d.cbf" % (self.xrdctpath, self.dataset, self.dataset, self.nextLine*self.na)
            print self.nextimageFile
            self.periodEventraw.start()
        elif self.nextLine == self.nt: #might need a sleep to give time to write the last image
            self.nextimageFile =  "%s%s/%s_%.4d.cbf" % (self.xrdctpath, self.dataset, self.dataset, self.nextLine*self.na-1)
            print self.nextimageFile
            self.periodEventraw.start()            
        else:
            print('All done')
            
        v = round((100*self.nextLine/self.nt))
        self.progress.emit(v) 
            
    def creategpujson(self):
        
        start=time.time()
        
        try:
            perm = 'chmod 777 %s.h5' %self.of
            os.system(perm)
        except:
            pass
        
        with open(self.jsonname, 'r') as f:
            data = json.load(f)
            data['poni_file'] = data['poni']
            data['do_SA'] = 0
            data['method'] = "ocl_csr_nosplit_gpu"
            
            data['npt'] = int(self.npt_rad)
#            data['npt_azim'] =  256
#            data['dummy'] = -10.0,
#            data['delta_dummy'] = 9.5            
			
            ####### Filters #########
            if self.filt == "No":
                data['plugin_name'] = 'id15.IntegrateManyFrames'
            elif self.filt == "Median":
                data['plugin_name'] = 'id15v2.IntegrateManyFrames'
                data['integration_method'] = "medfilt1d"
                data['percentile'] = 50
            elif self.filt == "trimmed_mean":
                data['plugin_name'] = 'id15v2.IntegrateManyFrames'
                data['integration_method'] = "medfilt1d"
                data['percentile'] = (round(float(self.prc)/2),100-round(float(self.prc)/2))         
            elif self.filt == "sigma":
                data['plugin_name'] = 'id15v2.IntegrateManyFrames'
                data['integration_method'] = "sigma_clip"                
                data['sigma_clip_thresold'] = float(self.thres)
                data['sigma_clip_max_iter'] = 5
            
    			# Number of xrd-ct dataset in the 3D scan
            for d in range(0, 1):  #range(self.ntomos, self.ntomos+1): 
                    #	da = '%s%.2d' %(self.dataset,d)
                da = '%s' %(self.dataset)
                cbfs = []
        
                filei = (self.na)*(self.nextLine-1)				
                filef = (self.na)*self.nextLine
                for ii in range(filei, filef):
                    if self.datatype == "cbf":
                        f = '%s_%.4d.cbf' % (da,ii)
                    elif self.datatype == "edf":
                        f = '%s_%.4d.edf' % (da,ii)
        
                    cbf = os.path.join(self.xrdctpath, da, f)
                    cbfs.append(cbf)
        
            data['input_files'] = cbfs
            of = '%s/%s_%.4d.azim' % (self.savepath, da, self.nextLine)
            data['output_file'] = of
            self.of = of
            print data['output_file']
        
        self.jsonfile = '%s_%.4d.json' % (da, self.nextLine)
        job = os.path.join( self.savepath, self.jsonfile)
        with open(job, 'w') as outfile:  
            json.dump(data, outfile)

        os.chdir(self.savepath)
        
        perm = 'chmod 777 %s' %self.jsonfile
        os.system(perm) 
        
        print time.time()-start
        
    def gpuproc(self):
        dahu = 'dahu-reprocess %s &' %self.jsonfile #### try with &
        print 'processing dataset %s' %self.jsonfile	
        os.system(dahu)

