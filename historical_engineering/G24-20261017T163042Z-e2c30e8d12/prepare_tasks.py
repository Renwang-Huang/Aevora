from audit import *
import random,csv
specs=[('P01','PILOT','A','read-only-lock','DELETE',12,'POSITIVE_TRANSFER'),('P02','PILOT','D','buggy','WAL',12,'NEGATIVE_TRANSFER'),('F01','FORMAL','A','read-only-lock','WAL',15,'POSITIVE_TRANSFER'),('F02','FORMAL','A','read-only-lock','DELETE',20,'POSITIVE_TRANSFER'),('F03','FORMAL','D','buggy','DELETE',15,'NEGATIVE_TRANSFER'),('F04','FORMAL','D','buggy','WAL',20,'NEGATIVE_TRANSFER'),('F05','FORMAL','D','split-ledger','DELETE',20,'NEGATIVE_TRANSFER'),('F06','FORMAL','D-V02','buggy','DELETE',15,'UNKNOWN_OR_CONFLICT'),('F07','FORMAL','D-V02','local_lock','WAL',20,'UNKNOWN_OR_CONFLICT'),('F08','FORMAL','D-V02','blind_cleanup','DELETE',20,'UNKNOWN_OR_CONFLICT')]
rng=random.Random(20261018);blocks=[]
for n,stage,ep,fault,journal,timeout,condition in specs:
 arms=['GRAPH','RAW_MEMORY','NO_MEMORY'];rng.shuffle(arms)
 blocks.append(dict(block=n,stage=stage,episode=ep,fault=fault,journal=journal,busy_timeout=timeout,condition=condition,seed=rng.randrange(2**31),arm_order=arms))
write(E/'01_protocol/TASKS_DRAFT.json',blocks)
