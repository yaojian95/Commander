import os

import os
os.environ["OMP_NUM_THREADS"] = "64" # export OMP_NUM_THREADS=4
os.environ["OPENBLAS_NUM_THREADS"] = "64" # export OPENBLAS_NUM_THREADS=4 
os.environ["MKL_NUM_THREADS"] = "64" # export MKL_NUM_THREADS=6
os.environ["VECLIB_MAXIMUM_THREADS"] = "64" # export VECLIB_MAXIMUM_THREADS=4
os.environ["NUMEXPR_NUM_THREADS"] = "64" # export NUMEXPR_NUM_THREADS=6
os.environ["MKL_INTERFACE_LAYER"]="ILP64"

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import healpy as hp
import h5py

import huffman

from multiprocessing import Pool

from time import time
from tqdm import tqdm


from scipy import sparse
import sys
from glob import glob

import cmasher as cmr
cmap = cmr.pride
cmap ='RdBu_r'

import warnings
warnings.filterwarnings("ignore")

from sparse_dot_mkl import dot_product_mkl, gram_matrix_mkl


# Fixed the coordinate transformation
version = 13

def make_dipole(amp, lon, lat, nside):
    vec = hp.ang2vec(lon, lat, lonlat=True)
    x,y,z = hp.pix2vec(nside, np.arange(hp.nside2npix(nside)))
    dip_map = x*vec[0] + y*vec[1] + z*vec[2]
    return dip_map*amp

def cg_solve(A, b, M_diag, imax=1000, eps=1e-6):
    p = (M_diag != 0)
    x = np.zeros_like(b)
    s = np.zeros_like(b)
    i = 0
    r = b - A.dot(x)
    d = np.zeros_like(b)
    d[p] = (r/M_diag)[p]
    delta_new = r.dot(d)
    delta_old = np.copy(delta_new)
    delta_0 = r.dot(d)
    while ((i < imax) & (delta_new > eps**2*delta_0) & (delta_new <= delta_old)):
        q = A.dot(d)
        alpha = delta_new/d.dot(q)
        x = x + alpha*d
        if (i % 50 == 0):
            r = b - A.dot(x)
        else:
            r = r - alpha*q
        s[p] = (r/M_diag)[p]
        delta_old = np.copy(delta_new)
        delta_new = r.dot(s)
        beta = delta_new/delta_old
        d = s + beta*d
        i += 1
    return x


def cg_test():
    A = np.array([[3,2],
                  [2,6]])
    b = np.array([2,-8])
    Minv = np.eye(2)

    x = cg_solve(A, b, Minv)
    assert np.allclose(A.dot(x), b), 'CG solution is not close enough'
    return

