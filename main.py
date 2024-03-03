#!/usr/bin/env python3
import os
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
    while response.cursor is not None:
        for actor in response.actors:
            yield actor
        cursor = response.cursor
        response = search_actors(query, limit, cursor)


def search_user(username):
    """Search for a user on Bluesky by username."""
    try:
        for actor in drain_all_actors(username):
            print(f"{actor.did} {actor.handle} -- {actor.display_name}")
    except requests.exceptions.RequestException as e:
        click.echo(f"Error: {e}")


def extract_did(line):
    return line.split(" ")[0]


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


def add_to_moderation_list(list_name, filename):
    """Add users from a newline delimited file to the moderation list."""
    try:
        my_did = atproto_client_info['login_response']['did']
        with open(filename, 'r') as file:
            lines = file.read().splitlines()
        new_modlist = create_atproto_list(list_name, my_did)

        for line in lines:
            did = extract_did(line)
            click.echo(f"Adding record to modlist: {line}")
            create_atproto_list_item(new_modlist['uri'], did, my_did)

        click.echo(f"Added {len(lines)} user(s) to the moderation list.")
    except requests.exceptions.RequestException as e:
        click.echo(f"Error: {e}")


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
@click.option("--list-name", help="Name of the list")
@click.argument('filename', type=click.Path(exists=True))
def add(list_name, filename):
    """Add users from a newline delimited file to the moderation list."""
    add_to_moderation_list(list_name, filename)


if __name__ == '__main__':
    cli()
