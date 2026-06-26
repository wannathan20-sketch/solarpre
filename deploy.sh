#!/bin/bash
set -e

echo "Preparing Solar Power Prediction System for deployment"
echo "====================================================="

if [ ! -d ".git" ]; then
    echo "Initializing Git repository..."
    git init
else
    echo "Git repository already exists."
fi

echo "Checking deployable files..."
test -f "solar/app.py"
test -f "solar/requirements.txt"
test -f "solar/solar_model.joblib"
test -f "nixpacks.toml"

echo "Adding files to Git..."
git add .

echo "Creating commit if there are staged changes..."
git commit -m "Prepare solar prediction personal project" || echo "No staged changes to commit."

echo ""
echo "Next steps:"
echo "1. Add your GitHub remote:"
echo "   git remote add origin https://github.com/<username>/<repository>.git"
echo "2. Push the project:"
echo "   git push -u origin main"
echo "3. Create a Zeabur project and add this GitHub repository as a service."