def get_data(fname, band, xbar, dxbar, nside=256, pol=False, mask=True):

    # From Planck 2019 I
    #dipoles = {'cobe':[3.358,  264.31,  48.05],
    #           'wmap':[3.355,  263.99,  48.26],
    #           'pl15':[3.3645, 264.00,  48.24],
    #           'lf18':[3.3644, 263.998, 48.265],
    #           'hf18':[3.3621, 264.021, 48.253],
    #           'pl18':[3.3621, 264.021, 48.253]}
    #amp, lon, lat = dipoles['cobe']
    #dipole = make_dipole(amp, lon, lat, nside)


    ntodsigma = 100
    npix = hp.nside2npix(nside)
    M = np.zeros(npix)
    b = np.zeros(npix)
    if pol:
        M_q = np.zeros(npix)
        b_q = np.zeros(npix)
        M_u = np.zeros(npix)
        b_u = np.zeros(npix)
        M_s = np.zeros(npix)
        b_s = np.zeros(npix)
    labels = [f'{band}13', f'{band}14',f'{band}23',f'{band}24']
    f= h5py.File(fname, 'r')
    obsid = str(list(f.keys())[0])
    huffTree = f[obsid+'/common/hufftree']
    huffSymb = f[obsid+'/common/huffsymb']
    h = huffman.Huffman(tree=huffTree, symb=huffSymb)



    '''
    TOD0 = np.array(f[obsid + '/' + labels[0] + '/tod'])
    if band == 'K1':
        if len(TOD0) != 675000:
            print(f'{fname} has wrong length')
            return None
    elif band == 'V1':
        if len(TOD0) != 1125000:
            print(f'{fname} has wrong length')
            return None
    '''
    
    DAs = [[], [], [], []]
    flags = [[], [], [], []]
    sigmas = []
    gains = np.zeros(len(labels))
    npsi = 2048
    psiBins = np.linspace(0, 2*np.pi, npsi)
    for num, label in enumerate(labels):
        TODs = np.array(f[obsid + '/' + label + '/tod'])
        scalars = f[obsid + '/' + label + '/scalars']
        gains[num] = scalars[0]
        #TODs = TODs - np.median(TODs)
        flag = h.Decoder(np.array(f[obsid + '/' + label + '/flag']))
        flags[num] = flags[num] + flag.tolist()
        DAs[num] = DAs[num] + TODs.tolist()
        sigmas.append(TODs.std())
        if label == f'{band}13':
            pixA = h.Decoder(np.array(f[obsid + '/' + label + \
                '/pixA'])).astype('int')
            pixB = h.Decoder(np.array(f[obsid + '/' + label + \
                '/pixB'])).astype('int')
            if pol:
                psiA = psiBins[h.Decoder(np.array(f[obsid + '/' + label + \
                    '/psiA'])).astype('int')]
                psiB = psiBins[h.Decoder(np.array(f[obsid + '/' + label + \
                    '/psiB'])).astype('int')]
    # bit array; bit 0 means data is suspect, bit 12 means Mars in AB, etc. til
    # 10. I think I'll just try to get rid of all data where there are any
    # planets in the beam, although i think the official release tried to use as
    # much data as possible, i.e., only cutting out the center.
    flags = np.array(flags).sum(axis=0)
    inds = (flags == 0)
    #inds = np.isfinite(flags)

    DAs = np.array(DAs)/gains.reshape(4,1)
    #sigma0 = np.mean(np.array(sigmas)**2)**0.5


    
    d1 = 0.5*(DAs[0] + DAs[1])
    d2 = 0.5*(DAs[2] + DAs[3])

    n1 = 0.5*(DAs[0] - DAs[1])
    n2 = 0.5*(DAs[2] - DAs[3])

    n = 0.5*(n1+n2)
    sigma0 = n.std()
    
    d = 0.5*(d1 + d2) # = i_A - i_B
    p = 0.5*(d1 - d2) # = q_A*cos(2*g_A) + u_A*sin(2*g_A) - q_B*cos(2*g_B) - u_B*sin(2*g_B)

    # subtract dipole solution from d
    #d = d - ((1*xbar)*dipole[pixA] - (1-xbar)*dipole[pixB])
    

    # most aggressive mask
    if mask:
        pm = hp.read_map('analysis_masks/wmap_processing_mask_K_yr2_r9_9yr_v5.fits',
                verbose=False, dtype=None)
        pm = hp.ud_grade(pm, nside)
    else:
        pm = np.ones(npix)

    pA = pm[pixA]
    pB = pm[pixB]
    f_A = (1 - pA*(1-pB))*inds
    f_B = (1 - pB*(1-pA))*inds
    p_hi = (pA==0) | (pB==0)
    p_lo = (pA==1) & (pB==1)
    sigma_hi = n[p_hi].std()
    sigma_lo = n[p_lo].std()


    sigmas = []
    for t in range(len(d)):
        '''
        Asymmetric masking means that when one beam is in a high Galactic
        emission region (as determined by a processing mask; Limon et al. 2010)
        and the other beam is in a low Galactic emission region, only the pixel
        in the high emission region is iteratively updated.
        # pm == 0 means it is in a high emission region
        '''
        if ((pm[pixA[t]] == 0) or (pm[pixB[t]] == 0)):
            b[pixA[t]] = b[pixA[t]] + f_A[t]*(1+xbar)*d[t]/sigma_hi**2
            b[pixB[t]] = b[pixB[t]] - f_B[t]*(1-xbar)*d[t]/sigma_hi**2

            M[pixA[t]] += f_A[t]*(1+xbar)**2/sigma_hi**2
            M[pixB[t]] += f_B[t]*(1-xbar)**2/sigma_hi**2
            sigmas.append(sigma_hi)
            if pol:
                b[pixA[t]] += f_A[t]*dxbar*p[t]/sigma_hi**2
                b[pixB[t]] += f_B[t]*dxbar*p[t]/sigma_hi**2
                b_q[pixA[t]] += f_A[t]*((1+xbar)*p[t] + dxbar*d[t])*np.cos(2*psiA[t])/sigma_hi**2
                b_q[pixB[t]] -= f_B[t]*((1-xbar)*p[t] - dxbar*d[t])*np.cos(2*psiB[t])/sigma_hi**2
                b_u[pixA[t]] += f_A[t]*((1+xbar)*p[t] + dxbar*d[t])*np.sin(2*psiA[t])/sigma_hi**2
                b_u[pixB[t]] -= f_B[t]*((1-xbar)*p[t] - dxbar*d[t])*np.sin(2*psiB[t])/sigma_hi**2
                b_s[pixA[t]] += f_A[t]*(dxbar*d[t] + (1+xbar)*p[t])/sigma_hi**2
                b_s[pixB[t]] += f_B[t]*(dxbar*d[t] - (1-xbar)*p[t])/sigma_hi**2


                M_q[pixA[t]] += f_A[t]*(((1+xbar) + dxbar)*np.cos(2*psiA[t]))**2/sigma_hi**2
                M_q[pixB[t]] += f_B[t]*(((1-xbar) - dxbar)*np.cos(2*psiB[t]))**2/sigma_hi**2
                M_u[pixA[t]] += f_A[t]*(((1+xbar) + dxbar)*np.sin(2*psiA[t]))**2/sigma_hi**2
                M_u[pixB[t]] += f_B[t]*(((1-xbar) +-dxbar)*np.sin(2*psiB[t]))**2/sigma_hi**2
                M_s[pixA[t]] += f_A[t]*(dxbar + (1+xbar))**2/sigma_hi**2
                M_s[pixB[t]] += f_B[t]*(dxbar - (1-xbar))**2/sigma_hi**2
        if ((pm[pixA[t]] == 1) and (pm[pixB[t]] == 1)):
            b[pixA[t]] = b[pixA[t]] + f_A[t]*(1+xbar)*d[t]/sigma_lo**2
            b[pixB[t]] = b[pixB[t]] - f_B[t]*(1-xbar)*d[t]/sigma_lo**2

            M[pixA[t]] += f_A[t]*(1+xbar)**2/sigma_lo**2
            M[pixB[t]] += f_B[t]*(1-xbar)**2/sigma_lo**2
            sigmas.append(sigma_lo)
            if pol:
                b[pixA[t]] += f_A[t]*dxbar*p[t]/sigma_lo**2
                b[pixB[t]] += f_B[t]*dxbar*p[t]/sigma_lo**2
                b_q[pixA[t]] += f_A[t]*((1+xbar)*p[t] + dxbar*d[t])*np.cos(2*psiA[t])/sigma_lo**2
                b_q[pixB[t]] -= f_B[t]*((1-xbar)*p[t] - dxbar*d[t])*np.cos(2*psiB[t])/sigma_lo**2
                b_u[pixA[t]] += f_A[t]*((1+xbar)*p[t] + dxbar*d[t])*np.sin(2*psiA[t])/sigma_lo**2
                b_u[pixB[t]] -= f_B[t]*((1-xbar)*p[t] - dxbar*d[t])*np.sin(2*psiB[t])/sigma_lo**2
                b_s[pixA[t]] += f_A[t]*(dxbar*d[t] + (1+xbar)*p[t])/sigma_lo**2
                b_s[pixB[t]] += f_B[t]*(dxbar*d[t] - (1-xbar)*p[t])/sigma_lo**2


                M_q[pixA[t]] += f_A[t]*(((1+xbar) + dxbar)*np.cos(2*psiA[t]))**2/sigma_lo**2
                M_q[pixB[t]] += f_B[t]*(((1-xbar) - dxbar)*np.cos(2*psiB[t]))**2/sigma_lo**2
                M_u[pixA[t]] += f_A[t]*(((1+xbar) + dxbar)*np.sin(2*psiA[t]))**2/sigma_lo**2
                M_u[pixB[t]] += f_B[t]*(((1-xbar) +-dxbar)*np.sin(2*psiB[t]))**2/sigma_lo**2
                M_s[pixA[t]] += f_A[t]*(dxbar + (1+xbar))**2/sigma_lo**2
                M_s[pixB[t]] += f_B[t]*(dxbar - (1-xbar))**2/sigma_lo**2


    if pol:
        b_p = np.concatenate((b_q, b_u, b_s))
        M_p = np.concatenate((M_q, M_u, M_s))


    if pol:
        return M, b, M_p, b_p, pixA, pixB, psiA, psiB, sigmas, f_A, f_B
    else:
        return M, b, pixA, pixB, sigmas, f_A, f_B

