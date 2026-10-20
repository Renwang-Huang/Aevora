from runtime import *
argv=json.loads((E/'commands/v4-clean-public-only-install/receipt.json').read_text())['argv']
old=str(E/'05_product/clean_install');new=E/'05_product/clean_install_retry2';new.mkdir(mode=0o700);base=[str(new) if x==old else x for x in argv[:-4]]
write(E/'05_product/CLEAN_INSTALL_RETRY1_FAILURE.json',{'classification':'EXTERNAL_PROTOCOL_CLIENT_BOOTSTRAP_SDK_NOT_INSTALLED','at':now(),'actual':'Public Core wheel installed in inner venv and Core serve started; outer probe client lacked mcp module','original_exception':'ModuleNotFoundError mcp','owner_grant_revoked':True,'fix':'Fresh public-only bootstrap with actual pinned official client SDK, retained original protocol assertions','source_assertions_unchanged':True})
assert record('v4-public-only-bootstrap-venv-retry2',[*base,'/usr/bin/python3.12','-m','venv','/install/bootstrap'])==0
assert record('v4-public-only-client-sdk-install-retry2',[*base,'/install/bootstrap/bin/python','-m','pip','install','mcp==1.26.0'])==0
assert record('v4-clean-public-only-install-retry2',[*base,'/install/bootstrap/bin/python','/probe.py','--label','pregen2-clean-onboarding'])==0
print('V4 clean public-only installation PASS')
