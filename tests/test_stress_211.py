import sys
import re
from pathlib import Path
import subprocess

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engine import HashcatEngine
from name_that_hash.hashes import prototypes
from core.detector import _HASHCAT_FALLBACKS

def run_stress_test():
    print("=== SHATTER 211 HASH MODES STRESS TEST ===")
    
    # 1. Gather all 211 supported modes
    supported_modes = set()
    for p in prototypes:
        if p.modes:
            for mode in p.modes:
                if hasattr(mode, 'hashcat') and mode.hashcat:
                    supported_modes.add(str(mode.hashcat))
                    
    for pattern, mode_name in _HASHCAT_FALLBACKS:
        match = re.search(r'\(m=(\d+)\)', mode_name)
        if match:
            supported_modes.add(match.group(1))

    print(f"[+] Total supported modes expected: {len(supported_modes)}")

    # 2. Parse examples.txt to get the hash and pass for each mode
    examples_file = Path('examples.txt')
    if not examples_file.exists():
        print("[-] examples.txt not found! Run hashcat --example-hashes > examples.txt first.")
        return

    mode_data = {}
    current_mode = None
    current_hash = None
    current_pass = None

    with open(examples_file, 'r', encoding='utf-16', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line.startswith('Hash mode #'):
                match = re.search(r'Hash mode #(\d+)', line)
                if match:
                    current_mode = match.group(1)
            elif line.startswith('Example.Hash') and not line.startswith('Example.Hash.Format'):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    current_hash = parts[1].strip()
            elif line.startswith('Example.Pass'):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    current_pass = parts[1].strip()
                    if current_mode and current_hash and current_pass:
                        mode_data[current_mode] = {'hash': current_hash, 'pass': current_pass}
                        current_mode = None
                        current_hash = None
                        current_pass = None

    # 3. Create a master wordlist
    wordlist_path = Path('tests/stress_wordlist.txt')
    unique_passes = set()
    for m, data in mode_data.items():
        if m in supported_modes:
            unique_passes.add(data['pass'])
            
    with open(wordlist_path, 'w', encoding='utf-8') as f:
        for p in unique_passes:
            f.write(f"{p}\n")
    print(f"[+] Created master wordlist with {len(unique_passes)} unique passwords.")

    # 4. Initialize Engine
    hashcat_exe = Path(r'C:\Users\alpha\Tools\hashcat\hashcat.exe')
    hashcat_dir = Path(r'C:\Users\alpha\Tools\hashcat')
    engine = HashcatEngine(hashcat_exe=hashcat_exe, hashcat_dir=hashcat_dir)

    # 5. Test each mode
    success_count = 0
    fail_count = 0
    
    test_hash_file = Path('tests/stress_temp_hash.txt')

    print("[+] Starting Engine Stress Test...")
    # Filter numeric only
    valid_modes = [m for m in supported_modes if m.isdigit()]
    
    for mode in sorted(valid_modes, key=lambda x: int(x)):
        if mode not in mode_data:
            # Some modes might not have examples in examples.txt
            continue
            
        hash_val = mode_data[mode]['hash']
        
        # Write temporary hash file
        with open(test_hash_file, 'w', encoding='utf-8') as f:
            f.write(f"{hash_val}\n")
            
        try:
            # Tell our engine to build the command
            settings = {
                "hash_file_path": str(test_hash_file.absolute()),
                "wordlist": str(wordlist_path.absolute()),
                "attack_mode": "0",  # Dictionary attack
            }
            cmd = engine._build_hashcat_cmd(
                m_value=mode,
                settings=settings
            )
            
            # Let's run hashcat with --left to just verify syntax and that it accepts the hash
            # We append --left to the command
            cmd.append('--left')
            # Ignore CUDA/OpenCL for fast syntax check
            cmd.append('--backend-ignore-cuda')
            cmd.append('--backend-ignore-opencl')
            
            # We don't want to actually run the full crack because it takes hours.
            # Running with --left checks if the hash matches the mode parser.
            result = subprocess.run(
                cmd,
                cwd=str(hashcat_dir),
                capture_output=True,
                text=True
            )
            
            if result.returncode in [0, 1]:  # Hashcat returns 1 if exhausted/left
                success_count += 1
            else:
                fail_count += 1
                print(f"[-] Mode {mode} failed. Return code: {result.returncode}")
                # DEEP DOWN DEBUGGING
                if result.stdout.strip():
                    print(f"    STDOUT: {result.stdout.strip()}")
                if result.stderr.strip():
                    print(f"    STDERR: {result.stderr.strip()}")
                
        except Exception as e:
            fail_count += 1
            print(f"[-] Mode {mode} crashed our engine: {e}")

    print("\n=== STRESS TEST RESULTS ===")
    print(f"Total Tested: {success_count + fail_count}")
    print(f"Successful Engine Builds & Verifications: {success_count}")
    print(f"Failed: {fail_count}")

    # Cleanup
    if test_hash_file.exists():
        test_hash_file.unlink()
    if wordlist_path.exists():
        wordlist_path.unlink()

if __name__ == '__main__':
    run_stress_test()
