#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: powerdns_zone
short_description: Manage PowerDNS zones
description:
- Create, update or delete a zone in PowerDNS via API
options:
  name:
    description: Zone name
    required: true
  pdns_host:
    description: Host running PowerDNS
    required: false
    default: 127.0.0.1
  pdns_port:
    description: Port used by PowerDNS API
    required: false
    default: 8081
  pdns_prot:
    description: Protocol used to connect to PowerDNS API
    required: false
    default: http
    choices: ['http', 'https']
notes:
author: "Thomas Krahn (@nosmoht)"
'''

EXAMPLES = '''
- powerdns_zone:
    name: zone01.internal.example.com
    state: present
    pdns_host: powerdns.example.cm
    pdns_port: 8080
    pdns_prot: http
'''

import requests
import json


class PowerDNSError(Exception):
    def __init__(self, url, status_code, message):
        self.url = url
        self.status_code = status_code
        self.message = message
        super(PowerDNSError, self).__init__()


class PowerDNSClient:
    def __init__(self, host, port, prot, api_key):
        self.url = '{prot}://{host}:{port}'.format(prot=prot, host=host, port=port)
        self.headers = {'X-API-Key': api_key,
                        'content-type': 'application/json',
                        'accept': 'application/json'
                        }

    def _handle_request(self, req):
        if req.status_code in [200, 201]:
            return json.loads(req.text)
        elif req.status_code == 404:
            error_message = 'Not found'
        else:
            error_message = self._get_request_error_message(data=req)

        raise PowerDNSError(url=req.url,
                            status_code=req.status_code,
                            message=error_message)

    def _get_request_error_message(self, data):
        request_json = data.json()
        if 'error' in request_json:
            request_error = request_json.get('error')
        elif 'errors' in request_json:
            request_error = request_json.get('errors')
        else:
            request_error = 'DONT KNOW'
        return request_error

    def _get_zones_url(self):
        return '{url}/servers/localhost/zones'.format(url=self.url)

    def _get_zone_url(self, name):
        return '{url}/{name}'.format(url=self._get_zones_url(), name=name)

    def get_zone(self, name):
        req = requests.get(url=self._get_zone_url(name), headers=self.headers)
        if req.status_code == 422:  # zone does not exist
            return None
        return self._handle_request(req)

    def create_zone(self, data):
        req = requests.post(url=self._get_zones_url(), data=json.dumps(data), headers=self.headers)
        return self._handle_request(req)

    def delete_zone(self, name):
        req = requests.delete(url=self._get_zone_url(name), headers=self.headers)
        return self._handle_request(req)


def ensure(module, pdns_client):
    kind = module.params['kind']
    masters = module.params['masters']
    name = module.params['name']
    nameservers = module.params['nameservers']
    state = module.params['state']
    try:
        zone = pdns_client.get_zone(name)
    except PowerDNSError as e:
        module.fail_json(msg='Error {code} on getting zone: {err}'.format(code=e.status_code, err=e.message))

    if not zone:
        if state == 'present':
            try:
                zone = dict(name=name, kind=kind, nameservers=nameservers, masters=masters)
                if module.check_mode:
                    module.exit_json(changed=True, zone=zone)
                pdns_client.create_zone(zone)
                return True, pdns_client.get_zone(name)
            except PowerDNSError as e:
                module.fail_json(msg='Could not create zone {name}: {err}'.format(name=name, err=e.message))
    else:
        if state == 'absent':
            try:
                if module.check_mode:
                    module.exit_json(changed=True, zone=zone)
                pdns_client.delete_zone(name)  # zone.get('id'))
                return True, None
            except PowerDNSError as e:
                module.fail_json(
                    msg='Could not delete zone {name}: HTTP {code}: {err}'.format(name=name, code=e.status_code,
                                                                                  err=e.message))
    return False, zone


def main():
    global module
    module = AnsibleModule(
        argument_spec=dict(
            kind=dict(type='str', required=False, default='master'),
            masters=dict(type='list', required=False),
            name=dict(type='str', required=True),
            nameservers=dict(type='list', required=False),
            state=dict(type='str', default='present', choices=['present', 'absent']),
            pdns_host=dict(type='str', default='127.0.0.1'),
            pdns_port=dict(type='int', default=8081),
            pdns_prot=dict(type='str', default='http', choices=['http', 'https']),
            pdns_api_key=dict(type='str', required=False),
        ),
        supports_check_mode=True,
    )

    pdns_client = PowerDNSClient(host=module.params['pdns_host'],
                                 port=module.params['pdns_port'],
                                 prot=module.params['pdns_prot'],
                                 api_key=module.params['pdns_api_key'])

    changed, zone = ensure(module, pdns_client)
    module.exit_json(changed=changed, zone=zone)


# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
