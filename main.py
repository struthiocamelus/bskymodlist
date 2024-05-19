#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timezone
import json

import atproto_client.exceptions
import click
import backoff
from atproto import Client

client = Client(base_url="https://bsky.social")
atproto_client_info = {}


def iso_8601_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@backoff.on_exception(
    backoff.expo,
    atproto_client.exceptions.RequestException,
    max_time=300
)
def search_actors(query, limit, cursor=None):
    return client.app.bsky.actor.search_actors({'q': query, 'limit': limit, 'cursor': cursor})


def drain_all_actors(query):
    limit = 100
    response = search_actors(query, limit)
    for actor in response.actors:
        yield actor
    while response.cursor is not None:
        response = search_actors(query, limit, response.cursor)
        for actor in response.actors:
            yield actor


def search_user(username):
    """Search for a user on Bluesky by username."""
    try:
        for actor in drain_all_actors(username):
            print(f"{actor.did} {actor.handle} -- {actor.display_name}")
    except Exception as e:
        click.echo(f"An exception occurred: {e}")


def extract_did(line):
    return line[0:32]


@backoff.on_exception(
    backoff.expo,
    atproto_client.exceptions.RequestException,
    max_time=300
)
def create_atproto_list(list_name, my_did):
    return client.com.atproto.repo.create_record({
        "collection": "app.bsky.graph.list",
        "record": {
            "$type": "app.bsky.graph.list",
            "createdAt": iso_8601_now(),
            "description": list_name,
            "name": list_name,
            "purpose": "app.bsky.graph.defs#modlist"
        },
        "repo": my_did
    })


@backoff.on_exception(
    backoff.expo,
    atproto_client.exceptions.RequestException,
    max_time=300
)
def create_atproto_list_item(list_uri, did, my_did):
    client.com.atproto.repo.create_record({
        "collection": "app.bsky.graph.listitem",
        "record": {
            "$type": "app.bsky.graph.listitem",
            "createdAt": iso_8601_now(),
            "list": list_uri,
            "subject": did
        },
        "repo": my_did
    })


@backoff.on_exception(
    backoff.expo,
    atproto_client.exceptions.RequestException,
    max_time=300
)
def get_atproto_list(list_key, my_did):
    return client.app.bsky.graph.get_list({
        "list": f"at://{my_did}/app.bsky.graph.list/{list_key}",
        "limit": 1
    })


@backoff.on_exception(
    backoff.expo,
    atproto_client.exceptions.RequestException,
    max_time=300
)
def get_atproto_lists(did, limit=100, cursor=None):
    return client.app.bsky.graph.get_lists({
        "actor": did,
        "limit": limit,
        "cursor": cursor
    })


def drain_atproto_lists(did):
    response = get_atproto_lists(did)
    for mod_list in response.lists:
        yield mod_list
    while response.cursor is not None:
        response = get_atproto_lists(did, cursor=response.cursor)
        for mod_list in response.lists:
            yield mod_list


def find_all_lists():
    """Find all moderation lists for user."""
    try:
        my_did = atproto_client_info['login_response']['did']
        lists = drain_atproto_lists(my_did)
        for mod_list in lists:
            print(f"{mod_list.uri} -- {mod_list.name} {mod_list.description}")
    except Exception as e:
        click.echo(f"An error occurred: {e}")


def add_to_moderation_list(list_name=None, list_did=None, filename=None):
    """Add users from a newline delimited file to the moderation list."""
    try:
        my_did = atproto_client_info['login_response']['did']
        with open(filename, 'r') as file:
            lines = file.read().splitlines()

        if list_name is not None:
            moderation_list = create_atproto_list(list_name, my_did)
        elif list_did is not None:
            moderation_list = get_atproto_list(list_did, my_did)
            moderation_list = moderation_list['list']
        else:
            raise RuntimeError("This should never happen")

        for line in lines:
            did = extract_did(line)
            if not did.startswith("did:plc:"):
                click.echo(f"{did} doesn't look like a DID, skipping...")
            click.echo(f"Adding record to modlist: {line}")
            try:
                create_atproto_list_item(moderation_list['uri'], did, my_did)
            except Exception as e:
                click.echo(f"Failed to add {did} to modlist, continuing...")

        click.echo(f"Added {len(lines)} user(s) to the moderation list.")
    except Exception as e:
        click.echo(f"An error occurred: {e}")


@click.group()
@click.option("--config", default=os.path.join(os.path.expanduser("~"), ".config", "bskymodlist.json"),
              help="Location of configuration file")
def cli(config):
    """Bluesky CLI tool."""
    atproto_username = None
    atproto_app_password = None
    try:
        config_file_contents = json.load(open(config))
        atproto_username = config_file_contents['atproto_username']
        atproto_app_password = config_file_contents['atproto_app_password']
    except:
        click.echo("No configuration file specified, getting credentials from command line.")
    if atproto_username is None:
        atproto_username = os.environ.get("ATPROTO_USERNAME", None)
    if atproto_username is None:
        atproto_username = click.prompt("Enter your bluesky username", type=str)
    if atproto_app_password is None:
        atproto_app_password = os.environ.get("ATPROTO_APP_PASSWORD", None)
    if atproto_app_password is None:
        atproto_app_password = click.prompt("Enter your bluesky app password", type=str)
    atproto_client_info['login_response'] = client.login(atproto_username, atproto_app_password)
    pass


@cli.command()
@click.option('--username', prompt='Enter the username to search for', help='Username to search for on Bluesky')
def search(username):
    """Search for a user on Bluesky by username."""
    search_user(username)


@cli.command()
def find_lists():
    find_all_lists()


@cli.command()
@click.option("--list-name", help="Name of the list")
@click.option("--list-key", help="Key of existing list. Use find-lists to find your lists.")
@click.argument('filename', type=click.Path(exists=True))
def add(list_name, list_did, filename):
    if list_name is None and list_did is None or list_name is not None and list_did is not None:
        click.echo("Only one of --list-name or --list-did is required. Use --help for help.")
        sys.exit(1)
    """Add users from a newline delimited file to the moderation list."""
    add_to_moderation_list(list_name, list_did, filename)


if __name__ == '__main__':
    cli()
