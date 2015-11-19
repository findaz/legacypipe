from __future__ import print_function
import numpy as np

from astrometry.util.fits import fits_table, merge_tables
from astrometry.util.starutil_numpy import degrees_between
from astrometry.util.util import Tan
from astrometry.util.miscutils import polygon_area
from legacypipe.common import Decals
import tractor

def main():
    decals = Decals()
    ccds = decals.get_ccds()

    print("HACK!")
    ccds.cut(np.array([name in ['N15', 'N16', 'N21', 'N9']
                       for name in ccds.ccdname]) *
                       ccds.expnum == 229683)
    
    I = decals.photometric_ccds(ccds)
    ccds.photometric = np.zeros(len(ccds), bool)
    ccds.photometric[I] = True

    I = decals.apply_blacklist(ccds)
    ccds.blacklist_ok = np.zeros(len(ccds), bool)
    ccds.blacklist_ok[I] = True

    ccds.good_region = np.empty((len(ccds), 4), np.int16)
    ccds.good_region[:,:] = -1

    ccds.ra0  = np.zeros(len(ccds), np.float64)
    ccds.dec0 = np.zeros(len(ccds), np.float64)
    ccds.ra1  = np.zeros(len(ccds), np.float64)
    ccds.dec1 = np.zeros(len(ccds), np.float64)
    ccds.ra2  = np.zeros(len(ccds), np.float64)
    ccds.dec2 = np.zeros(len(ccds), np.float64)
    ccds.ra3  = np.zeros(len(ccds), np.float64)
    ccds.dec3 = np.zeros(len(ccds), np.float64)

    ccds.dra  = np.zeros(len(ccds), np.float32)
    ccds.ddec = np.zeros(len(ccds), np.float32)
    ccds.ra_center  = np.zeros(len(ccds), np.float64)
    ccds.dec_center = np.zeros(len(ccds), np.float64)

    ccds.meansky = np.zeros(len(ccds), np.float32)
    ccds.stdsky  = np.zeros(len(ccds), np.float32)
    ccds.maxsky  = np.zeros(len(ccds), np.float32)
    ccds.minsky  = np.zeros(len(ccds), np.float32)

    ccds.pixscale_mean = np.zeros(len(ccds), np.float32)
    ccds.pixscale_std  = np.zeros(len(ccds), np.float32)
    ccds.pixscale_max  = np.zeros(len(ccds), np.float32)
    ccds.pixscale_min  = np.zeros(len(ccds), np.float32)

    ccds.psfnorm_mean = np.zeros(len(ccds), np.float32)
    ccds.psfnorm_std  = np.zeros(len(ccds), np.float32)
    ccds.galnorm_mean = np.zeros(len(ccds), np.float32)
    ccds.galnorm_std  = np.zeros(len(ccds), np.float32)

    # 2nd moments
    ccds.psf_mx2 = np.zeros(len(ccds), np.float32)
    ccds.psf_my2 = np.zeros(len(ccds), np.float32)
    ccds.psf_mxy = np.zeros(len(ccds), np.float32)
    #
    ccds.psf_a = np.zeros(len(ccds), np.float32)
    ccds.psf_b = np.zeros(len(ccds), np.float32)
    ccds.psf_theta = np.zeros(len(ccds), np.float32)
    ccds.psf_ell   = np.zeros(len(ccds), np.float32)


    ccds.humidity = np.zeros(len(ccds), np.float32)
    ccds.outtemp  = np.zeros(len(ccds), np.float32)

    '''
    Bitfield to summarize CCD-level errors thrown by the pipeline or
    perhaps concerns raised by the observers? E.g., how is the
    photometricity or cloudiness recorded?

    Do we need to associate exposures to passes? This is not always
    defined.
    '''
    
    for iccd,ccd in enumerate(ccds):
        im = decals.get_image_object(ccd)

        X = im.get_good_image_subregion()
        for i,x in enumerate(X):
            if x is not None:
                ccds.good_region[iccd,i] = x

        W,H = ccd.width, ccd.height
                
        psf = None
        wcs = None
        sky = None
        try:
            psf = im.read_psf_model(0, 0, pixPsf=True)
            wcs = im.read_pv_wcs()
            sky = im.read_sky_model(splinesky=True)

            hdr = im.read_image_primary_header()

        except:
            import traceback
            traceback.print_exc()
            continue
            
        print('Got PSF', psf)
        print('Got sky', sky)
        print('Got WCS', wcs)

        ccds.humidity[iccd] = hdr.get('HUMIDITY')
        ccds.outtemp[iccd]  = hdr.get('OUTTEMP')
        
        # Need a tim to instantiate PSF... well, actually the galaxy norm
        # requires WCS & photocal.
        # sig1 ?!
        pcal = tractor.LinearPhotoCal(1., band=ccd.filter)
        faketim = tractor.Image(data=np.zeros((H,W), np.float32),
                                inverr=np.ones((H,W), np.float32),
                                psf=psf, wcs=tractor.ConstantFitsWcs(wcs),
                                photocal=pcal)
        faketim.band = ccd.filter
            
        #tim = im.get_tractor_image(pixPsf=True, splinesky=True,
        #                           subsky=False, pixels=False)
            
        # Instantiate PSF on a grid
        S = 32
        xx = np.linspace(1+S, W-S, 5)
        yy = np.linspace(1+S, H-S, 5)
        xx,yy = np.meshgrid(xx, yy)
        psfnorms = []
        galnorms = []
        for x,y in zip(xx.ravel(), yy.ravel()):
            p = im.psf_norm(faketim, x=x, y=y)
            g = im.galaxy_norm(faketim, x=x, y=y)
            psfnorms.append(p)
            galnorms.append(g)
        ccds.psfnorm_mean[iccd] = np.mean(psfnorms)
        ccds.psfnorm_std [iccd] = np.std (psfnorms)
        ccds.galnorm_mean[iccd] = np.mean(galnorms)
        ccds.galnorm_std [iccd] = np.std (galnorms)

        # PSF in center of field
        cx,cy = (W+1)/2., (H+1)/2.
        p = psf.getPointSourcePatch(cx, cy).patch
        ph,pw = p.shape
        px,py = np.meshgrid(np.arange(pw), np.arange(ph))
        psum = np.sum(p)
        print('psum', psum)
        p /= psum
        # centroids
        cenx = np.sum(p * px)
        ceny = np.sum(p * py)
        print('cenx,ceny', cenx,ceny)
        # second moments
        x2 = np.sum(p * (px - cenx)**2)
        y2 = np.sum(p * (py - ceny)**2)
        xy = np.sum(p * (px - cenx)*(py - ceny))
        # semi-major/minor axes and position angle
        theta = np.rad2deg(np.arctan2(2 * xy, x2 - y2) / 2.)
        theta = np.abs(theta) * np.sign(xy)
        s = np.sqrt(((x2 - y2)/2.)**2 + xy**2)
        a = np.sqrt((x2 + y2) / 2. + s)
        b = np.sqrt((x2 + y2) / 2. - s)
        ell = 1. - b/a

        print('PSF second moments', x2, y2, xy)
        print('PSF position angle', theta)
        print('PSF semi-axes', a, b)
        print('PSF ellipticity', ell)

        ccds.psf_mx2[iccd] = x2
        ccds.psf_my2[iccd] = y2
        ccds.psf_mxy[iccd] = xy
        ccds.psf_a[iccd] = a
        ccds.psf_b[iccd] = b
        ccds.psf_theta[iccd] = theta
        ccds.psf_ell  [iccd] = ell
        
        # Sky
        mod = np.zeros((ccd.height, ccd.width), np.float32)
        sky.addTo(mod)
        ccds.meansky[iccd] = np.mean(mod)
        ccds.stdsky[iccd]  = np.std(mod)
        ccds.maxsky[iccd]  = mod.max()
        ccds.minsky[iccd]  = mod.min()

        # WCS
        ccds.ra0[iccd],ccds.dec0[iccd] = wcs.pixelxy2radec(1, 1)
        ccds.ra1[iccd],ccds.dec1[iccd] = wcs.pixelxy2radec(1, H)
        ccds.ra2[iccd],ccds.dec2[iccd] = wcs.pixelxy2radec(W, H)
        ccds.ra3[iccd],ccds.dec3[iccd] = wcs.pixelxy2radec(W, 1)

        midx, midy = (W+1)/2., (H+1)/2.
        rc,dc  = wcs.pixelxy2radec(midx, midy)
        ra,dec = wcs.pixelxy2radec([1,W,midx,midx], [midy,midy,1,H])
        ccds.dra [iccd] = max(degrees_between(ra, dc+np.zeros_like(ra),
                                              rc, dc))
        ccds.ddec[iccd] = max(degrees_between(rc+np.zeros_like(dec), dec,
                                              rc, dc))
        ccds.ra_center [iccd] = rc
        ccds.dec_center[iccd] = dc

        # Compute scale change across the chip
        # how many pixels to step
        step = 10
        xx = np.linspace(1+step, W-step, 5)
        yy = np.linspace(1+step, H-step, 5)
        xx,yy = np.meshgrid(xx, yy)
        pixscale = []
        for x,y in zip(xx.ravel(), yy.ravel()):
            sx = [x-step, x-step, x+step, x+step, x-step]
            sy = [y-step, y+step, y+step, y-step, y-step]
            sr,sd = wcs.pixelxy2radec(sx, sy)
            rc,dc = wcs.pixelxy2radec(x, y)
            # project around a tiny little TAN WCS at (x,y), with 1" pixels
            locwcs = Tan(rc, dc, 0., 0., 1./3600, 0., 0., 1./3600, 1., 1.)
            ok,lx,ly = locwcs.radec2pixelxy(sr, sd)
            #print('local x,y:', lx, ly)
            A = polygon_area((lx, ly))
            pixscale.append(np.sqrt(A / (2*step)**2))
        # print('Pixel scales:', pixscale)
        ccds.pixscale_mean[iccd] = np.mean(pixscale)
        ccds.pixscale_min[iccd] = min(pixscale)
        ccds.pixscale_max[iccd] = max(pixscale)
        ccds.pixscale_std[iccd] = np.std(pixscale)
            
    ccds.writeto('ccds-annotated.fits')


if __name__ == '__main__':
    import sys
    sys.exit(main())