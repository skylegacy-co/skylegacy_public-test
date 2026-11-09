#!/usr/bin/env python3
"""Sky Legacy public lead funnel with durable Supabase storage."""
from flask import Flask, render_template, request, redirect, url_for, abort
from types import SimpleNamespace
from supabase import create_client
from werkzeug.utils import secure_filename
import json, os, uuid

app = Flask(__name__)
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_SECRET_KEY = os.environ.get('SUPABASE_SECRET_KEY', '').strip()
BUCKET = 'project-photos'
ALLOWED = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
MAX_PHOTO_BYTES = 10 * 1024 * 1024

S = {
 'siding':('Siding / Exterior',[('repair','Targeted repair',900,2500),('wall','One wall',3000,6500),('several','Several walls',6500,12000),('whole','Whole exterior',12000,26000)]),
 'flooring':('Flooring',[('repair','Small repair',650,1800),('room','One room',1500,3500),('several','Several rooms',4000,9000),('whole','Whole home',8000,18000)]),
 'tile':('Tile',[('repair','Repair / backsplash',850,2500),('room','Floor or shower',2500,7000),('several','Bathroom remodel',6000,14000),('whole','Multiple areas',10000,24000)]),
 'paint':('Painting',[('repair','Touch-up / small space',600,1600),('room','One room',1000,2500),('several','Several areas',3000,8000),('whole','Whole home / exterior',7000,18000)]),
 'porch':('Porch / Deck',[('repair','Repair existing',1800,6500),('basic','Basic uncovered',5000,12000),('covered','Covered porch',12000,24000),('premium','Full outdoor living',18000,36000)]),
 'doors':('Doors',[('repair','Repair / adjustment',350,900),('one','One replacement',700,1800),('two','Two replacements',1400,3400),('three','Three replacements',2200,5200)]),
 'other':('Other / Not sure',[('inspection','Inspection / scope review',150,500),('small','Small repair',500,1800),('medium','Medium project',1800,6000),('large','Large project',5000,15000)])
}

def db():
 if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
  raise RuntimeError('Supabase environment variables are missing')
 return create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

def plan(service, code):
 return next(x for x in S[service][1] if x[0] == code)

def calc(service, code, text, has_photos):
 _,_,low,high = plan(service, code); multiplier=1; text=text.lower()
 if any(w in text for w in ['rot','water','leak','mold','structural','sag','damage']): multiplier += .15
 if any(w in text for w in ['two story','second story','high access']): multiplier += .12
 if not has_photos: multiplier += .06
 return int(round(low*multiplier/50)*50), int(round(high*multiplier/50)*50)

def get_lead(lead_id):
 result = db().table('leads').select('*').eq('lead_id', lead_id).limit(1).execute()
 return result.data[0] if result.data else None

def upload_photos(client, lead_id, files):
 paths=[]
 for index, f in enumerate(files[:8]):
  if not f or not f.filename: continue
  mime=(f.mimetype or '').lower()
  if mime not in ALLOWED: continue
  data=f.read(MAX_PHOTO_BYTES + 1)
  if not data or len(data) > MAX_PHOTO_BYTES: continue
  original=secure_filename(f.filename)
  extension=ALLOWED[mime]
  if '.' in original:
   candidate='.' + original.rsplit('.',1)[1].lower()
   if candidate in {'.jpg','.jpeg','.png','.webp'}: extension=candidate
  path=f'{lead_id}/{index}_{uuid.uuid4().hex[:8]}{extension}'
  client.storage.from_(BUCKET).upload(path=path, file=data, file_options={'content-type':mime, 'upsert':'false'})
  paths.append(path)
 return paths

@app.route('/', methods=['GET','POST'])
def home():
 if request.method == 'GET':
  return render_template('form.html', services=S, plans=json.dumps({k:{x[0]:x[1] for x in value[1]} for k,value in S.items()}))
 service=request.form.get('service','other')
 if service not in S: service='other'
 code=request.form.get('plan') or S[service][1][0][0]
 valid_codes={x[0] for x in S[service][1]}
 if code not in valid_codes: code=S[service][1][0][0]
 lead_id=uuid.uuid4().hex[:10]
 details=' | '.join(request.form.get(k,'').strip() for k in ['d1','d2','d3'])
 files=request.files.getlist('photos')[:8]
 has_photos=any(f and f.filename for f in files)
 low,high=calc(service,code,request.form.get('description','')+' '+details,has_photos)
 selected=plan(service,code)
 client=db()
 photo_paths=upload_photos(client,lead_id,files)
 row={
   'lead_id':lead_id,'name':request.form.get('name','').strip(),'phone':request.form.get('phone','').strip(),
   'email':request.form.get('email','').strip() or None,'zip':request.form.get('zip','').strip(),
   'urgency':request.form.get('urgency',''),'service':service,'service_label':S[service][0],
   'plan':code,'plan_label':selected[1],'description':request.form.get('description','').strip(),
   'details':details,'preliminary_low':low,'preliminary_high':high,'photo_paths':photo_paths,
   'source':'Sky Legacy website'
 }
 if not row['name'] or not row['phone'] or not row['zip']:
  return 'Name, phone, and ZIP are required.', 400
 client.table('leads').insert(row).execute()
 return redirect(url_for('result',lid=lead_id))

@app.get('/result/<lid>')
def result(lid):
 lead=get_lead(lid)
 if not lead: abort(404)
 ps=S[lead['service']][1]; i=[a[0] for a in ps].index(lead['plan'])
 display={**lead,'low':lead['preliminary_low'],'high':lead['preliminary_high']}
 return render_template('result.html',x=SimpleNamespace(**display),alts=ps[:i])

@app.post('/downscale/<lid>')
def downscale(lid):
 lead=get_lead(lid)
 if not lead: abort(404)
 code=request.form.get('plan','')
 valid={x[0] for x in S[lead['service']][1]}
 if code not in valid: abort(400)
 selected=plan(lead['service'],code)
 low,high=calc(lead['service'],code,(lead.get('description') or '')+' '+(lead.get('details') or ''),bool(lead.get('photo_paths')))
 db().table('leads').update({'plan':code,'plan_label':selected[1],'preliminary_low':low,'preliminary_high':high,'interest':'MAYBE','stage':'QUALIFIED','priority':'MEDIUM','next_action':'Discuss reduced scope'}).eq('lead_id',lid).execute()
 return redirect(url_for('result',lid=lid))

@app.post('/interest/<lid>')
def interest(lid):
 lead=get_lead(lid)
 if not lead: abort(404)
 value=request.form.get('interest','NO')
 if value == 'YES':
  priority='HIGH' if lead.get('urgency') in {'Within 2 weeks','As soon as possible'} else 'MEDIUM'
  updates={'interest':'YES','stage':'QUALIFIED','priority':priority,'next_action':'Contact customer'}
 else:
  updates={'interest':'NO','stage':'FUTURE','priority':'LOW','next_action':'Review smaller scope'}
 db().table('leads').update(updates).eq('lead_id',lid).execute()
 return render_template('thanks.html')

@app.get('/health')
def health():
 return {'ok':True,'mode':'PUBLIC_LIVE_SUPABASE','supabase_configured':bool(SUPABASE_URL and SUPABASE_SECRET_KEY)}

if __name__ == '__main__':
 app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
