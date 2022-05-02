import os
from multiprocessing import Queue, Process
import time

from numpy import size

def write(q_input, fifo_path, key_frame_freq):
    f_v = os.open(fifo_path + "video/svideopipe", os.O_WRONLY)
    print("send open1", time.time(), flush=True)
    f_p = os.open(fifo_path + "point/svideopipe", os.O_WRONLY)
    print("send open2",  time.time(), flush=True)
    cnt = 0
    while (True):
        if cnt % key_frame_freq == 0:
            s = q_input.get() + b'\x0f\x0f'
            print("send!!!", len(s), cnt)
            os.write(f_v, s)
        else:
            b = q_input.get()
            print("send!!!", len(b), cnt)
            os.write(f_p, b + b'\x0f\x0f')
        cnt = cnt + 1
        print("end write ", cnt, time.time(), flush=True)
        # time.sleep(0.01)

def read(q_output, fifo_path, key_frame_freq):
    f_v = os.open(fifo_path + "video/cvideopipe", os.O_RDONLY)
    print("receive open1", time.time(), flush=True)
    f_p = os.open(fifo_path + "point/cvideopipe", os.O_RDONLY)
    print("receive open2",  time.time(), flush=True)
    cnt = 0
    s = b''
    b = b''
    while (True):
        if cnt % key_frame_freq == 0:
            while not (b'\x0f\x0f' in s):
                s += os.read(f_v, 1024)
                print("!!!!!!!! ", len(s), cnt)
                # if b'\x0f\x0f' in s:
                #     break
            # print("!!!!!!!! ", len(s), cnt)
            lenth = len(s)
            index = s.find(b'\x0f\x0f')
            tmp = s[:index]
            q_output.put(tmp)
            s = s[index+2:]
        else:
            while not (b'\x0f\x0f' in b):
                b += os.read(f_p, 1024)
                # print("!!!!!!!! ", len(b), cnt)
                # if b'\x0f\x0f' in b:
                #     break
            lenth = len(b)
            index = b.find(b'\x0f\x0f')
            tmp = b[:index]
            q_output.put(tmp)
            b = b[index + 2:]
        cnt = cnt + 1
        print("end receive ", cnt, lenth,  time.time(), flush=True)
        # time.sleep(0.01)

def test_noFIFO(q_input, q_output):
    while (True):
        q_output.put(q_input.get())

def test():

    os.mkfifo("testFIFO")

    q_test_input = Queue()
    q_test_output = Queue()

    p_test_write = Process(target=write, args=(q_test_input, "testFIFO",))
    p_test_read = Process(target=read, args=(q_test_output, "testFIFO",))

    p_test_write.start()
    p_test_read.start()

    f = open("test", "rt")
    input_str = f.read()
    output_str = ""
    for i in range(0, len(input_str)):
        q_test_input.put(bytes(input_str[i], encoding='utf-8'))

    time.sleep(1)

    while (q_test_output.qsize() > 0):
        out = q_test_output.get()
        if q_test_output.qsize() == 0:
            print(out)
        output_str = output_str + str(out, encoding='utf-8')

    if (input_str == output_str):
        print("pass")
    else:
        print("not pass")
        print(input_str)
        print(output_str)

    p_test_write.kill()
    p_test_read.kill()

    os.remove("testFIFO")