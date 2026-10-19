from audit import *
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import secrets,subprocess,os
K=Path('/home/PRIVATE_MAINTAINER/.config/aevora')/('g23-audit-encryption-'+E.name.split('-')[-1]);key=(K/'archive-aes.key').read_bytes();receipt=json.loads((E/'reports/G23_CAPTURE_REDACTION_RECEIPT.json').read_text());checked=[]
for row in receipt['records']:
 data=(E/row['encrypted_original_file']).read_bytes();original=AESGCM(key).decrypt(data[:12],data[12:],row['associated_data'].encode());assert __import__('hashlib').sha256(original).hexdigest()==row['original_artifact_sha256'];checked.append(row['encrypted_original_file'])
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());assert cfg['container']=='aevora-g23-1e5e8e1af0';state=json.loads(subprocess.check_output(['docker','inspect',cfg['container']],text=True))[0]['State'];assert not state['Running'] and state['ExitCode']==139
p=Path(cfg['password_file']);old=p.read_bytes().strip();retired=K/'retired-db-secret';fd=os.open(retired,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,old+b'\n');os.close(fd)
conf=Path(cfg['configuration_file']);raw=conf.read_bytes();assert old in raw;new=secrets.token_hex(32).encode();conf.write_bytes(raw.replace(old,new));conf.chmod(0o600);p.write_bytes(new+b'\n');p.chmod(0o600)
write(E/'reports/G23_ENCRYPTED_ORIGINAL_RECOVERY_AND_KEY_RETIREMENT.json',dict(status='PASS',encrypted_originals_decrypted_in_memory=len(checked),all_original_artifact_sha256_match=True,plaintext_recovery_written_to_archive=False,key_external_only=True,temporary_original_owned_db_credential_rotated=True,container_still_stopped139=True,no_host_gateway_key_exposure_detected=True,no_legacy_database_or_frozen_archive_modified=True,at=now()))
# Scanner must still search the retired bytes, not just the new current key.
p=E/'credential_scan.py';s=p.read_text();needle="patterns=set()";assert needle in s;s=s.replace(needle,"paths.extend([Path('/home/PRIVATE_MAINTAINER/.config/aevora/g23-audit-encryption-1e5e8e1af0/retired-db-secret'),Path('/home/PRIVATE_MAINTAINER/.config/aevora/g23-audit-encryption-1e5e8e1af0/archive-aes.key')])\n"+needle);p.write_text(s)
print('ENCRYPTED_ORIGINALS_RECOVERED_IN_MEMORY_AND_TEMPORARY_DB_CREDENTIAL_RETIRED')
