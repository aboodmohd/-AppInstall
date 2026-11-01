#!/usr/bin/env python3
"""Explicit manual desktop-test pointer; requires an existing user uinput ACL."""
import fcntl
import os
import struct
import sys
import time

def click(x,y,double=False):
    fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
    try:
        for ev in (0,1,3): fcntl.ioctl(fd,0x40045564,ev)
        fcntl.ioctl(fd,0x40045565,272)
        for axis in (0,1): fcntl.ioctl(fd,0x40045567,axis)
        maximum=[0]*64; maximum[0]=1439;maximum[1]=899
        device=struct.pack('80sHHHHI',b'AppInstall integration test pointer',3,1,1,1,0)
        device+=struct.pack('64i',*maximum)+b'\0'*(256*3)
        os.write(fd,device); fcntl.ioctl(fd,0x5501)
        time.sleep(.6)
        def event(kind,code,value):os.write(fd,struct.pack('llHHi',0,0,kind,code,value))
        event(3,0,x);event(3,1,y);event(0,0,0);time.sleep(.2)
        for _ in range(2 if double else 1):
            event(1,272,1);event(0,0,0);time.sleep(.05)
            event(1,272,0);event(0,0,0);time.sleep(.08)
        time.sleep(.3)
    finally:
        fcntl.ioctl(fd,0x5502);os.close(fd)
if __name__=='__main__':click(int(sys.argv[1]),int(sys.argv[2]),'--double' in sys.argv)
