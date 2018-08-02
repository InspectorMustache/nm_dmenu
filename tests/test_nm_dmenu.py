import nm_dmenu
import re
import pytest


@pytest.fixture(scope='module')
def nm_cli_output():
    """Run nmcli, scan for networks and use its output as a fixture."""
    nm_dmenu.rescan_wifi_nw()
    return nm_dmenu.get_nmcli_out()


def test_nm_out_processing(nm_cli_output):
    nwl = nm_dmenu.get_nw_list(nm_cli_output)
    nco_lines_n = len(nm_cli_output.strip('\n').splitlines())
    assert len(nwl) == int(nco_lines_n / 4)
    for nw in nwl:
        assert type(nw['ssid']) is str
        assert re.match('^([\dA-F]{2}:){5}[\dA-F]{2}$', nw['bssid'])
        assert type(nw['frequency']) is str
        assert type(nw['security']) is list

    # make sure out_entries are actually unique
    oes = [e['out_entry'] for e in nwl]
    assert len(oes) == len(set(oes))
