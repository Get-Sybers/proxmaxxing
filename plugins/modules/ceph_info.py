# Copyright: (c) 2026, Get-Sybers <99623331+Get-Sybers@users.noreply.github.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: ceph_info
short_description: Structured read-only Ceph cluster facts via librados
version_added: "0.2.0"
description:
  - Returns Ceph cluster state as parsed JSON objects, obtained by issuing
    JSON mon commands over the python C(rados) bindings.
  - Uses B(no subprocess and no C(ceph) CLI). Callers filter structured
    objects instead of string-matching CLI output, which removes the
    stdout-parsing failure modes of the CLI path (pretty-printed-table
    matching, and C(until:) expressions that raise on empty stdout).
  - B(Read-only by construction.) The caller selects query I(names) from a
    fixed allowlist compiled into the module; it cannot supply a command
    prefix. No mutating Ceph command is expressible through this interface,
    so the module always returns C(changed=false) and is safe in check mode.
notes:
  - Must run on a host with the Ceph admin keyring and C(python3-rados)
    installed — i.e. a Proxmox cluster member; every node of a cluster that
    runs Ceph qualifies.
  - Connection and each query are independently timeout-bounded, so a wedged
    or quorum-less mon fails the task promptly instead of hanging the play.
    This matters here because C(min_size=2) means a degraded cluster blocks
    I/O rather than erroring.
options:
  queries:
    description:
      - Names of the read-only queries to run, from the module's allowlist.
      - Supported names are C(status), C(health), C(health_detail),
        C(osd_tree), C(osd_df), C(osd_dump), C(osd_perf), C(osd_pool_ls),
        C(osd_pool_ls_detail), C(df), C(pg_stat), C(pg_dump_stuck),
        C(mon_dump), C(quorum_status), C(mon_status), C(time_sync_status),
        C(config_dump), C(balancer_status), C(crash_ls), C(device_ls),
        C(versions), C(fsid).
      - Defaults to the diagnostic set used by the health gate.
    type: list
    elements: str
    default: [status, health_detail, osd_tree, osd_df, df, pg_stat, osd_pool_ls_detail, quorum_status, time_sync_status, config_dump, crash_ls]
  conffile:
    description: Path to C(ceph.conf).
    type: path
    default: /etc/ceph/ceph.conf
  keyring:
    description: Path to the Ceph keyring used to authenticate.
    type: path
    default: /etc/ceph/ceph.client.admin.keyring
  name:
    description: Ceph client name to connect as.
    type: str
    default: client.admin
  connect_timeout:
    description: Seconds to wait for the initial mon connection.
    type: int
    default: 15
  query_timeout:
    description: Seconds to wait for each individual mon command.
    type: int
    default: 30
  fail_on_query_error:
    description:
      - When C(true), a query that the mons reject fails the task.
      - When C(false) (default) the failure is recorded per-query in
        I(errors) and the remaining queries still run, so one unsupported
        query on a given Ceph release cannot blind the whole diagnostic.
    type: bool
    default: false
author:
  - Get-Sybers (@Get-Sybers)
'''
EXAMPLES = r'''
- name: Gather Ceph diagnostic facts
  get_sybers.cluster.ceph_info:
  register: ceph
- name: Refuse to reboot a node while the cluster cannot lose one
  ansible.builtin.assert:
    that:
      - ceph.ceph.status.health.status == 'HEALTH_OK'
      - ceph.ceph.pg_stat.num_pg_by_state
        | selectattr('name', 'search', 'degraded|undersized|incomplete')
        | list | length == 0
    fail_msg: Cluster is not in a state where a node may be taken down.
- name: Narrow gather for a fast liveness probe
  get_sybers.cluster.ceph_info:
    queries: [health, quorum_status]
    query_timeout: 10
  register: ceph_live
'''
RETURN = r'''
ceph:
  description:
    - Mapping of requested query name to its parsed JSON result.
    - 'A query whose output is not valid JSON is returned as
      C({"_raw": "<text>"}) rather than being dropped.'
  returned: always
  type: dict
  sample:
    health: {status: HEALTH_OK, checks: {}}
    pg_stat: {num_pgs: 129, num_bytes: 402653184000}
fsid:
  description: Cluster FSID, always returned.
  returned: always
  type: str
  sample: 8ffdef63-1eb6-45a3-a4dc-fc0455ef363b
errors:
  description:
    - Per-query failures, keyed by query name. Empty when every query
      succeeded. Populated instead of failing unless I(fail_on_query_error).
  returned: always
  type: dict
  sample: {device_ls: "rc=-22 invalid command"}
