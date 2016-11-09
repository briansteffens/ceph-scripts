import sys
import requests
import urllib
import json


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
            '&DiskList=' + str(root_disk_id) + ',' + str(data_disk_id))

    return r['ConfigID']


def boot_linode(linode_id):
    print('Booting Linode ID ' + str(linode_id) + '..')

    r = api_request('linode.boot' +
            '&LinodeID=' + str(linode_id))

    return r['JobID']


def print_all(avail_name):
    for x in api_request('avail.' + avail_name):
        print(x + '\n')


#print_all('linodeplans')
#print_all('distributions')
#print_all('kernels')

purge_ceph_linodes()

linode_id = create_linode('osd-0')
root_disk_id = deploy_stackscript(linode_id, {'a': 'testing'})
data_disk_id = create_data_disk(linode_id)
create_config(linode_id, root_disk_id, data_disk_id)
boot_linode(linode_id)

