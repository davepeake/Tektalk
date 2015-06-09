#!/usr/bin/python

'''
Module to control a TekTronix Scope using it's socket server functionality
'''
import socket
import select
import logging
import time

import numpy

logger = logging.getLogger(__name__)


class TekSocket:
    def __init__(self, ip, port, verbose=False, terminal=True):
        self.sock = socket.socket()
        self.sock.connect((ip, port))

        self.terminal = terminal
        self.verbose = verbose

    def debug_msg(self, msg):
        if self.verbose and len(msg) < 1000:
            logger.debug(msg)

    def send(self, data):
        if data.find('\r\n') == -1:
            data = data + '\r\n'

        self.debug_msg('Sending: %s' % (data.rstrip()))

        numsent = self.sock.send(data)

        while(numsent < len(data)):
            numsent += self.sock.send(data[numsent:])

    def recv(self):
        '''
        terminal variable strips the '\\r\\n>' from the results
        '''
        # waits until data is ready (useful? maybe...)
        select.select([self.sock, ], [], [])

        data = ''
        bDone = 0
        while not bDone:
            rl, wl, xl = select.select([self.sock, ], [], [], 1)
            if len(rl) == 0:
                bDone = 1
            else:
                data += self.sock.recv(4096)

        self.debug_msg('Received: %s' % (data.rstrip()))

        if self.terminal:
            data = data[:-2]
            while(data[0] == '>'):
                data = data[1:].strip()

        data = data.strip()
        self.debug_msg('Received: %s' % (data.rstrip()))

        return data

    def recv_raw(self):
        data = ''
        bDone = 0
        while not bDone:
            rl, wl, xl = select.select([self.sock, ], [], [], 1)
            if len(rl) == 0:
                bDone = 1
            else:
                data += self.sock.recv(4096)

        return data

class TekScope:
    def __init__(self, ip, port,verbose=False):
        self.T = TekSocket(ip, port, verbose=verbose)

        if self.T.terminal:
            self.T.recv()  # to flush out crapola

    def getRecordLength(self):
        self.T.send('HORizontal:RECOrdlength?')

        return eval(self.T.recv())

    def setRecordLength(self, record_len):
        '''
        Sets the record length; must be one of 1E(3,4,5,6) or 5E6
        '''
        allowed_lengths = [1000, 10000, 100000, 1000000, 5000000]

        if record_len not in allowed_lengths:
            # round it off
            if record_len > 5E6:
                record_len = 5E6
            if record_len < 1000:
                record_len = 1000

            if record_len not in allowed_lengths:
                for i in range(1, len(allowed_lengths)):
                    if record_len > allowed_length[i-1] and record_len < allowed_lengths[i]:
                        record_len = allowed_length[i-1]  # round down
                        break

        self.T.send('HORizontal:RECOrdlength %d' % (record_len))
        return record_len

    def setHorizontal(self, scale=None, pos=None):
        # Scale in s, Horizontal pos in percentage display left of center
        if scale is not None:
            # Set the scale
            self.T.send('HOR:SCA %e' % (scale))

        if pos is not None:
            # Sets the horizontal position
            self.T.send('HOR:POS %f' % (pos))

    def setVertical(self, ch, scale=None, pos=None, coupling=None):
        if scale is not None:
            self.T.send('CH%d:SCA %e' % (ch, scale))

        if pos is not None:
            self.T.send('CH%d:POS %e' % (ch, pos))

        if coupling is not None:
            self.T.send('CH%d:COUP %s' % (ch, coupling))

    def setImpedance(self, ch, imp):
        self.T.send('CH%d:IMP %s' % (ch, imp))

    def setEdgeTrigger(self, slope=None, source=None, coupling=None,
                       mode=None):
        self.T.send('TRIG:A:TYPE EDGE')  # set to edge trigger

        if slope is not None:
            self.T.send('TRIG:A:EDGE:SLO %s' % (slope))

        if source is not None:
            self.T.send('TRIG:A:EDGE:SOU %s' % (source))

        if coupling is not None:
            self.T.send('TRIG:A:EDGE:COUP %s' % (coupling))

        if mode is not None:
            self.T.send('TRIG:A:MOD %s' % (mode))

    def setTriggerLvl(self, lvl):
        # Level in Volts
        self.T.send('TRIG:A:LEV %f' % (lvl))

    def getWaveform(self, channel=1):
        numrecords = self.getRecordLength()

        self.T.send('SELect:CH%d ON' % (channel))
        self.T.send('DATa:SOUrce CH%d' % (channel))
        self.T.send('DATa:ENCdg SRIBinary')
        self.T.send('WFMINPRE:BYT_Nr 2')
        self.T.send('DATa:STARt 1')
        self.T.send('DATa:STOP %d' % (numrecords))

        # waveform preamble
        self.T.send('WFMOutpre?')
        wfm_desc = self.T.recv().split(';')
        while len(wfm_desc) < 11:
            self.T.send('WFMOutpre?')
            wfm_desc = self.T.recv().split(';')

        # get scaling data
        offset = wfm_desc[-2]  # not in units I think, eh, we'll figure it out
        toffset = eval(wfm_desc[10])  # offset in x
        tstep = eval(wfm_desc[9])  # sampling time
        scale = eval(wfm_desc[-3])  # in units

        # data
        self.T.send('CURVe?')
        data_str = self.T.recv()

        # convert data
        data = numpy.frombuffer(data_str[-(numrecords*2):], dtype=numpy.int16) * scale

        t = numpy.arange(toffset, (tstep*(numrecords))+toffset, tstep)
        t = numpy.linspace(toffset, (tstep*numrecords)+toffset, data.shape[0])
        return {'preamble': wfm_desc, 'data': data, 't': t}

    def getAllWaveforms(self):
        numrecords = self.getRecordLength()
        data = numpy.ones((numrecords, 4))

        for i in range(4):
            ret = self.getWaveform(i+1)
            data[:, i] = ret['data']

        return ret['t'], data

    def getMeasurement(self, measurement):
        meas_dict = {'measurement': measurement}
        # set the measurement
        self.T.send('MEASU:IMM:TYP %s' % (measurement))
        # get the units
        self.T.send('MEASU:IMM:UNI?')
        meas_dict['units'] = self.T.recv()
        # get the measurement value
        self.T.send('MEASU:IMM:VAL?')
        meas_dict['value'] = self.T.recv()

        try:
            meas_dict['value'] = float(meas_dict['value'])
        except:
            pass

        return meas_dict

    def getScreenshot(self, filename):

        self.T.send('SAVE:IMAG:FILEF PNG')
        self.T.send('HARDCOPY START')
        time.sleep(1)
        self.T.send('!r')
        buff = self.T.recv()

        # find png header
        buffstart = buff.find('\x89PNG')

        self.T.debug_msg('Buffstart: %d' % (buffstart))

        if filename is None:
            return buff[buffstart:]

        # otherwise
        with open(filename, 'wb') as fout:
            fout.write(buff[buffstart:])

        return buff[buffstart:]

    def saveToUSB(self, filename):
        self.T.send('SAVe:WAVEform:FILEFormat SPREADSheet')
        self.T.send('SAVe:WAVEform:ALL, "E:/%s' % (filename))

if __name__ == '__main__':
    T = TekScope('192.168.0.112', 4000, verbose=True)

    print T.getMeasurement('RISE')
    print T.setHorizontal(scale=2E-6, pos=25)
    print T.setVertical(1, scale=200E-3, pos=0, coupling='DC')
    print T.setEdgeTrigger(slope='FALL', mode='AUTO')
    print T.setTriggerLvl(0.5)
    T.getScreenshot('test.png')
