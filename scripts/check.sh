#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -v
node --check app/static/app.js
node --check app/static/upgrade.js
node --check app/static/redesign.js
node --check app/static/appearance.js
node --check app/static/compact.js
node --check app/static/feed.js
node --check app/static/weighing-report.js
node --check app/static/weekly-report.js
node --check app/static/cohort-link.js
node --check app/static/review.js
node --check app/static/feed-setup.js

node --check app/static/weekly-pdf.js

node --check app/static/feed-review.js

node --check app/static/movement-review.js

node --check app/static/feed-bulk.js
