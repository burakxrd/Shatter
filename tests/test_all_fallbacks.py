import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.detector import detect_hash_type, _HASHCAT_FALLBACKS

def generate_dummy(pattern_obj):
    p = pattern_obj.pattern
    # Only remove ^ at start and $ at end (but not if it's \$)
    if p.startswith('^'): p = p[1:]
    if p.endswith('$') and not p.endswith('\\$'): p = p[:-1]
    
    # Replace escaped characters
    p = p.replace('\\*', '*').replace('\\$', '$').replace('\\.', '.')
    p = p.replace('\\{', '{').replace('\\}', '}')
    p = p.replace('\\d+', '123')
    p = p.replace('[a-fA-F0-9]+', 'abcdef1234')
    p = p.replace('[a-fA-F0-9]{136}', 'a'*136)
    p = p.replace('[a-fA-F0-9]{88}', 'a'*88)
    p = p.replace('[A-Fa-f0-9]{40}', 'a'*40)
    p = p.replace('[a-f0-9]{32}', 'a'*32)
    p = p.replace('[A-Fa-f0-9]{60}', 'a'*60)
    p = p.replace('[a-f0-9]{40}', 'a'*40)
    p = p.replace('[a-fA-F0-9]{16}', 'a'*16)
    p = p.replace('[a-fA-F0-9]{32}', 'a'*32)
    p = p.replace('[a-fA-F0-9]{48}', 'a'*48)
    p = p.replace('[a-f0-9]+', 'a'*10)
    p = p.replace('[^:]+', 'user')
    p = p.replace('\\S+', 'domain')
    p = p.replace('(?i)', '')

    # Handle alternating groups
    if '(1password|agilekeychain)' in p:
        p = p.replace('(1password|agilekeychain)', '1password')
    if 'pkzip2?' in p:
        p = p.replace('pkzip2?', 'pkzip2')
    if 'zip2?' in p:
        p = p.replace('zip2?', 'zip')
    return p

print('| Hash Type | Regex Pattern | Dummy Test Hash | Detection Result | Pass? |')
print('| --- | --- | --- | --- | --- |')

all_passed = True
for regex, label in _HASHCAT_FALLBACKS:
    dummy = generate_dummy(regex)
    result = detect_hash_type(dummy)
    
    passed = (result == label)
    if not passed:
        all_passed = False
    
    pass_str = "PASS" if passed else "FAIL"
    print(f'| {label} | `{regex.pattern}` | `{dummy[:30]}...` | {result} | {pass_str} |')

print(f'\nOverall: {"ALL PASSED" if all_passed else "SOME FAILED"}')
