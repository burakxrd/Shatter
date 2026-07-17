import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.detector import detect_hash_type

def get_hashcat_examples():
    """Run hashcat --example-hashes and parse the output."""
    try:
        with open('examples.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Could not read examples.txt: {e}")
        return []

    examples = []
    current_mode = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('Hash mode #'):
            match = re.search(r'Hash mode #(\d+)', line)
            if match:
                current_mode = match.group(1)
        elif line.startswith('Example.Hash') and not line.startswith('Example.Hash.Format'):
            # e.g., Example.Hash........: 8743b52063cd84097a65d1633f5c74f5
            parts = line.split(':', 1)
            if len(parts) == 2:
                hash_val = parts[1].strip()
                if current_mode and hash_val:
                    examples.append((current_mode, hash_val))
                    current_mode = None
                
    return examples

def run_comprehensive_test():
    examples = get_hashcat_examples()
    if not examples:
        return

    print(f"Found {len(examples)} example hashes from Hashcat.")
    
    success_count = 0
    fail_count = 0
    
    failed_modes = []

    for mode, hash_val in examples:
        result = detect_hash_type(hash_val)
        
        # We consider it a success if the exact mode (m=XXXX) is present in the result
        target = f"(m={mode})"
        if target in result:
            success_count += 1
        else:
            fail_count += 1
            failed_modes.append((mode, hash_val, result))

    total = success_count + fail_count
    success_rate = (success_count / total) * 100 if total > 0 else 0
    
    with open('mass_test_results.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(f"--- RESULTS ---\n")
        out_f.write(f"Total Hashes Tested: {total}\n")
        out_f.write(f"Successfully Detected: {success_count}\n")
        out_f.write(f"Failed / Missing: {fail_count}\n")
        out_f.write(f"Accuracy: {success_rate:.2f}%\n")
        
        if failed_modes:
            out_f.write("\nFailures:\n")
            for mode, h, res in failed_modes:
                out_f.write(f"Mode {mode} | Expected: (m={mode}) | Got: {res}\n")

if __name__ == '__main__':
    run_comprehensive_test()
