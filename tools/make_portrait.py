"""My profile portrait: the photo drawn in text, mostly Zs, 92 columns, sized for GitHub's code font.
Usage: python tools/make_portrait.py <photo> <out.txt>"""
import sys, numpy as np, cv2
from collections import deque
src=cv2.imread(sys.argv[1],0); h,w=src.shape
box=(int(w*0.16),0,int(w*0.84),int(h*0.86)); crop=src[box[1]:box[3],box[0]:box[2]]
COLS=92; rows=int(COLS*crop.shape[0]/crop.shape[1]*8.158/19.72)
g=cv2.resize(crop.astype(np.float32)/255,(COLS,rows),interpolation=cv2.INTER_AREA)
# wall: flood from the border through cells close to the wall grey
tol=0.07
gw=np.median(crop[300:700,0:60])/255
wallrow=np.array([np.median(np.r_[g[r,:4],g[r,-4:]]) for r in range(rows)])  # the wall darkens toward the top
wallrow=np.where(np.abs(wallrow-gw)<0.12,wallrow,gw)                       # but the black jacket at the edges is not wall
bg=np.zeros_like(g,bool); q=deque()
for r in range(rows):
    for c in range(COLS):
        if (r==0 or c==0 or c==COLS-1) and abs(g[r,c]-wallrow[r])<tol: bg[r,c]=1; q.append((r,c))
while q:
    r,c=q.popleft()
    for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
        R,C=r+dr,c+dc
        if 0<=R<rows and 0<=C<COLS and not bg[R,C] and abs(g[R,C]-wallrow[R])<tol: bg[R,C]=1; q.append((R,C))
# tones of the person only, stretched to the full ramp
v=g[~bg]; lo,hi=np.percentile(v,1),np.percentile(v,99.5)
n=np.clip((g-lo)/(hi-lo),0,1)
RAMP=" .,:;-=+zZ"; gam=0.8
out=[]
for r in range(rows):
    L="".join(" " if bg[r,c] else RAMP[min(len(RAMP)-1,int((1-n[r,c])**gam*len(RAMP)))] for c in range(COLS))
    out.append(L.rstrip())
open(sys.argv[2],"w").write("\n".join(out)+"\n")
