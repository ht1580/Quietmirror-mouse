"""Print before the full kit: stem and axle clearance coupon, mm."""
from pathlib import Path
import cadquery as cq
from build_mouse import rounded_box
from build_v05 import save_model
from mechanisms_v08 import cyl
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'exports/v09/calibration';out.mkdir(parents=True,exist_ok=True)
plate=rounded_box(42,27,4,2,(0,0,2))
for x,g in [(-13,.2),(0,.3),(13,.4)]:
    plate=plate.cut(rounded_box(5.6+2*g,7.6+2*g,8,.7,(x,-4,2)))
for x,d in [(-13,3.2),(0,3.4),(13,3.6)]:plate=plate.cut(cyl(d/2,8,(x,8,-1)))
for x,d in [(-13,1.6),(0,1.7),(13,1.8)]:plate=plate.cut(cyl(d/2,8,(x,3,-1)))
stem=rounded_box(5.6,7.6,10,.45,(0,0,5)).fuse(rounded_box(10,12,2,1,(0,0,1)))
axle=cyl(1.5,12,(0,0,0)).fuse(cyl(3,2,(0,0,0)))
for n,s in [('CLEARANCE_COUPON',plate),('STEM_TEST',stem),('AXLE_TEST',axle)]:save_model(s,n,out)
print('Coupon: left/centre/right stem per-side gap 0.2/0.3/0.4 mm; axle holes 3.2/3.4/3.6 mm.')
