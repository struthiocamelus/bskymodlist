# Bsky Modlist

This is a command-line tool using python that you can use to turbocharge your
moderation list authoring power.

## Features

1. Search for users, output them to a space-delimited text file
2. Feed in a post, output liking users to a space-delimited text file
3. Take a newline separated list of user DIDs (any information after 
   the DID is discarded) and add them to a moderation list. Can be a new
   or existing list.
4. List all your moderation lists.

## Installation

### Requirements

Have Python (3.6+). 

### Installing from Github

```bash
pip install git+https://github.com/struthiocamelus/bskymodlist
```

## Configuration

The easiest and most secure way to configure this command line tool is to
create the `~/.config/bskymodlist.json` credentials file like so:

```bash
mkdir -p ~/.config # Create `.config` directory in home directory if it doesn't exist
echo "{
  \"atproto_username\": \"your-username\"
  \"atproto_app_password\": \"your-app-password\"
}" > ~/.config/bskymodlist.json # Create empty configuration file.
```

Irrespective of your OS or POSIX environment, this CLI will look for your
configuration file there. If you don't like that, you're welcome to use
environment variables (not secure) or input your app password securely
on the command line every time (secure, but troublesome).

Edit the file:
 - `atproto_username`: Your bsky username. Mine is `@ostrich.bsky.social`.
   - Environment variable fallback: `ATPROTO_USERNAME` 
 - `atproto_app_password`: Your app password. Generate one here: https://bsky.app/settings/app-passwords
   - Environment variable fallback: `ATPROTO_APP_PASSWORD`
   - **IT IS NOT RECOMMENDED TO PUT PASSWORDS IN PLAIN TEXT IN ENVIRONMENT VARIABLES**

### Usage

```bash
bskymodlist search "Nazi MRA" > people-i-would-rather-not-interact-with.txt
bskymodlist all-likes "{link to racist post}" >> people-i-would-rather-not-interact-with.txt
bskymodlist --list-name "Outcasts" \
   --list-description "People I would rather not interact with" \
   people-i-would-rather-not-interact-with.txt

```

This project comes with no warranty whatsoever. Don't use it in violation of the Bluesky terms
of service. I am not responsible for you getting banned or using up your API requests or
whatever. Do not @ me (unless you're going to thank me, then you can @ me).
