#!/usr/bin/env python

#
# Nexenta Collector Analyzer Tool (nxcat)
# Copyright 2015 Nexenta Systems, Inc.  All rights reserved.
#
# NB: This script assumes a collector bundle tarfile has
#     already been ingested and the argument to '--path'
#     is either the fully qualified or relative pathname
#     to the results of the ingested collector bundle.
#
import os
import re
import sys
import optparse
import json
import math
import time
import errno
import gzip
from pprint import pprint
from lib.CText import *


_ver = '1.0.0'
base = ''
zp_stat = {}
zp_vmode = ''
hc_vmode = ''
sac_res = False
debug = False
machid = ''


def read_raw_txt(rawfile):
    rawlines = []

    try:
        with open(rawfile, 'r') as f:
            for l in f.readlines():
                pattern = '^#.*$'           # skip comment lines
                if re.match(pattern, l):
                    continue
                rawlines.append(l.rstrip('\n'))

    except IOError:
        pass

    return rawlines


def get_cs_items():
    global base
    global machid
    csfile = os.path.join(base, 'collector.stats')
    license = ''
    done = False

    print_header('collector.stats')
    for l in read_raw_txt(csfile):
        if license and not done:
            customer = get_custy_info(license)

            print 'Customer:\t',
            if customer is not None:
                print_bold(customer, 'white', True)
            else:
                print_fail('unable to obtain customer name from DB')

            done = True
            continue

        elif l.startswith('License'):
            license = l.split(':')[-1].strip()
            print 'License:\t', license

            machid = l.split('-')[-2].strip()
            print 'Machine ID:\t',
            print_warn(machid, True)

            continue

        elif l.startswith('Appliance'):
            patt = '.*\((\S+)\)$'
            mp = re.match(patt, l)
            if mp:
                print 'NS Version:\t', mp.group(1)
            continue
    return


def get_opthac():
    global base
    global machid
    File = os.path.join(base, 'ingestor/json/tar-czf-opthac.tar.gz.json')

    if not os.path.exists(File):
        return

    print_header('Clustering Info')
    try:
        with open(File) as f:
            json_data = json.load(f)

    except IOError:
        print '\t',
        print_warn('No clustering info in bundle', True)
        return
 
    for c in json_data:
        for val in sorted(json_data[c]):
            if val == 'ha':
                print_bold('Clustered:\t', 'white', False)
                ha = json_data[c][val]
                if ha == True:
                    prfmt_bold(str(ha), '%11s', 'green', True)
                else:
                    # XXX - still to unit test this path
                    prfmt_warn(str(ha), '%11s')
                continue

            elif val == 'name':
                cn = json_data[c][val]
                print_bold('Cluster Name:\t' + 7 * ' ', 'white', False)
                print_pass(cn)
                continue

            elif val == 'node1' or val == 'node2':
                if json_data[c][val]['machid'] == machid:
                    node = 'master'
                    print_bold('Primary Node Info', 'white', True)

                else:
                    node = 'slave'
                    print 'Secondary Node Info'

                if 'hostname' in json_data[c][val]:
                    host = json_data[c][val]['hostname']
                    print '\tHostname:\t',
                    if node == 'master':
                        print_warn(host, True)
                    else:
                        print_lite(host, 'white', True)

                if 'machid' in json_data[c][val]:
                    mcid = json_data[c][val]['machid']
                    print '\tMachine ID:\t',
                    if node == 'master':
                        print_warn(mcid, True)
                    else:
                        print_lite(mcid, 'white', True)

                if 'mntpt' in json_data[c][val]:
                    mpnt = json_data[c][val]['mntpt']
                    print '\tMnt Point:\t',
                    if node == 'master':
                        print_warn(mpnt, True)
                    else:
                        print_lite(mpnt, 'white', True)

                if 'zpool_guid' in json_data[c][val]:
                    guid = json_data[c][val]['zpool_guid']
                    print '\tZPool GUID:\t',
                    if node == 'master':
                        print_warn(guid, True)
                    else:
                        print_lite(guid, 'white', True)

    return


def get_uptime():
    global base
    File = os.path.join(base, 'ingestor/json/uptime.out.json')

    up_stats = {}
    try:
        with open(File) as f:
            up_stats = json.load(f)

    except IOError:
        print 'Up Time:\t',
        print_warn('No uptime info in bundle', True)
        return
        
    print 'Up Time:\t', up_stats['uptime']
    return


#
# collector.stats Info
#
def process_cs():
    get_cs_items()
    get_uptime()
    return


#
# Dump Device
#
def dump_dev():
    global base
    dmpfile = os.path.join(base, 'kernel/dumpadm.conf')
    msgfile = os.path.join(base, 'kernel/messages')

    for l in read_raw_txt(dmpfile):
        if l.startswith('#'):
            continue
        elif l.startswith('DUMPADM_DEVICE'):
            dev = l.split('=')[-1]
            continue

    try:
        print 'Dump Device:\t', dev,

    except UnboundLocalError:
        print_warn('No dump device info in bundle', True)
        return

    size = ''
    for l in read_raw_txt(msgfile):
        patt = '.* dump on .*'
        mp = re.match(patt, l)
        if mp:
            size = l.split()[-2]    # in MB
            break

    if len(size) != 0:
        szgb = math.ceil(float(size) / 1024)
    else:
        szgb = '??'

    print_bold('\t( ' + str(szgb) + ' GB ' + ')', 'white', True)
    return