'''
import json
import traceback
from ansible.module_utils.basic import AnsibleModule, missing_required_lib
RADOS_IMPORT_ERROR = None
try:
    import rados
    HAS_RADOS = True
except ImportError:
    HAS_RADOS = False
    RADOS_IMPORT_ERROR = traceback.format_exc()
QUERY_MAP = {
    'status': {'prefix': 'status'},
    'health': {'prefix': 'health'},
    'health_detail': {'prefix': 'health', 'detail': 'detail'},
    'osd_tree': {'prefix': 'osd tree'},
    'osd_df': {'prefix': 'osd df'},
    'osd_dump': {'prefix': 'osd dump'},
    'osd_perf': {'prefix': 'osd perf'},
    'osd_pool_ls': {'prefix': 'osd pool ls'},
    'osd_pool_ls_detail': {'prefix': 'osd pool ls', 'detail': 'detail'},
    'df': {'prefix': 'df'},
    'pg_stat': {'prefix': 'pg stat'},
    'pg_dump_stuck': {'prefix': 'pg dump_stuck'},
    'mon_dump': {'prefix': 'mon dump'},
    'mon_status': {'prefix': 'mon_status'},
    'quorum_status': {'prefix': 'quorum_status'},
    'time_sync_status': {'prefix': 'time-sync-status'},
    'config_dump': {'prefix': 'config dump'},
    'balancer_status': {'prefix': 'balancer status'},
    'crash_ls': {'prefix': 'crash ls'},
    'device_ls': {'prefix': 'device ls'},
    'versions': {'prefix': 'versions'},
    'fsid': {'prefix': 'fsid'},
}
DEFAULT_QUERIES = [
    'status', 'health_detail', 'osd_tree', 'osd_df', 'df', 'pg_stat',
    'osd_pool_ls_detail', 'quorum_status', 'time_sync_status', 'config_dump',
    'crash_ls',
]


def run_query(cluster, name, query_timeout):
    """Issue one allowlisted read-only mon command. Returns (result, error)."""
    cmd = dict(QUERY_MAP[name])
    cmd['format'] = 'json'
    ret, out, err = cluster.mon_command(
        json.dumps(cmd), b'', timeout=query_timeout)
    if ret != 0:
        return None, 'rc=%d %s' % (ret, (err or '').strip())
    if isinstance(out, bytes):
        out = out.decode('utf-8', errors='replace')
    out = out.strip()
    if not out:
        return {}, None
    try:
        return json.loads(out), None
    except ValueError:
        return {'_raw': out}, None


def main():
    module = AnsibleModule(
        argument_spec=dict(
            queries=dict(type='list', elements='str', default=DEFAULT_QUERIES),
            conffile=dict(type='path', default='/etc/ceph/ceph.conf'),
            keyring=dict(
                type='path', default='/etc/ceph/ceph.client.admin.keyring'),
            name=dict(type='str', default='client.admin'),
            connect_timeout=dict(type='int', default=15),
            query_timeout=dict(type='int', default=30),
            fail_on_query_error=dict(type='bool', default=False),
        ),
        supports_check_mode=True,
    )
    if not HAS_RADOS:
        module.fail_json(
            msg=missing_required_lib(
                'rados',
                reason='required to query Ceph without shelling out to the '
                       'ceph CLI (Debian/Proxmox package: python3-rados)'),
            exception=RADOS_IMPORT_ERROR)
    queries = module.params['queries']
    unknown = [q for q in queries if q not in QUERY_MAP]
    if unknown:
        module.fail_json(
            msg='Unsupported query name(s): %s. This module exposes a fixed '
                'read-only allowlist; supported names are: %s'
                % (', '.join(sorted(unknown)), ', '.join(sorted(QUERY_MAP))))
    try:
        cluster = rados.Rados(
            conffile=module.params['conffile'],
            name=module.params['name'],
            conf={'keyring': module.params['keyring']},
        )
    except Exception as exc:
        module.fail_json(
            msg='Failed to initialise the rados client: %s' % to_text_safe(exc),
            exception=traceback.format_exc())
    try:
        cluster.connect(timeout=module.params['connect_timeout'])
    except Exception as exc:
        module.fail_json(
            msg='Failed to connect to the Ceph cluster within %ss: %s. A '
                'timeout here usually means the mons have lost quorum rather '
                'than that the config is wrong.'
                % (module.params['connect_timeout'], to_text_safe(exc)),
            exception=traceback.format_exc())
    results = {}
    errors = {}
    try:
        fsid = cluster.get_fsid()
        for name in queries:
            try:
                value, err = run_query(
                    cluster, name, module.params['query_timeout'])
            except Exception as exc:
                value, err = None, to_text_safe(exc)
            if err is None:
                results[name] = value
            else:
                errors[name] = err
    finally:
        try:
            cluster.shutdown()
        except Exception:
            pass
    if errors and module.params['fail_on_query_error']:
        module.fail_json(
            msg='One or more Ceph queries failed: %s'
                % json.dumps(errors, sort_keys=True),
            ceph=results, fsid=fsid, errors=errors)
    module.exit_json(changed=False, ceph=results, fsid=fsid, errors=errors)


def to_text_safe(exc):
    try:
        return str(exc)
    except Exception:
        return repr(exc)


if __name__ == '__main__':
    main()
