"""My profile portrait: the photo drawn in plain text shading, 92 columns, sized for GitHub's code font.
Usage: python tools/make_portrait.py <photo> <out.txt>"""
import sys
import numpy as np, cv2

src = cv2.imread(sys.argv[1], 0); h, w = src.shape
box = (int(w * 0.16), 0, int(w * 0.84), int(h * 0.86))
crop = src[box[1]:box[3], box[0]:box[2]]
COLS = 92
rows = int(COLS * crop.shape[0] / crop.shape[1] * 8.158 / 19.72)   # GitHub: 8.16 px wide, 19.72 px lines
g = cv2.createCLAHE(2.0, (4, 4)).apply(crop).astype(np.float32) / 255
s = cv2.resize(g, (COLS, rows), interpolation=cv2.INTER_AREA)
wall = np.median(crop[300:700, 0:60]) / 255
RAMP = " .,:;-=+*#%@"
out = []
for r in range(rows):
    line = ""
    for c in range(COLS):
        v = s[r, c]
        if abs(v - wall) < 0.06 and (c < 12 or c > 80 or r < 4):
            line += " "; continue
        line += RAMP[min(len(RAMP) - 1, int(max(0, 1 - v) ** 1.2 * len(RAMP)))]
    out.append(line.rstrip())
open(sys.argv[2], "w").write("\n".join(out) + "\n")
