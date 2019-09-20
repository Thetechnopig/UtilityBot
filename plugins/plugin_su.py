#  This is a simple utility bot
#  Copyright (C) 2019 Maciej Marciniak
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import typing

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()

__meta_data__ = {
    'name': 'plugin_su',
    'commands': ['mb.su', 'mb.whoami']
}

import shlex

# noinspection PyUnresolvedReferences
import twitchirc

log = main.make_log_function('su')


class Su:
    def __init__(self, user_to: str, override_channel: typing.Optional[str]):
        self.override_channel = override_channel
        self.user_to = user_to


su_ed_users: typing.Dict[str, Su] = {

}

# noinspection PyProtectedMember
old_handler = main.bot._call_command_handlers


def _call_command_handlers(msg: twitchirc.ChannelMessage):
    print(f'call cmd handlers {msg!r}')
    msg.real_user = msg.user
    if msg.user in su_ed_users:
        su_obj = su_ed_users[msg.user]
        msg.user = su_obj.user_to
        if su_obj.override_channel is not None:
            msg.channel = su_obj.override_channel
    old_handler(msg)


def on_reload():
    main.bot._call_command_handlers = old_handler
    # restore the previous handler to avoid weird things.


main.bot._call_command_handlers = _call_command_handlers
su_parser = twitchirc.ArgumentParser(prog='!su', add_help=False, message_handler=print)
su_group_1 = su_parser.add_mutually_exclusive_group()
su_group_1.add_argument('-h', '--help', dest='help', help='Request help', nargs='?', default=None,
                        const='usage', action='store')
su_group_2 = su_group_1.add_argument_group()
su_group_1.add_argument('-L', '--logout', dest='logout', help='Return to your account', action='store_true')
su_group_2.add_argument('-c', '--command', dest='command', metavar='COMMAND')

su_group_2.add_argument('-m', '-p', '--preserve-environment', dest='do_nothing', help='Do nothing.',
                        action='store_true')
su_group_2.add_argument('-s', '--shell', dest='do_nothing', help='Do nothing.', metavar='SHELL')
su_group_2.add_argument('-l', '-', '--login', dest='do_nothing', help='Do nothing.', action='store_true')
su_group_2.add_argument('-C', '--channel', dest='channel', help='Make as if all commands are run on CHANNEL',
                        metavar='CHANNEL')

su_group_2.add_argument('user', metavar='USER')

SU_HELP = {
    'c': 'Specify a command that will be invoked.',
    'command': 'Specify a command that will be invoked.',

    'h': 'Requesting help for help? LOL',
    'help': 'Requesting help for help? LOL',

    'm': 'Do nothing. Just here for compatibility',
    'p': 'Do nothing. Just here for compatibility',
    'preserve-environment': 'Do nothing. Just here for compatibility',

    'minus': 'Do nothing. Just here for compatibility',
    'l': 'Do nothing. Just here for compatibility',
    'login': 'Do nothing. Just here for compatibility',
    'shell': 'Do nothing. Just here for compatibility',
    's': 'Do nothing. Just here for compatibility',

    'L': 'Log out',
    'logout': 'Log out, duh'

}


@main.bot.add_command('mb.su')
def command_su(msg: twitchirc.ChannelMessage):
    if not hasattr(msg, 'real_user') and bool(main.bot.check_permissions(msg, ['su.su'])):
        return
    args = su_parser.parse_args(shlex.split(msg.args.replace(main.bot.prefix + command_su.chat_command + ' ', '')))
    if args is None:
        main.bot.send(msg.reply(f'@{msg.user} {su_parser.format_usage()}'))
        return
    print(args)
    if args.help is not None:
        if args.help == 'usage':
            main.bot.send(msg.reply(f'@{msg.user} {su_parser.format_usage()} (0)'))
        elif args.help in SU_HELP:
            main.bot.send(msg.reply(f'@{msg.user} {SU_HELP[args.help]} (0)'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} No such help topic found. Try !{command_su.chat_command} -h usage'
                                    f'(1)'))
    else:
        if args.logout:
            if hasattr(msg, 'real_user'):
                if msg.real_user not in su_ed_users:
                    main.bot.send(msg.reply(f'@{msg.real_user} You are not su-ed FeelsDankMan'))
                else:
                    del su_ed_users[msg.real_user]
            else:
                if msg.user not in su_ed_users:
                    main.bot.send(msg.reply(f'@{msg.user} You are not su-ed FeelsDankMan'))
                else:
                    del su_ed_users[msg.user]
            return

        if args.command:
            new_msg = twitchirc.ChannelMessage(args.command, args.user,
                                               msg.channel if args.channel is None else args.channel)
            _call_command_handlers(new_msg)
        else:
            if hasattr(msg, 'real_user'):
                su_ed_users[msg.real_user] = Su(args.user, args.channel)
            else:
                su_ed_users[msg.user] = Su(args.user, args.channel)
            main.bot.send(msg.reply(f'@{msg.user} Successfully changed user.'))


command_su: twitchirc.Command


@main.bot.add_command('mb.whoami')
def command_whoami(msg: twitchirc.ChannelMessage):
    if hasattr(msg, 'real_user'):
        main.bot.send(msg.reply(f'@{msg.real_user} You are {msg.user}'))
    else:
        main.bot.send(msg.reply(f'@{msg.user} You are {msg.user}'))
