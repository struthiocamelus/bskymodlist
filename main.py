#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timezone
import json
import re

import atproto_client.exceptions
import click
import backoff
from atproto import Client

client = Client(base_url="https://bsky.social")
atproto_client_info = {}


def iso_8601_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def format_actor(actor):
    return f"{actor.did} {actor.handle} -- {actor.display_name}"


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
            print(format_actor(actor))
    except Exception as e:
        click.echo(f"An exception occurred: {e}")


def search_exact_user_by_handle(username):
    """Search for an exact user on Bluesky by username"""
    try:
        for actor in drain_all_actors(username):
            if actor.handle == username:
                return actor
        return None
    except Exception as e:
        click.echo(f"An exception occurred: {e}")


def extract_did(line):
    return line[0:32]


@backoff.on_exception(
    backoff.expo,
    atproto_client.exceptions.RequestException,
    max_time=300
)
def create_atproto_list(list_name, list_description, my_did):
    return client.com.atproto.repo.create_record({
        "collection": "app.bsky.graph.list",
        "record": {
            "$type": "app.bsky.graph.list",
            "createdAt": iso_8601_now(),
            "description": list_description or list_name,
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


@backoff.on_exception(
    backoff.expo,
    atproto_client.exceptions.RequestException,
    max_time=300
)
def get_bsky_likes(uri, limit=100, cursor=None):
    return client.get_likes(uri, limit=limit, cursor=cursor)


def drain_atproto_lists(did):
    response = get_atproto_lists(did)
    for mod_list in response.lists:
        yield mod_list
    while response.cursor is not None:
        response = get_atproto_lists(did, cursor=response.cursor)
        for mod_list in response.lists:
            yield mod_list


def drain_bsky_likes(uri):
    response = get_bsky_likes(uri)
    for like in response.likes:
        yield like
    while response.cursor is not None:
        response = get_bsky_likes(uri, cursor=response.cursor)
        for like in response.likes:
            yield like


def find_all_lists():
    """Find all moderation lists for user."""
    try:
        my_did = atproto_client_info['login_response']['did']
        lists = drain_atproto_lists(my_did)
        for mod_list in lists:
            print(f"{mod_list.uri} -- {mod_list.name} {mod_list.description}")
    except Exception as e:
        click.echo(f"An error occurred: {e}")


def find_all_likes(post):
    """Parse a bsky post url and convert it into an at-uri"""
    matches = re.match(r"https://bsky\.app/profile/([^/]+)/post/([^/]+)", post)
    if (not (matches[1].startswith("did:plc:") and len(matches[1]) != 32)
            and not (matches[1].endswith(".bsky.social"))) or len(matches[2]) != 13:
        click.echo(f"Invalid post URL specified: {post}")
        click.echo("Posts should be in the format: https://bsky.app/profile/did:plc:{did}/post/{key}")
        sys.exit(1)
    user_did = matches[1]
    if user_did.endswith(".bsky.social"):
        user_did = search_exact_user_by_handle(user_did).did
    uri = f"at://{user_did}/app.bsky.feed.post/{matches[2]}"
    for liker in drain_bsky_likes(uri):
        print(format_actor(liker.actor))


def read_from_file(filename=None):
    if filename is None or filename == "-":
        for line in sys.stdin:
            yield line
    else:
        with open(filename, 'r') as file:
            for line in file.read():
                yield line


def add_to_moderation_list(list_name=None, list_description=None, list_did=None, filename=None):
    """Add users from a newline delimited file to the moderation list."""
    try:
        my_did = atproto_client_info['login_response']['did']

        if list_name is not None:
            moderation_list = create_atproto_list(list_name, list_description, my_did)
        elif list_did is not None:
            moderation_list = get_atproto_list(list_did, my_did)
            moderation_list = moderation_list['list']
        else:
            raise RuntimeError("This should never happen")

        num_lines = 0
        for line in read_from_file(filename):
            num_lines += 1
            did = extract_did(line)
            if not did.startswith("did:plc:"):
                click.echo(f"{did} doesn't look like a DID, skipping...")
            click.echo(f"Adding record to modlist: {line}")
            try:
                create_atproto_list_item(moderation_list['uri'], did, my_did)
            except Exception:
                click.echo(f"Failed to add {did} to modlist, continuing...")

        click.echo(f"Added {num_lines} user(s) to the moderation list.")
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
    except Exception:
        click.echo("No configuration file specified, getting credentials from command line.")
    if atproto_username is None:
        atproto_username = os.environ.get("ATPROTO_USERNAME", None)
    if atproto_username is None:
        atproto_username = click.prompt("Enter your bluesky username", type=str)
    if atproto_app_password is None:
        atproto_app_password = os.environ.get("ATPROTO_APP_PASSWORD", None)
    if atproto_app_password is None:
        atproto_app_password = click.prompt("Enter your bluesky app password", type=str, hide_input=True)
    atproto_client_info['login_response'] = client.login(atproto_username, atproto_app_password)
    pass


@cli.command(help="Return the DID of every user who liked a post")
@click.argument('post')
def all_likes(post):
    """Return all users who liked a post"""
    find_all_likes(post)


@cli.command(help="Search for a user or part of their display name on Bluesky")
@click.argument('query')
def user_search(query):
    """Search for a user on Bluesky by username."""
    search_user(query)


@cli.command(help="Show all moderation lists created by the current user")
def find_lists():
    find_all_lists()


@cli.command(help="Add users from a newline delimited file to a moderation list")
@click.option("--list-name", help="Name of the list (if new)")
@click.option("--list-description", help="List description (if new)")
@click.option("--list-key", help="Key of existing list. Use find-lists to find your lists.")
@click.argument('filename', type=click.Path(exists=True, allow_dash=True))
def add(list_name, list_description, list_key, filename):
    """Add users from a newline delimited file to the moderation list."""
    if list_name is None and list_key is None or list_name is not None and list_key is not None:
        click.echo("Only one of --list-name or --list-did is required. Use --help for help.")
        sys.exit(1)
    add_to_moderation_list(list_name, list_description, list_key, filename)


if __name__ == '__main__':
    cli()
