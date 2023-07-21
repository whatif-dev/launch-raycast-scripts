#!/usr/bin/env python3
#
# Utility library for interacting with the Quip API and for other common
# functions.
#
# Diego Zamboni <diego@zzamboni.org>

import quip
import os
import sys
import subprocess
import re
from datetime import datetime
from configparser import ConfigParser, ExtendedInterpolation

config = None
config_file = "quip_config.ini"

# Custom config interpolation class that allows interpolating the current
# section name.
# Code from https://stackoverflow.com/a/47360765
class ExtendedSectionInterpolation(ExtendedInterpolation):
    def before_get(self, parser, section, option, value, defaults):
        defaults.maps.append({'section': section})
        return super().before_get(parser, section, option, value, defaults)

# Print error message and exit with a non-zero code.
def fail(message):
    red = "\u001b[31m"
    print(red + message)
    sys.exit(1)

# Produce a macOS notification message
def notify(title, text):
    CMD = '''
    on run argv
      display notification (item 2 of argv) with title (item 1 of argv)
    end run
    '''
    subprocess.call(['osascript', '-e', CMD, title, text])

# Read configuration file into global config variable.
def readConfig(filename=config_file):
    global config
    config = ConfigParser(interpolation=ExtendedSectionInterpolation())
    files_read = config.read(filename)
    if filename not in files_read:
        fail(f"Could not read config file '{filename}'.")

# Check whether the APIToken field has a non-empty value and exit if it doesn't.
# Does not verify that it's valid.
def checkAPIToken(doc_type):
    if config[doc_type].get('APIToken', "") == "":
        fail(f"Error: Please configure APIToken in {config_file}.")

# Put a string in the macOS clipboard using the pbcopy command.
#
# Function originally from
# https://gist.github.com/XuankangLin/7ec82f80a0044a52330720244de2d15a modified
# to automatically call encode('utf_8') on its argument, with the assumption
# that it's a string.
def setClipboardData(text):
    p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    p.stdin.write(text.encode('utf_8'))
    p.stdin.close()
    retcode = p.wait()

def quip_open(thing, doc_type='DEFAULT'):
    # thing can be a DocID or a URL. DocIDs are 11 or 12 characters long
    if len(thing) in {11, 12}:
        url = config[doc_type].get('BaseURL', 'https://quip.com/') + thing
    else:
        url = thing
    app_args = ["-a", "Quip"] if config[doc_type].getboolean('UseQuipApp') else []
    try:
        open_args=["/usr/bin/open", *app_args, url]
        # We use Popen to put the open process in the background.
        pid = subprocess.Popen(open_args).pid
    except OSError as e:
        fail(f"Execution failed: {e}")

# Normalize a string by lowercasing and replacing whitespace with dashes.
def normalize(s):
    return re.sub('\W+', '-', s.lower())

# Create a new document in Quip.
#
# The document is created according to the configuration associated with the
# given doc_type. This indicates parameters such as the APIToken to use, whether
# to prepend the current date to the text, and the folder in which the document
# should be stored. See quip_config.ini for the full list of available
# configuration parameters.
#
def quip_new_doc(doc_type, text):
    readConfig()
    if not config.has_section(doc_type):
        denormalized_types = {normalize(t): t for t in config.sections()}
        if doc_type in denormalized_types:
            doc_type = denormalized_types[doc_type]
        else:
            fail(f"Error: Quip document type '{doc_type}' is not defined in {config_file}.")
    checkAPIToken(doc_type)

    # Prepend date to the text if needed
    if text and config[doc_type].getboolean('PrependDate'):
        dateformat = config[doc_type].get('DateFormat', "%Y-%m-%d")
        text = f"{datetime.now().strftime(dateformat)} {text}"

    # What to do?
    action = config[doc_type].get('action', 'create')
    # Notification message to produce at the end
    message_title = ""
    message_body = ""

    try:
        client = quip.QuipClient(access_token=config[doc_type]['APIToken'], base_url=config[doc_type]['APIURL'])

        if action == 'create':
            folderID = config[doc_type].get('FolderID',None)
            folders = [folderID] if folderID else []
            if templateID := config[doc_type].get('TemplateID', None):
                result = client.copy_document(templateID, folder_ids=[folderID], title=text)
            else:
                result = client.new_document(content=text, format="markdown", member_ids=folders)
            message_title = f"New {doc_type} created"
            message_body = message_title
        elif action == 'add':
            listtype = config[doc_type].get('ListType', 'none')
            docid = config[doc_type].get('DocID', None)
            if not docid:
                fail("Error: no DocID provided, needed for 'add' action.")
            if text:
                listmarkup = { "todo": "[] ", "bullet": "- ", "num": "1. " }
                if listtype in listmarkup:
                    text = listmarkup[listtype] + text
                result = client.edit_document(docid, text, format='markdown', section_id='')
                message_title = f"New {doc_type} added to document"
                message_body = message_title
            else:
                if config[doc_type].getboolean('OpenDocIfEmptyArg'):
                    message_title = f"Opening {doc_type} document"
                quip_open(docid, doc_type)
                sys.exit(0)
        else:
            fail(f"Error: Invalid action value '{action}', should be 'create' or 'add'.")

    except Exception as e:
        if e.code == 401:
            fail(f"Please configure/verify your Quip API token in {config_file}")
        elif e.code == 400:
            fail(f"Please configure/verify folder ID for [{doc_type}] in {config_file}")
        else:
            fail("Received a Quip error:", e, file=sys.stderr)

    if result:
        if url := result['thread']['link']:
            if config[doc_type].getboolean('CopyURLToClipboard'):
                setClipboardData(url)
                message_body = f"{message_body}, URL copied to clipboard"

            if config[doc_type].getboolean('OpenDoc'):
                message_body = f"{message_body}, opening {url}"
                quip_open(url, doc_type)
            message_body = f"{message_body}."
            print(message_body)
            if config[doc_type].getboolean('Notify'):
                notify(message_title, message_body)
        else:
            fail("Something went wrong, could not get the document URL.")
    else:
        fail("Something went wrong, could not create document.")
