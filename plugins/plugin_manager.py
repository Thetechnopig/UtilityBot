#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
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
import asyncio
import traceback
import typing
from typing import Dict

import twitchirc
from twitchirc import Event

from plugins.models.channelsettings import SettingScope
import plugins.models.channelsettings as channelsettings_model

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()

__meta_data__ = {
    'name': 'plugin_manager',
    'commands': [],
    'no_reload': True
}

log = main.make_log_function('plugin_manager')

# noinspection PyProtectedMember
call_command_handlers = main.bot._call_command_handlers

# map of command name and blacklisted channels.
blacklist: typing.Dict[
    str, typing.List[str]
] = {}
error_notification_channel = main.bot.username.lower()


def _call_handler(command, message):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_acall_handler(command, message))


async def _acall_handler(command, message):
    if message.channel in blacklist and command.chat_command in blacklist[message.channel]:
        # command is blocked in this channel.
        log('info', f'User {message.user} attempted to call command {command.chat_command} in channel '
                    f'{message.channel} where it is blacklisted.')
        return
    try:
        # noinspection PyProtectedMember
        await main.bot._call_command(command, message)
    except Exception as e:
        _acommand_error_handler(e, command, message)  # this shouldn't trigger but just in case.


def _acommand_error_handler(exception, command, message):
    msg = twitchirc.ChannelMessage(
        text=f'Errors monkaS {chr(128073)} ALERT: {exception!r}',
        user='TO_BE_SENT',
        channel=error_notification_channel
    )
    msg.outgoing = True
    main.bot.force_send(msg)
    log('err', f'Error while running command {command.chat_command}')
    log('info', f'{message.user}@{message.channel}: {message.text}')
    for i in traceback.format_exc(30).split('\n'):
        log('err', i)

    msg2 = message.reply(f'@{message.user}, an error was raised during the execution of your command: '
                         f'{command.chat_command}')
    main.bot.send(msg2)


main.bot.command_error_handler = _acommand_error_handler


# noinspection PyProtectedMember
async def _acall_command_handlers(message: twitchirc.ChannelMessage):
    """Handle commands."""
    if message.text.startswith(main.bot.prefix):
        was_handled = False
        if ' ' not in message.text:
            message.text += ' '
        for handler in main.bot.commands:
            if callable(handler.matcher_function) and handler.matcher_function(message, handler):
                await _acall_handler(handler, message)
                was_handled = True
            if message.text.startswith(main.bot.prefix + handler.ef_command):
                await _acall_handler(handler, message)
                was_handled = True

        if not was_handled:
            main.bot._do_unknown_command(message)
    else:
        await main.bot._acall_forced_prefix_commands(message)


def add_conditional_alias(alias: str, condition: typing.Callable[[twitchirc.Command, twitchirc.ChannelMessage], bool]):
    def decorator(command: twitchirc.Command):
        @main.bot.add_command(alias, enable_local_bypass=command.enable_local_bypass,
                              required_permissions=command.permissions_required)
        async def new_command(msg: twitchirc.ChannelMessage):
            if condition(command, msg):
                return await command.acall(msg)

        return command

    return decorator


all_settings: typing.Dict[str, 'Setting'] = {}
ChannelSettings, Setting = channelsettings_model.get(main.Base, main.session_scope, all_settings)

channel_settings: Dict[str, ChannelSettings] = {}
channel_settings_session = None


def _init_settings():
    global channel_settings_session

    channel_settings_session = main.Session()
    channel_settings_session.flush = lambda *a, **kw: print('CS: Flushing a readonly session.')
    print('Load channel settings.')
    with main.session_scope() as write_session:
        print('Loading existing channel settings...')
        for i in ChannelSettings.load_all(write_session):
            i.fill_defaults(forced=False)
            i.update()
            if i.channel_alias == -1:  # global settings.
                channel_settings[SettingScope.GLOBAL.name] = i
            else:
                channel_settings[i.channel.last_known_username] = i
        print('OK')
        print('Creating missing channel settings...')
        for j in main.bot.channels_connected + [SettingScope.GLOBAL.name]:
            if j in channel_settings:
                continue
            cs = ChannelSettings()
            if j == SettingScope.GLOBAL.name:
                cs.channel_alias = -1
                write_session.add(cs)
                continue

            channels = main.User.get_by_name(j.lower(), write_session)
            if len(channels) != 1:
                continue
            cs.channel = channels[0]
            write_session.add(cs)
            channel_settings[channels[0].last_known_username] = cs
        print('OK')
        print('Commit.')
    print(f'Done. Loaded {len(channel_settings)} channel settings entries.')


main.bot.schedule_event(0.1, 100, _init_settings, (), {})


def _reload_settings():
    global channel_settings
    channel_settings = {}
    _init_settings()
    return 'OK'


main.reloadables['channel_settings'] = _reload_settings

# command definitions

@main.bot.add_command('mb.unblacklist_command', required_permissions=['util.unblacklist_command'],
                      enable_local_bypass=True)