#
# Hardware
#
def vendor_cpu():
    global  base
    File = os.path.join(base, 'ingestor/json/prtdiag-v.out.json')

    try:
        with open(File) as f:
            json_data = json.load(f)

    except IOError:
        print 'MB Vendor:\t',
        print_warn('No vendor info in bundle', True)
        print 'CPU:\t\t',
        print_warn('No CPU info in bundle', True)
        return

    for section in json_data:
        if section == 'header':
            vendor = json_data[section][0].split(':')[1].lstrip()
            print 'MB Vendor:\t', vendor

        elif section == 'cpu info':
            nc = len(json_data[section])
            print 'CPU:\t\t',
            ncpu = str(nc) + 'x'

            try:
                cpuinfo = json_data[section][0].lstrip().split('@')[0]

            except IndexError:
                print_warn('No CPU info in bundle', True)
                return

            print ncpu, cpuinfo


def memory():
    global base
    File = os.path.join(base,
        'ingestor/json/echo-memstat-mdb-k-tail-n2.out.json')

    try:
        with open(File) as f:
            json_data = json.load(f)

    except IOError:
        print 'RAM:\t\t',
        print_warn('No memory info in bundle', True)
        return

    for section in json_data:
        if section == 'total':
            mem = json_data[section]['MBs']
            if len(mem) > 3:
                mem = math.ceil(float(mem) / 1024)
                unit = "GB"
            else:
                unit = "MB"
            print 'RAM:\t\t', mem, unit


#
# ZPool Info
#
def print_fmt_msg(hdr, msg, disp):
    formatted = []
    t = 0
    i = 55

    #
    # work w/single string and slice it up in
    # lines of 55 chars (or so) until done and
    # put them in formatted list.
    #
    s = ' '.join(msg)
    sl = len(s)
    while i < sl:
        while s[i] != ' ':
            i += 1
            if i == sl:
                break

        formatted.append(s[t:i].lstrip())
        t = i
        i = t + 55
        if i >= sl:
            formatted.append(s[t:sl].lstrip())
            break

    #
    # Finally simply print the passed in header
    # and the formatted output.
    #
    prt_hdr = False
    for f in formatted:
        if not prt_hdr:
            if disp == 'bold':
                print_warn(hdr + ':\t\t' + f, True)
            else:
                print_debug(hdr + ':\t\t' + f, True)
            prt_hdr = True
            continue
        if disp == 'bold':
            print_warn('\t\t' + f.lstrip(), True)
        else:
            print_debug('\t\t' + f.lstrip(), True)

    return


def print_status(pool):
    if 'status' in zp_stat[pool]:
        print_fmt_msg('Status', zp_stat[pool]['status'], 'bold')

    return


def get_vdev(pool, item):
    global zp_stat

    pname = zp_stat[pool]['config'][item]
    for x in pname['vdev']:
        if 'vdev' in pname['vdev'][x]:
            vdev = pname['vdev'][x]['vdev']
        else:
            vdev = pname['vdev']

    return vdev


def slot_xref(msg, vd, color):
    global base
    File = os.path.join(base, 'ingestor/json/nmc-c-show-lun-slotmap.out.json')

    if not os.path.exists(File):
        print_bold(msg + vd, color, True)
        return False
    else:
        try:
            with open(File) as f:
                slotmap = json.load(f)

        except Exception, e:
            print 'Exception %s raised' % str(e)
            return False

    jbod = slotno = False
    try:
        jb = slotmap[vd]['jbod']
        jbod = True

    except KeyError:
        print_bold(msg + vd, color, True)
        return False

    try:
        sn = slotmap[vd]['slot#']
        slotno = True

    except KeyError:
        print_bold(msg + vd, color, True)
        return False

    if jbod and slotno:
        s = msg + vd + '\t\t( ' + jb + ', slot:' + sn + ' )'
        print_bold(s, color, True)
    else:
        print_bold(msg + vd, color, True)
        return False

    return True


def simple_device(dev):
    patt = 'c[0-9]+t[0-9]+d[0-9]+.*'
    mp = re.match(patt, dev)
    if mp:
        return True
    return False