def inner_productdq(t):
    global d, sigma0s, pixA, pixB
    dq = (d[pixA[t]] - d[pixB[t]])/sigma0s[t]*2
    return pixA[t], pixB[t], dq

def inner_productxr(t):
    global x, sigma0s, pixA, pixB
    dr = (x[pixA[t]] - x[pixB[t]])/sigma0s[t]**2
    return pixA[t], pixB[t], dr

def inner_product(pixA, pixB, dA, dB, sigma0, sign=1):
    dq = (dA - dB)*sign
    return pixA, pixB, dq

def innerproduct_pol(pixA, pixB, psiA, psiB, f_A, f_B, xbar, dxbar, x, nside=256):
    # Evalaluate y = (P^t Ninv P) x
    T,Q,U,S = np.split(x, 4)
    T_,Q_,U_,S_ = np.split(x*0, 4)
    for t in tqdm(range(len(pixA))):
        Px_d = (1+xbar)*T[pixA[t]] - (1-xbar)*T[pixB[t]] +\
                dxbar*(Q[pixA[t]]*np.cos(2*psiA[t]) + Q[pixB[t]]*np.cos(2*psiB[t])) +\
                dxbar*(U[pixA[t]]*np.sin(2*psiA[t]) + U[pixB[t]]*np.sin(2*psiB[t])) +\
                dxbar*(S[pixA[t]] + S[pixB[t]])
        Px_p = dxbar*(T[pixA[t]] + T[pixB[t]]) +\
                (1+xbar)*Q[pixA[t]]*np.cos(2*psiA[t]) - (1-xbar)*Q[pixB[t]]*np.cos(psiB[t]) +\
                (1+xbar)*U[pixA[t]]*np.sin(2*psiA[t]) - (1-xbar)*U[pixB[t]]*np.sin(psiB[t]) +\
                (1+xbar)*S[pixA[t]] - (1-xbar)*S[pixB[t]]
        T_[pixA[t]] += f_A[t]*( (1+xbar)*Px_d + dxbar*Px_p)
        T_[pixB[t]] += f_B[t]*(-(1-xbar)*Px_d + dxbar*Px_p)
        Q_[pixA[t]] += f_A[t]*(np.cos(2*psiA[t])*(dxbar*Px_d + (1+xbar)*Px_p))
        Q_[pixB[t]] += f_B[t]*(np.cos(2*psiB[t])*(dxbar*Px_d - (1-xbar)*Px_p))
        U_[pixA[t]] += f_A[t]*(np.sin(2*psiA[t])*(dxbar*Px_d + (1+xbar)*Px_p))
        U_[pixB[t]] += f_B[t]*(np.sin(2*psiB[t])*(dxbar*Px_d - (1-xbar)*Px_p))
        S_[pixA[t]] += f_A[t]*(dxbar*Px_d + (1+xbar)*Px_p )
        S_[pixB[t]] += f_B[t]*(dxbar*Px_d - (1-xbar)*Px_p )

    return np.concatenate((T_,Q_,U_,S_))

