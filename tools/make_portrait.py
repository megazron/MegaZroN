import numpy as np, sys
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont
SRC=sys.argv[1]; COLS=int(sys.argv[2]) if len(sys.argv)>2 else 96
WORDS=("TEXT·TO·ROBOT  ROBOT·STUDIO  zronOS  ROBOT·CHALAO  BEYOND·SAGITTARIUS  HUAWEI·R&D·UK  "
 "IMPERIAL·COLLEGE·LONDON  ISRO·NARL  IIT·BOMBAY  SMART·INDIA·HACKATHON·WINNER·2023  SMART·INDIA·HACKATHON·WINNER·2024  "
 "CANSAT·2022·WINNER  6·PATENTS  EEG·WHEELCHAIR  COAXIAL·DRONE  DEBRIS·HUNTER  COAX·EYE  MIND·DRIVE  TWIN·ARMS  SAC·PILOT  "
 "AGENT·NET  GeoTRACE  VLA  ROS·2  MuJoCo  ISAAC·LAB  KINOVA·GEN3  TELEOPERATION  DEEP·RL  LiDAR  SATELLITES  MARK·43  ")
rgb=Image.open(SRC).convert("RGB")
w,h=rgb.size
box=(int(w*0.16),int(h*0.02),int(w*0.84),int(h*0.86))
rgb=rgb.crop(box); im=rgb.convert("L")
import cv2
g=np.asarray(im)
g0=g.copy(); g=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(g)
g=(0.55*g0+0.45*g).astype(np.uint8)
im=Image.fromarray(g).filter(ImageFilter.UnsharpMask(2,90,2))
ASPECT=0.50   # char height/width ~2 in GitHub mono
rows=int(COLS*im.size[1]/im.size[0]*ASPECT)
a=np.asarray(im.resize((COLS,rows),Image.LANCZOS),dtype=float)/255
hi=np.asarray(im,dtype=np.float32)
gx=cv2.Sobel(hi,cv2.CV_32F,1,0,ksize=3); gy=cv2.Sobel(hi,cv2.CV_32F,0,1,ksize=3)
edge=np.hypot(gx,gy); edge=cv2.GaussianBlur(edge,(0,0),2.0)
edge=np.asarray(Image.fromarray(edge).resize((COLS,rows),Image.BOX),dtype=float)
edge=np.clip(edge/np.quantile(edge,0.97),0,1)
a=np.clip(a-0.34*edge,0,1)
# background: the grey studio wall ~ uniform; mark as bg where close to its level near edges
hsv=np.asarray(rgb.convert("HSV").resize((COLS,rows),Image.LANCZOS),dtype=float)/255
v0=np.asarray(rgb.convert("L").resize((COLS,rows),Image.LANCZOS),dtype=float)/255
lvl=np.median(np.concatenate([v0[:,0:3].ravel(),v0[:,-3:].ravel(),v0[0:2,:].ravel()]))
bg=(hsv[...,1]<0.12)&(np.abs(v0-lvl)<0.09)
# flood from borders so only connected background is removed
from collections import deque
mask=np.zeros_like(bg); q=deque()
for r in range(rows):
    for c in (0,COLS-1):
        if bg[r,c] and not mask[r,c]: mask[r,c]=1; q.append((r,c))
for c in range(COLS):
    if bg[0,c] and not mask[0,c]: mask[0,c]=1; q.append((0,c))
while q:
    r,c=q.popleft()
    for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
        R,C=r+dr,c+dc
        if 0<=R<rows and 0<=C<COLS and bg[R,C] and not mask[R,C]: mask[R,C]=1; q.append((R,C))
# what each part of me is made of
VISION=("BUILD·THE·IMPOSSIBLE·WITH·SCIENCE  10·BILLION·PERCENT  ROBOTS·THAT·SEE·THINK·AND·MOVE  "
        "EMBODIED·AI  VISION·LANGUAGE·ACTION  ROBOTS·FOR·EVERYONE  BRAIN·COMPUTER·INTERFACES  NEUROREHAB  ")
MIND=("TEXT·TO·ROBOT  ROBOT·STUDIO  zronOS  ROBOT·CHALAO  BEYOND·SAGITTARIUS  HUAWEI·R&D·UK  IMPERIAL·COLLEGE·LONDON  "
      "MSc·ROBOTICS  ISRO·NARL  IIT·BOMBAY  SMART·INDIA·HACKATHON·WINNER·2023  SMART·INDIA·HACKATHON·WINNER·2024  "
      "CANSAT·2022·WINNER  6·PATENTS  EEG·WHEELCHAIR  COAXIAL·DRONE  DEBRIS·HUNTER  TWIN·ARMS  SAC·PILOT  AGENT·NET  "
      "GeoTRACE  ISPRS·2025  IEEE·InGARSS  VLA  ROS·2  MuJoCo  ISAAC·LAB  KINOVA·GEN3  DEEP·RL  LiDAR  QISKIT  "
      "GDSC·LEAD  GOOGLE·I/O·CONNECT  MARK·43  ")
