# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
import os
import tempfile
import sys
import collections
from functools import wraps

from test_utils import CharmTestCase

with mock.patch('charmhelpers.core.hookenv.cached') as cached:
    def passthrough(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._wrapped = func
        return wrapper
    cached.side_effect = passthrough
    import rabbit_utils

sys.modules['MySQLdb'] = mock.Mock()

TO_PATCH = [
    # charmhelpers.core.hookenv
    'is_leader',
    'related_units',
    'relation_ids',
    'relation_get',
    'relation_set',
    'leader_get',
    'config',
    'is_unit_paused_set',
    'assert_charm_supports_ipv6',
    'get_ipv6_addr',
    'unit_get',
    'network_get_primary_address',
    'get_address_in_network',
]


class ConfigRendererTests(CharmTestCase):

    class FakeContext(object):
        def __call__(self, *a, **k):
            return {'foo': 'bar'}

    config_map = collections.OrderedDict(
        [('/this/is/a/config', {
            'hook_contexts': [
                FakeContext()
            ]
        })]
    )

    def setUp(self):
        super(ConfigRendererTests, self).setUp(rabbit_utils,
                                               TO_PATCH)
        self.renderer = rabbit_utils.ConfigRenderer(
            self.config_map)

    def test_has_config_data(self):
        self.assertTrue(
            '/this/is/a/config' in self.renderer.config_data.keys())

    @mock.patch("rabbit_utils.log")
    @mock.patch("rabbit_utils.render")
    def test_write_all(self, log, render):
        self.renderer.write_all()

        self.assertTrue(render.called)
        self.assertTrue(log.called)


RABBITMQCTL_CLUSTERSTATUS_RUNNING = """Cluster status of node 'rabbit@juju-devel3-machine-19' ...
[{nodes,[{disc,['rabbit@juju-devel3-machine-14',
                'rabbit@juju-devel3-machine-19']}]},
 {running_nodes,['rabbit@juju-devel3-machine-14',
                 'rabbit@juju-devel3-machine-19']},
 {cluster_name,<<"rabbit@juju-devel3-machine-14.openstacklocal">>},
 {partitions,[]}]
 """

RABBITMQCTL_CLUSTERSTATUS_SOLO = """Cluster status of node 'rabbit@juju-devel3-machine-14' ...
[{nodes,[{disc,['rabbit@juju-devel3-machine-14']}]},
 {running_nodes,['rabbit@juju-devel3-machine-14']},
 {cluster_name,<<"rabbit@juju-devel3-machine-14.openstacklocal">>},
 {partitions,[]}]
 """


class UtilsTests(CharmTestCase):
    def setUp(self):
        super(UtilsTests, self).setUp(rabbit_utils,
                                      TO_PATCH)

    @mock.patch("rabbit_utils.log")
    def test_update_empty_hosts_file(self, mock_log):
        map = {'1.2.3.4': 'my-host'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            rabbit_utils.HOSTS_FILE = tmpfile.name
            rabbit_utils.HOSTS_FILE = tmpfile.name
            rabbit_utils.update_hosts_file(map)

        with open(tmpfile.name, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "%s %s\n" % (map.items()[0]))

    @mock.patch("rabbit_utils.log")
    def test_update_hosts_file_w_dup(self, mock_log):
        map = {'1.2.3.4': 'my-host'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            rabbit_utils.HOSTS_FILE = tmpfile.name

            with open(tmpfile.name, 'w') as fd:
                fd.write("%s %s\n" % (map.items()[0]))

            rabbit_utils.update_hosts_file(map)

        with open(tmpfile.name, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "%s %s\n" % (map.items()[0]))

    @mock.patch("rabbit_utils.log")
    def test_update_hosts_file_entry(self, mock_log):
        altmap = {'1.1.1.1': 'alt-host'}
        map = {'1.1.1.1': 'hostA',
               '2.2.2.2': 'hostB',
               '3.3.3.3': 'hostC',
               '4.4.4.4': 'hostD'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            rabbit_utils.HOSTS_FILE = tmpfile.name

            with open(tmpfile.name, 'w') as fd:
                fd.write("#somedata\n")
                fd.write("%s %s\n" % (altmap.items()[0]))

            rabbit_utils.update_hosts_file(map)

        with open(rabbit_utils.HOSTS_FILE, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "#somedata\n")
        self.assertEqual(lines[1], "%s %s\n" % (map.items()[0]))
        self.assertEqual(lines[4], "%s %s\n" % (map.items()[3]))

    @mock.patch('rabbit_utils.running_nodes')
    def test_not_clustered(self, mock_running_nodes):
        print "test_not_clustered"
        mock_running_nodes.return_value = []
        self.assertFalse(rabbit_utils.clustered())

    @mock.patch('rabbit_utils.running_nodes')
    def test_clustered(self, mock_running_nodes):
        mock_running_nodes.return_value = ['a', 'b']
        self.assertTrue(rabbit_utils.clustered())

    @mock.patch('rabbit_utils.subprocess')
    def test_running_nodes(self, mock_subprocess):
        '''Ensure cluster_status can be parsed for a clustered deployment'''
        mock_subprocess.check_output.return_value = \
            RABBITMQCTL_CLUSTERSTATUS_RUNNING
        self.assertEqual(rabbit_utils.running_nodes(),
                         ['rabbit@juju-devel3-machine-14',
                          'rabbit@juju-devel3-machine-19'])

    @mock.patch('rabbit_utils.subprocess')
    def test_running_nodes_solo(self, mock_subprocess):
        '''Ensure cluster_status can be parsed for a single unit deployment'''
        mock_subprocess.check_output.return_value = \
            RABBITMQCTL_CLUSTERSTATUS_SOLO
        self.assertEqual(rabbit_utils.running_nodes(),
                         ['rabbit@juju-devel3-machine-14'])

    @mock.patch('rabbit_utils.get_hostname')
    def test_get_node_hostname(self, mock_get_hostname):
        mock_get_hostname.return_value = 'juju-devel3-machine-13'
        self.assertEqual(rabbit_utils.get_node_hostname('192.168.20.50'),
                         'juju-devel3-machine-13')
        mock_get_hostname.assert_called_with('192.168.20.50', fqdn=False)

    @mock.patch('rabbit_utils.peer_retrieve')
    def test_leader_node(self, mock_peer_retrieve):
        mock_peer_retrieve.return_value = 'juju-devel3-machine-15'
        self.assertEqual(rabbit_utils.leader_node(),
                         'rabbit@juju-devel3-machine-15')

    @mock.patch('rabbit_utils.relation_set')
    @mock.patch('rabbit_utils.wait_app')
    @mock.patch('rabbit_utils.subprocess.check_call')
    @mock.patch('rabbit_utils.subprocess.check_output')
    @mock.patch('rabbit_utils.time')
    @mock.patch('rabbit_utils.running_nodes')
    @mock.patch('rabbit_utils.leader_node')
    @mock.patch('rabbit_utils.clustered')
    @mock.patch('rabbit_utils.cmp_pkgrevno')
    def test_cluster_with_not_clustered(self, mock_cmp_pkgrevno,
                                        mock_clustered, mock_leader_node,
                                        mock_running_nodes, mock_time,
                                        mock_check_output, mock_check_call,
                                        mock_wait_app,
                                        mock_relation_set):
        mock_cmp_pkgrevno.return_value = True
        mock_clustered.return_value = False
        mock_leader_node.return_value = 'rabbit@juju-devel7-machine-11'
        mock_running_nodes.return_value = ['rabbit@juju-devel5-machine-19']
        rabbit_utils.cluster_with()
        mock_check_output.assert_called_with([rabbit_utils.RABBITMQ_CTL,
                                              'join_cluster',
                                              'rabbit@juju-devel7-machine-11'],
                                             stderr=-2)

    @mock.patch('rabbit_utils.subprocess.check_call')
    @mock.patch('rabbit_utils.subprocess.check_output')
    @mock.patch('rabbit_utils.time')
    @mock.patch('rabbit_utils.running_nodes')
    @mock.patch('rabbit_utils.leader_node')
    @mock.patch('rabbit_utils.clustered')
    @mock.patch('rabbit_utils.cmp_pkgrevno')
    def test_cluster_with_clustered(self, mock_cmp_pkgrevno, mock_clustered,
                                    mock_leader_node, mock_running_nodes,
                                    mock_time, mock_check_output,
                                    mock_check_call):
        mock_clustered.return_value = True
        mock_leader_node.return_value = 'rabbit@juju-devel7-machine-11'
        mock_running_nodes.return_value = ['rabbit@juju-devel5-machine-19',
                                           'rabbit@juju-devel7-machine-11']
        rabbit_utils.cluster_with()
        self.assertEqual(0, mock_check_output.call_count)

    @mock.patch('rabbit_utils.wait_app')
    @mock.patch('rabbit_utils.subprocess.check_call')
    @mock.patch('rabbit_utils.subprocess.check_output')
    @mock.patch('rabbit_utils.time')
    @mock.patch('rabbit_utils.running_nodes')
    @mock.patch('rabbit_utils.leader_node')
    @mock.patch('rabbit_utils.clustered')
    @mock.patch('rabbit_utils.cmp_pkgrevno')
    def test_cluster_with_no_leader(self, mock_cmp_pkgrevno, mock_clustered,
                                    mock_leader_node, mock_running_nodes,
                                    mock_time, mock_check_output,
                                    mock_check_call, mock_wait_app):
        mock_clustered.return_value = False
        mock_leader_node.return_value = None
        mock_running_nodes.return_value = ['rabbit@juju-devel5-machine-19']
        rabbit_utils.cluster_with()
        self.assertEqual(0, mock_check_output.call_count)

    @mock.patch('rabbit_utils.application_version_set')
    @mock.patch('rabbit_utils.get_upstream_version')
    def test_assess_status(self, mock_get_upstream_version,
                           mock_application_version_set):
        mock_get_upstream_version.return_value = None
        with mock.patch.object(rabbit_utils, 'assess_status_func') as asf:
            callee = mock.MagicMock()
            asf.return_value = callee
            rabbit_utils.assess_status('test-config')
            asf.assert_called_once_with('test-config')
            callee.assert_called_once_with()
            self.assertFalse(mock_application_version_set.called)

    @mock.patch('rabbit_utils.application_version_set')
    @mock.patch('rabbit_utils.get_upstream_version')
    def test_assess_status_installed(self, mock_get_upstream_version,
                                     mock_application_version_set):
        mock_get_upstream_version.return_value = '3.5.7'
        with mock.patch.object(rabbit_utils, 'assess_status_func') as asf:
            callee = mock.MagicMock()
            asf.return_value = callee
            rabbit_utils.assess_status('test-config')
            asf.assert_called_once_with('test-config')
            callee.assert_called_once_with()
            mock_application_version_set.assert_called_with('3.5.7')

    @mock.patch.object(rabbit_utils, 'clustered')
    @mock.patch.object(rabbit_utils, 'status_set')
    @mock.patch.object(rabbit_utils, 'assess_cluster_status')
    @mock.patch.object(rabbit_utils, 'services')
    @mock.patch.object(rabbit_utils, '_determine_os_workload_status')
    def test_assess_status_func(self,
                                _determine_os_workload_status,
                                services,
                                assess_cluster_status,
                                status_set,
                                clustered):
        services.return_value = 's1'
        _determine_os_workload_status.return_value = ('active', '')
        clustered.return_value = True
        rabbit_utils.assess_status_func('test-config')()
        # ports=None whilst port checks are disabled.
        _determine_os_workload_status.assert_called_once_with(
            'test-config', {}, charm_func=assess_cluster_status, services='s1',
            ports=None)
        status_set.assert_called_once_with('active',
                                           'Unit is ready and clustered')

    def test_pause_unit_helper(self):
        with mock.patch.object(rabbit_utils, '_pause_resume_helper') as prh:
            rabbit_utils.pause_unit_helper('random-config')
            prh.assert_called_once_with(
                rabbit_utils.pause_unit,
                'random-config')
        with mock.patch.object(rabbit_utils, '_pause_resume_helper') as prh:
            rabbit_utils.resume_unit_helper('random-config')
            prh.assert_called_once_with(
                rabbit_utils.resume_unit,
                'random-config')

    @mock.patch.object(rabbit_utils, 'services')
    def test_pause_resume_helper(self, services):
        f = mock.MagicMock()
        services.return_value = 's1'
        with mock.patch.object(rabbit_utils, 'assess_status_func') as asf:
            asf.return_value = 'assessor'
            rabbit_utils._pause_resume_helper(f, 'some-config')
            asf.assert_called_once_with('some-config')
            # ports=None whilst port checks are disabled.
            f.assert_called_once_with('assessor', services='s1', ports=None)

    @mock.patch('rabbit_utils.subprocess.check_call')
    def test_rabbitmqctl_wait(self, check_call):
        rabbit_utils.rabbitmqctl('wait', '/var/lib/rabbitmq.pid')
        check_call.assert_called_with(['timeout', '180',
                                       '/usr/sbin/rabbitmqctl', 'wait',
                                       '/var/lib/rabbitmq.pid'])

    @mock.patch('rabbit_utils.subprocess.check_call')
    def test_rabbitmqctl_start_app(self, check_call):
        rabbit_utils.rabbitmqctl('start_app')
        check_call.assert_called_with(['/usr/sbin/rabbitmqctl', 'start_app'])

    @mock.patch('rabbit_utils.subprocess.check_call')
    def test_rabbitmqctl_wait_fail(self, check_call):
        check_call.side_effect = (rabbit_utils.subprocess.
                                  CalledProcessError(1, 'cmd'))
        with self.assertRaises(rabbit_utils.subprocess.CalledProcessError):
            rabbit_utils.wait_app()

    @mock.patch('rabbit_utils.subprocess.check_call')
    def test_rabbitmqctl_wait_success(self, check_call):
        check_call.return_value = 0
        self.assertTrue(rabbit_utils.wait_app())

    @mock.patch.object(rabbit_utils, 'is_leader')
    @mock.patch.object(rabbit_utils, 'related_units')
    @mock.patch.object(rabbit_utils, 'relation_ids')
    @mock.patch.object(rabbit_utils, 'config')
    def test_is_sufficient_peers(self, mock_config, mock_relation_ids,
                                 mock_related_units, mock_is_leader):
        # With leadership Election
        mock_is_leader.return_value = False
        _config = {'min-cluster-size': None}
        mock_config.side_effect = lambda key: _config.get(key)
        self.assertTrue(rabbit_utils.is_sufficient_peers())

        mock_is_leader.return_value = False
        mock_relation_ids.return_value = ['cluster:0']
        mock_related_units.return_value = ['test/0']
        _config = {'min-cluster-size': 3}
        mock_config.side_effect = lambda key: _config.get(key)
        self.assertFalse(rabbit_utils.is_sufficient_peers())

        mock_is_leader.return_value = False
        mock_related_units.return_value = ['test/0', 'test/1']
        _config = {'min-cluster-size': 3}
        mock_config.side_effect = lambda key: _config.get(key)
        self.assertTrue(rabbit_utils.is_sufficient_peers())

    @mock.patch.object(rabbit_utils.os.path, 'exists')
    def test_rabbitmq_is_installed(self, mock_os_exists):
        mock_os_exists.return_value = True
        self.assertTrue(rabbit_utils.rabbitmq_is_installed())

        mock_os_exists.return_value = False
        self.assertFalse(rabbit_utils.rabbitmq_is_installed())

    @mock.patch.object(rabbit_utils, 'clustered')
    @mock.patch.object(rabbit_utils, 'rabbitmq_is_installed')
    @mock.patch.object(rabbit_utils, 'is_sufficient_peers')
    def test_cluster_ready(self, mock_is_sufficient_peers,
                           mock_rabbitmq_is_installed, mock_clustered):

        # Not sufficient number of peers
        mock_is_sufficient_peers.return_value = False
        self.assertFalse(rabbit_utils.cluster_ready())

        # This unit not yet clustered
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = 'teset/0'
        _config = {'min-cluster-size': 3}
        self.config.side_effect = lambda key: _config.get(key)
        mock_clustered.return_value = False
        self.assertFalse(rabbit_utils.cluster_ready())

        # Not all cluster ready
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = False
        _config = {'min-cluster-size': 3}
        self.config.side_effect = lambda key: _config.get(key)
        mock_clustered.return_value = True
        self.assertFalse(rabbit_utils.cluster_ready())

        # All cluster ready
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = 'teset/0'
        _config = {'min-cluster-size': 3}
        self.config.side_effect = lambda key: _config.get(key)
        mock_clustered.return_value = True
        self.assertTrue(rabbit_utils.cluster_ready())

        # Not all cluster ready no min-cluster-size
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = False
        _config = {'min-cluster-size': None}
        self.config.side_effect = lambda key: _config.get(key)
        mock_clustered.return_value = True
        self.assertFalse(rabbit_utils.cluster_ready())

        # All cluster ready no min-cluster-size
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = 'teset/0'
        _config = {'min-cluster-size': None}
        self.config.side_effect = lambda key: _config.get(key)
        mock_clustered.return_value = True
        self.assertTrue(rabbit_utils.cluster_ready())

        # Assume single unit no-min-cluster-size
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = []
        self.related_units.return_value = []
        self.relation_get.return_value = None
        _config = {'min-cluster-size': None}
        self.config.side_effect = lambda key: _config.get(key)
        mock_clustered.return_value = True
        self.assertTrue(rabbit_utils.cluster_ready())

    def test_client_node_is_ready(self):
        # Paused
        self.is_unit_paused_set.return_value = True
        self.assertFalse(rabbit_utils.client_node_is_ready())

        # Not ready
        self.is_unit_paused_set.return_value = False
        self.relation_ids.return_value = ['amqp:0']
        self.leader_get.return_value = {}
        self.assertFalse(rabbit_utils.client_node_is_ready())

        # Ready
        self.is_unit_paused_set.return_value = False
        self.relation_ids.return_value = ['amqp:0']
        self.leader_get.return_value = {'amqp:0_password': 'password'}
        self.assertTrue(rabbit_utils.client_node_is_ready())

    @mock.patch.object(rabbit_utils, 'cluster_ready')
    @mock.patch.object(rabbit_utils, 'rabbitmq_is_installed')
    def test_leader_node_is_ready(self, mock_rabbitmq_is_installed,
                                  mock_cluster_ready):
        # Paused
        self.is_unit_paused_set.return_value = True
        self.assertFalse(rabbit_utils.leader_node_is_ready())

        # Not installed
        self.is_unit_paused_set.return_value = False
        mock_rabbitmq_is_installed.return_value = False
        self.is_leader.return_value = True
        mock_cluster_ready.return_value = True
        self.assertFalse(rabbit_utils.leader_node_is_ready())

        # Not leader
        self.is_unit_paused_set.return_value = False
        mock_rabbitmq_is_installed.return_value = True
        self.is_leader.return_value = False
        mock_cluster_ready.return_value = True
        self.assertFalse(rabbit_utils.leader_node_is_ready())

        # Not clustered
        self.is_unit_paused_set.return_value = False
        mock_rabbitmq_is_installed.return_value = True
        self.is_leader.return_value = True
        mock_cluster_ready.return_value = False
        self.assertFalse(rabbit_utils.leader_node_is_ready())

        # Leader ready
        self.is_unit_paused_set.return_value = False
        mock_rabbitmq_is_installed.return_value = True
        self.is_leader.return_value = True
        mock_cluster_ready.return_value = True
        self.assertTrue(rabbit_utils.leader_node_is_ready())

    def test_get_unit_ip(self):
        AMQP_IP = '10.200.1.1'
        OVERRIDE_AMQP_IP = '10.250.1.1'
        CLUSTER_IP = '10.100.1.1'
        OVERRIDE_CLUSTER_IP = '10.150.1.1'
        IPV6_IP = '2001:DB8::1'
        DEFAULT_IP = '172.16.1.1'
        self.assert_charm_supports_ipv6.return_value = True
        self.get_ipv6_addr.return_value = [IPV6_IP]
        self.unit_get.return_value = DEFAULT_IP
        self.get_address_in_network.return_value = DEFAULT_IP
        self.network_get_primary_address.return_value = DEFAULT_IP

        # IPv6
        _config = {'prefer-ipv6': True,
                   'cluster-network': '10.100.1.0/24',
                   'access-network': '10.200.1.0/24'}
        self.config.side_effect = lambda key: _config.get(key)
        self.assertEqual(IPV6_IP, rabbit_utils.get_unit_ip())

        # Overrides
        _config = {'prefer-ipv6': False,
                   'cluster-network': '10.100.1.0/24',
                   'access-network': '10.200.1.0/24'}
        self.config.side_effect = lambda key: _config.get(key)

        self.get_address_in_network.return_value = OVERRIDE_AMQP_IP
        self.assertEqual(OVERRIDE_AMQP_IP, rabbit_utils.get_unit_ip())

        self.get_address_in_network.return_value = OVERRIDE_CLUSTER_IP
        self.assertEqual(OVERRIDE_CLUSTER_IP,
                         rabbit_utils.get_unit_ip(
                             config_override='cluster-network',
                             interface='cluster'))

        # Network-get calls
        _config = {'prefer-ipv6': False,
                   'cluster-network': None,
                   'access-network': None}
        self.config.side_effect = lambda key: _config.get(key)

        self.network_get_primary_address.return_value = AMQP_IP
        self.assertEqual(AMQP_IP, rabbit_utils.get_unit_ip())

        self.network_get_primary_address.return_value = CLUSTER_IP
        self.assertEqual(CLUSTER_IP,
                         rabbit_utils.get_unit_ip(
                             config_override='cluster-network',
                             interface='cluster'))

        # Default
        self.network_get_primary_address.return_value = AMQP_IP
        self.network_get_primary_address.side_effect = NotImplementedError
        self.assertEqual(DEFAULT_IP, rabbit_utils.get_unit_ip())

    @mock.patch.object(rabbit_utils, 'get_upstream_version')
    def test_get_managment_port_legacy(self, mock_get_upstream_version):
        mock_get_upstream_version.return_value = '2.7.1'
        self.assertEqual(rabbit_utils.get_managment_port(), 55672)

    @mock.patch.object(rabbit_utils, 'get_upstream_version')
    def test_get_managment_port(self, mock_get_upstream_version):
        mock_get_upstream_version.return_value = '3.5.7'
        self.assertEqual(rabbit_utils.get_managment_port(), 15672)
