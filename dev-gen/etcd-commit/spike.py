import time, json, signal, subprocess
from cluster import *
c=Cluster("/tmp/sp")
time.sleep(4)
for k in range(5):
    print(call(0,"/v3/kv/put",{"key":b64(f"/a/{k}"),"value":b64("v")}))
print(call(1,"/v3/kv/range",{"key":b64("/a/"),"range_end":b64("/a0")})["header"])
print(call(2,"/v3/kv/txn",{"compare":[{"key":b64("/a/1"),"target":"VERSION","result":"EQUAL","version":"1"}],"success":[{"request_put":{"key":b64("/a/1"),"value":b64("w")}}],"failure":[]}))
print(call(2,"/v3/kv/deleterange",{"key":b64("/zz")}))
print(call(2,"/v3/lease/grant",{"TTL":5}))
time.sleep(1)
c.killall()
print(subprocess.run(["etcd-dump-logs","/tmp/sp/m4/data"],capture_output=True,text=True).stdout[-3000:])
print(subprocess.run(["etcd-dump-db","iterate-bucket","/tmp/sp/m4/data","key","--decode"],capture_output=True,text=True).stdout[-1500:])
print(subprocess.run(["etcd-dump-db","iterate-bucket","/tmp/sp/m4/data","meta","--decode"],capture_output=True,text=True))