def innerproduct_pol_t(pixA, pixB, psiA, psiB, f_A, f_B, xbar, dxbar, x, nside=256):
    # Evalaluate y = (P^t Ninv P) x
    T,Q,U,S = np.split(x, 4)
    T_,Q_,U_,S_ = np.split(x*0, 4)
    Px_d = (1+xbar)*T[pixA] - (1-xbar)*T[pixB] +\
            dxbar*(Q[pixB]*np.cos(2*psiA) + Q[pixB]*np.cos(2*psiB)) +\
            dxbar*(U[pixB]*np.sin(2*psiA) + U[pixB]*np.sin(2*psiB)) +\
            dxbar*(S[pixB] + S[pixB])
    Px_p = dxbar*(T[pixB] + T[pixB]) +\
            (1+xbar)*Q[pixB]*np.cos(2*psiA) - (1-xbar)*Q[pixB]*np.cos(psiB) +\
            (1+xbar)*U[pixB]*np.sin(2*psiA) - (1-xbar)*U[pixB]*np.sin(psiB) +\
            (1+xbar)*S[pixB] - (1-xbar)*S[pixB]
    T_[pixB] += f_A*( (1+xbar)*Px_d + dxbar*Px_p)
    T_[pixB] += f_B*(-(1-xbar)*Px_d + dxbar*Px_p)
    Q_[pixB] += f_A*(np.cos(2*psiA)*(dxbar*Px_d + (1+xbar)*Px_p))
    Q_[pixB] += f_B*(np.cos(2*psiB)*(dxbar*Px_d - (1-xbar)*Px_p))
    U_[pixB] += f_A*(np.sin(2*psiA)*(dxbar*Px_d + (1+xbar)*Px_p))
    U_[pixB] += f_B*(np.sin(2*psiB)*(dxbar*Px_d - (1-xbar)*Px_p))
    S_[pixB] += f_A*(dxbar*Px_d + (1+xbar)*Px_p )
    S_[pixB] += f_B*(dxbar*Px_d - (1-xbar)*Px_p )

    return np.concatenate((T_,Q_,U_,S_))


