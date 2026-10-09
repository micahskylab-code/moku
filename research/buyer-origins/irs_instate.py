import csv,sys,glob,os,json
names={'001':'Hawaii Island','003':'Oahu','005':'Kalawao','007':'Kauai','009':'Maui'}
res={}
for f in sorted(glob.glob(os.path.join(sys.argv[1],'countyinflow*.csv'))):
    yr=os.path.basename(f)[12:16]; yy=f'20{yr[:2]}-{yr[2:]}'
    d={}
    with open(f,encoding='latin-1') as fh:
        for r in csv.DictReader(fh):
            r={k.lower():v for k,v in r.items()}
            for k in ('y2_statefips','y1_statefips'): r[k]=r[k].zfill(2)
            for k in ('y2_countyfips','y1_countyfips'): r[k]=r[k].zfill(3)
            if r['y2_statefips']!='15': continue
            dst=names.get(r['y2_countyfips'])
            n=int(r['n1']); agi=int(r['agi'])
            if r['y1_statefips']=='15' and r['y1_countyfips']!=r['y2_countyfips'] and r['y1_countyfips'] in names:
                d.setdefault(dst,{})['from '+names[r['y1_countyfips']]]=(n,agi)
            if r['y1_statefips']=='97' and r['y1_countyfips']=='001': d.setdefault(dst,{})['same state total']=(n,agi)
            if r['y1_statefips']=='97' and r['y1_countyfips']=='003': d.setdefault(dst,{})['other states total']=(n,agi)
            if r['y1_statefips']!='15' and r['y1_statefips'] not in ('96','97','98','57','58','59') :
                k='top-other'
                cur=d.setdefault(dst,{}).get(k)
                if cur is None or n>cur[0]: d[dst][k]=(n,agi,r['y1_countyname'],r['y1_state'])
    res[yy]=d
json.dump(res,open(sys.argv[2],'w'))
for yy,d in res.items():
    print('==',yy)
    for dst in ['Maui','Kauai','Hawaii Island','Oahu']:
        print('  ',dst, {k:v for k,v in d.get(dst,{}).items()})