HEART=("DR·STONE  DRAGON·BALL·Z  SOLO·LEVELING  TOMB·RAIDER·KING  MARVEL  SPIDER-MAN  TONY·STARK  NIGHTWING  "
       "ANIME  SKATING  SWIMMING  SINGING  GAMING  ESPORTS  ")
ROOTS=("AURANGABAD  CHHATRAPATI·SAMBHAJINAGAR  MAHARASHTRA  INDIA  PODAR·INTERNATIONAL·SCHOOL  BALBHIM·COLLEGE  "
       "MGM·UNIVERSITY  JNEC  B·TECH·ECT  RANK·1·IN·DEPARTMENT  A·P·J·ABDUL·KALAM·OF·THE·DEPARTMENT  "
       "SHISHYOTTAM·BEST·STUDENT  PARENTS·FELICITATED  ASSALAMU·ALAIKUM  NAMASKAR  ")
streams={k:(iter(v*600),iter(v.lower()*600)) for k,v in dict(VISION=VISION,MIND=MIND,HEART=HEART,ROOTS=ROOTS).items()}
# regions in source-photo pixels (1079x1080 portrait), mapped into the cropped grid
SW,SH=1079,1080
def to_grid(x,y): return (x-box[0])/(box[2]-box[0])*COLS, (y-box[1])/(box[3]-box[1])*rows
def region(r,c):
    x=box[0]+(c+0.5)/COLS*(box[2]-box[0]); y=box[1]+(r+0.5)/rows*(box[3]-box[1])
    if 360<=y<=505 and 310<=x<=720: return "VISION"          # eyes and glasses
    if y>=700 and 400<=x<=720 and y<=935: return "HEART"       # turtleneck over the heart
    if y>=700: return "ROOTS"                                  # shoulders and jacket: grounded
    return "MIND"                                              # head and hair
subj=a[mask==0]
q=np.quantile(subj,[0.40,0.55,0.68,0.80,0.92])
out=[]
for r in range(rows):
    line=[]
    for c in range(COLS):
        v=a[r,c]
        if mask[r,c]: line.append(" "); continue
        up,lo=streams[region(r,c)]
        reg=region(r,c)
        if reg=="VISION" and v<q[2]: line.append(next(up)); continue   # the eyes carry the vision clearly
        if reg=="ROOTS":                                               # the ground I stand on, written out
            if v<q[2]: line.append(next(up)); continue
            if v<q[3]: line.append(next(lo)); continue
        if v<q[0]: line.append(next(up))
        elif v<q[1]: line.append(next(lo))
        elif v<q[2]: line.append(";")
        elif v<q[3]: line.append(":")
        elif v<q[4]: line.append("·")
        else: line.append(" ")
    out.append("".join(line).rstrip())
open(sys.argv[3],"w").write("\n".join(out)+"\n")
print(rows,"rows")

# ---- small text drawings in the empty background: arms, drones, satellites, a CanSat ----
ICONS = {
 "arm": ["  __", " [__]==o", "    \\\\", "     \\\\__", "  ___|__|___"],
 "drone": ["~~+~~   ~~+~~", "    \\___/", "    [o_o]", "    /   \\", "~~+~~   ~~+~~"],
 "sat": ["[=][=]-(o)-[=][=]", "       /|\\"],
 "sat2": ["  .-.", "-[|o|]-", "  '-'"],
 "rover": ["   _[]_", " _|____|_", "(o)----(o)"],
 "cansat": ["  ,^,", " |CAN|", " |SAT|", "  \\|/"],
}
PLACES = [("sat", 1, 3), ("drone", 7, 2), ("arm", 15, 4), ("cansat", 24, 6),
          ("sat2", 1, -16), ("drone", 9, -18), ("rover", 18, -16), ("arm", 26, -14)]
lines = [l.ljust(COLS) for l in open(sys.argv[3]).read().splitlines()]
for name, r0, c0 in PLACES:
    art = ICONS[name]; w = max(len(x) for x in art)
    c0 = c0 if c0 >= 0 else COLS + c0
    ok = all(r0 + i < len(lines) and lines[r0 + i][c0:c0 + w].strip() == "" for i in range(len(art)))
    if not ok:
        continue  # never draw over the face
    for i, x in enumerate(art):
        L = lines[r0 + i]; lines[r0 + i] = L[:c0] + x.ljust(w) + L[c0 + w:]
open(sys.argv[3], "w").write("\n".join(l.rstrip() for l in lines) + "\n")
