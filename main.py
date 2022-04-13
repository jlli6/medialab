import sys, getopt
from multiprocessing import Queue, Process

# lib
import server 
import encoding
import pipeIO
import transport

def run_system(mode="run", server_port=8080, remote_ip="0.0.0.0", remote_port="1114", local_port="1114"):
    # data
    q_send_server_encoding = Queue()
    q_send_encoding_pipe = Queue()
    q_receive_pipe_decoding = Queue()
    q_reveive_decoding_server = Queue()
    v_pipe_path = "./pipe/video/"
    v_send_pipe = v_pipe_path + "svideopipe"
    v_receive_pipe = v_pipe_path + "cvideopipe"

    # process
    processes = []
    p_server = Process(target=server.server, args=(server_port, q_send_server_encoding, q_reveive_decoding_server,))
    processes.append(p_server)
    p_encoding = Process(target=encoding.encode, args=(q_send_server_encoding, q_send_encoding_pipe,))
    processes.append(p_encoding)
    if mode == "test_noFIFO":
        p_pipe = Process(target=pipeIO.test_noFIFO, args=(q_send_encoding_pipe, q_receive_pipe_decoding,))
        processes.append(p_pipe)
    else:
        p_vsend_pipe = Process(target=pipeIO.write, args=(q_send_encoding_pipe, v_send_pipe,))
        processes.append(p_vsend_pipe)
        p_transport = Process(target=transport.run, args=(v_pipe_path, remote_ip, remote_port, local_port,))
        processes.append(p_transport)
        p_vreceive_pipe = Process(target=pipeIO.read, args=(q_receive_pipe_decoding, v_receive_pipe,))
        processes.append(p_vreceive_pipe)
    p_decoding = Process(target=encoding.decode, args=(q_receive_pipe_decoding, q_reveive_decoding_server,))
    processes.append(p_decoding)

    for process in processes:
        process.start()

    input()

    for process in processes:
        process.kill()

def test_server():
    p_server = Process(target=server.test)
    p_server.start()
    p_server.join()

def test_encoding():
    p_encoding = Process(target=encoding.test)
    p_encoding.start()
    p_encoding.join()

def test_pipe():
    p_pipe = Process(target=pipeIO.test)
    p_pipe.start()
    p_pipe.join() 

if __name__ == "__main__":
    server_port = 8080
    remote_ip = "0.0.0.0"
    remote_port = "1114"
    local_port = "1114"
    test_flag = False

    # input
    opts, _ = getopt.getopt(sys.argv[1:], "t:", ["test=", "server_port=", "remote_ip=", "remote_port=", "local_port="])

    if opts:
        # load paras
        for o, a in opts:
            if o in ("--server_port"):
                server_port = int(a)
            if o in ("--remote_ip"):
                remote_ip = a
            if o in ("--remote_port"):
                remote_port = a
            if o in ("--local_port"):
                local_port = a
        # test
        for o, a in opts:
            if o in ("-t", "--test"):
                test_flag = True
                if a == "system":
                    run_system(mode="test_noFIFO", server_port=server_port)
                elif a == "server":
                    test_server()
                elif a == "encoding":
                    test_encoding()
                elif a == "pipe":
                    test_pipe()
        if not test_flag:
            run_system(mode="run", server_port=server_port, remote_ip=remote_ip, remote_port=remote_port, local_port=local_port)
    else:
        print("Error: no params. Use --test to enter test mode. Add --remote_ip to enter run mode.")
