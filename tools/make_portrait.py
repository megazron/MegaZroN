import numpy as np, sys
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont
SRC=sys.argv[1]; COLS=int(sys.argv[2]) if len(sys.argv)>2 else 96
WORDS=("TEXT·TO·ROBOT  ROBOT·STUDIO  zronOS  ROBOT·CHALAO  BEYOND·SAGITTARIUS  HUAWEI·R&D  "
 "IMPERIAL·COLLEGE·LONDON  ISRO·NARL  SIH·WINNER·2023  SIH·WINNER·2024  "
 "CANSAT·2022·WINNER  6·PATENTS  EEG·WHEELCHAIR  COAXIAL·DRONE  DEBRIS·HUNTER  COAX·EYE  MIND·DRIVE  TWIN·ARMS  SAC·PILOT  "
 "AGENT·NET  GeoTRACE  VLA  ROS·2  MuJoCo  ISAAC·LAB  KINOVA·GEN3  TELEOPERATION  DEEP·RL  LiDAR  SATELLITES  MARK·43  ")
rgb=Image.open(SRC).convert("RGB")
w,h=rgb.size
box=(int(w*0.16),int(h*0.0),int(w*0.84),int(h*0.86))   # tight on the head so the face gets enough characters
rgb=rgb.crop(box); im=rgb.convert("L")
import cv2
g=np.asarray(im)
g0=g.copy(); g=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(g)
g=(0.55*g0+0.45*g).astype(np.uint8)
im=Image.fromarray(g).filter(ImageFilter.UnsharpMask(2,90,2))
ASPECT=8.158/19.72   # measured on github.com: 13.6px mono is 8.16px wide, lines 19.72px tall
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
_full=np.asarray(Image.open(SRC).convert("L"),dtype=float)/255
lvl=np.median(np.concatenate([_full[300:700,10:120].ravel(),_full[300:700,-120:-10].ravel()]))   # the grey studio wall beside my head
bg=(hsv[...,1]<0.15)&(np.abs(v0-lvl)<0.12)
# flood from borders so only connected background is removed
from collections import deque
mask=np.zeros_like(bg); q=deque()
for r in range(rows):
    for c in (0,COLS-1):
        if bg[r,c] and not mask[r,c]: mask[r,c]=1; q.append((r,c))
for c in range(COLS):
    for r in (0,rows-1):
        if bg[r,c] and not mask[r,c]: mask[r,c]=1; q.append((r,c))
while q:
    r,c=q.popleft()
    for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
        R,C=r+dr,c+dc
        if 0<=R<rows and 0<=C<COLS and bg[R,C] and not mask[R,C]: mask[R,C]=1; q.append((R,C))
