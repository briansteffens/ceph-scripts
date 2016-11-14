import os
import sys
import requests
import urllib
import json
import subprocess
from datetime import datetime
import time


def shell(cmd):
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)

    if len(res.stderr):
        print('ERROR: ' + res.stderr.decode('utf-8'))
        sys.exit(6)

    return res.stdout.decode('utf-8')


if not os.path.exists('id_rsa'):
    shell('ssh-keygen -f ./id_rsa -N \'\'')


ID_RSA = open('id_rsa').read()
ID_RSA_PUB = open('id_rsa.pub').read()


try:
    with open('config.json') as f:
        config = json.loads(f.read())
except:
    print('Failed to open file: config.json')
    sys.exit(3)


DATACENTER_ID = 6
PLAN_ID = 1
STACKSCRIPT_ID = 48715
DISTRIBUTION_ID = 140
KERNEL_ID = 138


def api_request(url_snippet):
    r = requests.get('https://api.linode.com/?api_key=' + config['api_key'] +
            '&api_action=' + url_snippet)

    if r.status_code != 200:
        print(r.status_code)
        sys.exit(1)

    res = r.json()

    if len(res['ERRORARRAY']):
        for error in res['ERRORARRAY']:
            print('Error: ' + str(error))
        sys.exit(2)

    return res['DATA']


def linodes():
    return api_request('linode.list')


def ceph_linodes():
    return [l for l in linodes() if l['LPM_DISPLAYGROUP'] == 'ceph']


def ceph_linode(label):
    for linode in ceph_linodes():
        if linode['LABEL'] == label:
            return linode

    print('No node with label ' + label + ' found.')
    sys.exit(4)


def get_id(linode_or_id):
    try:
        return linode_or_id['LINODEID']
    except:
        pass

    return linode_or_id


def linode_ips(linode_id):
    return api_request('linode.ip.list' +
            '&LinodeID=' + str(get_id(linode_id)))


def _linode_ip(linode_id, predicate):
    for ip in linode_ips(linode_id):
        if predicate(ip):
            return ip['IPADDRESS']

    print('No matching IP found.')
    sys.exit(5)


def linode_public_ip(linode_id):
    return _linode_ip(linode_id, lambda ip: ip['ISPUBLIC'] == 1)


def linode_private_ip(linode_id):
    return _linode_ip(linode_id, lambda ip: ip['ISPUBLIC'] == 0)


def purge_ceph_linodes():
    for linode in ceph_linodes():
        linode_id = linode['LINODEID']

        print('Deleting Linode ID ' + str(linode_id) + '..')

        api_request('linode.delete' +
                '&LinodeID=' + str(linode_id) +
                '&skipChecks=true')


def create_linode(label):
    print('Creating Linode ' + label + '..')

    r = api_request('linode.create' +
            '&DatacenterID=' + str(DATACENTER_ID) +
            '&PlanID=' + str(PLAN_ID))

    linode_id = r['LinodeID']

    print('New Linode ID: ' + str(linode_id) + '..')
    print('Setting Linode fields..')

    api_request('linode.update' +
            '&LinodeID=' + str(linode_id) +
            '&Label=' + label +
            '&lpm_displayGroup=ceph')

    return linode_id


def deploy_stackscript(linode_id, udfs):
    udfs_encoded = urllib.parse.quote_plus(json.dumps(udfs))

    print('Creating root disk from stackscript..')

    return api_request('linode.disk.createfromstackscript' +
            '&LinodeID=' + str(linode_id) +
            '&StackScriptID=' + str(STACKSCRIPT_ID) +
            '&StackScriptUDFResponses=' + udfs_encoded +
            '&Label=root' +
            '&Size=' + str(1024 * 2) +
            '&DistributionID=' + str(DISTRIBUTION_ID) +
            '&rootSSHKey=' + urllib.parse.quote_plus(config['ssh_key']) +
            '&rootPass=' + config['root_pass'])['DiskID']


def create_data_disk(linode_id):
    print('Creating data disk..')

    return api_request('linode.disk.create' +
            '&LinodeID=' + str(linode_id) +
            '&Label=data' +
            '&Type=raw' +
            '&Size=' + str(10 * 1024))['DiskID']


