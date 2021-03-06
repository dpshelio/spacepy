#!/usr/bin/env python
'''
Classes, functions, and methods for reading, writing, and plotting output
from the Ridley Ionosphere Model (RIM) and the similar legacy code, 
Ridley Serial.

Copyright 2010 Los Alamos National Security, LLC.
'''

import numpy as np
from spacepy.plot.apionly import set_target
from spacepy.pybats import PbData, dmarray

def fix_format(filename, finalize=True):
    '''
    Some 2D output files for RIM/RidleySerial have a broken format: values for
    the same lat-lon entry are split across two lines.  This function
    detects and fixes such files in-place.

    The original file will not be overwritten if kwarg *finalize* is set
    to **False**.

    Parameters
    ==========
    filename : str
       The file to repair.
    
    Other Parameters
    ================
    finalize : bool
       If **True**, overwrite the original file.  If **False**, perform a dry
       run for testing purposes.  Defaults to **True**.

    '''
    
    import os
    
    # Slurp in entire file.  This is necessary to detect the number of f.
    f = open(filename, 'r')
    raw = f.readlines()
    f.close()

    i = raw.index('NUMERICAL VALUES\n')
    nvars = int(raw[i+1].split()[0])
    ntheta= int(raw[i+2].split()[0])
    nphi  = int(raw[i+3].split()[0])

    # A broken file will have more than 4X lines than nTheta*nPhi.
    # This is because nLines = header + 2*nTheta*nPhi in a two-hemisphere file.
    if not len(raw) > 4*ntheta*nphi:
        return

    out = open('temp_iono_fix.txt', 'w')
    iNorth = raw.index('BEGIN NORTHERN HEMISPHERE\n')
    iSouth = raw.index('BEGIN SOUTHERN HEMISPHERE\n')
    
    # Rewrite header:
    out.writelines(raw[0:iNorth+1])

    # Rewrite northern hemisphere.
    for l1, l2 in zip(raw[iNorth+1:iSouth:2], raw[iNorth+2:iSouth:2]):
        out.write(l1.strip()+l2)

    # Rewrite southern hemisphere.
    out.write(raw[iSouth])
    for l1, l2 in zip(raw[iSouth+1::2], raw[iSouth+2::2]):
        out.write(l1.strip()+l2)

    out.close()

    # Move files.
    if finalize:
        os.remove(filename)
        os.rename(out.name, filename)

    return True

def get_iono_cb(ct_name='bwr'):
    '''
    Several custom colorbars used by RIM and AMIE have become standard when
    visualizing data from these models.  These are 'blue_white_red' and 
    'white_red', used for data that have positive and negative values and
    for data that have only positive values, respectively.  This function
    builds and returns these colorbars when called with the initials of the
    color table name as the only argument.

    Other Parameters
    ================
    ct_name : str
       Select the color table.  Can be 'bwr' for blue-white-red or 'wr' for
       white-red.  Defaults to 'bwr'.

    Examples
    ========
    >>> bwr_map = get_iono_cb('bwr')
    >>> wr_map  = get_iono_cb('wr')

    '''

    from matplotlib.colors import LinearSegmentedColormap as lsc

    if ct_name=='bwr':
        table = {
            'red':  [(0.,0.,.0),(.34,0.,0.),(.5,1.,1.),(1.,1.,1.)],
            'green':[(0.,0.,0.),(.35,1.,1.),(.66,1.,1.),(1.,0.,0.)],
            'blue' :[(0.,1.,1.),(.5,1.,1.),(.66,0.,0.),(.85,0.,0.),(1.,.1,.1)]
            }
        cmap = lsc('blue_white_red',table)
    elif ct_name=='wr':
        table = {
            'red':  [(0.,1.,1.),(1.,1.,1.)],
            'green':[(0.,1.,1.),(1.,0.,0.)],
            'blue' :[(0.,1.,1.),(1.,.0,.0)]
            }
        cmap = lsc('white_red',table)

    return cmap

