#!/usr/bin/env python

import subprocess
import sys
import os

try:
    from gi import require_version
    require_version('Notify', '0.7')
    from gi.repository import Notify
    Notify.init('NetworkManager Dmenu')
except ImportError as e:
    sys.stderr.write('{}\n'.format(e.msg))
    sys.stderr.flush()

RESCAN_NETWORKS = 'Netzwerke scannen'
RESCAN_NETWORKS_MSG = 'Netzwerkscan abgeschlossen'
CONNECTION_MADE_MSG = 'Erfolgreich verbunden mit'
ERROR_MSG = 'Fehler beim Ausführen von'
DMENU_OPS = os.getenv('DMENU_DEFAULT_OPS', default='').split()


class catchProcError():
    def __init__(self, cmdname):
        self.cmdname = cmdname

    def __call__(self, f):
        def wrapped_f(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except (subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                    FileNotFoundError) as e:
                exit_with_msg(
                    '\n'.join(['{} {}:'.format(ERROR_MSG, self.cmdname),
                               str(e)]))
        return wrapped_f


def send_notification(msg):
    """Try to send a notification. If notify wasn't imported, do nothing."""
    try:
        Notify.Notification.new(msg).show()
    except NameError:
        pass


def exit_with_msg(msg):
    send_notification(msg)
    sys.stderr.write('{}\n'.format(msg))
    sys.stderr.flush()
    exit(1)


def populate_entry(entry):
    e = {'ssid': entry[0][5:],
         'bssid': entry[1][6:],
         'frequency': entry[2][5:],
         'security': entry[3][9:].split(' ')}
    return e


def add_output_entry(nw_list):
    """Add a unique out_entry to every entry in nw_list."""
    # also make sure there's no network that has RESCAN_NETWORKS as its ssid
    # (however unlikely that may be)
    out_entries = [RESCAN_NETWORKS]
    for e in nw_list:
        oe = create_uniq_output_entry(
            '{} ({})'.format(e['ssid'], e['frequency']), out_entries)
        out_entries.append(oe)
        e['out_entry'] = oe

    return nw_list


def create_uniq_output_entry(entry, entry_list):
    """Append asterisks to an entry until it is unique."""
    if entry not in entry_list:
        return entry
    else:
        new_entry = '{}*'.format(entry)
        return create_uniq_output_entry(new_entry, entry_list)


def slice_up_list(l):
    for i in range(0, len(l), 4):
        yield l[i:i+4]


def get_entry_from_out_entry(out_entry, nw_list):
    """Return the network entry from nw_list that has out_entry as the value of
    its out_entry key."""
    # next() will return the ONLY entry because we made sure each out_entry is
    # unique
    try:
        return next(e for e in nw_list if e['out_entry'] == out_entry)
    except StopIteration:
        return RESCAN_NETWORKS


def get_nw_list(nm_output):
    """Turn output into a list of strings."""
    out = nm_output.strip('\n').split(sep='\n')
    nwl = [populate_entry(e) for e in list(slice_up_list(out))]
    nwl = add_output_entry(nwl)
    return sorted(nwl, key=lambda x: x['out_entry'])


@catchProcError('nmcli')
def get_nmcli_out():
    nmcli_out = subprocess.check_output(
        ['nmcli', '-g', 'SSID,BSSID,FREQ,SECURITY', '--mode', 'multiline',
         'device', 'wifi', 'list', '--rescan', 'no'], encoding='utf-8',
        stderr=subprocess.PIPE)
    return nmcli_out


@catchProcError('nmcli')
def rescan_wifi_nw():
    """Rescan wifi networks."""
    # use list subcommand so we have an indicator when scanning is done
    subprocess.run(['nmcli', 'device', 'wifi', 'list', '--rescan', 'yes'],
                   check=True, stdout=subprocess.DEVNULL, timeout=60)
    send_notification(RESCAN_NETWORKS_MSG)


@catchProcError('dmenu')
def get_user_choice(entry_list):
    """Return the network chosen by user via dmenu."""
    entry_list.insert(0, RESCAN_NETWORKS)
    dmenup = subprocess.Popen(['dmenu', *DMENU_OPS], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              encoding='utf-8')

    stdout, stderr = dmenup.communicate(input='\n'.join(entry_list))
    if dmenup.returncode == 0:
        return stdout.rstrip('\n')
    else:
        sys.exit(dmenup.returncode)


@catchProcError('nmcli')
def up_connection(ssid):
    """Try bringing the connection up. Return false if there's an error."""
    try:
        subprocess.run(['nmcli', 'connection', 'up', ssid], timeout=30)
        return True
    except subprocess.CalledProcessError as e:
        if e.returncode == 10:
            return False
        else:
            raise e


def get_user_pass():
    """Return a user password using a Qt dialog."""
    return None


@catchProcError('nmcli')
def make_new_connection(entry):
    """Try to establish a connection to network and create a new nm connection
    profile."""
    # TODO: get a password from user if necessary
    pass_arg = []
    if entry['security']:
        # get_password_from_user()
        pass

    subprocess.run(['nmcli', 'wifi', 'connect', entry['bssid'], *pass_arg])
    return True


def connect_to_nw(entry):
    """Connect to the network specified in entry."""
    if up_connection(entry['ssid']) or make_new_connection(entry):
        send_notification('{} {}.'.format(CONNECTION_MADE_MSG,
                                          entry['ssid']))
    else:
        exit_with_msg()


def process_dmenu_selection(sel, nw_list):
    if sel == RESCAN_NETWORKS:
        rescan_wifi_nw()
    else:
        connect_to_nw(get_entry_from_out_entry(sel, nw_list))


if __name__ == '__main__':
    nwl = get_nw_list(get_nmcli_out())
    sel = get_user_choice([e['out_entry'] for e in nwl])
    process_dmenu_selection(sel, nwl)
