#!/bin/bash
# Script to build and publish the package to PyPI

echo "Building package..."
python -m build

echo "Checking package..."
python -m twine check dist/*

echo "Uploading to PyPI..."
echo "Make sure you have your PyPI credentials configured!"
python -m twine upload dist/*

echo "Done!"