def print_devices(pool):
    global zp_stat

    vdevs = [pool, 'cache', 'logs']
    for v in vdevs:
        try:
            pname = zp_stat[pool]['config'][v]
        except KeyError:
            continue

        vtype = ''
        dok = dfl = 0
        devices = pname['vdev']
        for d in devices:
            vtype = d

            if simple_device(d):
                vds = pname['vdev'][d]['state']
                if vds == 'ONLINE':
                    dok += 1
                elif vds == 'FAULTED' or vds == 'DEGRADED':
                    dfl += 1
                continue

            vDv = get_vdev(pool, v)
            for vc in vDv:
                vds = vDv[vc]['state']
                if vds == 'ONLINE':
                    dok += 1                    # Number of ONLINE devices
                else:
                    try:
                        notol = vDv[vc]['vdev']
                        for flt in notol:
                            if notol[flt]['state'] == 'FAULTED':
                                dfl += 1        # Number of FAULTED devices

                    except KeyError:
                        pass

        devlen = len(devices)
        tdev = dok / devlen

        if tdev > 11:               # Anything more thn 11 disks, flag fail
            col = 'red'
        elif vtype == 'raidz1-0':   # raidz1 is pow2 + 1 parity disk, else warn
            col = 'yellow' if (tdev - 1) % 2 else 'green'
        elif vtype == 'raidz2-0':   # raidz2 is pow2 + 2 parity disks, else warn
            col = 'yellow' if (tdev - 2) % 2 else 'green'
        elif vtype == 'raidz3-0':   # raidz3 is pow2 + 3 parity disks, else warn
            col = 'yellow' if (tdev - 3) % 2 else 'green'
        else:
            col = 'white'           # Anything else not considered a problem
        kd = str(tdev)

        sdev = False
        done = False
        for x in devices:
            stt = pname['vdev'][x]['state']

            #
            # NB: Hack to deal w/json files that have multiple devices
            #     as vdevs for 'cache' or 'logs', instead of a properly
            #     defined dictionary that has the one vdev and multiple
            #     devices underneath.
            #
            if len(devices) > 1:
                sdev = simple_device(x)
                if v == 'cache' or v == 'logs' or sdev:
                    if not done:
                        done = True
                    else:
                        continue

            if v == 'cache' or v == 'logs':
                msg = 'vdev:\t' + v
            elif sdev:
                msg = 'vdev:\t' + 'Concatenation'
                kd = str(dok + dfl)
            else:
                msg = 'vdev:\t' + x
            print_pass(msg) if stt == 'ONLINE' else print_fail(msg)

            print '\tTotal Devices: (',
            print_bold(kd, col, False)
            print ')'

            fd = str(dfl)
            if dfl != 0:
                print_fail('\tFailed Devices:\t' + fd)

            try:
                vdev = pname['vdev'][x]['vdev']
            except KeyError:
                vdev = pname['vdev']

            for vd in vdev:
                if vdev[vd]['state'] == 'ONLINE':
                    slot_xref('\t\t', vd, 'green')

                else:
                    try:
                        pdevs = vdev[vd]['vdev']    # raidz2 devices

                        for fds in pdevs:
                            vds = vdev[vd]['vdev'][fds]['state']
                            if vds == 'FAULTED' or vds == 'DEGRADED':
                                slot_xref('\t\t\t', fds, 'red')
                                print_fail('\t\t\t\t' + '<< ' + \
                                    vdev[vd]['vdev'][fds]['info'] + ' >>')
                            else:
                                slot_xref('\t\t\t', fds, 'green')

                    except KeyError:                # mirror devices

                        vds = vdev[vd]['state']
                        if vds == 'FAULTED' or vds == 'DEGRADED':
                            slot_xref('\t\t', vd, 'red')
                            print_fail('\t\t\t' + \
                                '<< ' + vdev[vd]['info'] + ' >>')
                        else:
                            slot_xref('\t\t\t', vd, 'green')
    return


def print_scan(pool):
    global zp_stat

    if 'scan' in zp_stat[pool]:
        print_fmt_msg('Scan', zp_stat[pool]['scan'], 'lite')

    return


def zp_status(zpool):
    global base
    global zp_stat
    File = os.path.join(base, 'ingestor/json/zpool-status-dv.out.json')

    with open(File) as f:
        zp_stat = json.load(f)

    for pool in zp_stat:
        if pool != zpool:
            continue
        print_status(pool)
        print_devices(pool)
        print_scan(pool)

    return


def zp_list(mode):
    global base
    File = os.path.join(base, 'ingestor/json/zpool-list-o-all.out.json')

    if not os.path.exists(File):
        return

    print_header('ZPools Info')
    with open(File) as f:
        json_data = json.load(f)

    for section in json_data:
        if json_data[section]:
            name = json_data[section]['name']
            health = json_data[section]['health']
            bootfs = json_data[section]['bootfs']
            used = json_data[section]['alloc']
            free = json_data[section]['free']
            size = json_data[section]['size']
            cap = json_data[section]['cap']
            if 'lowatermark' in json_data[section]:
                lowat = int(json_data[section]['lowatermark'])
            else:
                lowat = 50      # some sane value

            if 'hiwatermark' in json_data[section]:
                hiwat = int(json_data[section]['hiwatermark'])
            else:
                hiwat = 80      # some sane value

            print 70 * '-'
            print 'Pool:\t\t',
            print_bold(name, 'white', True)

            tint = 'red' if health != 'ONLINE' else 'green'
            print_bold('Health:\t\t' + health, tint, True)

            if mode == 'verbose' or health != 'ONLINE':
                zp_status(name)

            print 'Active Boot:\t',
            print_bold(bootfs, 'white', True)

            print 'Total:\t\t',
            print_bold(size + ' / ' + used, 'white', True)

            capacity = int(cap.split('%')[0])
            if capacity <= lowat:
                tint = 'green'
            elif capacity > lowat and capacity <= hiwat:
                tint = 'yellow'
            elif capacity > hiwat:
                tint = 'red'
            print 'Capacity:\t',
            print_bold(cap, tint, True)


#
# JBOD Info
#
def print_jbod_hdr():

    prfmt_mc_row('     ,      ,      ,      , Total,  Busy',
                 ' %15s,  %12s,  %20s,  %21s,   %9s,   %6s',
                 'white, white, white, white, white, white',
                 ' bold,  bold,  bold,  bold,  bold,  bold')

    prfmt_mc_row('JBOD, Vendor, Model, Serial Number, Slots, Slots',
                 '%12s,    %8s,  %16s,          %17s,   %7s,  %5s,',
                 'white, white, white,         white, white, white',
                 ' bold,  bold,  bold,          bold,  bold,  bold')

    prfmt_mc_row('----------, ------, ---------------, \
                 ----------------, -----, -----',
                 '%12s,    %8s,  %16s,  %17s,   %7s,  %8s,',
                 'white, white, white, white, white, white',
                 ' bold,  bold,  bold,  bold,  bold,  bold')


