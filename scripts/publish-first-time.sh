#!/usr/bin/env bash
set -euo pipefail

REMOTE="https://github.com/AASoftIR/resume.git"

git init

git add .
if ! git diff --cached --quiet; then
  git commit -m "feat: JSON-driven 3D resume with PDF build pipeline"
fi

git branch -M main
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE"
else
  git remote add origin "$REMOTE"
fi

git push -u origin main

echo
echo "Published. GitHub Actions will build the PDF and deploy Pages."
echo "Live site: https://aasoftir.github.io/resume/"
echo "PDF:       https://aasoftir.github.io/resume/resume.pdf"
