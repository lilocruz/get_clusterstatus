import json
import requests
from requests.auth import HTTPBasicAuth
#import maskpass
import argparse
import sys
import concurrent.futures
import asyncio
import pprint
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("-t", help="Specify Target Fusion Environment IP/Hostname", required=True)
parser.add_argument("-u", help="Specify Fusion username", required=True)
parser.add_argument("-f", help="Specify file name to write to", required=False)
args = parser.parse_args()

def firstPassword(item_property):
    try:
        items = subprocess.check_output(["op", "item", "get", item_property], stderr=subprocess.STDOUT).decode("utf-8")
        lines = items.split("\n")
        for line in lines:
            if line.strip().startswith("password:"):
                password = line.split(":")[1].strip()
                return password
        
        print("Error: Password not found in 1Password")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching password from 1Password: {e.output}")
        sys.exit(1)

def get_collections(url, username, pwd):
    headers =  {"Content-Type":"application/json"}
    basic   = HTTPBasicAuth(username, pwd)
    
    if url.endswith("/"):
        url = url[:-1]

    response = requests.get(url + "/api/collections", auth=basic, headers=headers)
    
    return response.json()

def get_collection_status(url, username, pwd):
    headers =  {"Content-Type":"application/json"}
    basic   = HTTPBasicAuth(username, pwd)
    
    if url.endswith("/"):
        url = url[:-1]
    
    response = requests.get(url, auth=basic, headers=headers)

    return response.json()

def get_collection_urls(url, ids_list):

    return_list = list()

    if url.endswith("/"):
        url = url[:-1]

    for id in ids_list:
       return_list.append(url + "/api/collections/" + id + "/status/")

    return return_list

def write_to_file(file_path, content):
    with open(file_path, "w") as dest:
        pprint.pprint(json.loads(content), dest)
    return

async def main():
    # get CLI args
    cmd_args   = sys.argv
    url        = str()
    pwd        = firstPassword("Kohler-dev-Readonly-FusionUI")
    filename   = str()
    write_file = False

    for opt in range(len(cmd_args)):
        # this flag will set commit to true, regardless of config
        if cmd_args[opt] == '-t':
            url = cmd_args[opt + 1]
            if not url.startswith("http"):
                url = "https://" + url
        if cmd_args[opt] == '-u':
            username = cmd_args[opt + 1]
        if cmd_args[opt] == '-f':
            write_file = True
            filename   = cmd_args[opt + 1]
    
    # get list of all Solr collections for Fusion env
    collections_list = get_collections(url, username, pwd)
    ids_list         = list()
    urls_list        = list()
    
    for collection in collections_list:
        this_id = collection["id"]
        ids_list.append(this_id)

    urls_list = get_collection_urls(url, ids_list)

    clusterstatus_dict = dict()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10000) as executor:
        futures = []
        for url in urls_list:futures.append(executor.submit(get_collection_status, url, username, pwd))
        concurrent.futures.wait(futures)
        for status in futures:
            if "configName" not in status.result().keys():
                continue
            this_status = status.result()
            this_id     = this_status["configName"]
            clusterstatus_dict[this_id] = status.result()
    
    if write_file:
        write_to_file(filename, json.dumps(clusterstatus_dict, indent=4))
    else:
        print(json.dumps(clusterstatus_dict, indent=4))


if __name__ == '__main__':
    asyncio.run(main())