def get_cg(band='K1', nside=256, nfiles=200, sparse_test=False,
        sparse_only=False, pol=False, imbalance=True, mask=True,
        imax = 3000,
        eps = 1e-16,
        ):

    imax = min(imax, nfiles)

    # There are gain imbalance parameters that need to be included in the
    # mapmaking. I don't think this fits in with the hdf5 files, so I'll include
    # them here. This is from Bennett et al. (2013) Table 1.

    allbands = ['K1', 'Ka1', 'Q1', 'Q2', 'V1', 'V2', 'W1', 'W2', 'W3', 'W4']

    x_im = np.array([-0.00067, 0.00536, 0.00353, 0.00154,
                     -0.00013, 0.00414, 0.00756, 0.00986,
                      0.00053, 0.00250, 0.00352, 0.00245,
                      0.01134, 0.00173, 0.01017, 0.01142,
                     -0.00122, 0.00463, 0.02311, 0.02054])
    x_bar = (x_im[::2] + x_im[1::2])/2
    dxbar = (x_im[::2] - x_im[1::2])/2

    xbar = {b:x for b, x in zip(allbands, x_bar)}
    dxbar = {b:dx for b, dx in zip(allbands, dxbar)}

    if imbalance:
        xbar = xbar[band]
        dxbar = dxbar[band]
    else:
        xbar = 0
        dxbar = 0



    global x, d, sigma0s, pixA, pixB
    npix = hp.nside2npix(nside)
    b = np.zeros(npix)
    b_full = np.zeros(npix)
    M_diag = np.zeros(npix)
    M_diag_full = np.zeros(npix)
    if pol:
        b_p = np.zeros(3*npix)
        M_diag_p = np.zeros(3*npix)

    fnames = glob(f'/mn/stornext/d16/cmbco/bp/wmap/data/wmap_{band}_*v{version}.h5')
    fnames.sort()
    if ~np.isfinite(nfiles):
        fnames = fnames
    elif nfiles == 1:
        fnames = [fnames[0]]
    elif nfiles < 200:
        np.random.seed(137)
        fnames = np.random.choice(fnames, nfiles, replace=False)
    elif nfiles < len(fnames):
        np.random.seed(137)
        fnames = np.random.choice(fnames, nfiles, replace=False)
    else:
        fnames = fnames

    pool = Pool(processes=min(nfiles, 120))
    print('Preparing pool')
    funcs = [pool.apply_async(get_data, (fname, band, xbar, dxbar),
        dict(pol=pol, mask=mask)) for fname in fnames]
    pixA = []
    pixB = []
    psiA = []
    psiB = []
    sigma0s = []
    f_A = []
    f_B = []
    print('Getting data')
    for i in tqdm(range(len(funcs))):
        result = funcs[i].get()
        if result is not None:
            if pol:
                M_i, b_i, Mp_i, bp_i, pixA_i, pixB_i, psiA_i, psiB_i, sigma_i,\
                        flagsA_i, flagsB_i = result
            else:
                M_i, b_i, pixA_i, pixB_i, sigma_i, flagsA_i, flagsB_i = result
            M_diag += M_i
            b += b_i
            pixA += pixA_i.tolist()
            pixB += pixB_i.tolist()
            f_A += flagsA_i.tolist()
            f_B += flagsB_i.tolist()
            if pol:
                M_diag_p += Mp_i
                b_p += bp_i
                psiA += psiA_i.tolist()
                psiB += psiB_i.tolist()
            sigma0s += sigma_i
    print('Finished pool')
    sigma0s = np.array(sigma0s)
    # For some reason when loading the entire dataset, the integers became
    # floats somewhere around here. Try and figure out where this might be
    # happening.
    pixA = np.array(pixA).astype('int')
    pixB = np.array(pixB).astype('int')
    if pol:
        psiA = np.array(psiA)
        psiB = np.array(psiB)
    f_A = np.array(f_A)
    f_B = np.array(f_B)

    print('Loaded data')

    if sparse_test or sparse_only:
        if pol:
            print('Constructing pointing matrix')
            A_p = sparse.csr_matrix((
             np.concatenate((
                f_A*(1+xbar)/sigma0s**2,
                f_A*dxbar*np.cos(2*psiA)/sigma0s**2,
                f_A*dxbar*np.sin(2*psiA)/sigma0s**2,
                f_A*dxbar/sigma0s**2,
                f_A*dxbar/sigma0s**2,
                f_A*(1+xbar)*np.cos(2*psiA)/sigma0s**2,
                f_A*(1+xbar)*np.sin(2*psiA)/sigma0s**2,
                f_A*(1+xbar)/sigma0s**2)),
                (np.arange(8*len(pixA)), 
                 np.concatenate((pixA, pixA+npix, pixA+2*npix, pixA+3*npix,
                                 pixA, pixA+npix, pixA+2*npix, pixA+3*npix)))))\
             + sparse.csr_matrix((
                np.concatenate((
                f_B*(-1+xbar)/sigma0s**2,
                f_B*dxbar*np.cos(2*psiB)/sigma0s**2,
                f_B*dxbar*np.sin(2*psiB)/sigma0s**2,
                f_B*dxbar/sigma0s**2,
                f_B*dxbar/sigma0s**2,
                f_B*(-1+xbar)*np.cos(2*psiB)/sigma0s**2,
                f_B*(-1+xbar)*np.sin(2*psiB)/sigma0s**2,
                f_B*(-1+xbar)/sigma0s**2)),
                (np.arange(8*len(pixB)), 
                 np.concatenate((pixB, pixB+npix, pixB+2*npix, pixB+3*npix,
                                 pixB, pixB+npix, pixB+2*npix, pixB+3*npix)))))

            del pixA, pixB, psiA, psiB, f_A, f_B, sigma0s
           


            print('Constructing A')
            A_p = dot_product_mkl(A_p.T, A_p)
        else:
            times = np.arange(len(pixA))
            print('Creating the pointing matrices')
            t0 = time()
            # This is strictly P, but I am renaming it to be A so that when I do
            # construct A, it is overwritten.
            A = (1+xbar)*sparse.csr_matrix((f_A*flags/sigma0s, (times, pixA))) - \
                (1-xbar)*sparse.csr_matrix((f_B*flags/sigma0s, (times, pixB)))
            print(f'Pointing matrix construction takes {time()-t0} seconds')
            print('Constructing the CG matrix A')
            t0 = time()
            A = A.T.dot(A)
            #print(A.data.nbytes + A.indptr.nbytes + A.indices.nbytes)
            print(f'Inner product takes {time()-t0} seconds')





    '''
    x = cg_solve(A, b, M_diag)

    '''

    if pol:
        data = hp.ud_grade(hp.read_map(f'data/wmap_iqusmap_r9_9yr_K1_v5.fits',
            verbose=False, field=(0,1,2,3)), nside)
        x_arr = []
        delta_arr = []

        b_p = np.concatenate((b, b_p))
        M_diag_p = np.concatenate((M_diag, M_diag_p))
        dts = []
        i = 0
        x_p = np.zeros_like(b_p)
        d = np.zeros_like(b_p)
        q = np.zeros_like(b_p)
        s = np.zeros_like(b_p)
        r = b_p
        p = (M_diag_p != 0)
        d[p] = r[p]/M_diag_p[p]
        delta_new = r.dot(d)
        delta_0 = np.copy(delta_new)
        delta_old = np.copy(delta_new)

        
        print('starting while loop')
        while ((i < imax) & (delta_new > eps**2*delta_0) & (delta_new <= delta_old)):
            t0 = time()
            if sparse_only:
                q = dot_product_mkl(A_p, d)
            else:
                q = innerproduct_pol(pixA, pixB, psiA, psiB, f_A, f_B, xbar, dxbar, d)
            alpha = delta_new/d.dot(q)
            x_p = x_p + alpha*d
            if i % 50 == 0:
                print('Divisible by 50')
                if sparse_only:
                    r = b_p - dot_product_mkl(A_p, x_p)
                else:
                    r = b_p - innerproduct_pol(pixA, pixB, psiA, psiB, f_A, f_B, xbar, dxbar, x_p)
            else:
                r = r - alpha*q
            if i % 10 == 0:
                print(np.round(i/imax,2),\
                        int(np.log10(delta_new)),\
                        delta_new)
            s[p] = r[p]/M_diag_p[p]
            delta_old = np.copy(delta_new)
            delta_new = r.dot(s)
            beta = delta_new/delta_old
            d = s + beta*d
            i += 1
            dts.append(time()-t0)
            delta_arr.append(delta_new)
            x_arr.append(x_p)

        x_i, x_q, x_u, x_s = np.split(x_p, 4)
        x_tot = np.array([x_i, x_q, x_u, x_s])
        hp.write_map(f'cg_v{version}_{band}_pol.fits', x_tot, overwrite=True)


        x_arr = np.array(x_arr)
        np.save('all_samples_pol', x_arr)

        d = np.array(delta_arr)
        np.save('all_samples_delta_pol', d)

        amps = [0.35, 0.035, 0.035, 0.035]
        mpl.rcParams['figure.figsize'][0] *= 2
        mpl.rcParams['figure.figsize'][1] *= 2
        for i in range(4):
            plt.figure('sol1')
            hp.mollview(x_tot[i], min=-amps[i], max=amps[i], title='Solution',
                    cmap=cmap, sub=(2,2,i+1))
            plt.savefig(f'solution1_{band}_pol.png', bbox_inches='tight')
            plt.figure('sol2')
            hp.mollview(x_tot[i], min=-10*amps[i], max=10*amps[i], title='Solution',
                    cmap=cmap, sub=(2,2,i+1))
            plt.savefig(f'solution2_{band}_pol.png', bbox_inches='tight')
            plt.figure('sol3')
            hp.mollview(x_tot[i], min=-100*amps[i], max=100*amps[i], title='Solution',
                    cmap=cmap, sub=(2,2,i+1))
            plt.savefig(f'solution3_{band}_pol.png', bbox_inches='tight')
                
               
            plt.figure('wmap1')
            hp.mollview(data[i], min=-amps[i], max=amps[i], title=f'WMAP {band}',
                    cmap=cmap, sub=(2,2,i+1))
            plt.savefig(f'wmap_sol1_{band}_pol.png', bbox_inches='tight')
            plt.figure('wmap2')
            hp.mollview(data[i], min=-10*amps[i], max=10*amps[i], title=f'WMAP {band}',
                    cmap=cmap, sub=(2,2,i+1))
            plt.savefig(f'wmap_sol2_{band}_pol.png', bbox_inches='tight')


            plt.figure('wmapdiff')
            hp.mollview(x_tot[i] - data[i], min=-amps[i], max=amps[i], cmap=cmap,
                    title='CG - WMAP', sub=(2,2,i+1))
            plt.savefig(f'wmap_diff_{band}_pol.png', bbox_inches='tight')

            plt.figure('wmapdiff_artifacts')
            hp.mollview(abs(x_tot[i] - data[i]), norm='hist', title='CG - WMAP',
                    sub=(2,2,i+1))
            plt.savefig(f'wmap_diff_{band}_artifacts_pol.png', bbox_inches='tight')

            
            plt.figure('wmapdiff_artifacts1')
            hp.mollview(abs(x_tot[i] - data[i]), min=0, max=0.1, title='Difference',
                    sub=(2,2,i+1))
            plt.savefig(f'wmap_diff_{band}_artifacts_1_pol.png', bbox_inches='tight')

            plt.figure('wmapdiff_artifacts2')
            hp.mollview(abs(x_tot[i] - data[i]), min=0, max=0.5, title='Difference',
                    sub=(2,2,i+1))
            plt.savefig(f'wmap_diff_{band}_artifacts_2_pol.png', bbox_inches='tight')

            plt.figure('wmapdiff_artifacts3')
            hp.mollview(abs(x_tot[i] - data[i]), min=0, max=1, title='Difference',
                    sub=(2,2,i+1))
            plt.savefig(f'wmap_diff_{band}_artifacts_3_pol.png', bbox_inches='tight')

            plt.figure('wmapdiff_artifacts4')
            hp.mollview(abs(x_tot[i] - data[i]), min=0, max=10, title='Difference',
                    sub=(2,2,i+1))
            plt.savefig(f'wmap_diff_{band}_artifacts_4_pol.png', bbox_inches='tight')
    else:
        data = hp.ud_grade(hp.read_map(f'data/wmap_imap_r9_9yr_{band}_v5.fits',
            verbose=False), nside)

        dts = []
        i = 0
        x = np.zeros_like(b)
        d = np.zeros_like(b)
        q = np.zeros_like(b)
        s = np.zeros_like(b)
        r = b
        p = (M_diag != 0)
        d[p] = r[p]/M_diag[p]
        delta_new = r.dot(d)
        delta_0 = np.copy(delta_new)
    
        x_arr = []
        delta_arr = []
    
        
        print('starting while loop')
        while (i < imax) & (delta_new > eps**2*delta_0):
            #x, mono = hp.remove_monopole(x, gal_cut=20, verbose=False, fitval=True)
            #x = hp.remove_dipole(x, gal_cut=20, verbose=False)
            #x = hp.remove_monopole(x, gal_cut=20, verbose=False)
            t0 = time()
            if sparse_only:
                q = A.dot(d)
            else:
                q *= 0
                funcs = [pool.apply_async(inner_productdq, args=[i]) for i in tqdm(range(len(pixA)))]
                for res in funcs:
                    result = res.get()
                    pA, pB, dq = result
                    q[pA] += dq*(1+x_bar)
                    q[pB] -= dq
                #for t in tqdm(range(len(pixA))):
                #    pA, pB, dq = inner_productdq(t)
                #    q[pA] += dq
                #    q[pB] -= dq
                if (i < 10) and sparse_test:
                    q_test = A.dot(d)
                    print(np.allclose(q_test, q))
            alpha = delta_new/d.dot(q)
            x = x + alpha*d
            if i % 50 == 0:
                print('Divisible by 50')
                if sparse_only:
                    r = b - A.dot(x)
                else:
                    r = 0 + b
                    for t in tqdm(range(len(pixA))):
                        pA, pB, dr = inner_productxr(t)
                        r[pA] -= dr
                        r[pB] += dr
                    if (i < 10) and sparse_test:
                        r_test = b - A.dot(x)
                        print(np.allclose(r_test, r))
            else:
                r = r - alpha*q
            if i % 10 == 0:
                exp = 10.**np.round(int(np.log10(delta_new)))
                dn_r = np.round(delta_new/exp,2)*exp
                print(np.round(i/imax,2),\
                        np.round(1/np.log10(delta_new/(delta_0*eps**2)),1),\
                        dn_r)
            s[p] = r[p]/M_diag[p]
            delta_old = np.copy(delta_new)
            delta_new = r.dot(s)
            beta = delta_new/delta_old
            d = s + beta*d
            i += 1
            dts.append(time()-t0)
            #x += mono
            x_arr.append(x)
    
            #metric = np.linalg.norm(s)
            delta_arr.append(delta_new)


        hp.write_map(f'cg_v{version}_{band}.fits', x, overwrite=True)


        x_arr = np.array(x_arr)
        np.save('all_samples', x_arr)

        d = np.array(delta_arr)
        np.save('all_samples_delta', d)

        amp = 0.35
        hp.mollview(x, min=-amp, max=amp, title='Solution', cmap=cmap)
        plt.savefig(f'solution1_{band}.png', bbox_inches='tight')
        hp.mollview(x, min=-10*amp, max=10*amp, title='Solution', cmap=cmap)
        plt.savefig(f'solution2_{band}.png', bbox_inches='tight')
        hp.mollview(x, min=-100*amp, max=100*amp, title='Solution', cmap=cmap)
        plt.savefig(f'solution3_{band}.png', bbox_inches='tight')
            
            
        x = hp.remove_dipole(x, gal_cut=20, verbose=False)


        hp.mollview(b, min=-amp, max=amp, cmap=cmap, title='Noise-weighted average')
        plt.savefig(f'noise_avg1_{band}.png')
        hp.mollview(b, min=-10*amp, max=10*amp, cmap=cmap, title='Noise-weighted average')
        plt.savefig(f'noise_avg2_{band}.png')
        hp.mollview(b, norm='hist', cmap=cmap, title='Noise-weighted average')
        plt.savefig(f'noise_avg3_{band}.png')
        hp.mollview(M_diag, norm='hist', title='Preconditioner')
        plt.savefig(f'preconditioner_{band}.png')
        hp.mollview(x, min=-amp, max=amp, title='Solution', cmap=cmap)



        hp.mollview(data, min=-amp, max=amp, title=f'WMAP {band}', cmap=cmap)
        plt.savefig(f'wmap_sol1_{band}.png', bbox_inches='tight')
        hp.mollview(data, min=-10*amp, max=10*amp, title=f'WMAP {band}',
                cmap=cmap)
        plt.savefig(f'wmap_sol2_{band}.png', bbox_inches='tight')


        hp.mollview(x - data, min=-amp, max=amp, cmap=cmap, title='CG - WMAP')
        plt.savefig(f'wmap_diff_{band}.png', bbox_inches='tight')

        hp.mollview(abs(x - data), norm='hist', title='CG - WMAP')
        plt.savefig(f'wmap_diff_{band}_artifacts.png', bbox_inches='tight')

        #plt.show()
        hp.mollview(abs(x - data), min=0, max=0.1, title='Difference')
        plt.savefig(f'wmap_diff_{band}_artifacts_1.png', bbox_inches='tight')

        hp.mollview(abs(x - data), min=0, max=0.5, title='Difference')
        plt.savefig(f'wmap_diff_{band}_artifacts_2.png', bbox_inches='tight')

        hp.mollview(abs(x - data), min=0, max=1, title='Difference')
        plt.savefig(f'wmap_diff_{band}_artifacts_3.png', bbox_inches='tight')

        hp.mollview(abs(x - data), min=0, max=10, title='Difference')
        plt.savefig(f'wmap_diff_{band}_artifacts_4.png', bbox_inches='tight')


    

    return


