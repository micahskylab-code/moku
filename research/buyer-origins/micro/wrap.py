# Wrap the scratch build as a standalone HTML document (same wrapper as the repo copy).
import sys
S = '/tmp/claude-0/-home-user-moku/72fb7234-fad9-5bdc-aaaa-c922016ddc21/scratchpad'
n = open(f'{S}/hawaii-buyer-origins.html').read()
head = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
k = n.find('\n<nav class="bar"'); assert k > 0 and n[:k].rstrip().endswith('</style>')
out = head + n[:k].rstrip('\n') + '\n</head>\n<body>\n\n' + n[k:].lstrip('\n')
out = out.rstrip('\n') + '\n</body>\n</html>\n'
open(sys.argv[1], 'w').write(out)
