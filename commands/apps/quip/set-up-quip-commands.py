#!/usr/bin/env python3

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Set up Quip commands
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon /Applications/Quip.app/Contents/Resources/AppIcon.icns
# @raycast.packageName Quip utilities
# @raycast.needsConfirmation true

# Documentation:
# @raycast.description Create script commands for creating Quip documents, based on the configuration in quip_config.ini.
# @raycast.author diego_zamboni
# @raycast.authorURL https://raycast.com/diego_zamboni

import quip_utils
import os
import glob

# Read template
cmd_template="quip-new.template.py"
with open(cmd_template, 'r') as file:
    template = file.read()

blue = "\u001b[34m"
yellow = "\u001b[33m"
green = "\u001b[32m"
red = "\u001b[31m"

print("Reading quip_config.ini...")
quip_utils.readConfig()
doc_types = quip_utils.config.sections()
quip_utils.checkAPIToken('DEFAULT')
print(
    f"{blue}The configuration file contains the following document types: {' '.join(doc_types)}"
)

print(f"{yellow}Removing old scripts before creating new ones...")
for file in glob.glob("quip-new-*.py"):
    print(f"{yellow}   {file}")
    os.remove(file)

for type in doc_types:
    new_script = template
    normalized_type = quip_utils.normalize(type)
    filename = f"quip-new-{normalized_type}.py"
    print(f"{blue}Creating script for '{type}': ", end="")
    # Replace config values in template
    template_values = {}
    for k,v in quip_utils.config[type].items():
        # If it's a boolean value, convert it to a JSON-style boolean (i.e. "true" or "false", all lowercase)
        if v in quip_utils.config.BOOLEAN_STATES.keys():
            v = str(quip_utils.config[type].getboolean(k)).lower()
        template_k = "{{" + k + "}}"
        new_script = new_script.replace(template_k, v)
    with open(filename, 'w') as file:
        file.write(new_script)
        print(f"{green}{filename}")
