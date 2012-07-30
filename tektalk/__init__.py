#!/usr/bin/python

'''
Module to control a TekTronix Scope using it's socket server functionality
'''
import socket, select

import numpy

class TekSocket:
    def __init__(self, ip, port,verbose=False, terminal=True):
        self.sock = socket.socket()
        self.sock.connect((ip,port))

        self.terminal = terminal
        self.verbose = verbose

    def debug_msg(self, msg):
        if self.verbose and len(msg) < 1000:
            print msg

    def send(self, data):
        if data.find('\r\n') == -1:
            data = data + '\r\n'

        self.debug_msg('Sending: %s'%(data))
    
        numsent = self.sock.send(data)

        while(numsent < len(data)):
            numsent += self.sock.send(data[numsent:])

    def recv(self):
        '''
        terminal variable strips the '\\r\\n>' from the results
        '''
        # waits until data is ready (useful? maybe...)
        select.select([self.sock,],[],[])

        data = ''
        bDone = 0
        while not bDone:
            rl,wl,xl = select.select([self.sock,],[],[],1)
            if len(rl) == 0:
                bDone = 1
            else:
                data += self.sock.recv(4096)

        if self.terminal:
            data = data[:-2]
            if data[0] == '>':
                data = data[1:]

        data = data.strip()
        self.debug_msg('Recieved: %s'%(data))

        return data

class TekScope:
    def __init__(self, ip, port,verbose=False):
        self.T = TekSocket(ip,port,verbose=verbose)

        if self.T.terminal:
            self.T.recv() # to flush out crapola

    def getRecordLength(self):
        self.T.send('HORizontal:RECOrdlength?')

        return eval(self.T.recv())

    def setRecordLength(self,record_len):
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
                for i in range(1,len(allowed_lengths)):
                    if record_len > allowed_length[i-1] and record_len < allowed_lengths[i]:
                        record_len = allowed_length[i-1] # round down
                        break

        self.T.send('HORizontal:RECOrdlength %d'%(record_len))
        return record_len

    def getWaveform(self,channel=1):
        numrecords = self.getRecordLength()

        self.T.send('SELect:CH%d ON'%(channel))
        self.T.send('DATa:SOUrce CH%d'%(channel))
        self.T.send('DATa:ENCdg SRIBinary')
        self.T.send('WFMINPRE:BYT_Nr 2')
        self.T.send('DATa:STARt 1')
        self.T.send('DATa:STOP %d'%(numrecords))

        # waveform preamble
        self.T.send('WFMOutpre?')
        wfm_desc = self.T.recv().split(';')
        while len(wfm_desc) < 11:
            self.T.send('WFMOutpre?')
            wfm_desc = self.T.recv().split(';')        
 
        # get scaling data
        offset = wfm_desc[-2] # not in units I think, eh, we'll figure it out
        toffset = eval(wfm_desc[10]) # offset in x
        tstep = eval(wfm_desc[9]) # sampling time
        scale = eval(wfm_desc[-3]) # in units
    
        # data
        self.T.send('CURVe?')
        data_str = self.T.recv()

        # convert data
        data = numpy.frombuffer(data_str[-(numrecords*2):], dtype=numpy.int16) * scale

        t = numpy.arange(toffset, (tstep*(numrecords))+toffset, tstep)
        t = numpy.linspace(toffset, (tstep*numrecords)+toffset, data.shape[0])
        return {'preamble':wfm_desc, 'data':data, 't':t}

    def getAllWaveforms(self):
        numrecords = self.getRecordLength()
        data = numpy.ones((numrecords,4))

        for i in range(4):
            ret = self.getWaveform(i+1)
            data[:,i] = ret['data']
       
        return ret['t'], data
        
    def saveToUSB(self,filename):
        self.T.send('SAVe:WAVEform:FILEFormat SPREADSheet')
        self.T.send('SAVe:WAVEform:ALL, "E:/%s'%(filename))

if __name__ == '__main__':
    import pylab

    T = TekScope('192.168.0.104',4000,verbose=True)

    t,data =  T.getAllWaveforms()

    print t.shape, data.shape    
	   
    pylab.plot(t, data)    
    pylab.show()    