# what each part of me is made of
VISION=("BISMILLAH  RABBI·ZIDNI·ILMA  BUILD·THE·IMPOSSIBLE  INNA·MA'AL·USRI·YUSRA  NEVER·GIVE·UP  LA·TAHZAN·INNALLAHA·MA'ANA  TAWAKKUL  WA·MA·TAWFIQI·ILLA·BILLAH  LOCKED·IN  HASBUNALLAHU·WA·NI'MAL·WAKIL  WE·ARE·SO·BACK  ")
MIND=("TEXT·TO·ROBOT  ROBOT·STUDIO  zronOS  ROBOT·CHALAO  BEYOND·SAGITTARIUS  HUAWEI·R&D  IMPERIAL·COLLEGE·LONDON  MSc·ROBOTICS  ISRO·NARL  SIH·WINNER·2023  SIH·WINNER·2024  CANSAT·2022·WINNER  6·PATENTS  EEG·WHEELCHAIR  COAXIAL·DRONE  DEBRIS·HUNTER  TWIN·ARMS  SAC·PILOT  AGENT·NET  GeoTRACE  ISPRS·2025  IEEE·InGARSS  VLA  ROS·2  MuJoCo  ISAAC·LAB  KINOVA·GEN3  DEEP·RL  LiDAR  QISKIT  GDSC·LEAD  GOOGLE·I/O·CONNECT  MARK·43  SIH·TRAFFIC·1·LAKH  SIH·PORT·SECURITY·1·LAKH  SIH·THREE·YEARS·IN·A·ROW  CANSAT·GRAND·FINALIST·2024  FELICITATED·BY·ISRO·CHAIRMAN  IASc·INSA·NASI·FELLOW  QUANTUM·HACKATHON·TOP·16  QISKIT·QUANTUM·EXCELLENCE  MICROSOFT·Q#·BLOG  GOOGLE·DEVFEST·AWARD  GOOGLE·FOR·DEVELOPERS·AD  GDSC·800+·MEMBERS  IDE·BOOTCAMP·TOP·5  STAR·AVIONICS  IEEE·YP  ICCC·2025  IJSRST·2024  HYPERSPECTRAL  LIBERO  SmolVLA  OpenVLA  OCTO  ACT  DIFFUSION·POLICY  PYTORCH  C++  JULIA  FUSION·360  JETSON  UNITREE·GO2  TWIN·TRUTH  SCENEBREAKER  REPOLENS  AYRPORT  STICKERSOUNDS  PHONE·TO·ROBOT  BRAIN·TUMOR·YOLO  GLOBAL·TALENT·VISA  HBR·REP  LET·HIM·COOK  BUILT·DIFFERENT  NO·CAP  GOATED  AURA·FARMING  ")
HEART=("IT'S·HERO·TIME  GOOD·FOR·YOU  I·ALONE·AM·THE·HONORED·ONE  DOMAIN·EXPANSION  INFINITE·VOID  HOLLOW·PURPLE  ARE·YOU·THE·STRONGEST·BECAUSE·YOU'RE·GOJO·SATORU  STAND·PROUD·YOU'RE·STRONG  HEAVENLY·RESTRICTION  ZERO·CURSED·ENERGY  SORCERER·KILLER  BLACK·FLASH  WITH·THIS·TREASURE·I·SUMMON  TEN·BILLION·PERCENT  THIS·IS·EXHILARATING  GET·EXCITED  KINGDOM·OF·SCIENCE  IT'S·OVER·9000  KAMEHAMEHA  ULTRA·INSTINCT  SUPER·SAIYAN  FINAL·FLASH  I·AM·THE·HOPE·OF·THE·UNIVERSE  ARISE  SHADOW·MONARCH  I·ALONE·LEVEL·UP  DAILY·QUEST·COMPLETE  [SYSTEM]·YOU·HAVE·LEVELED·UP  RELICS·ARE·MINE  THE·TOMB·IS·OPEN  I·AM·IRON·MAN  I·LOVE·YOU·3000  THE·MAN·WHO·LEFT·IT·ALL·BEHIND  OMNITRIX  HUMUNGOUSAUR  WAY·BIG  XLR8  FOUR·ARMS  HEATBLAST  ALIEN·X  BEN·10,000  GENIUS·TRILLIONAIRE·SHORMA·INNOVATOR  WITH·GREAT·POWER·COMES·GREAT·RESPONSIBILITY  ANYONE·CAN·WEAR·THE·MASK  WHATEVER·IT·TAKES  FLYING·GRAYSON  BLUDHAVEN·NIGHTS  FIRST·ROBIN  SKATE·OR·DIE  SWIM·SZN  MIC·CHECK  GG·EZ  1V5·CLUTCH  TOUCH·GRASS  RIZZ  SIGMA  AURA·+1000  FR·FR  SLAY  ATE·NO·CRUMBS  MOGGED  SKIBIDI  SIX·SEVEN  DELULU  BUSSIN  IT'S·GIVING  ")
ROOTS=("ASSALAMU·ALAIKUM  PARENTS·FELICITATED  FAMILY·FIRST  RANK·1·IN·DEPARTMENT  A·P·J·ABDUL·KALAM·OF·THE·DEPARTMENT  SHISHYOTTAM·BEST·STUDENT  B·TECH·ECT  5TH·SEM·TOPPER  CLASS·REPRESENTATIVE  SCIENCE·OLYMPIAD·GOLD  HOUSE·CAPTAIN  QUIZ·CHAMPION  STAY·HUMBLE  STAY·GROUNDED  MUM·AND·DAD  WHERE·IT·ALL·STARTED  IMPERIAL·COLLEGE·LONDON  ")
streams={k:(iter(v*600),iter(v.lower()*600)) for k,v in dict(VISION=VISION,MIND=MIND,HEART=HEART,ROOTS=ROOTS).items()}
# regions in source-photo pixels (1079x1080 portrait), mapped into the cropped grid
SW,SH=1079,1080
def to_grid(x,y): return (x-box[0])/(box[2]-box[0])*COLS, (y-box[1])/(box[3]-box[1])*rows
def region(r,c):
    x=box[0]+(c+0.5)/COLS*(box[2]-box[0]); y=box[1]+(r+0.5)/rows*(box[3]-box[1])
    if ((x-540)/205)**2+((y-480)/245)**2<=1 and y>=262: return "FACE"   # the face itself: shading only, so it looks like me
    if y>=700 and (330<=x<=760 if y>=790 else 400<=x<=720): return "HEART"       # turtleneck over the heart
    if y>=700: return "ROOTS"                                  # shoulders and jacket: grounded
    return "MIND"                                              # head and hair
subj=a[mask==0]
q=np.quantile(subj,[0.40,0.55,0.68,0.80,0.92])
WORDLIST={k:[w for w in v.split() if w] for k,v in dict(VISION=VISION,MIND=MIND,HEART=HEART,ROOTS=ROOTS).items()}
used={k:{w:0 for w in v} for k,v in WORDLIST.items()}
pos={k:0 for k in WORDLIST}
def textcell(r,c):
    """Cells that carry words: dark enough, or any tone in the eyes and the jacket."""
    if mask[r,c]: return False
    v=a[r,c]; reg=region(r,c)
    if reg=="FACE": return False
    if reg in ("VISION","ROOTS","HEART"): return v<q[2]
    return v<q[1]
