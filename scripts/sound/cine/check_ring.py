"""ringing detector: Welch-averaged spectrum per 1.5 s window after t0; a stable tone survives averaging, noise does not.
reports the strongest narrow peak (dB above the local +-250 Hz median) in 200-9000 Hz."""
import sys,numpy as np
from scipy.io import wavfile
from scipy import signal, ndimage
def run(p,t0=28.0,W=1.5):
    sr,x=wavfile.read(p); m=(x.astype(float)/32768).mean(1)
    print(p)
    for a in np.arange(t0,len(m)/sr-W+0.01,W):
        s=m[int(a*sr):int((a+W)*sr)]
        f,P=signal.welch(s,sr,nperseg=16384,noverlap=12288); L=10*np.log10(P+1e-14)
        k=(f>200)&(f<9000); fk,Lk=f[k],L[k]
        med=ndimage.median_filter(Lk,size=int(500/(f[1]-f[0])),mode='reflect')
        d=Lk-med; i=int(np.argmax(d))
        print(f'  {a:5.1f}-{a+W:4.1f}s  max peak +{d[i]:4.1f} dB at {fk[i]:6.0f} Hz')
for p in sys.argv[1:]: run(p)
