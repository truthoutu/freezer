@echo off
python -c "with open('targets_registry.py','r',encoding='utf-8') as fh:
    lines = fh.readlines()

# Find Germany section and add more URLs
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    
    # After Germany default line, add more URLs
    if 'Germany' in line and i < len(lines)-1:
        # Skip to end of Germany section
        j = i
        while j < len(lines) and not (lines[j].strip().startswith('}') and j > i + 5):
            j += 1
        # Add extra URLs before closing
        if j < len(lines):
            extra = [
                '            # Additional URLs for broader coverage
',
            ]
            new_lines.extend(extra)
    
    i += 1

with open('targets_registry.py','w',encoding='utf-8') as fh:
    fh.writelines(new_lines)

print('Done')"
