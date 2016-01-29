from __future__ import print_function
import matplotlib
matplotlib.use('Agg')
import pylab as plt
import numpy as np

from astrometry.util.fits import *
from astrometry.util.plotutils import *

from legacypipe.common import *

def main():
    ps = PlotSequence('shotgun')

    decals = Decals()
    C = fits_table('decals-ccds-annotated.fits')
    print(len(C), 'CCDs')
    C.cut(C.photometric)
    C.cut(C.blacklist_ok)
    print(len(C), 'photometric and not blacklisted')
    C.cut(C.tilepass > 0)
    print(len(C), 'taken by DECaLS')

    targets = dict(g=24.0, r=23.4, z=22.5)

    def ivtomag(iv, nsigma=5.):
        return -2.5 * (np.log10(nsigma / np.sqrt(iv)) - 9)

    def band_index(band):
        allbands = 'ugrizY'
        return allbands.index(band)

    ccmap = dict(g='g', r='r', z='m')

    ceil_exptime = dict(g=125., r=125., z=250.)
    
    plt.clf()
    
    for band in 'grz':
        tmag = targets[band]
        print()
        print(band, 'band, target depth', tmag)
        ccds = C[C.filter == band]
        ccdarea = (2046*4094*(0.262/3600.)**2)
        print(len(ccds), 'CCDs, total exptime', np.sum(ccds.exptime),
              '(mean %.1f)' % np.mean(ccds.exptime), 'total area',
              len(ccds)*ccdarea, 'sq.deg')
        detsig1 = ccds.sig1 / ccds.galnorm_mean
        totiv = np.sum(1. / detsig1**2)
        # depth we would have if we had all exposure time in one CCD
        print('5-sigma galaxy depth if concentrated in one CCD:', ivtomag(totiv))
        # mean depth
        print('5-sigma galaxy depth if spread equally among', len(ccds), 'CCDs:', ivtomag(totiv / len(ccds)))
        print('vs median depth', np.median(ccds.galdepth))
        print('5-sigma galaxy depth if spread equally among %i/2' % (len(ccds)), 'CCDs:', ivtomag(totiv / (len(ccds)/2)))
        print('5-sigma galaxy depth if spread equally among %i/3' % (len(ccds)), 'CCDs:', ivtomag(totiv / (len(ccds)/3)))
        # spread over 6000 sq deg
        sqdeg = 6000
        avgiv = totiv * ccdarea / sqdeg
        print('5-sigma galaxy depth if spread over', sqdeg, 'sqdeg:', ivtomag(avgiv))

        tflux = 10.**(tmag / -2.5 + 9)
        tiv = 1. / (tflux / 5)**2
        print('Fraction of', sqdeg, 'sqdeg survey complete:', avgiv / tiv)

        iband = band_index(band)
        ext = ccds.decam_extinction[:,iband]
        medext = np.median(ext)
        print('With extinction (median %.2f mag):' % medext)

        transmission = 10.**(-ext / 2.5)

        detsig1 = ccds.sig1 / ccds.galnorm_mean / transmission
        totiv = np.sum(1. / detsig1**2)
        # depth we would have if we had all exposure time in one CCD
        print('5-sigma galaxy depth if concentrated in one CCD:', ivtomag(totiv))
        # mean depth
        print('5-sigma galaxy depth if spread equally among', len(ccds), 'CCDs:', ivtomag(totiv / len(ccds)))
        print('vs median depth', np.median(ccds.galdepth - ext))
        print('5-sigma galaxy depth if spread equally among %i/2' % (len(ccds)), 'CCDs:', ivtomag(totiv / (len(ccds)/2)))
        print('5-sigma galaxy depth if spread equally among %i/3' % (len(ccds)), 'CCDs:', ivtomag(totiv / (len(ccds)/3)))
        # spread over 6000 sq deg
        sqdeg = 6000
        avgiv = totiv * ccdarea / sqdeg
        print('5-sigma galaxy depth if spread over', sqdeg, 'sqdeg:', ivtomag(avgiv))
        print('Fraction of', sqdeg, 'sqdeg survey complete:', avgiv / tiv)

        plt.hist(ccds.exptime, bins=25, histtype='step', color=ccmap[band])

        I = np.flatnonzero(ccds.exptime < (ceil_exptime[band] - 1.))
        ccds.cut(I)
        print('Cutting out exposures with ceil exposure time:', len(ccds))

        plt.hist(ccds.exptime, bins=25, histtype='step', color=ccmap[band],
                 linestyle='dotted', linewidth=3, alpha=0.3)

        transmission = transmission[I]
        ext = ext[I]
        
        detsig1 = ccds.sig1 / ccds.galnorm_mean / transmission
        totiv = np.sum(1. / detsig1**2)
        # depth we would have if we had all exposure time in one CCD
        print('5-sigma galaxy depth if concentrated in one CCD:', ivtomag(totiv))
        # mean depth
        print('5-sigma galaxy depth if spread equally among', len(ccds), 'CCDs:', ivtomag(totiv / len(ccds)))
        print('vs median depth', np.median(ccds.galdepth - ext))
        print('5-sigma galaxy depth if spread equally among %i/2' % (len(ccds)), 'CCDs:', ivtomag(totiv / (len(ccds)/2)))
        print('5-sigma galaxy depth if spread equally among %i/3' % (len(ccds)), 'CCDs:', ivtomag(totiv / (len(ccds)/3)))
        # spread over 6000 sq deg
        sqdeg = 6000
        avgiv = totiv * ccdarea / sqdeg
        print('5-sigma galaxy depth if spread over', sqdeg, 'sqdeg:', ivtomag(avgiv))
        print('Fraction of', sqdeg, 'sqdeg survey complete:', avgiv / tiv)

        

        
    plt.xlabel('Exposure time (s)')
    ps.savefig()
        
    print()

    ralo  = max(  0, min(C.ra_center  - C.dra ))
    rahi  = min(360, max(C.ra_center  + C.dra ))
    declo = max(-90, min(C.dec_center - C.ddec))
    dechi = min( 90, max(C.dec_center + C.ddec))

    # brick 0001m002
    ralo,rahi = 0., 0.25
    declo,dechi = -0.375, -0.125
    
    print('RA,Dec range', (ralo, rahi), (declo, dechi))

    N = 10000

    nbatch = 1000
    rr,dd = [],[]
    ntotal = 0
    while ntotal < N:
        ru = np.random.uniform(size=nbatch)
        d = np.random.uniform(low=declo, high=dechi, size=nbatch)
        # Taper the accepted width in RA based on Dec
        cosd = np.cos(np.deg2rad(d))
        I = np.flatnonzero(ru < cosd)
        if len(I) == 0:
            continue
        r = ralo + (rahi - ralo) * ru[I]/cosd[I]
        d = d[I]
        rr.append(r)
        dd.append(d)
        ntotal += len(r)
        print('Kept', len(r), 'of', nbatch)

    ra  = np.hstack(rr)
    dec = np.hstack(dd)
    del rr
    del dd
    ra  = ra[:N]
    dec = dec[:N]
    
    plt.clf()
    plt.plot(ra, dec, 'b.', alpha=0.1)
    ps.savefig()

        
if __name__ == '__main__':
    main()