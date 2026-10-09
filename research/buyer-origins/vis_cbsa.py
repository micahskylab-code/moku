import sys, json, openpyxl
wb=openpyxl.load_workbook(sys.argv[1],read_only=True,data_only=True)
ws=[w for w in wb.worksheets if w.title.strip()=='TABLE 55'][0]
rows=[]
for i,row in enumerate(ws.iter_rows(values_only=True)):
    if i>=3 and row[0] and isinstance(row[1],(int,float)):
        rows.append(dict(metro=row[0].strip(),total=row[1],Oahu=row[2],Maui=row[4],Kauai=row[7],Hawaii=row[8]))
UT=[r for r in rows if r['metro'] in ('Salt Lake City UT','Provo-Orem UT','Ogden-Clearfield UT')]
assert len(UT)==3
rows=[r for r in rows if r not in UT]+[dict(metro='Salt Lake City–Provo–Ogden UT',**{k:sum(r[k] for r in UT) for k in ('total','Oahu','Maui','Kauai','Hawaii')})]
T=sum(r['total'] for r in rows)
out={}
for isl in ['Oahu','Maui','Kauai','Hawaii']:
    base=sum(r[isl] for r in rows)/T
    lst=[dict(metro=r['metro'],n=r[isl],share=r[isl]/r['total'],idx=(r[isl]/r['total'])/base) for r in rows]
    out[isl]=dict(base=base,top=sorted(lst,key=lambda d:-d['n'])[:10],over=sorted([d for d in lst if d['n']>=10000],key=lambda d:-d['idx'])[:10])
json.dump(dict(metros=rows,islands=out,n_metros=len(rows)),open(sys.argv[2],'w'),ensure_ascii=False)
for isl,o in out.items():
    print('==',isl,'base %.3f'%o['base'])
    print('  top:', ', '.join(f"{d['metro'].split('-')[0].split(' ')[0]} {d['n']:,}" for d in o['top'][:8]))
    print('  over (>=10k):', ', '.join(f"{d['metro'][:22]} {d['idx']:.2f} ({d['n']:,})" for d in o['over'][:10]))
