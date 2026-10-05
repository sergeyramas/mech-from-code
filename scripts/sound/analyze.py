import sys, glob, numpy as np
from scipy.io import wavfile
from scipy import signal
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
d=os.path.dirname(os.path.abspath(__file__))
os.makedirs(d+"/spec",exist_ok=True)
bands=[(20,120),(120,500),(500,2000),(2000,6000),(6000,16000)]
for f in sorted(glob.glob(d+"/wav/*.wav")):
    sr,x=wavfile.read(f); x=x.astype(float)/32768; m=x.mean(1)
    fr,P=signal.welch(m,sr,nperseg=4096); tot=P.sum()
    bs=" ".join(f"{int(10*np.log10(P[(fr>=a)&(fr<b)].sum()/tot+1e-12))}" for a,b in bands)
    cen=(fr*P).sum()/tot
    hop=sr//10; env=[np.sqrt(np.mean(m[i:i+hop]**2)) for i in range(0,len(m)-hop,hop)]
    env_db=20*np.log10(np.array(env)+1e-6)
    st=np.corrcoef(x[:,0],x[:,1])[0,1]
    print(f"{os.path.basename(f):26s} {len(m)/sr:5.1f}s centroid {cen:6.0f}Hz bands dB[{bs}] LR-corr {st:.2f} env min/max {env_db.min():.0f}/{env_db.max():.0f}dB clip {np.mean(np.abs(x)>0.99):.5f}")
    ff,tt,S=signal.spectrogram(m,sr,nperseg=2048,noverlap=1536)
    plt.figure(figsize=(10,3.2)); plt.pcolormesh(tt,ff,10*np.log10(S+1e-12),vmin=-110,vmax=-30,shading='auto'); plt.ylim(0,12000); plt.tight_layout()
    plt.savefig(d+"/spec/"+os.path.basename(f)[:-4]+".png",dpi=70); plt.close()
