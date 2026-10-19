from runtime import *
argv=json.loads((E/'commands/v4-clean-public-only-install/receipt.json').read_text())['argv']
assert argv[-4:]==['/usr/bin/python3.12','/probe.py','--label','pregen2-clean-onboarding']
old=str(E/'05_product/clean_install');new=E/'05_product/clean_install_retry1';new.mkdir(mode=0o700)
base=[str(new) if x==old else x for x in argv[:-4]]
write(E/'05_product/CLEAN_INSTALL_ATTEMPT1_FAILURE.json',{'classification':'BASE_TOOLCHAIN_HAS_ENSUREPIP_BUT_NO_SYSTEM_PIP','first_exit':1,'source_assertions_unchanged':True,'fix':'Create actual bootstrap venv inside public-only namespace, then run original SDK assertions with that Python','prior_output_preserved':old,'new_output':str(new),'at':now()})
assert record('v4-public-only-bootstrap-venv',[*base,'/usr/bin/python3.12','-m','venv','/install/bootstrap'])==0
assert record('v4-clean-public-only-install-retry1',[*base,'/install/bootstrap/bin/python','/probe.py','--label','pregen2-clean-onboarding'])==0
print('V4 clean install retry PASS')