def dump_jbod_data(status, alias, vendor, model, serial, tslots, bslots):

    if status == None:
        tint = 'white'
    elif status == 'OK':
        tint = 'green'
    else:
        tint = 'yellow'

    vals = '%s, %s, %s, %s, %s, %s' %  \
        (alias, vendor, model, serial, tslots, bslots)
    fmts = '%12s,    %8s,  %16s,  %17s,   %7s,  %7s,'
    cols = '%s, %s, %s, %s, %s, %s' %  \
        (tint, 'white', 'white', 'white', 'white', 'white')
    disp = ' bold,  lite,  lite,  lite,  lite,  lite'

    prfmt_mc_row(vals, fmts, cols, disp)


def jbods():
    global base
    File1 = os.path.join(base, 'ingestor/json/nmc-c-show-jbod-all.out.json')
    File2 = os.path.join(base, 'ingestor/json/sesctl-enclosure.out.json')
    colorized = False

    if not os.path.exists(File1):
        return

    print_header('JBOD Enclosure Info')
    try:
        with open(File1) as f:
            jbods = json.load(f)
    except IOError:
        print_warn('\tNo JBOD info found in bundle', True)
        return

    if os.path.exists(File2):
        try:
            with open(File2) as f:
                sesctl = json.load(f)
                colorized = True
        except IOError:
            pass

    #
    # Alpha-numeric sort of 'jbod-1, jbod-10, jbod-11, jbod-2, ...' items
    #
    print_jbod_hdr()
    for jb in sorted(jbods, key=lambda item: int(item.split('-')[1])):
        alias = jbods[jb]['alias']
        vendor = jbods[jb]['vendor']
        model = jbods[jb]['model']
        serial = jbods[jb]['serial']
        tslots = jbods[jb]['total_slots']
        bslots = jbods[jb]['busy_slots']

        status = None
        if colorized:
            for lid in sesctl:
                if lid == serial:
                    status = sesctl[lid]['status']

        patt = '[a-zA-Z0-9-]+_SIM_.*'
        mp = re.match(patt, model)
        if mp:
            continue

        patt = '\s*SuperMicro\s*'
        mp = re.match(patt, vendor)
        if mp:
            vendor = 'SMC'

        patt = '\s*LSI_CORP\s*'
        mp = re.match(patt, vendor)
        if mp:
            vendor = 'LSI'

        patt = '\s*(SuperMicro-)(\S*)'
        mp = re.match(patt, model)
        if mp:
            model = mp.group(2)

        patt = '\s*(DataON-)(\S*)'
        mp = re.match(patt, model)
        if mp:
            model = mp.group(2)

        patt = '\s*(LSI_CORP-)(\S*)'
        mp = re.match(patt, model)
        if mp:
            model = 'LSI_' + mp.group(2)

        if vendor == 'SMC':
            patt = '(\S*)-back$'
            mp = re.match(patt, model)
            if mp:
                patt1 = '(\S*)-(\S*)-back'
                mp1 = re.match(patt1, model)
                if mp1:
                    model = mp1.group(1) + '-back'

        dump_jbod_data(status, alias, vendor, model, serial, tslots, bslots)


#
# hddisco Info
#
def print_hddko_hdr():
    prfmt_mc_row('count, vendor, model, firmware, paths',
                  '%12s,   %12s,  %20s,     %12s,   %7s',
                 'white,  white, white,    white, white',
                 ' bold,   bold,  bold,     bold,  bold')

    prfmt_mc_row('-----, ----------, ---------------, --------, -----',
                  '%12s,       %12s,            %20s,     %12s,   %7s',
                 'white,      white,           white,    white, white',
                 ' bold,       bold,            bold,     bold,  bold')


def hddko():
    global base
    File = os.path.join(base, 'ingestor/json/hddisco.out.json')
    brands = {}

    if not os.path.exists(File):
        return

    print_header('hddisco Info')
    with open(File) as f:
        disks = json.load(f)

    for hdd in disks:
        if disks[hdd]['mpxio_enabled'] == "yes":
            vendr = disks[hdd]['vendor']
            model = disks[hdd]['product']
            fware = disks[hdd]['revision']
            paths = disks[hdd]['path_count']
            if debug:
                print hdd, vendr, model, fware, paths

            if vendr not in brands:
                brands[vendr] = {}
            if model not in brands[vendr]:
                brands[vendr][model] = {}
            if fware not in brands[vendr][model]:
                brands[vendr][model][fware] = {}
            if paths not in brands[vendr][model][fware]:
                brands[vendr][model][fware][paths] = {}
                brands[vendr][model][fware][paths]['count'] = 0

            brands[vendr][model][fware][paths]['count'] += 1

    if debug:
        pprint(brands)

    print_hddko_hdr()
    for v in brands:
        for m in brands[v]:
            for f in brands[v][m]:
                col = 'white'
                dsp = 'lite'
                fw = f
                if v == 'STEC' and m == 'ZeusRAM':
                    if f < 'C023':
                        col = 'red'
                        dsp = 'bold'
                        fw = '   ' + f
                for p in brands[v][m][f]:
                    c = brands[v][m][f][p]['count']
                    prfmt_mc_row('%s, %s, %s, %s, %s' % (c, v, m, fw, p),
                            '%12s,  %12s,  %20s,  %12s,  %7s',
                            'white, white, white, %s, white' % col,
                            'lite,  lite,  lite,  %s,  lite' % dsp)
                    