def check_hdf5(nside=256, version=8, band='K1'):
    # Take official W-band K-band, scan it with the same pointing matrix, divide
    # by gain, subtract from timestream, check the gain and pointing solution
    # directly. Should just be white noise.
    npix = hp.nside2npix(nside)
    b = np.zeros(hp.nside2npix(nside))
    b_p = np.zeros(2*hp.nside2npix(nside))
    M_diag = np.zeros(npix)
    M_diag_p = np.zeros(2*npix)

    from glob import glob
    fnames = glob(f'/mn/stornext/d16/cmbco/bp/wmap/data/wmap_{band}_*v{version}.h5')
    fnames.sort()
    fname = fnames[0]
    f= h5py.File(fname, 'r')
    obsid = str(list(f.keys())[0])
    labels = [f'{band}13', f'{band}14',f'{band}23',f'{band}24']

    huffTree = f[obsid+'/common/hufftree']
    huffSymb = f[obsid+'/common/huffsymb']
    h = huffman.Huffman(tree=huffTree, symb=huffSymb)


    '''
    TOD0 = np.array(f[obsid + '/' + labels[0] + '/tod'])
    if band == 'K1':
        if len(TOD0) != 675000:
            print(f'{fname} has wrong length')
            return None
    elif band == 'V1':
        if len(TOD0) != 1125000:
            print(f'{fname} has wrong length')
            return None
    '''
    
    
    DAs = [[], [], [], []]
    pixAs = []
    pixBs = []
    sigmas = []
    gains = np.zeros(len(labels))
    for num, label in enumerate(labels):
        TODs = np.array(f[obsid + '/' + label + '/tod'])
        scalars = f[obsid + '/' + label + '/scalars']
        #flag = h.Decoder(np.array(f[obsid + '/' + label + '/flag']))
        gains[num] = scalars[0]
        TODs = TODs - np.median(TODs)
        DAs[num] = DAs[num] + TODs.tolist()
        sigmas.append(TODs.std())
        if label == f'{band}13':
            pixA = h.Decoder(np.array(f[obsid + '/' + label + \
                '/pixA'])).astype('int')
            pixB = h.Decoder(np.array(f[obsid + '/' + label + \
                '/pixB'])).astype('int')

    DAs = np.array(DAs)/gains.reshape(4,1)
    
    d1 = 0.5*(DAs[0] + DAs[1])
    d2 = 0.5*(DAs[2] + DAs[3])
    
    d = 0.5*(d1 + d2) # = i_A - i_B
    p = 0.5*(d1 - d2) # = q_A*cos(2*g_A) + u_A*sin(2*g_A) - q_B*cos(2*g_B) - u_B*sin(2*g_B)


    cg = hp.read_map(f'cg_v{version}_{band}.fits', verbose=False)
    # dipole
    dipoles = {'cobe':[3.358,  264.31,  48.05],
               'wmap':[3.355,  263.99,  48.26],
               'pl15':[3.3645, 264.00,  48.24],
               'lf18':[3.3644, 263.998, 48.265],
               'hf18':[3.3621, 264.021, 48.253],
               'pl18':[3.3621, 264.021, 48.253]}
    amp, lon, lat = dipoles['pl18']
    dipole = make_dipole(amp, lon, lat, nside)
    # all in mK
    sol = hp.read_map(f'data/wmap_imap_r9_9yr_{band}_v5.fits', verbose=False)
    sol = hp.ud_grade(sol, nside)


    dip_sub = hp.remove_dipole(cg, gal_cut=10)

    hp.mollview(sol, min=-2.5, max=2.5, title='WMAP', cmap='RdBu_r')
    plt.savefig(f'wmap_{band}.png', bbox_inches='tight')
    hp.mollview(dip_sub, min=-2.5, max=2.5, title='CG Dipole Subtracted', cmap='RdBu_r')
    plt.savefig(f'cg_dipsub_{band}.png', bbox_inches='tight')
    hp.mollview(sol - dip_sub, min=-0.25, max=0.25, title='Difference', cmap='RdBu_r')
    plt.savefig(f'diff_{band}.png', bbox_inches='tight')

    sol += dipole

    max_t = 10000

    d_sol = np.zeros(len(pixA))
    d_cg = np.zeros(len(pixA))
    for t in range(len(pixA)):
        d_sol[t] = sol[pixA[t]] - sol[pixB[t]]
        d_cg[t] = cg[pixA[t]] - cg[pixB[t]]
    fig, axes = plt.subplots(nrows=2, sharex=True, sharey=True)
    axes[0].plot(d_sol[:max_t])
    axes[0].set_ylabel('WMAP solution (mK)')
    #axes[1].plot(d[:max_t])
    #axes[1].set_ylabel('(Raw timestream - baseline) x g (mK)')

    axes[1].plot(d_cg[:max_t])
    axes[1].set_ylabel('CG solution')

    #plt.figure()
    #bins = np.linspace(-15, 15,  100)
    #plt.hist(d, label='CG Solution', alpha=0.5, bins=bins)
    #plt.hist(d_sol, label='WMAP solution', alpha=0.5, bins=bins)
    #plt.legend(loc='best')
    #plt.show()


    #plt.show()

    hp.mollview(abs(sol - dip_sub), norm='hist', title='Difference', cmap='RdBu_r')
    plt.show()
    return


if __name__ == '__main__':
    #cg_test()
    bands = ['K1', 'Ka1', 'Q1', 'Q2', 'V1', 'V2', 'W1', 'W2', 'W3', 'W4']
    get_cg(band='K1', nfiles=800, sparse_test=False, sparse_only=True,
            imbalance=True, mask=False, pol=True, imax=100)
    #get_cg(band='Ka1', nfiles=400, sparse_test=False, sparse_only=True,
    #        processing_mask=False)
    #get_cg(band='Q1', nfiles=100, sparse_test=False, sparse_only=True)
    #for band in bands:
    #    get_cg(band=band, nfiles=200, sparse_test=False, sparse_only=True)
    #get_cg(band='V1')
    #check_hdf5(version=11)