def create_config(linode_id, root_disk_id, data_disk_id):
    print('Creating config..')

    r = api_request('linode.config.create' +
            '&LinodeID=' + str(linode_id) +
            '&KernelID=' + str(KERNEL_ID) +
            '&Label=default' +
            '&DiskList=' + str(root_disk_id) + ',' + str(data_disk_id) +
            '&helper_network=1')

    return r['ConfigID']


def boot_linode(linode_id):
    print('Booting Linode ID ' + str(linode_id) + '..')

    r = api_request('linode.boot' +
            '&LinodeID=' + str(linode_id))

    return r['JobID']


def print_all(avail_name):
    for x in api_request('avail.' + avail_name):
        print(x + '\n')


def add_private_ip(linode_id):
    res = api_request('linode.ip.addprivate&' +
            'LinodeID=' + str(linode_id))['IPADDRESS']

    print('Linode ID ' + str(linode_id) + ' now has private IP ' + res)

    return res


def provision(name, node_type):
    linode_id = create_linode(name)
    add_private_ip(linode_id)
    root_disk_id = deploy_stackscript(linode_id, {'type': node_type})
    data_disk_id = create_data_disk(linode_id)
    create_config(linode_id, root_disk_id, data_disk_id)
    boot_linode(linode_id)
    return linode_id


def register_admin():
    admin = ceph_linode('admin')
    admin_ip = linode_public_ip(admin)

    with open('register-admin.sh') as f:
        script = f.read(). \
                replace('{{ ID_RSA }}', ID_RSA). \
                replace('{{ ID_RSA_PUB }}', ID_RSA_PUB)

        with open('temp', 'w') as f:
            f.write(script)

        print(shell('ssh -o StrictHostKeyChecking=no root@' + admin_ip +
                    ' \'bash\' < temp'))


def remote_shell(node_ip, cmd):
    return shell('ssh -o StrictHostKeyChecking=no root@' + node_ip + ' ' + cmd)


def remote_script(node_ip, script):
    return remote_shell(node_ip, '\'bash\' < ' + script)


def authorize_admin_to_node(node_id):
    node_ip = linode_public_ip(node_id)

    with open('authorize-node.sh') as f:
        script = f.read(). \
                replace('{{ AUTHORIZED_KEY }}', ID_RSA_PUB)

        with open('temp', 'w') as f:
            f.write(script)

        print(remote_script(node_ip, 'temp'))


def register_node(node_id, node_name):
    admin = ceph_linode('admin')
    admin_ip = linode_public_ip(admin)

    node_private_ip = linode_private_ip(node_id)

    with open('register-node.sh') as f:
        register_node_sh = f.read(). \
                replace('{{ NODE_NAME }}', node_name). \
                replace('{{ NODE_IP }}', node_private_ip)

        with open('temp', 'w') as f:
            f.write(register_node_sh)

        print(remote_script(node_ip, 'temp'))


def wait_for_provision(node_id, timeout=120, throttle=3):
    node_id = get_id(node_id)
    node_ip = linode_public_ip(node_id)

    print('Waiting for ' + str(node_id) + ' to come up..')

    started = datetime.now()
    while (datetime.now() - started).total_seconds() < timeout:
        try:
            if remote_script(node_ip, 'is_provisioned.sh').strip() == 'YES':
                print(str(node_id) + ' is up.')
                return
        except:
            pass

        time.sleep(throttle)

    print('Node ' + str(node_id) + ' never came up.')
    sys.exit(5)


#register_node('osd-0', 


#print_all('linodeplans')
#print_all('distributions')
#print_all('kernels')


#purge_ceph_linodes()

#admin_id = provision('admin', 'admin')
#osd0_id = provision('osd0', 'osd')

admin_id = ceph_linode('admin')

wait_for_provision(admin_id)
print('** A')
#wait_for_provision(osd0_id)
print('** B')

#register_admin()
print('** C')

#authorize_admin_to_node(osd0_id)
print('** D')
#register_node(osd0_id, 'osd0')

print('** E')
#osd0 = ceph_linode('osd0')
#authorize_admin_to_node(osd0)
#osd0_ip = linode_private_ip(osd0)
#register_node('osd0', osd0_ip)