#
# Networking
#
def print_net_hdr():
    prfmt_mc_row('Network, State, Speed, Duplex',
                    '%15s,  %13s,  %15s,   %16s',
                   'white, white, white,  white',
                    'bold,  bold,  bold,   bold')

    prfmt_mc_row('-------, -----, ------, -------',
                    '%15s,  %13s,  %16s,   %16s',
                   'white, white, white,  white',
                    'bold,  bold,  bold,   bold')


def network():
    global base
    File = os.path.join(base, 'ingestor/json/dladm-show-phys.out.json')

    if not os.path.exists(File):
        return

    print_header('Networking Info')
    with open(File) as f:
        nics = json.load(f)

    print_net_hdr()
    for ic in nics:
        devname = nics[ic]['device']
        duplex = nics[ic]['duplex']
        speed = nics[ic]['speed']
        state = nics[ic]['state']

        # state color
        stc = 'red' if state != 'up' else 'green'
        # speed color
        spc = 'red' if speed == '0' else 'green'
        # duplex color
        dxc = 'red' if duplex != 'full' or state != 'up' else 'green'
        # nic color
        nmc = 'white' if state == 'up' else 'red'

        prfmt_mc_row('%s, %s, %s, %s' % (devname, state, speed, duplex),
                    '%15s,  %13s,  %15s,  %16s',
                    '%s, %s, %s, %s' % (nmc, stc, spc, dxc),
                    'bold,  bold,  bold,   bold')


#
# Faults
#
def nms_faults():
    global base
    File = os.path.join(base, 'ingestor/json/nmc-c-show-faults.out.json')

    if not os.path.exists(File):
        return

    print_header('nms Faults')
    with open(File) as f:
        json_data = json.load(f)

    for section in json_data:
        if section.startswith('fault'):
            sev = json_data[section]['severity']
            trig = json_data[section]['trigger']

            if sev == 'NOTICE':
                print_warn(sev + ' ' + trig, True)
            else:
                print_fail(sev + ' ' + trig)
            print '\tCount:\t\t', json_data[section]['count']
            print '\tFault:\t\t', json_data[section]['fault']

            if sev == 'NOTICE':
                print_warn('\tMessage:\t' + json_data[section]['msg'], True)
            else:
                print_fail('\tMessage:\t' + json_data[section]['msg'])
            print '\tTime:\t\t', json_data[section]['time'], '\n'
        else:
            data = json_data[section]
            dlen = len(data)
            summ = 'Summary:'
            slen = len(summ) + 1        # account for trailing space
            idx = 80                    # length of terminal
            i = idx - slen - 4          # Crude calculation; see str.rfind()
            row1 = data[:i]
            row2 = data[i:]

            print_bold('Summary:', 'white', False)
            print_debug(row1 + '\n\t' + row2, True)
    return


def print_secs(l, h):   # h == hex string
    i = int(h, 16)      # convert from hex to int
    f = float(i)        # int to floating point val
    s = str(f / 1e9)    # convert from nS to Secs

    print_warn('%18s' % l + 7*' ' + s + ' Secs', True)
    return


def fma_faults():
    global base
    File = os.path.join(base, 'ingestor/json/fmdump-e.out.gz.json')
    zflags = ('pool_failmode',  \
            'parent_type',      \
            'cksum_algorithm',  \
            'cksum_actual',     \
            'cksum_expected',   \
            'vdev_path',        \
            'pool')
    uflags = ('product',        \
            'vendor',           \
            'serial',           \
            'revision',         \
            'un-decode-info',   \
            'driver-assessment',\
            'device-path',      \
            'devid')
    sflags = ('product',        \
            'vendor',           \
            'serial',           \
            'revision',         \
            'device-path',      \
            'devid',            \
            'delta',            \
            'threshold')

    if not os.path.exists(File):
        return

    print_header('fma Faults (30 days)')
    with open(File) as f:
        faults_json = json.load(f)

    for key in faults_json:
        zfs = False
        scsi = False
        print_bold(key, 'blue', True)
        flt = faults_json[key]

        if 'class' in flt:      # consider using flt.has_key('class')
            line = flt['class']

            patt = '\S+\.zfs\.\S+'
            mp = re.match(patt, line)
            if mp:
                zfs = True

            patt = '\S+\.io\.scsi\.\S+'
            mp = re.match(patt, line)
            if mp:
                scsi = True
                etyp = line.split('.')[-1]

            tint = 'gray'
            font = 'lite'
            for k in flt:
                if zfs:
                    if k in zflags:
                        if k == 'cksum_actual' and  \
                           flt[k] != flt['cksum_expected']:
                                tint = 'red'
                                font = 'bold'
                        else:
                            tint = 'yellow'
                            font = 'bold'
                    else:
                        tint = 'gray'
                        font = 'lite'
                elif scsi:
                    if etyp == 'uderr' or etyp == 'derr':
                        if k in uflags:
                            if k == 'driver-assessment' and flt[k] == 'fail':
                                tint = 'red'
                                font = 'bold'
                            else:
                                tint = 'yellow'
                                font = 'bold'
                        else:
                            tint = 'gray'
                            font = 'lite'
                    elif etyp == 'slow-io':
                        if k in sflags:
                            tint = 'yellow'
                            font = 'bold'
                            if k == 'threshold' or k == 'delta':
                                print_secs(k, flt[k])
                                continue
                        else:
                            tint = 'gray'
                            font = 'lite'

                fmt_func = eval('prfmt_%s' % font)
                reg_func = eval('print_%s' % font)

                fmt_func(k + '\t', '%19s', tint, False)
                reg_func(flt[k].ljust(40, ' '), tint, True)

    return


def faults():
    nms_faults()
    fma_faults()


