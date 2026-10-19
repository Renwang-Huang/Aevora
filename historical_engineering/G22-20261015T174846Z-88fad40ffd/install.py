import subprocess,sys
subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--no-build-isolation','-e','.', '-e','aevora_core','-e','console'],check=True)
