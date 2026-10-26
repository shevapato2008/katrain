import urllib.request,time,json,statistics
urls=[('search','http://127.0.0.1:8001/api/v1/kifu/albums?q=%E7%8E%8B%E6%98%9F%E6%98%8A&page=1&page_size=20&lang=cn',5),('all','http://127.0.0.1:8001/api/v1/kifu/albums?page=1&page_size=20&lang=cn',3)]
for label,url,n in urls:
    samples=[]
    for i in range(n):
        start=time.perf_counter()
        response=urllib.request.urlopen(url,timeout=12)
        body=response.read()
        samples.append(round((time.perf_counter()-start)*1000,3))
        time.sleep(.3)
    print(json.dumps(dict(label=label,samples_ms=samples,p50_ms=statistics.median(samples),p95_nearest_rank_ms=sorted(samples)[-1],n=n,bytes=len(body),total=json.loads(body)['total'])),flush=True)