def NFS():
    # XXX - much work to be done here
    global base
    File = os.path.join(base,   \
        'ingestor/json/svccfg-s-svcnetworknfsserverdefault-listprop.out.json')

    with open(File) as f:
        topix = json.load(f)
    for key in topix.keys():
        print key


def services():
    # XXX - disabled at the moment
    print_header('Appliance Services')
    NFS()


def disk_heuristics(dev, tput):

    if tput >= 150:         # threshold: 150 MB/s; flag anything slower
        prfmt_lite(dev, '%25s', 'green', False)
        prfmt_bold('PASS', '%33s', 'green', True)
    else:
        prfmt_lite(dev, '%25s', 'red', False)
        prfmt_bold('FAIL', '%33s', 'red', True)

    return
 

def sac_results():
    global base

    Dir = os.path.join(base, 'go-live')
    if not os.path.exists(Dir):
        return

    if not os.listdir(Dir):     # simply return if go-live dir is empty
        return

    jfiles = []
    Files = os.listdir(Dir)
    for f in Files:
        if f.endswith('json'):
            jfiles.append(f)

    json_files = sorted(jfiles)
    File = os.path.join(Dir, json_files[-1])    # newest json file
    try:
        with open(File) as f:
            sacres = json.load(f)

    except Exception, e:
        print 'Exception %s raised' % str(e)
        return

    print_header('SAC Results')
    for r in sacres['results']:
        c = Colors()
        print '\t', c.bold_white + r + c.reset, '\t',

        expt = ''
        if 'exception' in sacres['results'][r]:
            if sacres['results'][r]['exception'] == False:
                expt = False
            else:
                prfmt_bold('FAIL', '%27s', 'red', True)
                msg = sacres['results'][r]['exception_str']
                print_fail('\t\t\t' + msg)
                continue

        if 'status' in sacres['results'][r]:
            if sacres['results'][r]['status'] == True:
                if not expt:
                    if len(r) <= 12:
                        prfmt_pass('PASS', '%35s')
                    else:
                        prfmt_pass('PASS', '%27s')
                else:
                    if len(r) <= 12:
                        # XXX - still need to be unit tested
                        prfmt_fail('[FAIL]', '%38s')
                    else:
                        # XXX - still need to be unit tested
                        prfmt_fail('(FAIL)', '%30s')
            else:
                if not expt:
                    prfmt_fail('FAIL', '%35s')
                    try:
                        msg = sacres['results'][r]['output']
                        print_fail('\t\t' + msg)
                    except KeyError:
                        print_fail('\t\t\tUnable to retrieve failure message')
                    continue
        else:
            print ''
            for k in sacres['results'][r].keys():
                if k == 'exception':
                    continue
                if 'status' in sacres['results'][r][k]:
                    if sacres['results'][r][k]['status'] == True:
                        if not expt:
                            if r == 'check_disk_perf':
                                tput = sacres['results'][r][k]['tput']
                                disk_heuristics(k, tput)
                                continue
                            else:
                                print '%25s' % k,
                                prfmt_pass('PASS', '%33s')

                        else:
                            # XXX - still need to be unit tested
                            print '%25s' % k,
                            prfmt_fail('<FAIL>', '%35s')
    print ''


def orchestrator():
    global zp_vmode
    global sac_res

    process_cs()
    vendor_cpu()
    memory()
    dump_dev()
    get_opthac()
    zp_list(zp_vmode)       # pass in 'verbose' to zp_list() for full output
    jbods()
    hddko()
    network()
    faults()
    #services()
    if sac_res:
        sac_results()


def lookup_by_lkey(dbfile, lkey):

    if not os.path.exists(dbfile):
        return None

    fd = gzip.open(dbfile, 'rb')
    try:
        for l in fd:
            line = l.split('|')

            try:
                cname = line[1]
                email = line[2].split('@')[1]
                licen = line[3]
                mchid = line[4]
                custy = line[-3]

            except IndexError:      # badly formated line in DB
                pass

            if lkey == licen:
                if custy:
                    if custy == 'Yes' or custy == 'No':
                        customer = email
                    else:
                        customer = custy
                else:
                    customer = email

                return customer

    finally:
        fd.close()

    return None


def lookup_by_machid(dbfile, lkey):

    if not os.path.exists(dbfile):
        return None

    lkmid = lkey.split('-')[2]

    fd = gzip.open(dbfile, 'rb')
    try:
        for l in fd:
            line = l.split('|')

            try:
                cname = line[1]
                email = line[2].split('@')[1]
                licen = line[3]
                mchid = line[4]
                custy = line[-3]

            except IndexError:      # badly formated line in DB
                pass

            if lkmid == mchid:
                if custy:
                    if custy == 'Yes' or custy == 'No':
                        customer = email
                    else:
                        customer = custy
                else:
                    customer = email
                return customer

    finally:
        fd.close()

    return None


def get_custy_info(lkey):

    DBFile = "./DB/product_reg.db.ryuji.gz"

    custy = lookup_by_lkey(DBFile, lkey)
    if custy is None:
        custy = lookup_by_machid(DBFile, lkey)

    return custy


#
# Dark-Site Support
#
currdir = os.getcwd()
basedir = '/mnt/carbon-steel'
uplddir = os.path.join(basedir, 'upload')
ingtdir = os.path.join(basedir, 'ingested')
tarfile = ''
datestr = time.strftime('%Y-%m-%d', time.localtime())


def prep_tree():
    if not os.path.exists(basedir):
        os.mkdir(basedir)

    if not os.path.exists(uplddir):
        os.mkdir(uplddir)

    return


