"""2D motion proposals only; camera/object ambiguity remains."""
from pathlib import Path
import cv2,json,numpy as np,subprocess,time
W,H=256,144
def propose(video, output):
 OUT=Path(output).parent;OUT.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(2)
 f=Path(output)
 if f.exists():return json.loads(f.read_text())
 args=["ffmpeg","-v","error","-threads","2","-i",str(video),"-vf",r"select=not(mod(n\,10)),scale=256:144,format=gray","-vsync","0","-f","rawvideo","pipe:1"]
 p=subprocess.Popen(args,stdout=subprocess.PIPE);last=None;index=0;samples=[];start=time.time()
 mask=np.zeros((H,W),np.uint8);mask[8:int(H*.72),8:W-8]=255
 while True:
  raw=p.stdout.read(W*H)
  if not raw:break
  if len(raw)!=W*H:raise RuntimeError("short decoded frame")
  now=np.frombuffer(raw,np.uint8).reshape(H,W).copy();frame=index*10+1
  if last is not None:
   points=cv2.goodFeaturesToTrack(last,150,.01,8,mask=mask)
   labels=[];dx=dy=scale=0.;quality=0
   if points is not None and len(points)>=25:
    target,status,error=cv2.calcOpticalFlowPyrLK(last,now,points,None,winSize=(21,21),maxLevel=3)
    good=(status[:,0]>0)&(error[:,0]<25)
    if good.sum()>=20:
     A,inliers=cv2.estimateAffinePartial2D(points[good],target[good],method=cv2.RANSAC,ransacReprojThreshold=2)
     if A is not None:
      quality=float(inliers.mean());scale=float(np.hypot(A[0,0],A[1,0])-1)
      center=np.array([W/2,H/2,1]);shift=A@center-center[:2];dx,dy=map(float,shift)
      if quality>=.6:
       if abs(dx)>W*.025:labels.append("left" if dx>0 else "right")
       if abs(dy)>H*.025:labels.append("up" if dy>0 else "down")
       if abs(scale)>.025 and abs(dx)<W*.04 and abs(dy)<H*.04:labels.append("forward" if scale>0 else "backward")
   samples.append({"frame":frame,"labels":labels,"dx":round(dx,3),"dy":round(dy,3),"scale":round(scale,4),"inlier_ratio":round(quality,3)})
  last=now;index+=1
  if index%1000==0:print("motion_frames",frame,"elapsed",round(time.time()-start,1),flush=True)
 p.stdout.close();assert p.wait()==0
 proposals=[];current=None
 for s in samples:
  labels=sorted(s["labels"])
  if labels and current and current["labels"]==labels and s["frame"]-current["end"]==10:current["end"]=s["frame"];current["quality"].append(s["inlier_ratio"])
  else:
   if current and current["end"]-current["start"]>=20:proposals.append(current)
   current={"start":max(1,s["frame"]-10),"end":s["frame"],"labels":labels,"quality":[s["inlier_ratio"]]} if labels else None
 if current and current["end"]-current["start"]>=20:proposals.append(current)
 for x in proposals:x["quality"]=round(float(np.mean(x["quality"])),3);x["status"]="automatic_optical_flow_proposal_unreviewed"
 f.write_text(json.dumps({"method":"upper-image robust affine flow at 5Hz; camera/object-motion ambiguity remains","proposals":proposals,"sample_count":len(samples)},indent=2)+"\n")
 return json.loads(f.read_text())