RAMP="  .,:;-~=+*&#%@"   # light skin to dark features
_face=None
def fq(v):
    """Where this value sits among the face's own tones (0 dark .. 1 light), so the face uses the whole ramp."""
    global _face
    if _face is None:
        vals=[a[r,c] for r in range(rows) for c in range(COLS) if not mask[r,c] and region(r,c)=="FACE"]
        _face=np.sort(np.array(vals))
    return np.searchsorted(_face,v)/len(_face)
def tone(v):
    if v<q[2]: return ";"
    if v<q[3]: return ":"
    if v<q[4]: return "·"
    return " "
def take(reg, room):
    """A whole phrase that fits, the least used first, so nothing is cut and nothing repeats more than it must."""
    fits=[w for w in WORDLIST[reg] if len(w)<=room]
    if not fits: return None
    w=min(fits,key=lambda w:(used[reg][w],-len(w)))
    used[reg][w]+=1; return w
out=[]
for r in range(rows):
    line=[" "]*COLS
    for c in range(COLS):
        if mask[r,c]: continue
        if region(r,c)=="FACE":
            d=(1-fq(a[r,c]))**1.8          # skin stays light, only real shadows get ink
            line[c]=RAMP[min(len(RAMP)-1,int(d*len(RAMP)))]
        else: line[c]=tone(a[r,c])
    c=0
    while c<COLS:
        if not textcell(r,c): c+=1; continue
        reg=region(r,c); e=c
        while e<COLS and textcell(r,e) and region(r,e)==reg: e+=1
        x=c
        if x>0 and line[x-1].isalnum(): line[x]=" "; x+=1     # never glue onto the previous region's word
        while x<e:
            w=take(reg,e-x)
            if not w: break
            line[x:x+len(w)]=list(w); x+=len(w)
            if x<e: line[x]=" "; x+=1        # a space between phrases
        while x<e: line[x]="·"; x+=1          # leftover too short for any word
        c=e
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
# my eyes hold my faith and my vision: a short line inside each lens
def place(text, sx, sy):
    rr = int((sy - box[1]) / (box[3] - box[1]) * rows); c0 = int((sx - box[0]) / (box[2] - box[0]) * COLS) - len(text) // 2
    L = list(lines[rr].ljust(COLS)); L[c0 - 1:c0 + len(text) + 1] = list(" " + text + " "); lines[rr] = "".join(L)
LEFT, RIGHT = 410, 598                     # lens centres x in the photo; pupils sit at y~440, verses go under them
place("BISMILLAH", LEFT, 470); place("RABBI·ZIDNI·ILMA", LEFT, 492)
place("TAWAKKUL", RIGHT, 470); place("LA·TAHZAN", RIGHT, 492)
# the lips say it
MOUTH_Y, MOUTH_X = (606, 606), 505        # lips in source pixels (top, bottom) and centre x
r0 = int((MOUTH_Y[0] - box[1]) / (box[3] - box[1]) * rows); r1 = int(round((MOUTH_Y[1] - box[1]) / (box[3] - box[1]) * rows))
cc = int((MOUTH_X - box[0]) / (box[2] - box[0]) * COLS)
word = "ALHAMDULILLAH"
for r in range(r0, r0 + 2):  # upper and lower lip
    L = list(lines[r].ljust(COLS)); c0 = cc - len(word) // 2
    L[c0:c0 + len(word)] = list(word)
    # never leave half a word touching the lips: clear letters on either side up to the next gap
    for step, start in ((-1, c0 - 1), (1, c0 + len(word))):
        k = start
        while 0 <= k < COLS and (L[k].isalnum() or L[k] in "#&"):
            L[k] = ":"; k += step
    lines[r] = "".join(L)
# the top of my head says it
import re
m = re.search(r"[A-Za-z0-9][^ ;:]*[A-Za-z0-9]", lines[0])
t = "NAH·I'D·WIN"; c0 = m.start() + (len(m.group()) - len(t)) // 2
lines[0] = (lines[0][:m.start()] + " " * len(m.group()) + lines[0][m.end():])
lines[0] = lines[0][:c0] + t + lines[0][c0 + len(t):]
# and one lone z, somewhere on the wall
import random; rnd = random.Random(43)
spots = [(r, c) for r in range(rows) for c in range(2, COLS - 2) if mask[r, c] and lines[r][c - 2:c + 3].strip() == ""]
zr, zc = rnd.choice(spots); lines[zr] = lines[zr][:zc] + "z" + lines[zr][zc + 1:]
open(sys.argv[3], "w").write("\n".join(l.rstrip() for l in lines) + "\n")