def collector_for_this_node():
    global tarfile

    print_debug('The following step', False)
    print_warn('WILL', False)
    print_debug('take time... please be patient !\n', True)

    print_bold('Generating Local Collector Bundle...\t', 'white', False)

    cmd = '/bin/nexenta-collector --no-upload'
    fd = os.popen(cmd)

    for line in fd:
        if not line.startswith('Result'):
            continue
    
        patt = '^Result file:\s+(\S+)$'
        mp = re.match(patt, line)
        if mp:
            collector_file = mp.group(1)
            cf = os.path.basename(collector_file)
            new_loc = os.path.join(uplddir, cf)
            
            tarfile = new_loc
            os.rename(collector_file, new_loc)

    print_pass('Done')
    return


def ingest_in_background():
    global tarfile
    nza_ingdir = '/root/bin/python/NXTA_DS_Ingestor'
    nzingestor = os.path.join(nza_ingdir, 'NZA_Ingestor.py')

    print_bold('Ingesting Local Collector Bundle...\t', 'white', False)
    os.chdir(nza_ingdir)
    cmd = nzingestor + ' --ingest ' + tarfile
    fd = os.popen(cmd)

    for line in fd:
        if not line.startswith('Ingestion'):
            continue
        print line

    print_pass('Done')
    return


def find_ingestion_dir():
    global datestr

    idir = ''
    line = os.path.basename(tarfile)
    patt = '^(\S+T)\.\d+\.tar\.gz$'
    mp = re.match(patt, line)
    if mp:
        idir = mp.group(1)
    else:
        print_fail('Could NOT decipher correct ingestion directory')
        sys.exit(1)

    return os.path.join(os.path.join(ingtdir, datestr), idir)
    

def dark_site():
    prep_tree()
    collector_for_this_node()
    ingest_in_background()

    return find_ingestion_dir()


def volun_to_vdev(vol, lun):
    File = os.path.join(base, 'ingestor/json/zpool-status-dv.out.json')
    
    if not os.path.exists(File):
        return None

    with open(File) as f:
        zpstat = json.load(f)

    for pool in zpstat:
        if pool != vol:
            continue

        pname = zpstat[pool]['config'][pool]
        for x in pname['vdev']:
            if 'vdev' in pname['vdev'][x]:
                vdev = pname['vdev'][x]['vdev']
            else:
                vdev = pname['vdev']

            for l in vdev:
                L = l.lower()
                if L == lun:
                    return x.split('-')[0]

                #
                # XXX - will need to test this against other collector
                #       bundles to make sure we do get all devices.
                #
                patt = '^(spare.*)'
                mp = re.match(patt, L)
                if mp:
                    nl = mp.group(1)
                    s9 = zpstat[pool]['config'][pool]['vdev'][x]['vdev'][nl]
                    
                    for v in s9['vdev']:
                        state = s9['vdev'][v]['state']

                        if state != 'ONLINE':
                            return 'Fault'
                        else:
                            return x.split('-')[0]
    
        # couldn't find it under pool, let's check other pool vdevs
        vdevs = ['cache', 'logs', 'spares']
        for v in vdevs:
            try:
                pname = zpstat[pool]['config'][v]
            except KeyError:
                continue

            vdev = pname['vdev']
            for d in vdev:
                if d == lun:
                    return v.split('-')[0]


def lun_to_zvol(lun):
    File = os.path.join(base, 'ingestor/json/nmc-c-show-lun-smartstat.out.json')
    
    if not os.path.exists(File):
        return None

    with open(File) as f:
        lunsmart = json.load(f)

    for vol in lunsmart:
        for l in lunsmart[vol]['luns']:
            if l.lower() == lun:
                return vol


def CI_Disk_1():
    global base
    global hc_vmode
    File = os.path.join(base, 'ingestor/json/iostat-en.out.json')

    if not os.path.exists(File):
        return

    print_header('CI-Disk-1')
    with open(File) as f:
        iostat = json.load(f)

    primed = False
    for lun in sorted(iostat):
        vol = lun_to_zvol(lun)
        vdev = volun_to_vdev(vol, lun)
        if not primed:
            ll = lun
            lv = iostat[lun]['vendor']
            vc = 1
            ls = iostat[lun]['size:']
            sc = 1
            lp = iostat[lun]['product']
            pc = 1
            lr = iostat[lun]['revision']
            rc = 1
            if hc_vmode == 'verbose':
                prfmt_mc_row('%s, %s, %s, %s, %s, %s, %s' %
                            (ll, lv, lp, lr, ls, vol, vdev),
                            ' %10s,   %8s,  %16s,   %5s,  %10s,   %5s,   %5s',
                            'white, white, white, white, white, white, white',
                            ' bold,  bold,  bold,  bold,  bold,  bold,  bold')

            primed = True
            continue

        try:
            vr = iostat[lun]['vendor']
            pr = iostat[lun]['product']
            sz = iostat[lun]['size:']
            rv = iostat[lun]['revision']
        except KeyError:
            continue

        same_v = False
        if lv == vr:
            same_v = True
        else:
            vc += 1

        same_p = False
        if lp == pr:
            same_p = True
        else:
            pc += 1

        same_s = False
        if ls == sz:
            same_s = True
        else:
            sc += 1

        same_r = False
        if lr == rv:
            same_r = True
        else:
            rc += 1

        if hc_vmode == 'verbose':

            if same_v and same_p and same_s and same_r:
                col = 'red' if vol is None else 'white'
                prfmt_mc_row('%s, %s, %s, %s, %s, %s, %s' %
                    (lun, vr, pr, rv, sz, vol, vdev),
                    ' %10s,   %8s,  %16s,   %5s,  %10s,   %5s,   %5s',
                    'white, white, white, white, white,    %s, white' % col,
                    ' bold,  bold,  bold,  bold,  bold,  bold,  bold')

            else:
                prfmt_bold(lun, '%10s', 'white', False)

                if same_v:
                    prfmt_bold(vr, '%8s', 'white', False)
                else:
                    prfmt_bold(vr, '%8s', 'yellow', False)

                if same_p:
                    prfmt_bold(pr, '%16s', 'white', False)
                else:
                    prfmt_bold(pr, '%16s', 'yellow', False)

                if same_r:
                    prfmt_bold(rv, '%5s', 'white', False)
                else:
                    prfmt_bold(rv, '%5s', 'yellow', False)
            
                if same_s:
                    prfmt_bold(sz, '%10s', 'white', False)
                else:
                    prfmt_bold(sz, '%10s', 'yellow', False)

                if vol is None:
                    tint = 'red'
                else:
                    tint = 'white'
                prfmt_bold(vol, '%5s', '%s' % tint, False)
                prfmt_bold(vdev, '%5s', '%s' % tint, True)

        ll = lun
        lv = vr
        ls = sz
        lp = pr
        lr = rv

    if vc > 1 or pc > 1 or sc > 1:
        if hc_vmode == 'verbose':
            print ''

        msg1 = 'WARNING: Disks in system span %d vendors, ' % vc
        msg2 = '%d products, %d sizes and %d f/w revs\n' %  (pc, sc, rc)
        print_warn(msg1 + msg2, True)

    return


