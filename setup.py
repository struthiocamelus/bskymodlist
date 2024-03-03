from setuptools import setup

setup(
    entry_points={
        'console_scripts': ['bskymodlist=main:cli']
    },
    name="bskymodlist",
    version="1.0.1",
    author="ostrich",
    description="Search bluesky for users, then add them to a moderation list.",
    install_requires=[
        "click",
        "backoff",
        "atproto",
    ],
    python_requires=">=3.5"
)