def tex_label(varname):
    '''
    Many variable names used in the Ridley Ionosphere Model look much better
    in LaTeX format with their proper Greek letters.  This function takes
    a variable name, and if it is recognized, returns a properly formatted
    string that uses MatPlotLib's MathText functionality to display the 
    proper characters.  If it is not recognized, the varname is returned.

    Parameters
    ==========
    varname : string
       The variable to convert to a LaTeX label.

    Examples
    ========
    >>>tex_label('n_phi')
    '\\Phi_{Ionosphere}'
    >>>tex_label('Not Recognized')
    'Not Recognized'

    '''

    if varname[:2]=='n_' or varname[:2]=='s_':
        varname=varname[2:]
    
    known = {
        'phi': r'$\Phi_{Ionosphere}$',
        'sigmah':r'$\sigma_{Hall}$',
        'jr':r'$J_{radial}$',
        'mA/m^2':r'$mA/m^{2}$'
        }


    if varname in known:
        label = known[varname]
    else:
        label = varname

    return label

class Iono(PbData):
    '''
    A class for handling 2D output from the Ridley Ionosphere Model.
    Instantiate an object as follows:
    
    >>> iono = rim.Iono('filename.idl')

    ...where filename.idl is the name of a RIM 2D output file.
    '''

    def __init__(self, infile, *args, **kwargs):
        super(Iono, self).__init__(*args, **kwargs)
        self.attrs['file']=infile
        self.readascii()

    def readascii(self):
        '''
        Read an ascii ".idl" output file and load the contents into the object.
        '''
        
        import re
        import datetime as dt
        from numpy import zeros, reshape

        # slurp entire file.
        infile = open(self.attrs['file'], 'r')
        raw = infile.readlines()
        infile.close()

        # Parse header
        title = raw[raw.index('TITLE\n')+1]
        self.attrs['title'] = title[title.index('"')+1:title.rindex('"')]

        i = raw.index('NUMERICAL VALUES\n')
        self.attrs['nvars'] = int(raw[i+1].split()[0])
        self.attrs['ntheta']= int(raw[i+2].split()[0])
        self.attrs['nphi']  = int(raw[i+3].split()[0])

        # Convenience:
        nphi, ntheta = self.attrs['nphi'], self.attrs['ntheta']

        i = raw.index('TIME\n')
        self.attrs['time'] = dt.datetime(
            int(raw[i+1].split()[0]),      #year
            int(raw[i+2].split()[0]),      #month
            int(raw[i+3].split()[0]),      #day
            int(raw[i+4].split()[0]),      #hour
            int(raw[i+5].split()[0]),      #min
            int(raw[i+6].split()[0]),      #sec
            int(raw[i+7].split()[0])*1000  #microsec
            )

        i = raw.index('SIMULATION\n')
        self.attrs['iter']    =   int(raw[i+1].split()[0])
        self.attrs['simtime'] = float(raw[i+2].split()[0])

        i = raw.index('DIPOLE TILT\n')
        self.tilt = zeros(2)
        self.tilt[0] = float(raw[i+1].split()[0])
        self.tilt[1] = float(raw[i+2].split()[0])

        i = raw.index('VARIABLE LIST\n')
        namevar = []
        units   = {}
        for j in range(i+1,i+self.attrs['nvars']+1):
            match = re.match('\s*\d+\s+([\w\s\W]+)\[([\w\s\W]+)\]',raw[j])
            if match:
                name = (match.group(1).strip()).lower()
                namevar.append(name)
                units[name] = match.group(2).strip()
            else:
                raise ValueError('Could not parse %s' % raw[j])
                
            
        ### Read all data ###

        # Create data arrays
        nPts = self.attrs['ntheta']*self.attrs['nphi']
        for key in namevar:
            self['n_'+key] = dmarray(zeros(nPts), {'units':units[key]})
            self['s_'+key] = dmarray(zeros(nPts), {'units':units[key]})
        i = raw.index('BEGIN NORTHERN HEMISPHERE\n')+1
        # Fill data arrays
        for j, line in enumerate(raw[i:i+nPts]):
            parts = line.split()
            for k in range(self.attrs['nvars']):
                self['n_'+namevar[k]][j] = parts[k]
        i = raw.index('BEGIN SOUTHERN HEMISPHERE\n')+1
        for j, line in enumerate(raw[i:i+nPts]):
            parts = line.split()
            for k in range(self.attrs['nvars']):
                self['s_'+namevar[k]][j] = parts[k]

        # Create 2-D arrays.
        for key in namevar:
            nkey, skey = 'n_'+key, 's_'+key
            self[nkey] = reshape(self[nkey], (ntheta, nphi), 'F')
            self[skey] = reshape(self[skey], (ntheta, nphi), 'F')

    def add_cont(self, var, target=None, n=24, maxz=False, lines=True, 
                 cmap=False, add_cbar=False, label=None, loc=111,
                 xticksize=12, yticksize=12, **kwargs):
        '''
        Create a polar contour of variable *var*.  Plot will be either drawn
        on a new matplotlib figure and axes, or you can specify a plot target
        using the *target* kwarg.

        Parameters
        ==========
        var : str
           The name of the variable to plot.

        Returns
        =======
        fig : matplotlib figure object
        ax  : matplotlib axes object
        cnt : matplotlib contour object
        cb  : matplotlib colorbar object

        Other Parameters
        ================
        target : Figure or Axes
            If None (default), a new figure is generated from scratch.
            If a matplotlib Figure object, a new axis is created
            to fill that figure.
            If a matplotlib Axes object, the plot is placed
            into that axis.
        loc : int
            Use to specify the subplot placement of the axis
            (e.g. loc=212, etc.) Used if target is a Figure or None.
            Default 111 (single plot).
        n : int
            Set number of levels.  Should be a multiple of 3 for best match
            between filled and traced contours.  Default is 21.
        lines : bool
            Add unfilled black solid/dashed contours to plot for additional
            contrast.  Default is **True**.
        maxz : real
            Set the max/min value for the color bar.  Default is set by data.
        cmap : str
            Set the colormap.  Default is to autoselect using classic IE maps.
            Can be 'bwr', 'wr', or any name of a matplotlib colar map.
        add_cbar : bool
            Add colorbar to plot.  Default is **False** which will
            not add one to the plot.

        Extra keywords are passed to the contourf routine.

        '''
        # Get only what we need to decrease runtime.
        from math import pi
        from numpy import linspace
        from matplotlib.colors import Normalize
        from matplotlib.ticker import MaxNLocator, MultipleLocator
        from matplotlib.pyplot import clabel, colorbar

        fig, ax = set_target(target, polar=True, loc=loc)
        
        hemi = var[:2]

        # Set levels and ticks:
        if label==None:
            label=tex_label(var)
        lt_labels = ['06',    label, '18',   '00']
        xticks    = [   0,   pi/2,   pi, 3*pi/2]
        lct = MultipleLocator(10)
        minz = self[var].min()
        if minz < 0.0:
            if not maxz:
                maxz = max([abs(minz),self[var].max()])
            crange = Normalize(vmin=-1.*maxz, vmax=maxz)
            levs = linspace(-1.*maxz, maxz, n)
        else:
            if not maxz:
                maxz = self[var].max()
            crange = Normalize(vmin=0., vmax=maxz)
            levs = linspace(0., maxz, n)

        # Get color map if not given:
        if not cmap:
            if self[var].min() >= 0.0:
                cmap=get_iono_cb('wr')
            else:
                cmap=get_iono_cb('bwr')

        cnt1 = ax.contourf(self[hemi+'psi']*pi/180.0+pi/2., 
                           self[hemi+'theta'], np.array(self[var]),
                           levs, norm=crange, cmap=cmap)
        # Set xtick label size, increase font of top label.
        labels = ax.get_xticklabels()
        for l in labels: l.set_size(xticksize)
        labels[1].set_size(xticksize*1.25)
        
        if lines:
            nk = int(round(n/3.0))
            cnt2 = ax.contour(self[hemi+'psi']*pi/180.0+pi/2., 
                              self[hemi+'theta'], np.array(self[var]),
                              nk, colors='k')
            #clabel(cnt2,fmt='%3i',fontsize=10)

        if add_cbar:
            cbarticks = MaxNLocator(7)
            cbar = colorbar(cnt1, ticks=cbarticks, shrink=0.75, pad=0.08)
            cbar.set_label(tex_label(self[var].attrs['units']))
        else:
            cbar=False
        ax.set_xticks(xticks)
        ax.set_xticklabels(lt_labels)
        ax.yaxis.set_major_locator(lct)
        ax.set_ylim([0,40])

        # Use text function to manually add pretty ticks.
        ax.set_yticklabels('') # old ticks off.
        opts = {'size':yticksize, 'rotation':-45, 'ha':'center', 'va':'center'}
        for theta in [80.,70.,60.]:
            txt = '{:02.0f}'.format(theta)+r'$^{\circ}$'
            ax.text(pi/4., 90.-theta, txt, color='w', weight='heavy', **opts)
            ax.text(pi/4., 90.-theta, txt, color='k', weight='light', **opts)

        return fig, ax, cnt1, cbar
