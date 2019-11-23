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
import datetime
import time
import typing

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc
import requests

import twitch_auth

__meta_data__ = {
    'name': 'plugin_uptime',
    'commands': [
        'uptime',
        'downtime'
    ]
}
log = main.make_log_function('uptime')
reqs: typing.List[typing.Dict[str, typing.Union[twitchirc.ChannelMessage, requests.Request]]] = []


@main.bot.add_command('title')
def command_title(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('title', msg, global_cooldown=30, local_cooldown=60)
    if cd_state:
        return
    r, status_code = main.twitch_auth.new_api.get_streams(user_login=msg.channel, wait_for_result=True)
    if status_code == 200 and 'data' in r and len(r['data']) > 0:
        main.bot.send(msg.reply(f'@{msg.user} {r["data"][0]["title"]}'))
    else:
        main.bot.send(msg.reply(f'@{msg.user} eShrug Stream not found.'))


@main.bot.add_command('uptime')
def command_uptime(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('uptime', msg, global_cooldown=30, local_cooldown=60)
    if cd_state:
        return
    c_uptime_r = requests.get('https://api.twitch.tv/helix/streams', params={'user_login': msg.channel},
                              headers={'Client-ID': twitch_auth.json_data['client_id']})
    reqs.append({
        'msg': msg,
        'r': c_uptime_r,
        'type': 'uptime'
    })


@main.bot.add_command('downtime')
def command_downtime(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('downtime', msg, global_cooldown=30, local_cooldown=60)
    if cd_state:
        return
    uptime_r = requests.get('https://api.twitch.tv/helix/streams', params={'user_login': msg.channel},
                            headers={'Client-ID': twitch_auth.json_data['client_id']})
    user_r = requests.get('https://api.twitch.tv/helix/users', params={'login': msg.channel},
                          headers={'Client-ID': twitch_auth.json_data['client_id']})

    reqs.append({
        'msg': msg,
        'r': uptime_r,
        'type': 'downtime',
        'r2': user_r,
    })


def round_time_delta(td):
    ntd = datetime.timedelta(seconds=round(td.total_seconds(), 0))
    return ntd


def _check_downtime_request(i):
    json_data = i['r'].json()
    data = json_data['data']
    if data:
        main.bot.send(i["msg"].reply(f'@{i["msg"].user} {i["msg"].channel} is live.'))
    else:
        # channel is not live
        json_data = i['r2'].json()
        data = json_data['data']
        user_id = data[0]['id']
        video_r = requests.get('https://api.twitch.tv/helix/videos',
                               params={
                                   'user_id': user_id,
                                   'sort': 'time',
                                   'type': 'archive',
                                   'first': '1'
                               },
                               headers={'Client-ID': twitch_auth.json_data['client_id']})
        reqs.append({
            'msg': i["msg"],
            'type': 'downtime_1',
            'r': video_r
        })


def _parse_duration(duration: str) -> datetime.timedelta:
    buf = ''
    hours = 0
    minutes = 0
    seconds = 0
    for i in duration:
        if i.isnumeric():
            buf += i
        else:
            if i == 's':
                seconds += int(buf)
                buf = ''
            elif i == 'm':
                minutes += int(buf)
                buf = ''
            elif i == 'h':
                hours = int(buf)
                buf = ''
    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)


def _check_downtime_2_request(i):
    # WAYTOODANK Zone. Don't touch this unless you need to it is held using bad sticky tape and it will fall apart when
    # you pick it up.
    # You have been warned.

    json_data = i['r'].json()
    print(json_data)
    if not json_data['data']:
        return
    data = json_data['data'][0]
    duration = _parse_duration(data['duration'])
    print(duration)

    struct_time = time.strptime(data['created_at'],
                                "%Y-%m-%dT%H:%M:%SZ")
    print(struct_time)
    created_at = datetime.datetime(year=struct_time[0],
                                   month=struct_time[1],
                                   day=struct_time[2],
                                   hour=struct_time[3],
                                   minute=struct_time[4],
                                   second=struct_time[5])

    now = datetime.datetime.utcnow()
    time_start_difference = now - created_at
    offline_for = round_time_delta(time_start_difference - duration)

    print(duration, created_at, offline_for)
    main.bot.send(i['msg'].reply(f'@{i["msg"].user} {i["msg"].channel} has been offline for {offline_for}'))


def check_on_requests(*args):
    del args
    for i in reqs.copy():
        if i['type'] == 'uptime':
            _check_uptime_request(i)
        elif i['type'] == 'downtime':
            _check_downtime_request(i)
        elif i['type'] == 'downtime_1':
            _check_downtime_2_request(i)
        main.bot.flush_queue(100)
        reqs.remove(i)


def _check_uptime_request(i):
    json_data = i['r'].json()
    print(json_data)
    # if json_data['status'] == 200:  # OK
    data = json_data['data']
    if data:
        data = data[0]
        start_time = datetime.datetime(*(time.strptime(data['started_at'],
                                                       "%Y-%m-%dT%H:%M:%SZ")[0:6]))
        # start_time = datetime.datetime.strptime(json_data['started_at'],
        #                                         "%Y-%m-%dT%H:%M:%SZ")
        uptime = round_time_delta(datetime.datetime.utcnow() - start_time)
        reply = i['msg'].reply(f'@{i["msg"].user} {i["msg"].channel} has been live for {uptime!s}')
        main.bot.send(reply)
    else:
        main.bot.send(i['msg'].reply(f'@{i["msg"].user} {i["msg"].channel} is not live.'))


main.bot.schedule_repeated_event(1, 5, check_on_requests, (), {})
# main.bot.handlers['any_msg'].append(check_on_requests)
