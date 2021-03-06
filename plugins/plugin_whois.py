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
import datetime
import queue
import shlex
import time
import typing

import aiohttp

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

try:
    import plugin_plugin_prefixes as plugin_prefixes
except ImportError:
    import plugins.plugin_prefixes as plugin_prefixes

__meta_data__ = {
    'name': 'plugin_whois',
    'commands': [
        'whois'
    ]
}
log = main.make_log_function('whois')

whois_parser = twitchirc.ArgumentParser(prog='whois')
g = whois_parser.add_mutually_exclusive_group(required=True)
g.add_argument('-i', '--id', help='Use the ID instead of using a username', dest='id', type=int)
g.add_argument('-n', '--name', help='Use the username', dest='name', type=str)


@plugin_manager.add_conditional_alias('whois', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.whois')
async def command_whois(msg: twitchirc.ChannelMessage):
    if not bots or bots_invalidates <= time.time():
        await _load_bots()

    cd_state = main.do_cooldown('whois', msg, global_cooldown=30,
                                local_cooldown=60)
    if cd_state:
        return
    try:
        argv = shlex.split(msg.text.replace('\U000e0000', ''))
    except ValueError as e:
        return f'@{msg.user} FeelsWeirdMan {e.args}'

    args = whois_parser.parse_args(argv[1:] if len(argv) > 1 else [])
    if args is None:
        return f'@{msg.user} {whois_parser.format_usage()}'
    if args.id is not None:
        name = args.id
        id_ = True
    elif args.name is not None:
        name = args.name
        id_ = False
    else:
        return f'@{msg.user} Do you really want the bot to crash?'

    async with aiohttp.request('get', f'https://api.ivr.fi/twitch/resolve/{name}',
                               params=({'id': 1}) if id_ else {},
                               headers={
                                   'User-Agent': 'Mm\'sUtilityBot/v1.0 (by Mm2PL), Twitch chat bot',
                                   'Requested-By': msg.user
                               }) as request:
        data = await request.json()
        if data['status'] == 404:
            return f'@{msg.user} No such user found.'

        roles = ''
        if data['roles']['isAffiliate']:
            roles += 'affiliate, '
        if data['roles']['isPartner']:
            roles += 'partner, '
        if data['roles']['isSiteAdmin']:
            roles += 'site admin, '
        if data['roles']['isStaff']:
            roles += 'staff, '
        if roles == '':
            roles = 'none'
        roles = (roles[::-1].replace(', '[::-1], '', 1))[::-1]
        # replace last ", " with "".
        if data['displayName'].lower() != data['login'].lower():
            login = f'({data["login"]})'
        else:
            login = ''
        created_on = datetime.datetime.strptime(data['createdAt'][:-8], '%Y-%m-%dT%H:%M:%S')
        bot_notes = ''
        bot = _find_bot(data['login'])
        if bot is not None:
            last_active = f', Last active: {bot["lastSeen"][:-4]}' if bot['lastSeen'] is not None else ''
            bot_notes = (f' Prefix: {bot["prefix"] if bot["prefix"] is not None else "<blank>"}, '
                         f'Description: {bot["description"] if bot["description"] is not None else "<blank>"}, '
                         f'Language: {bot["language"] if bot["language"] is not None else "<unknown>"}'
                         f'{last_active}')

        return (f'@{msg.user}, {"BANNED " if data["banned"] else ""}{"bot " if data["bot"] else ""}'
                f'user {data["displayName"]}{login}, '
                f'chat color: {data["chatColor"]}, '
                f'account created at {created_on}, '
                f'roles: {roles}, '
                f'id: {data["id"]}, '
                f'bio: '
                f'{data["bio"] if data["bio"] is not None else "<blank>"}'
                f'{bot_notes}')


bots: typing.List[dict] = []
bots_invalidates = time.time()


async def _load_bots():
    global bots, bots_invalidates
    bots_invalidates = time.time() + 600  # make the bot list invalidate in 10 minutes.
    async with aiohttp.request('get', 'https://supinic.com/api/bot/active') as r:
        r: aiohttp.ClientResponse
        if r.status == 200:
            bots = (await r.json())['data']
            return 'ok'
        else:
            print(r.content)
            return f'not okay: {r.status}'


def _find_bot(username):
    for bot in bots:
        if bot['name'] == username:
            return bot
