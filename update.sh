# will update all of the quartet dependency files
echo "Updating quartet_integrations dependency files..."
pip-compile requirements_test.in -o requirements_test.txt --upgrade
pip-compile requirements.in -o requirements.txt --upgrade
pip-compile requirements_dev.in -o requirements_dev.txt --upgrade
echo "Complete."

