# quorum-loss — submission sheet

**Phase-1 idea check (advisory):**
Disaster recovery for an etcd 3.5.17 cluster that lost quorum for good. Three of five members are gone. The agent gets the m4 and m5 data dirs (raft WAL, snap files, bbolt backend) as found on disk, and the services' JSON logs of every grpc gateway call (sent/finished times, member hit, request body, response headers with revision and raft_term, or the error). It must write /app/out/restore.db, an etcd snapshot holding exactly the keys whose raft committed final value the evidence settles, and /app/out/uncertain.txt with exactly the keys it cannot settle. Traps: m5 has the longest log, but past index 2052 it is a dead term 2 branch; m4's persisted commit (2459) lags the truth; 13 committed writes exist on no surviving disk and only their acks show them; m4's unacked last entry is settled only by the raft_term bound in later response headers; one revision slot with a lost ack has 9 in-flight candidates; refused calls never reached etcd. Graded all or nothing: the verifier restores the snapshot with real etcdutl, boots etcd and reads the keyspace back.

**Category:** Software
**Labels:** Databases, Systems
**Task name:** quorum-loss
**Bundle:** tasks/quorum-loss/quorum-loss.zip
