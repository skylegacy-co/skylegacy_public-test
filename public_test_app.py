#!/usr/bin/env python3
"""Sky Legacy public customer-flow demo.
No owner dashboard. No persistent leads. Uploaded photos are not stored.
"""
from flask import Flask, render_template, request, redirect, url_for, abort
from types import SimpleNamespace
import json, os, uuid

app=Flask(__name__)
S={'siding':('Siding / Exterior',[('repair','Targeted repair',900,2500),('wall','One wall',3000,6500),('several','Several walls',6500,12000),('whole','Whole exterior',12000,26000)]),'flooring':('Flooring',[('repair','Small repair',650,1800),('room','One room',1500,3500),('several','Several rooms',4000,9000),('whole','Whole home',8000,18000)]),'tile':('Tile',[('repair','Repair / backsplash',850,2500),('room','Floor or shower',2500,7000),('several','Bathroom remodel',6000,14000),('whole','Multiple areas',10000,24000)]),'paint':('Painting',[('repair','Touch-up / small space',600,1600),('room','One room',1000,2500),('several','Several areas',3000,8000),('whole','Whole home / exterior',7000,18000)]),'porch':('Porch / Deck',[('repair','Repair existing',1800,6500),('basic','Basic uncovered',5000,12000),('covered','Covered porch',12000,24000),('premium','Full outdoor living',18000,36000)]),'doors':('Doors',[('repair','Repair / adjustment',350,900),('one','One replacement',700,1800),('two','Two replacements',1400,3400),('three','Three replacements',2200,5200)]),'other':('Other / Not sure',[('inspection','Inspection / scope review',150,500),('small','Small repair',500,1800),('medium','Medium project',1800,6000),('large','Large project',5000,15000)])}
DEMO={}
def plan(s,p): return next(x for x in S[s][1] if x[0]==p)
def calc(s,p,text,has_photos):
 _,_,lo,hi=plan(s,p);m=1;t=text.lower()
 if any(w in t for w in ['rot','water','leak','mold','structural','sag','damage']):m+=.15
 if any(w in t for w in ['two story','second story','high access']):m+=.12
 if not has_photos:m+=.06
 return int(round(lo*m/50)*50),int(round(hi*m/50)*50)
@app.route('/',methods=['GET','POST'])
def home():
 if request.method=='GET':return render_template('form.html',services=S,plans=json.dumps({k:{x[0]:x[1] for x in v[1]} for k,v in S.items()}))
 s=request.form.get('service','other');p=request.form.get('plan') or S[s][1][0][0];lid=uuid.uuid4().hex[:10]
 details=' | '.join(request.form.get(k,'') for k in ['d1','d2','d3']);photos=request.files.getlist('photos')[:8]
 lo,hi=calc(s,p,request.form.get('description','')+' '+details,bool([f for f in photos if f.filename]));q=plan(s,p)
 DEMO[lid]={'lead_id':lid,'name':request.form.get('name',''),'service':s,'service_label':S[s][0],'plan':p,'plan_label':q[1],'description':request.form.get('description',''),'details':details,'low':lo,'high':hi}
 return redirect(url_for('result',lid=lid))
@app.get('/result/<lid>')
def result(lid):
 x=DEMO.get(lid) or abort(404);ps=S[x['service']][1];i=[a[0] for a in ps].index(x['plan']);return render_template('result.html',x=SimpleNamespace(**x),alts=ps[:i])
@app.post('/downscale/<lid>')
def downscale(lid):
 x=DEMO.get(lid) or abort(404);p=request.form['plan'];q=plan(x['service'],p);lo,hi=calc(x['service'],p,x['description']+' '+x['details'],False);x.update(plan=p,plan_label=q[1],low=lo,high=hi);return redirect(url_for('result',lid=lid))
@app.post('/interest/<lid>')
def interest(lid):
 if lid not in DEMO:abort(404)
 return render_template('thanks.html')
@app.get('/health')
def health():return {'ok':True,'mode':'PUBLIC_DEMO_NO_PERSISTENCE'}
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
