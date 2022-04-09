import os
from multiprocessing import Queue, Process
import time

def write(q_input, fifo):
    f = os.open(fifo, os.O_WRONLY)
    while (True):
        os.write(f, q_input.get())

def read(q_output, fifo):
    f = os.open(fifo, os.O_RDONLY)
    while (True):
        q_output.put(os.read(f, 100))

def test_noFIFO(q_input, q_output):
    while (True):
        q_output.put(q_input.get())

def run_oneway(q_input, q_output):
    def quic_server(path):
        os.chdir(path)
        os.system("./server 0.0.0.0 1114 > /dev/null")

    def quic_client(path):
        os.chdir(path)
        os.system("./client 127.0.0.1 1114 > /dev/null")

    quic_path = "/home/new_quic/build/"
    input_pipe = quic_path + "svideopipe"
    output_pipe = quic_path + "cvideopipe"

    p_oneway_write = Process(target=write, args=(q_input, input_pipe,))
    p_oneway_read = Process(target=read, args=(q_output, output_pipe,))
    p_quic_server = Process(target=quic_server, args=(quic_path,))
    p_quic_client = Process(target=quic_client, args=(quic_path,))

    p_oneway_write.start()
    p_oneway_read.start()

    p_quic_server.start()
    time.sleep(1)
    p_quic_client.start()

def run(q_input, q_output):
    return

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