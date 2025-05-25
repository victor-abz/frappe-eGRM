# Copyright (c) 2015, Web Notes Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import click

click.disable_unicode_literals_warning = True


def call_command(cmd, context):
    return click.Context(cmd, obj=context).forward(cmd)


def get_commands():
    # prevent circular imports
    from .admin_regions import commands as admin_regions_command
    from .create_government_workers import commands as create_gov_workers_command

    clickable_link = "https://frappeframework.com/docs"
    all_commands = admin_regions_command + create_gov_workers_command

    for command in all_commands:
        if not command.help:
            command.help = f"Refer to {clickable_link}"

    return all_commands


commands = get_commands()