def health_check():
    global base

    print_bold('Initiating Health Check...', 'white', False)
    CI_Disk_1()
    return


def main():
    global base
    global zp_vmode
    global hc_vmode
    global sac_res

    c = Colors()

    parser = optparse.OptionParser(usage='%prog ' + c.bold_white +          \
        '--path ' + c.reset + 'collector_bundle_dir ' + '[ ' +              \
        c.bold_white + '--zpmode' + c.reset + ' (\'summary\'|\'verbose\') ]'\
        + '\n' + 16*' ' + '[ ' + c.bold_white + '--sac' + c.reset + ' ]' +  \
        '\n' + 7*' '+ 'nxcat.py' + c.bold_white + ' --dark-site' + c.reset  \
        + '\n' + 7*' ' + 'nxcat.py' + c.bold_white + ' --path' + c.reset +  \
        ' collector_bundle_dir' + c.bold_white + ' --health-check' + c.reset\
        + '\n' + 16*' ' + '[ ' + c.bold_white + '--hvmode' + c.reset +      \
        ' (\'summary\'|''\'verbose\') ]')

    parser.add_option('--path', dest='path', type='str', default=None,
        help='Fully qualified path to already ingested collector bundle ' + \
        'directory', metavar='BundlePath', nargs=1)
    parser.add_option('--zpmode', dest='zvmode', type='str', default='summary',
        help='\'summary\' or \'verbose\' Mode for Zpool Information',
        metavar='vmode', nargs=1)
    parser.add_option('--sac', action="store_true", default=False,
        help='Show SAC results for bundles that were successfully autosac\'ed',
        metavar=None)
    parser.add_option('--dark-site', action="store_true", default=False,
        help='For use in Dark Sites: Automatically generates, ingests and ' +\
        'analyzes the newly generated bundle', metavar=None)
    parser.add_option('--health-check', action="store_true", default=False,
        help='Perform Health Check as per Appendix C procedures of SOW; ' + \
        'mutually exclusive to --zpmode and --sac options', metavar=None)
    parser.add_option('--hvmode', dest='hvmode', type='str', default='summary',
        help='\'summary\' or \'verbose\' mode for Health Check Status',
        metavar='hcmode', nargs=1)

    (options_args, args) = parser.parse_args()

    #pprint(options_args)

    dark = options_args.dark_site
    if dark:
        base = dark_site()

    elif options_args.path is not None:
        base = options_args.path

        if options_args.health_check:
            if  options_args.sac:
                print_warn('\n\t' + 'Options --health-check ' + \
                    'and --sac are mutually exclusive !\n', True)
                sys.exit(0)
            
            hc_vmode = options_args.hvmode
            health_check()
            sys.exit(0)

        sac_res = options_args.sac
    else:
        parser.print_help()
        sys.exit(1)

    if not dark:
        zp_vmode = options_args.zvmode
        if zp_vmode != 'summary' and zp_vmode != 'verbose':
            print_warn('\n\t' + zp_vmode, False)
            print 'is not a valid option for',
            print_bold('\'--zpmode\'\n', 'white', True)
            parser.print_help()
            sys.exit(2)

    orchestrator()


#
# Boilerplate
#
if __name__ == '__main__':
    main()


# pydoc
__author__ = "Rick Mesta"
__copyright__ = "Copyright 2015 Nexenta Systems, Inc. All rights reserved."
__credits__ = ["Rick Mesta"]
__license__ = "undefined"
__version__ = "$Revision: " + _ver + " $"
__created_date__ = "$Date: 2015-05-18 18:57:00 +0600 (Mon, 18 Mar 2015) $"
__last_updated__ = "$Date: 2015-08-12 09:49:00 +0600 (Wed, 12 Aug 2015) $"
__maintainer__ = "Rick Mesta"
__email__ = "rick.mesta@nexenta.com"
__status__ = "Production"