def command_unblacklist(msg: twitchirc.ChannelMessage) -> str:
    ensure_blacklist(msg.channel)
    args = msg.text.split(' ')
    if len(args) != 2:
        return (f'@{msg.user} Usage: '
                f'"{main.bot.prefix}{command_unblacklist.chat_command} COMMAND". '
                f'Where COMMAND is the command you want to unblacklist.')
    target = args[1]
    for i in main.bot.commands:
        if i.chat_command == target:
            if target not in blacklist[msg.channel]:
                return (f"@{msg.user} Cannot unblacklist command {target} that isn't blacklisted "
                        f"here.")
            blacklist[msg.channel].remove(target)
            return f'@{msg.user} Unblacklisted command {target} from channel #{msg.channel}.'
    return f'@{msg.user} Cannot unblacklist nonexistent command {target}.'


@main.bot.add_command('mb.blacklist_command', required_permissions=['util.blacklist_command'], enable_local_bypass=True)
def command_blacklist(msg: twitchirc.ChannelMessage) -> str:
    ensure_blacklist(msg.channel)
    args = msg.text.split(' ')
    if len(args) != 2:
        return (f'@{msg.user} Usage: '
                f'"{main.bot.prefix}{command_blacklist.chat_command} COMMAND". '
                f'Where COMMAND is the command you want to blacklist.')
    target = args[1]
    if target in blacklist[msg.channel]:
        return f'@{msg.user} That command is already blacklisted.'

    for i in main.bot.commands:
        if i.chat_command == target:
            blacklist[msg.channel].append(target)
            return (f'@{msg.user} Blacklisted command {target}. '
                    f'To undo use {main.bot.prefix}{command_unblacklist.chat_command} {target}.')
    return f'@{msg.user} Cannot blacklist nonexistent command {target}.'


@main.bot.add_command('mb.list_blacklisted_commands', required_permissions=['util.blacklist_command'],
                      enable_local_bypass=True)
def command_list_blacklisted(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    main.bot.send(msg.reply(f'@{msg.user}, There are {len(blacklist[msg.channel])} blacklisted commands: '
                            f'{", ".join(blacklist[msg.channel])}'))


@main.bot.add_command('blacklisted_join', required_permissions=[twitchirc.PERMISSION_COMMAND_JOIN],
                      enable_local_bypass=False)
def command_join_blacklisted(msg: twitchirc.ChannelMessage) -> str:
    ensure_blacklist(msg.channel)
    chan = msg.text.split(' ')[1].lower()
    if chan in ['all']:
        return f'Cannot join #{chan}.'
    if chan in main.bot.channels_connected:
        return f'This bot is already in channel #{chan}.'
    else:
        blacklist[msg.channel] = [i.chat_command for i in main.bot.commands]
        blacklist[msg.channel].remove('mb.blacklist_command')
        blacklist[msg.channel].remove('mb.unblacklist_command')
        blacklist[msg.channel].remove('mb.list_blacklisted_commands')
        main.bot.send(msg.reply(f'Joining channel #{chan} with all commands blacklisted apart from '
                                f'mb.blacklist_command, mb.unblacklist_command and mb.list_blacklisted_command'))
        main.bot.join(chan)


def ensure_blacklist(channel):
    if channel not in blacklist:
        blacklist[channel] = []


main.bot._acall_command_handlers = _acall_command_handlers

if 'command_blacklist' in main.bot.storage.data:
    blacklist = main.bot.storage['command_blacklist']
else:
    main.bot.storage['command_blacklist'] = {}


class ExceptionDetectionMiddleware(twitchirc.AbstractMiddleware):
    def __init__(self):
        super().__init__()
        self.fire_triggered = False
        print('fire detection loaded')

    def on_action(self, event: Event):
        super().on_action(event)
        if event.name == 'fire':
            self.fire(event)

    def fire(self, event: Event) -> None:
        print('FIRE!!!!! WAYTOODANK')
        if self.fire_triggered:
            return
        self.fire_triggered = True
        pinged = ''
        if isinstance(event.source, twitchirc.Bot):
            for user, perms in event.source.permissions.users.items():
                print(user, perms)
                if ((twitchirc.permission_names.GLOBAL_BYPASS_PERMISSION in perms
                     or 'util.fire_ping' in perms
                     or 'parent.bot_admin' in perms)
                        and 'util.fire_ping_disable' not in perms):
                    pinged += f' @{user}'
        e = event.data['exception']
        m = twitchirc.ChannelMessage(text=f'The bot\'s breaking!!! {pinged} WAYTOODANK {e!r}',
                                     user='OUTGOING', channel=error_notification_channel,
                                     outgoing=True, parent=None)
        event.source.send(m)
        event.source.flush_queue()

    def send(self, event: Event) -> None:
        pass

    def receive(self, event: Event) -> None:
        pass

    def command(self, event: Event) -> None:
        pass

    def permission_check(self, event: Event) -> None:
        pass

    def join(self, event: Event) -> None:
        pass

    def part(self, event: Event) -> None:
        pass

    def disconnect(self, event: Event) -> None:
        pass

    def connect(self, event: Event) -> None:
        pass

    def add_command(self, event: Event) -> None:
        pass


main.bot.middleware.append(ExceptionDetectionMiddleware())
